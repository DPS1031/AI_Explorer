import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gpt-4o-mini"

_client = None


def _get_client() -> OpenAI:
    """Lazy initialization of the OpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY not found in environment variables. "
                "Please set it in your .env file."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def generate_content(
    contents: str | list,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_completion_tokens: int | None = None,
) -> str | None:
    """Calls OpenAI chat completion API.

    Args:
        contents: The user message/prompt. Can be a string or a list of content parts
                  (for multimodal messages with images).
        system_prompt: Optional system message for context.
        temperature: Controls randomness (0.0 for deterministic).
        max_completion_tokens: Limit output tokens for short responses.

    Returns:
        The assistant's response text, or None on failure.
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": contents})

    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
    }
    if max_completion_tokens is not None:
        kwargs["max_completion_tokens"] = max_completion_tokens

    client = _get_client()
    try:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        print(f"[OpenAI Error] {type(e).__name__}: {e}")
        raise
