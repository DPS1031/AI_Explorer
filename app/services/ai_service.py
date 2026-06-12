"""Core AI service functions (intent classification, SQL generation, summarization).

This module also re-exports all functions from sub-modules for backward compatibility.
"""

from app.services.key_manager import generate_content
from app.services.ai_prompts import (
    DDL,
    SYSTEM_PROMPT,
    EXTRACT_PRODUCT_PROMPT,
    CHART_CLASSIFICATION_PROMPT,
    INTENT_CLASSIFICATION_PROMPT,
    RESPONSE_LANGUAGE_INSTRUCTION,
    SYMPTOM_TO_SQL_PROMPT,
    CONVERSATIONAL_PROMPT,
    DATA_SUMMARY_PROMPT,
    CONVERSATIONAL_WITH_PRODUCTS_PROMPT,
)

# Re-export image service functions
from app.services.ai_image_service import (  # noqa: F401
    analyze_image,
    analyze_multiple_images,
    generate_image_recommendation,
    generate_multi_image_recommendation,
)

# Re-export order service functions
from app.services.ai_order_service import (  # noqa: F401
    classify_order_intent,
    extract_order_product,
    extract_multi_order_products,
    generate_data_collection_message,
    parse_customer_data,
    generate_data_confirmation_message,
    classify_data_confirmation,
    generate_product_options_message,
    generate_multi_order_summary,
    parse_product_selection,
    parse_multi_order_selection,
)


def classify_intent(prompt: str) -> str:
    """Classifies whether the question needs DB access or is conversational."""
    try:
        result = generate_content(
            contents=f"User question: {prompt}",
            system_prompt=INTENT_CLASSIFICATION_PROMPT,
            temperature=0.0,
            max_completion_tokens=10,
        )
    except Exception as e:
        print(f"[classify_intent error] {e}")
        return "DATABASE"
    if result is None:
        return "DATABASE"
    result = result.strip().upper()
    if result not in ["DATABASE", "CONVERSATIONAL"]:
        return "DATABASE"
    return result


def generate_conversational_response(prompt: str) -> str:
    """Generates a conversational response without SQL."""
    try:
        result = generate_content(
            contents=f"User question: {prompt}",
            system_prompt=CONVERSATIONAL_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION,
            temperature=0.7,
        )
    except Exception as e:
        return f"Error generating response: {e}"
    if result is None:
        return "I'm sorry, I couldn't generate a response. Please try again."
    return result.strip()


def generate_symptom_sql(prompt: str) -> str:
    """Generates a SQL query to find relevant products based on user symptoms."""
    result = generate_content(
        contents=f"User question: {prompt}",
        system_prompt=SYMPTOM_TO_SQL_PROMPT,
        temperature=0.0,
        max_completion_tokens=500,
    )
    if result is None:
        raise ValueError("OpenAI did not return a response")
    return result.strip()


def generate_conversational_with_products(prompt: str, products_data: list[dict], history: list[dict] | None = None) -> str:
    """Generates a conversational response that includes real product recommendations."""
    if products_data:
        products_text = "\n".join(
            f"- {p.get('name', 'N/A')} | Dosage: {p.get('medication_dosage', 'N/A')} | Form: {p.get('dosage_form', 'N/A')} | "
            f"Lab: {p.get('laboratory', 'N/A')} | Price: {p.get('price', 'N/A')} COP | Stock: {p.get('actual_stock', 'N/A')} units | "
            f"Indications: {p.get('indication_and_symptoms', 'N/A')}"
            for p in products_data
        )
    else:
        products_text = "No matching products found in our current inventory."

    # Build conversation context from history
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:  # Last 6 messages for context and language detection
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation (use this to detect the customer's language):\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"Current user question: {prompt}\n\n"
        f"IMPORTANT: Detect the language from the conversation history and the current question. Respond ENTIRELY in that language.\n\n"
        f"Available products in our pharmacy:\n{products_text}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=CONVERSATIONAL_WITH_PRODUCTS_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION,
            temperature=0.7,
        )
    except Exception as e:
        return f"Error generating response: {e}"
    if result is None:
        return "I'm sorry, I couldn't generate a response. Please try again."
    return result.strip()


def extract_product_term(prompt: str) -> str | None:
    """Extracts the product term(s) from the user question, or None if not applicable.
    Returns a single product name, or multiple separated by ' | '.
    """
    try:
        result = generate_content(
            contents=f"User question: {prompt}",
            system_prompt=EXTRACT_PRODUCT_PROMPT,
            temperature=0.0,
            max_completion_tokens=100,
        )
    except Exception as e:
        print(f"[extract_product_term error] {e}")
        return None
    if result is None:
        return None
    result = result.strip()
    if result.upper() == "NONE":
        return None
    return result




def generate_sql(prompt: str, product_name: str | None = None, history: list[dict] | None = None) -> str:
    """Sends the prompt to OpenAI and gets a SQL query."""
    system = SYSTEM_PROMPT
    if product_name:
        if "," in product_name:
            # Multiple products
            products = [p.strip() for p in product_name.split(",")]
            products_list = ", ".join(f'"{p}"' for p in products)
            system += f'\n\nIMPORTANT: The user is referring to these products: {products_list}. Use these exact names in the WHERE clause with IN or multiple ILIKE conditions. Include ALL of them in the query results.'
        else:
            system += f'\n\nIMPORTANT: The user is referring to the exact product: "{product_name}". Use this exact name in the WHERE clause.'

    # Add conversation context so the AI can resolve references like "the first one", "it", etc.
    context_text = ""
    if history:
        history_lines = []
        for msg in history[-4:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        context_text = "\n\nRecent conversation for context (use this to resolve references like 'it', 'the first one', 'that product'):\n" + "\n".join(history_lines)

    user_content = f"User question: {prompt}{context_text}"

    result = generate_content(
        contents=user_content,
        system_prompt=system,
        temperature=0.0,
        max_completion_tokens=500,
    )
    if result is None:
        raise ValueError("OpenAI did not return a response")
    return result.strip()


def classify_chart_type(prompt: str) -> str:
    """Classifies what type of chart is appropriate for the question."""
    try:
        result = generate_content(
            contents=f"User question: {prompt}",
            system_prompt=CHART_CLASSIFICATION_PROMPT,
            temperature=0.0,
            max_completion_tokens=10,
        )
    except Exception as e:
        print(f"[classify_chart_type error] {e}")
        return "NONE"
    if result is None:
        return "NONE"
    result = result.strip().upper()
    if result not in ["BAR", "LINE", "PIE"]:
        return "NONE"
    return result


def summarize_query_results(prompt: str, columns: list[str], rows: list[tuple], history: list[dict] | None = None, language: str | None = None) -> str:
    """Generates a natural language summary of the query results."""
    # Format the data as a readable table for the AI
    if not rows:
        return "No results were found for your query."

    data_text = f"Columns: {', '.join(columns)}\n"
    for row in rows[:20]:  # Limit to 20 rows to avoid token overflow
        data_text += f"  {', '.join(str(v) for v in row)}\n"
    if len(rows) > 20:
        data_text += f"  ... and {len(rows) - 20} more rows.\n"

    # Build conversation context from history
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation (use this to detect the customer's language):\n" + "\n".join(history_lines) + "\n\n"

    # Explicit language instruction if provided
    lang_instruction = ""
    if language:
        lang_map = {
            "en": "You MUST respond ENTIRELY in English. Do NOT use Spanish or French.",
            "fr": "You MUST respond ENTIRELY in French. Do NOT use Spanish or English.",
            "es": "You MUST respond ENTIRELY in Spanish. Do NOT use English or French.",
        }
        lang_instruction = f"\n\nCRITICAL LANGUAGE OVERRIDE: {lang_map.get(language, lang_map['en'])}"

    user_message = (
        f"{history_text}"
        f"User question (RESPOND IN THE SAME LANGUAGE AS THIS QUESTION): {prompt}\n\n"
        f"Query results ({len(rows)} row(s)):\n{data_text}"
        f"{lang_instruction}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=DATA_SUMMARY_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION,
            temperature=0.7,
            max_completion_tokens=200,
        )
    except Exception as e:
        return f"I found {len(rows)} result(s) for your query."
    if result is None:
        return f"I found {len(rows)} result(s) for your query."
    return result.strip()


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validates that the generated SQL is safe (SELECT only).
    Returns (is_valid, error_message).
    """
    cleaned = sql.strip().upper()

    # Remove line comments
    lines = [
        line for line in cleaned.split("\n") if not line.strip().startswith("--")
    ]
    cleaned = " ".join(lines)

    # Verify it starts with SELECT or WITH (for CTEs)
    if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
        return False, "Query must start with SELECT or WITH."

    # Verify it doesn't contain dangerous operations
    dangerous_keywords = [
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "DROP ",
        "ALTER ",
        "TRUNCATE ",
        "CREATE ",
        "GRANT ",
        "REVOKE ",
        "EXEC ",
        "EXECUTE ",
    ]
    for keyword in dangerous_keywords:
        if keyword in cleaned:
            return False, f"Forbidden operation detected: {keyword.strip()}"

    return True, ""


# ============================================================
