import os
import threading
from google import genai
from dotenv import load_dotenv

load_dotenv()


class GeminiKeyManager:
    """Manages multiple Gemini API keys with automatic rotation on rate limit errors."""

    def __init__(self):
        keys_raw = os.getenv("GEMINI_API_KEYS", "")
        self._keys = [k.strip() for k in keys_raw.split(",") if k.strip()]
        if not self._keys:
            raise ValueError("No GEMINI_API_KEYS found in environment variables.")
        self._current_index = 0
        self._lock = threading.Lock()

    @property
    def current_key(self) -> str:
        with self._lock:
            return self._keys[self._current_index]

    def rotate(self) -> str:
        """Rotate to the next available key. Returns the new key."""
        with self._lock:
            self._current_index = (self._current_index + 1) % len(self._keys)
            return self._keys[self._current_index]

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def get_client(self) -> genai.Client:
        """Creates a Gemini client with the current API key."""
        return genai.Client(api_key=self.current_key)

    def generate_with_retry(self, model: str, contents: str) -> str:
        """Calls Gemini with automatic key rotation on rate limit errors.
        Tries all available keys before raising the error.
        """
        attempts = 0
        last_error = None

        while attempts < self.total_keys:
            try:
                client = self.get_client()
                response = client.models.generate_content(
                    model=model, contents=contents
                )
                return response.text
            except Exception as e:
                error_str = str(e).lower()
                # Detect rate limit / quota errors
                if any(
                    keyword in error_str
                    for keyword in ["429", "resource_exhausted", "quota", "rate limit"]
                ):
                    last_error = e
                    self.rotate()
                    attempts += 1
                else:
                    # Non-rate-limit error, raise immediately
                    raise e

        raise Exception(
            f"All {self.total_keys} API keys exhausted. Last error: {last_error}"
        )


# Singleton instance — shared across the app
key_manager = GeminiKeyManager()
