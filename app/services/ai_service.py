from app.services.key_manager import generate_content

DDL = """
CREATE TABLE IF NOT EXISTS categories(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL
);
CREATE TABLE IF NOT EXISTS customers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL,
    address VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    medication_dosage VARCHAR(255) NOT NULL,
    dosage_form VARCHAR(255) NOT NULL,
    laboratory VARCHAR(255) NOT NULL,
    indication_and_symptoms TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_indications_categories FOREIGN KEY (category_id) REFERENCES categories(id),
    CONSTRAINT fk_indications_supliers FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);
CREATE TABLE IF NOT EXISTS product_images(
    id SERIAL PRIMARY KEY,
    products_id INTEGER NOT NULL,
    image_url VARCHAR(500),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS inventory(
    id SERIAL PRIMARY KEY,
    actual_stock INTEGER NOT NULL DEFAULT 0,
    products_id INTEGER NOT NULL,
    minimum_stock INTEGER NOT NULL,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS orders(
    id SERIAL PRIMARY KEY,
    customers_id INTEGER,
    contact_email VARCHAR(255),
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_customers FOREIGN KEY (customers_id) REFERENCES customers(id),
    CHECK (order_state IN ('pending', 'confirmed', 'delivered', 'cancelled'))
);
CREATE TABLE IF NOT EXISTS order_items(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    products_id INTEGER NOT NULL,
    products_price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS order_status_history(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CHECK (order_state IN ('pending', 'confirmed', 'delivered', 'cancelled'))
);
CREATE TABLE IF NOT EXISTS users(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conversations(
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NULL,
    user_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS messages(
    id SERIAL PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    conversations_id INTEGER NOT NULL,
    message_content TEXT,
    images VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_conversation FOREIGN KEY (conversations_id) REFERENCES conversations(id),
    CHECK (sender IN ('assistant', 'user'))
);
"""

SYSTEM_PROMPT = f"""You are an expert SQL assistant for PostgreSQL.
Your only task is to generate valid SQL SELECT queries based on the following DDL:

{DDL}

Rules:
- Only generate SELECT queries (never INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
- Respond ONLY with the SQL query, no explanations, no markdown.
- Do not use code fences or backticks in your response.
- The tables you must query are: categories, suppliers, customers, products, product_images, inventory, orders, order_items, order_status_history, conversations, messages.
- When filtering by product name, ALWAYS use the EXACT name provided in quotes.
- This prompt is ONLY reached when the question requires database access. Generate SQL accordingly.
"""

EXTRACT_PRODUCT_PROMPT = """You are an assistant that analyzes questions about sales in a pharmacy.
Given the following user question, determine if the question references a specific product.

If the question mentions a product (or part of its name), respond ONLY with the exact search term as written by the user, without translating or modifying it.
If the question does NOT reference a specific product (e.g. "top 5 products", "total sales this month"), respond ONLY with: NONE

IMPORTANT: Do NOT translate the product name. Return it exactly as the user wrote it.

Examples:
- "What's the price of Ibuprofen?" -> Ibuprofen
- "¿Cuánto se vendió de ibuprofeno?" -> ibuprofeno
- "ventas de paracetamol" -> paracetamol
- "How much Amoxicillin do we have?" -> Amoxicillin
- "¿Cuáles son los 5 productos más vendidos?" -> NONE
- "total de ventas del último mes" -> NONE
- "show me top selling products" -> NONE
- "muéstrame las ventas de vitamina d3" -> vitamina d3
"""

CHART_CLASSIFICATION_PROMPT = """You are a data visualization expert for a pharmacy system.
Given a user question, determine if the results would benefit from a chart.

Rules:
- Respond ONLY with one word: BAR, LINE, PIE, or NONE
- BAR: rankings, comparisons, top N products, quantities by category
- LINE: trends over time, sales evolution, monthly/weekly data
- PIE: distributions, percentages, proportions of a whole
- NONE: single values, prices, specific product info, yes/no questions

Examples:
- "top 10 best selling products" -> BAR
- "sales trend over the last 6 months" -> LINE
- "distribution of products by category" -> PIE
- "what is the price of ibuprofen" -> NONE
- "how many units of amoxicillin do we have" -> NONE
- "orders by status" -> PIE
- "monthly revenue this year" -> LINE
- "which supplier has most products" -> BAR
"""

INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for a pharmacy AI assistant.
Your job is to determine if a user question requires querying the pharmacy database or can be answered with general pharmaceutical knowledge.

Rules:
- Respond ONLY with one word: DATABASE or CONVERSATIONAL
- DATABASE: questions about specific stock levels, prices, orders, customers, suppliers, inventory, or any data that lives in the pharmacy system
- CONVERSATIONAL: medical questions, symptoms, drug interactions, side effects, general health advice, medication recommendations, or anything answerable without database access

Examples:
- "how many units of ibuprofen do we have" -> DATABASE
- "what is the price of vitamin C" -> DATABASE
- "show me all orders from this month" -> DATABASE
- "which products are low on stock" -> DATABASE
- "who are our top customers" -> DATABASE
- "what is good for a headache" -> CONVERSATIONAL
- "what are the side effects of amoxicillin" -> CONVERSATIONAL
- "I have a fever, what do you recommend" -> CONVERSATIONAL
- "can I take ibuprofen and paracetamol together" -> CONVERSATIONAL
- "what medications are good for back pain" -> CONVERSATIONAL
- "explain what antihistamines do" -> CONVERSATIONAL
"""

RESPONSE_LANGUAGE_INSTRUCTION = """IMPORTANT: Always respond in the SAME language the user used in their question. 
If the user writes in English, respond in English. If the user writes in Spanish, respond in Spanish."""

SYMPTOM_TO_SQL_PROMPT = f"""You are an expert pharmacist assistant that generates SQL queries.
Given a user's health question or symptoms, generate a SQL SELECT query that finds relevant medications 
from the pharmacy database that could help with those symptoms.

DDL:
{DDL}

Rules:
- Generate ONLY a SELECT query, no explanations, no markdown, no backticks.
- Search in the products table using the indication_and_symptoms column and the name/description columns.
- Use ILIKE with % wildcards for flexible matching.
- Include product name, description, price, medication_dosage, dosage_form, laboratory, and indication_and_symptoms.
- Also join with inventory to show actual_stock so we only recommend products in stock (actual_stock > 0).
- Limit results to 5 most relevant products.
- Think about what keywords relate to the user's symptoms and search for them.
- Search using BOTH English and Spanish keywords for symptoms since the database may contain either language.

Examples:
- "what's good for a headache" -> search for: headache, dolor de cabeza, pain, dolor, analgesic, analgésico
- "I have a cough" -> search for: cough, tos, cold, resfriado, flu, gripe, respiratory, respiratorio
- "my skin is itchy" -> search for: itching, picazón, rash, erupción, dermatitis, skin, piel
"""

CONVERSATIONAL_PROMPT = """You are a friendly and knowledgeable pharmacy assistant.
You help customers with general pharmaceutical questions, medication recommendations, 
side effects, drug interactions, and health advice.

Rules:
- Provide helpful, accurate pharmaceutical information.
- Always recommend consulting a doctor or pharmacist for serious conditions.
- Be concise but thorough in your answers.
- Respond in the same language the user uses (Spanish or English).
- Do NOT generate SQL or reference database tables.
- Keep responses under 300 words unless the topic requires more detail.
"""

CONVERSATIONAL_WITH_PRODUCTS_PROMPT = """You are a friendly and knowledgeable pharmacy assistant.
You help customers with general pharmaceutical questions and recommend products from our pharmacy.

The user asked a health-related question. Below you have:
1. The user's question
2. Products available in our pharmacy that may help

Rules:
- First, provide a brief medical explanation about the condition/symptoms (2-3 sentences max).
- Then, recommend the available products from the list below with their details (name, dosage, form, price, laboratory).
- Format prices nicely (e.g., $25,000 COP or the appropriate format).
- End by asking if they'd like to place an order for any of the recommended products.
- If no products were found, still give the medical advice but mention we don't currently have matching products in stock.
- Respond in the same language the user uses (Spanish or English).
- Be warm and professional, like a pharmacist helping a customer.
- Always recommend consulting a doctor for serious or persistent symptoms.
"""


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


def generate_conversational_with_products(prompt: str, products_data: list[dict]) -> str:
    """Generates a conversational response that includes real product recommendations."""
    if products_data:
        products_text = "\n".join(
            f"- {p['name']} | Dosage: {p['medication_dosage']} | Form: {p['dosage_form']} | "
            f"Lab: {p['laboratory']} | Price: ${p['price']} | Stock: {p['actual_stock']} units | "
            f"Indications: {p['indication_and_symptoms']}"
            for p in products_data
        )
    else:
        products_text = "No matching products found in our current inventory."

    user_message = (
        f"User question: {prompt}\n\n"
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
    """Extracts the product term from the user question, or None if not applicable."""
    try:
        result = generate_content(
            contents=f"User question: {prompt}",
            system_prompt=EXTRACT_PRODUCT_PROMPT,
            temperature=0.0,
            max_completion_tokens=50,
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


def generate_sql(prompt: str, product_name: str | None = None) -> str:
    """Sends the prompt to OpenAI and gets a SQL query."""
    system = SYSTEM_PROMPT
    if product_name:
        system += f'\n\nIMPORTANT: The user is referring to the exact product: "{product_name}". Use this exact name in the WHERE clause.'

    result = generate_content(
        contents=f"User question: {prompt}",
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
