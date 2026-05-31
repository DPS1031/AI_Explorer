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

Important data relationships:
- To find "best selling" or "most sold" products, you MUST join order_items with products and SUM the quantity column from order_items. The order_items table tracks what was actually sold.
- The inventory table shows current stock levels (actual_stock), NOT sales.
- The orders table has the total amount and status. order_items has the individual products in each order.
- To calculate revenue per product, multiply order_items.products_price * order_items.quantity.
- When asked about "sales" or "sold", always use order_items joined with products.
- When asked about "stock" or "available", use the inventory table.

Budget/Quote/Cost calculations:
- When the user asks for a "presupuesto" (budget/quote), "cuánto cuestan" (how much do they cost), or "how much does X cost", calculate: price * quantity.
- If the user specifies quantities (e.g., "2 cajas de ibuprofeno"), multiply the product price by that quantity.
- If multiple products are mentioned, show each product's price and calculate the total.
- Use the products table for prices. ALWAYS include the laboratory column so the user knows which brand.
- If a product exists from multiple laboratories, show ALL options.
- Example: SELECT name, laboratory, price, (price * 2) as total FROM products WHERE name ILIKE '%ibuprofen%'
- When the user asks "do we have X?" or "tenemos X?", include name, price, laboratory, medication_dosage, dosage_form, and actual_stock from inventory.
"""

EXTRACT_PRODUCT_PROMPT = """You are an assistant that analyzes questions about products in a pharmacy.
Given the following user question (which may include recent conversation history for context), determine if the question references specific products.

Rules:
- If the question mentions ONE product, respond with that product name exactly as written.
- If the question mentions MULTIPLE products, respond with each product name separated by " | " (pipe with spaces).
- If the question does NOT reference a specific product (e.g. "top 5 products", "total sales this month"), respond ONLY with: NONE
- Do NOT translate the product name. Return it exactly as the user wrote it.
- Do NOT include quantities, just the product names.
- If the user uses references like "it", "that one", "the first one", look at the conversation history to identify which product they mean and return that product name.
- If the conversation history mentions products and the user asks about cost/price/stock of "it" or "that", extract the product name from history.

Examples:
- "What's the price of Ibuprofen?" -> Ibuprofen
- "¿Cuánto se vendió de ibuprofeno?" -> ibuprofeno
- "ventas de paracetamol" -> paracetamol
- "How much Amoxicillin do we have?" -> Amoxicillin
- "¿Cuáles son los 5 productos más vendidos?" -> NONE
- "total de ventas del último mes" -> NONE
- "show me top selling products" -> NONE
- "muéstrame las ventas de vitamina d3" -> vitamina d3
- "Me puedes dar un presupuesto de 2 cajas de ibuprofeno y una caja de vitamina C" -> ibuprofeno | vitamina C
- "How much does 3 boxes of amoxicillin and 2 ibuprofen cost?" -> amoxicillin | ibuprofen
- "Cuanto cuestan 2 cajas de ibuprofeno?" -> ibuprofeno
- "Give me a quote for acetaminophen and loratadine" -> acetaminophen | loratadine
- "Tenemos acetaminofen?" -> acetaminofen
- "And how much does it cost?" (history mentions Acetaminophen) -> Acetaminophen
- "How much does the first one cost?" (history shows top 5: Cetirizine, Loratadine...) -> Cetirizine
"""

CHART_CLASSIFICATION_PROMPT = """You are a data visualization expert for a pharmacy system.
Given a user question, determine if the results would benefit from a chart visualization.

Rules:
- Respond ONLY with one word: BAR, LINE, PIE, or NONE
- BAR: rankings, comparisons, top/bottom N items, quantities by category, sorted lists, "most/least" questions
- LINE: trends over time, evolution, monthly/weekly/daily data, historical patterns
- PIE: distributions as proportions, percentage breakdowns, status compositions, market share
- NONE: single values, specific lookups, yes/no questions, detailed lists without aggregation, price checks

Key principles:
- If the question asks for items sorted by quantity/amount → BAR
- If the question asks for proportions or "by status/category" without time → PIE
- If the question involves time periods or evolution → LINE
- If the question asks for a specific value or detail → NONE
- When in doubt between BAR and NONE, prefer BAR if there are multiple items being compared

Examples:
- "top 10 best selling products" -> BAR
- "products from most sold to least sold" -> BAR
- "which products sell the most" -> BAR
- "sales trend over the last 6 months" -> LINE
- "monthly revenue this year" -> LINE
- "distribution of products by category" -> PIE
- "orders by status" -> PIE
- "what percentage of orders are cancelled" -> PIE
- "what is the price of ibuprofen" -> NONE
- "how many units of amoxicillin do we have" -> NONE
- "show me customer details" -> NONE
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

RESPONSE_LANGUAGE_INSTRUCTION = """CRITICAL LANGUAGE RULE: You MUST respond in the EXACT SAME language as the CURRENT user question (the last question asked, NOT the conversation history).
If the current question is in English, you MUST respond entirely in English regardless of what language previous messages were in.
If the current question is in Spanish, you MUST respond entirely in Spanish.
Do NOT let the conversation history influence your response language. ONLY the current question determines the language.
ALL prices are in Colombian Pesos (COP). Always use the word COP after the amount. Example: 25,000 COP.
Do NOT use $ symbol before prices (it causes rendering issues). Just write the number followed by COP.
Do NOT use any markdown or special formatting: no **bold**, no *italic*, no backticks, no code blocks, no special characters. Write in plain text only."""

SYMPTOM_TO_SQL_PROMPT = f"""You are an expert pharmacist assistant that generates SQL queries.
Given a user's health question or symptoms, generate a SQL SELECT query that finds relevant medications 
from the pharmacy database that could help with those symptoms.

DDL:
{DDL}

Rules:
- Generate ONLY a SELECT query, no explanations, no markdown, no backticks.
- Search in the products table using the indication_and_symptoms column and the name/description columns.
- Use ILIKE with % wildcards for flexible matching.
- Include product name, description, price, medication_dosage, dosage_form, laboratory, indication_and_symptoms, and actual_stock from inventory.
- ALWAYS join with inventory to show actual_stock so we only recommend products in stock (actual_stock > 0).
- The SELECT must include these exact column names: name, price, medication_dosage, dosage_form, laboratory, indication_and_symptoms, actual_stock
- Limit results to 5 most relevant products.
- Think broadly about what medications help with the user's symptoms.
- Search using BOTH English and Spanish keywords for symptoms since the database may contain either language.
- Think about the CATEGORY of medication that treats the symptom, not just the symptom keyword.

Common mappings (use multiple keywords):
- headache/dolor de cabeza → analgesic, pain, dolor, headache, fever, fiebre
- cough/tos → cough, tos, cold, resfriado, flu, gripe, respiratory, respiratorio, expectorant
- back pain/dolor de espalda → pain, dolor, inflammation, inflamación, muscle, muscular, analgesic, analgésico, anti-inflammatory
- allergies/alergias → allergy, alergia, antihistamine, antihistamínico, rhinitis, rinitis, itching, picazón
- fever/fiebre → fever, fiebre, antipyretic, antipirético, pain, dolor
- infection/infección → antibiotic, antibiótico, infection, infección
- skin/piel → dermatitis, skin, piel, rash, cream, crema, topical, tópico

Example query structure:
SELECT p.name, p.price, p.medication_dosage, p.dosage_form, p.laboratory, p.indication_and_symptoms, i.actual_stock
FROM products p
JOIN inventory i ON i.products_id = p.id
WHERE i.actual_stock > 0
AND (p.indication_and_symptoms ILIKE '%keyword1%' OR p.indication_and_symptoms ILIKE '%keyword2%' OR p.name ILIKE '%keyword3%' OR p.description ILIKE '%keyword4%')
LIMIT 5
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

DATA_SUMMARY_PROMPT = """You are a friendly pharmacy assistant that explains database query results in natural language.
Given the user's original question and the query results, provide a clear, concise summary of the data.

Rules:
- Summarize the results in a natural, conversational way.
- Mention specific numbers, names, and values from the data.
- Keep it brief (2-4 sentences max) unless the data is complex.
- Do NOT mention SQL, queries, databases, or technical details.
- Do NOT use markdown tables — the data will be shown separately in a chart/table.
- Do NOT use markdown formatting like **bold**, *italic*, or any special characters for emphasis.
- Write in plain text only. No asterisks, no underscores, no special formatting.
- Be warm and helpful, like a pharmacist explaining information to a customer.
- If the data has rankings or comparisons, highlight the top items.
- If the data shows trends, mention the direction.
- When showing prices or quotes, ALWAYS mention the laboratory/brand if available in the data.
- If there are multiple options from different laboratories, mention all of them so the customer can choose.
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Example: 25,000 COP. Do NOT use the $ symbol.
"""

CONVERSATIONAL_WITH_PRODUCTS_PROMPT = """You are a friendly and knowledgeable pharmacy assistant.
You help customers with general pharmaceutical questions and recommend products from our pharmacy.

The user asked a health-related question. Below you have:
1. The user's question
2. Recent conversation history (if available) for context
3. Products available in our pharmacy that may help (if any were found)

Rules:
- First, provide a brief medical explanation about the condition/symptoms (2-3 sentences max).
- Then, if products were found, recommend them with their details (name, dosage, form, price, laboratory).
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Example: 25,000 COP. Do NOT use the $ symbol.
- Do NOT use markdown formatting like **bold**, *italic*, or special characters. Write in plain text only.
- Do NOT use the $ symbol anywhere in your response.
- If products were found, end by asking if they'd like to place an order for any of the recommended products.
- If no products were found BUT the conversation history mentions relevant products, refer back to those products from the history. Do NOT say "we don't have products" if you already recommended something relevant in a previous message.
- If no products were found and nothing relevant is in the history, give medical advice and mention that we don't currently have matching products in stock, but suggest they visit the pharmacy for more options.
- Be warm and professional, like a pharmacist helping a customer.
- Always recommend consulting a doctor for serious or persistent symptoms.
- ALWAYS try to be helpful and provide actionable advice regardless of whether products were found.
- Use the conversation history to understand context (e.g., if the user says "it" or "that one", refer to the previous messages to understand what they mean).
"""


IMAGE_ANALYSIS_PROMPT = """You are a pharmaceutical image recognition assistant.
Analyze the provided image of a medication (box, bottle, blister pack, sachet, etc.) and extract the following information:

Rules:
- Identify the medication name, dosage, form (tablet, capsule, syrup, sachet, etc.), and laboratory/brand if visible.
- Respond ONLY with a short structured summary like: "Ibuprofen 400mg tablets by Bayer, 20 units"
- If you can partially identify the medication (e.g., you can see it's Vitamin C but can't read the dosage), still provide what you can identify.
- Look for text on packaging, brand logos, and product descriptions visible in the image.
- If the image shows ANY pharmaceutical or health product (vitamins, supplements, OTC medications), identify it — do NOT respond with NOT_MEDICATION.
- Only respond with NOT_MEDICATION if the image clearly shows something completely unrelated to health/pharmacy (e.g., food, electronics, animals).
"""

IMAGE_RECOMMENDATION_PROMPT = """You are a friendly and knowledgeable pharmacy assistant.
A customer has shared an image of a medication. You have analyzed the image and identified the product.
Below you have:
1. What was identified in the image
2. The user's message/question about it
3. Matching products available in our pharmacy

Rules:
- Start by confirming what you identified in the image (e.g., "I can see you have a box of Ibuprofen 400mg...").
- If we have matching or similar products in our pharmacy, recommend them with details (name, dosage, form, price, laboratory).
- If the user seems to need a refill or is asking about the medication, provide helpful information.
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Example: 25,000 COP. Do NOT use the $ symbol.
- Do NOT use markdown formatting like **bold**, *italic*, or special characters. Write in plain text only.
- Do NOT use the $ symbol anywhere in your response.
- Be warm and professional, like a pharmacist helping a customer.
- If no matching products were found, acknowledge the medication and suggest they check back or ask about alternatives.
- Always recommend consulting a doctor if they have concerns about their medication.
"""


def analyze_image(image_base64: str, user_text: str = "") -> str:
    """Analyzes a medication image and returns the identified product."""
    content_parts = [
        {"type": "text", "text": f"User message: {user_text}" if user_text else "Identify this medication."},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
        },
    ]

    try:
        result = generate_content(
            contents=content_parts,
            system_prompt=IMAGE_ANALYSIS_PROMPT,
            temperature=0.0,
            max_completion_tokens=100,
        )
    except Exception as e:
        print(f"[analyze_image error] {e}")
        return None
    if result is None:
        return None
    return result.strip()


def generate_image_recommendation(user_text: str, image_analysis: str, products_data: list[dict]) -> str:
    """Generates a response combining image analysis with product recommendations."""
    if products_data:
        products_text = "\n".join(
            f"- {p['name']} | Dosage: {p.get('medication_dosage', 'N/A')} | Form: {p.get('dosage_form', 'N/A')} | "
            f"Lab: {p.get('laboratory', 'N/A')} | Price: ${p.get('price', 'N/A')} | Stock: {p.get('actual_stock', 'N/A')} units"
            for p in products_data
        )
    else:
        products_text = "No matching products found in our current inventory."

    user_message = (
        f"Image analysis result: {image_analysis}\n\n"
        f"User message (RESPOND IN THIS LANGUAGE): {user_text}\n\n"
        f"Available matching products in our pharmacy:\n{products_text}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=IMAGE_RECOMMENDATION_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\nThe user's message is: \"{user_text}\". Detect the language of THIS message and respond ENTIRELY in that language.",
            temperature=0.7,
        )
    except Exception as e:
        return f"I identified the medication as: {image_analysis}. However, I encountered an error generating recommendations."
    if result is None:
        return f"I identified the medication as: {image_analysis}. Please try again for product recommendations."
    return result.strip()


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
        for msg in history[-4:]:  # Last 4 messages for context
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"Current user question (RESPOND IN THE LANGUAGE OF THIS QUESTION): {prompt}\n\n"
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


def summarize_query_results(prompt: str, columns: list[str], rows: list[tuple], history: list[dict] | None = None) -> str:
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
        for msg in history[-4:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation:\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"User question: {prompt}\n\n"
        f"Query results ({len(rows)} row(s)):\n{data_text}"
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
