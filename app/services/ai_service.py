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
- When the user asks for "all products" or a list/table of products, do NOT filter by name — return ALL products.
- When the user asks for products "with their laboratory" or similar, include the laboratory column and return ALL products.
- When asked about products with "more than one presentation" or "multiple presentations", note that in this database each product row IS a unique presentation (unique combination of name + dosage + form + laboratory). To find products with multiple presentations, look for product names that appear more than once, OR interpret it as products that have different dosage forms or dosages.
- ALWAYS return ALL matching rows. Do NOT use LIMIT unless the user explicitly asks for a specific number (e.g., "top 5", "first 10").

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
- If the question mentions ONE specific product BY NAME, respond with that product name exactly as written.
- If the question mentions MULTIPLE specific products BY NAME, respond with each product name separated by " | " (pipe with spaces).
- If the question does NOT reference a specific product by name, respond ONLY with: NONE
- Do NOT translate the product name. Return it exactly as the user wrote it.
- Do NOT include quantities, just the product names.
- If the user uses references like "it", "that one", "the first one", look at the conversation history to identify which product they mean and return that product name.
- If the conversation history mentions products and the user asks about cost/price/stock of "it" or "that", extract the product name from history.

IMPORTANT - Respond with NONE for these types of questions:
- Questions about ALL products, lists of products, or product tables (e.g. "show me all products", "dame una tabla de todos los productos")
- Questions about categories, rankings, or aggregations (e.g. "top 5 products", "products with more than one presentation")
- Questions that use words like "todos", "all", "cada", "every", "lista", "table", "tabla" referring to multiple/all products generically
- Questions about product attributes in general (e.g. "products with their laboratory", "productos con su laboratorio")
- Statistical or analytical questions (e.g. "total sales this month", "how many products do we have")

Examples:
- "What's the price of Ibuprofen?" -> Ibuprofen
- "¿Cuánto se vendió de ibuprofeno?" -> ibuprofeno
- "ventas de paracetamol" -> paracetamol
- "How much Amoxicillin do we have?" -> Amoxicillin
- "¿Cuáles son los 5 productos más vendidos?" -> NONE
- "total de ventas del último mes" -> NONE
- "show me top selling products" -> NONE
- "Dame una tabla de todos los productos con su laboratorio" -> NONE
- "Dame una tabla de todos los productos que tengan mas de una presentacion" -> NONE
- "Show me all products with their laboratory" -> NONE
- "List all products by category" -> NONE
- "Cuantos productos tenemos?" -> NONE
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

RESPONSE_LANGUAGE_INSTRUCTION = """CRITICAL LANGUAGE RULE: You MUST respond in the same language that the customer has been using throughout the conversation.
- If the conversation history shows the customer speaking English, respond in English.
- If the conversation history shows the customer speaking French, respond in French.
- If the conversation history shows the customer speaking Spanish, respond in Spanish.
- Short messages like "yes", "si", "oui", data entries (names, addresses, numbers), or confirmations do NOT change the conversation language.
- Look at the LONGER messages from the customer in the conversation history to determine the language.
- If there is no conversation history, use the current message language.
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
- Respond in the same language the user is using in the conversation.
- Do NOT generate SQL or reference database tables.
- Keep responses under 300 words unless the topic requires more detail.
- You can respond in ANY language the customer uses (English, Spanish, French, Portuguese, etc.)
"""

DATA_SUMMARY_PROMPT = """You are a friendly pharmacy assistant that explains database query results in natural language.
Given the user's original question and the query results, provide a clear, concise summary of the data.

Rules:
- Summarize the results in a natural, conversational way.
- ONLY mention data that is ACTUALLY present in the query results provided. NEVER invent, assume, or hallucinate data that is not in the results.
- If the results show only one entry for a product (e.g., one laboratory), do NOT claim there are other laboratories or options unless they appear in the data.
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
- If there are multiple options from different laboratories IN THE DATA, mention all of them so the customer can choose.
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Example: 25,000 COP. Do NOT use the $ symbol.
- When the results contain many rows, summarize the count and highlight a few examples. Do NOT try to list all rows in the summary.
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
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation (use this to detect the customer's language):\n" + "\n".join(history_lines) + "\n\n"

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


# ============================================================
# ORDER FLOW PROMPTS AND FUNCTIONS
# ============================================================

ORDER_INTENT_PROMPT = """You are an intent classifier for a pharmacy order flow.
Given the user's message and recent conversation history, determine if the user is:

1. CONFIRMING an order (saying yes to buying/ordering a product that was previously discussed or mentioned)
2. Just having a normal conversation

Rules:
- Respond ONLY with: ORDER_CONFIRMED or NOT_ORDER
- ORDER_CONFIRMED: The user explicitly says they want to order/buy a product. Examples:
  - "Si, quiero ordenar ese"
  - "Si deseo ordenar el acetaminofen"
  - "Yes, I want to buy that"
  - "Quiero pedir ese medicamento"
  - "Si, lo quiero"
  - "Ordenar" / "Pedir" / "Comprar" (when context shows a product was discussed)
  - "Si" or "Yes" (ONLY when the previous assistant message explicitly asked if they want to order)
- NOT_ORDER: Anything else, including:
  - Asking about prices without intent to buy
  - Asking for more information
  - General health questions
  - Saying "no" or declining

IMPORTANT: A simple "si" or "yes" is ONLY ORDER_CONFIRMED if the immediately preceding assistant message asked something like "would you like to order?" or "do you want to place an order?". Otherwise it's NOT_ORDER.
"""

ORDER_EXTRACT_PRODUCT_PROMPT = """You are an assistant that extracts the product a customer wants to order from conversation context.
Given the conversation history and the user's CURRENT message, identify:
1. The product name they want to order
2. The quantity (default to 1 if not specified)
3. The preferred laboratory/brand (ONLY if the user specifies it in their CURRENT message)

Rules:
- Look at the conversation history to find which product was being discussed RECENTLY.
- If the user mentions a specific product in their CURRENT message, use that.
- If the user just says "si" or "yes", look at the last assistant message to find which product was recommended/discussed.
- If the user says "that one", "ese", "that product", "ese producto", look at the last product mentioned by the assistant.
- IMPORTANT: Extract the FULL product name as it appears in the conversation (e.g., "Vitamina C" not just "Vitamina", "Acetaminophen" not just "Aceta").
- If multiple products were mentioned, extract ONLY the one the user is referring to based on their CURRENT message context.
- LABORATORY: ONLY extract a laboratory if the user EXPLICITLY mentions it in their CURRENT message (e.g., "the one from Bayer", "el de Genfar", "le genfar"). Do NOT extract a laboratory from previous orders or earlier conversation history. If the user just says "I want to order acetaminophen" without mentioning a lab, respond with LABORATORY: NONE.
- IMPORTANT: If the conversation shows a COMPLETED previous order (invoice generated, PDF downloaded), do NOT use that order's details for the new request. The user is starting a NEW order.
- Respond in this EXACT format (no extra text):
  PRODUCT: <product name>
  QUANTITY: <number>
  LABORATORY: <laboratory name or NONE if not specified in CURRENT message>
- If you cannot determine the product, respond with: UNKNOWN
"""

ORDER_DATA_COLLECTION_PROMPT = """You are a friendly pharmacy assistant collecting customer information for an order.
The customer has confirmed they want to order a product. You need to collect their personal information for the invoice.

You need to ask for ALL of the following data in a single message:
1. Nombre completo
2. Tipo de documento (Cedula de Ciudadania, Cedula de Extranjeria, Pasaporte)
3. Numero de documento (Cedula)
4. Correo electronico (where the invoice will be sent)
5. Direccion completa
6. Ciudad
7. Celular o telefono

Rules:
- Ask for ALL fields in a single, clear message.
- Be warm and professional.
- Mention that the invoice will be sent to the email they provide.
- CRITICAL: You MUST respond in the same language that the customer has been using throughout the conversation. Look at the conversation history to determine the language. If the conversation has been in English, respond in English. If in French, respond in French. If in Spanish, respond in Spanish.
- Do NOT use markdown formatting. Plain text only.
- Keep it concise but friendly.
"""

ORDER_PARSE_CUSTOMER_DATA_PROMPT = """You are a data extraction assistant.
Given the user's message containing their personal information for an order, extract the following fields.

Respond in this EXACT format (one field per line, no extra text):
NOMBRE: <full name>
TIPO_DOCUMENTO: <document type>
CEDULA: <document number>
CORREO: <email>
DIRECCION: <full address>
CIUDAD: <city>
CELULAR: <phone number>

Rules:
- Extract each field from the user's message.
- If a field is missing, write MISSING for that field.
- Do NOT add any explanation or extra text.
- The document type should be one of: Cedula de Ciudadania, Cedula de Extranjeria, Pasaporte
- If the user writes "CC" or "cedula", interpret as "Cedula de Ciudadania"
- If the user writes "CE", interpret as "Cedula de Extranjeria"
- Clean up the data (capitalize names properly, format phone numbers, etc.)
"""

ORDER_CONFIRM_DATA_PROMPT = """You are a friendly pharmacy assistant confirming customer data before generating an invoice.
Present the customer's information back to them in a clear, organized way and ask them to confirm if everything is correct.

Rules:
- Show ALL the data clearly organized.
- Ask explicitly: "Are all the data correct?" / "Todos los datos son correctos?" / "Toutes les informations sont-elles correctes?"
- CRITICAL: You MUST respond in the same language that the customer has been using throughout the conversation. Look at the conversation history to determine the language. If the conversation has been in English, respond in English. If in French, respond in French. If in Spanish, respond in Spanish.
- Do NOT use markdown formatting. Plain text only.
- Be warm and professional.
- Mention the product they are ordering, the quantity, and the total price.
"""

ORDER_DATA_CONFIRMED_PROMPT = """You are an intent classifier.
Given the user's message, determine if they are confirming that their personal data is correct.

Rules:
- Respond ONLY with: DATA_CONFIRMED or DATA_NOT_CONFIRMED
- DATA_CONFIRMED: "si", "yes", "correcto", "todo bien", "esta bien", "confirmo", "si estan correctos", etc.
- DATA_NOT_CONFIRMED: "no", "hay un error", "cambiar", "corregir", "el correo esta mal", etc.
"""


def classify_order_intent(prompt: str, history: list[dict] | None = None) -> str:
    """Determines if the user is confirming an order."""
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:300]}")
        history_text = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = f"{history_text}Current user message: {prompt}"

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_INTENT_PROMPT,
            temperature=0.0,
            max_completion_tokens=20,
        )
    except Exception as e:
        print(f"[classify_order_intent error] {e}")
        return "NOT_ORDER"
    if result is None:
        return "NOT_ORDER"
    result = result.strip().upper()
    if "ORDER_CONFIRMED" in result:
        return "ORDER_CONFIRMED"
    return "NOT_ORDER"


def extract_order_product(prompt: str, history: list[dict] | None = None) -> dict | None:
    """Extracts the product and quantity from the order confirmation context.
    Returns dict with 'product', 'quantity', and optionally 'laboratory' keys, or None if unknown.
    """
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:300]}")
        history_text = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = f"{history_text}User's confirmation message: {prompt}"

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_EXTRACT_PRODUCT_PROMPT,
            temperature=0.0,
            max_completion_tokens=100,
        )
    except Exception as e:
        print(f"[extract_order_product error] {e}")
        return None
    if result is None or "UNKNOWN" in result.upper():
        return None

    # Parse the response
    product = None
    quantity = 1
    laboratory = None
    for line in result.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("PRODUCT:"):
            product = line.split(":", 1)[1].strip()
        elif line.upper().startswith("QUANTITY:"):
            try:
                quantity = int(line.split(":", 1)[1].strip())
            except ValueError:
                quantity = 1
        elif line.upper().startswith("LABORATORY:"):
            lab_value = line.split(":", 1)[1].strip()
            if lab_value.upper() != "NONE":
                laboratory = lab_value

    if product:
        result_dict = {"product": product, "quantity": quantity}
        if laboratory:
            result_dict["laboratory"] = laboratory
        return result_dict
    return None


MULTI_ORDER_EXTRACT_PROMPT = """You are an assistant that extracts MULTIPLE products a customer wants to order.
Given the user's message, identify ALL products they want to order with their quantities.

Rules:
- Extract EVERY product mentioned in the user's message.
- For each product, extract the name and quantity (default 1 if not specified).
- If the user specifies a laboratory for a specific product, include it.
- Respond in this EXACT format (one product per line, no extra text):
  PRODUCT: <name> | QUANTITY: <number> | LABORATORY: <lab or NONE>
  PRODUCT: <name> | QUANTITY: <number> | LABORATORY: <lab or NONE>
  ...
- If you cannot identify any products, respond with: UNKNOWN

Examples:
- "Quiero ordenar un acetaminofen, un ibuprofeno y una vitamina C" ->
  PRODUCT: acetaminofen | QUANTITY: 1 | LABORATORY: NONE
  PRODUCT: ibuprofeno | QUANTITY: 1 | LABORATORY: NONE
  PRODUCT: vitamina C | QUANTITY: 1 | LABORATORY: NONE
- "I want 2 boxes of ibuprofen from Bayer and 3 amoxicillin" ->
  PRODUCT: ibuprofen | QUANTITY: 2 | LABORATORY: Bayer
  PRODUCT: amoxicillin | QUANTITY: 3 | LABORATORY: NONE
- "Quiero 5 cajas de acetaminofen genfar y 2 de vitamina C redoxon" ->
  PRODUCT: acetaminofen | QUANTITY: 5 | LABORATORY: Genfar
  PRODUCT: vitamina C | QUANTITY: 2 | LABORATORY: Redoxon
"""


def extract_multi_order_products(prompt: str, history: list[dict] | None = None) -> list[dict] | None:
    """Extracts multiple products from a multi-product order request.
    Returns list of dicts with 'product', 'quantity', and optionally 'laboratory' keys, or None if unknown.
    """
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-4:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:300]}")
        history_text = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = f"{history_text}User's order message: {prompt}"

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=MULTI_ORDER_EXTRACT_PROMPT,
            temperature=0.0,
            max_completion_tokens=500,
        )
    except Exception as e:
        print(f"[extract_multi_order_products error] {e}")
        return None
    if result is None or "UNKNOWN" in result.upper():
        return None

    # Parse multiple products
    products = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line.upper().startswith("PRODUCT:"):
            continue
        
        # Parse: PRODUCT: <name> | QUANTITY: <num> | LABORATORY: <lab>
        parts = line.split("|")
        product_info = {}
        for part in parts:
            part = part.strip()
            if part.upper().startswith("PRODUCT:"):
                product_info["product"] = part.split(":", 1)[1].strip()
            elif part.upper().startswith("QUANTITY:"):
                try:
                    product_info["quantity"] = int(part.split(":", 1)[1].strip())
                except ValueError:
                    product_info["quantity"] = 1
            elif part.upper().startswith("LABORATORY:"):
                lab_val = part.split(":", 1)[1].strip()
                if lab_val.upper() != "NONE":
                    product_info["laboratory"] = lab_val
        
        if "product" in product_info:
            if "quantity" not in product_info:
                product_info["quantity"] = 1
            products.append(product_info)

    return products if products else None


MULTI_ORDER_SUMMARY_PROMPT = """You are a friendly pharmacy assistant presenting a multi-product order summary to a customer.
The customer wants to order multiple products. Present ALL products with their details in a clear summary.

Rules:
- Show EVERY product with: name, dosage, form, laboratory, unit price, quantity, and subtotal.
- At the end, show the GRAND TOTAL of all products combined.
- If any product was NOT FOUND in the inventory, mention it clearly.
- If any product has MULTIPLE options (different labs/dosages), list ALL options for that product and ask the customer to choose which one they want (by number or lab name).
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Do NOT use the $ symbol.
- Do NOT use markdown formatting. Plain text only.
- Be warm and professional.
- This is a summary/budget view — make it clear and organized.
- If ALL products are confirmed (no options to choose from), show the complete budget summary and then ask for their personal data to generate the invoice (full name, document type, document number, email, address, city, phone).
- If there ARE products with multiple options, show the budget for confirmed products and ask the customer to choose for the remaining ones. Do NOT ask for personal data yet.
"""


def generate_multi_order_summary(products_found: list[dict], products_not_found: list[str], products_with_options: list[dict], prompt: str, language: str = "es") -> str:
    """Generates a summary message for a multi-product order showing all products, prices, and total."""
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    # Build the products info text
    found_text = ""
    if products_found:
        found_lines = []
        for p in products_found:
            found_lines.append(
                f"- {p['name']} | Dosis: {p.get('medication_dosage', 'N/A')} | Forma: {p.get('dosage_form', 'N/A')} | "
                f"Lab: {p.get('laboratory', 'N/A')} | Precio: {p['price']} COP | Cantidad: {p['quantity']} | "
                f"Subtotal: {float(p['price']) * p['quantity']:,.2f} COP"
            )
        found_text = "Products confirmed for the order:\n" + "\n".join(found_lines)

    not_found_text = ""
    if products_not_found:
        not_found_text = "\nProducts NOT FOUND in inventory: " + ", ".join(products_not_found)

    options_text = ""
    if products_with_options:
        options_lines = []
        for item in products_with_options:
            options_lines.append(f"\nProduct '{item['search_term']}' has multiple options:")
            for i, opt in enumerate(item["options"], 1):
                options_lines.append(
                    f"  {i}. {opt['name']} - Dosis: {opt.get('medication_dosage', 'N/A')} - "
                    f"Lab: {opt.get('laboratory', 'N/A')} - Precio: {opt['price']} COP - Stock: {opt.get('actual_stock', 'N/A')}"
                )
        options_text = "\n".join(options_lines)

    # Calculate total
    total = sum(float(p["price"]) * p["quantity"] for p in products_found)

    # Determine if all products are confirmed or if there are pending selections
    all_confirmed = len(products_with_options) == 0

    user_message = (
        f"Customer's message: \"{prompt}\"\n\n"
        f"{found_text}\n"
        f"{not_found_text}\n"
        f"{options_text}\n\n"
        f"Grand Total (confirmed products): {total:,.2f} COP\n\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n"
        f"{'ALL products are confirmed. Show the budget summary and ask for personal data (name, document type, document number, email, address, city, phone) to generate the invoice.' if all_confirmed else 'Some products have multiple options. Show the budget for confirmed products and ask the customer to choose which option they want for the remaining products.'}"
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=MULTI_ORDER_SUMMARY_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
            max_completion_tokens=800,
        )
    except Exception:
        # Fallback
        return f"Resumen del pedido:\n{found_text}\n{not_found_text}\n{options_text}\n\nTotal: {total:,.2f} COP"
    if result is None:
        return f"Resumen del pedido:\n{found_text}\n{not_found_text}\n{options_text}\n\nTotal: {total:,.2f} COP"
    return result.strip()


MULTI_ORDER_SELECTION_PROMPT = """You are an assistant that resolves product selections for a multi-product order.
The customer was shown multiple options for some products and needs to choose.
Given the conversation history and the user's response, determine which options they selected.

Rules:
- The user might say things like "the first one", "Bayer for the acetaminophen", "option 1 for both", "I want both", etc.
- For each product that needed selection, determine which option(s) (by number) the user chose.
- IMPORTANT: The user CAN select MULTIPLE options for the same product (e.g., "I want 1 of each", "quiero 1 de Grünenthal y 1 de Novartis", "una caja de genfar y otra de bayer"). In that case, list each selection separately with its quantity.
- If the user specifies a laboratory name, match it to the option number from the list shown in the conversation.
- If the user says "both" or "all" or "one of each" or "una de cada una" for a product, select ALL options with quantity 1 each.
- IMPORTANT: If the user makes selections for MULTIPLE pending products in a single message, extract ALL of them. Do not ignore any.
- Use the EXACT product name as shown in the pending options list (e.g., if the list says "acetaminofen", use "acetaminofen" not "acetaminofén").
- Respond in this EXACT format (one per line, NO extra text):
  PRODUCT: <product name> | SELECTION: <option number> | QUANTITY: <number>
  PRODUCT: <product name> | SELECTION: <option number> | QUANTITY: <number>
- For multiple selections of the same product, use multiple lines:
  PRODUCT: Tramadol | SELECTION: 1 | QUANTITY: 1
  PRODUCT: Tramadol | SELECTION: 2 | QUANTITY: 1
- For selections across different products:
  PRODUCT: acetaminofen | SELECTION: 1 | QUANTITY: 1
  PRODUCT: acetaminofen | SELECTION: 2 | QUANTITY: 1
  PRODUCT: Tramadol | SELECTION: 1 | QUANTITY: 1
  PRODUCT: Tramadol | SELECTION: 2 | QUANTITY: 1
- If you cannot determine a selection for a product, use: SELECTION: UNKNOWN
"""


def parse_multi_order_selection(prompt: str, history: list[dict] | None = None) -> list[dict] | None:
    """Parses the user's selections for products with multiple options in a multi-order.
    Returns list of dicts [{product, selection (1-based), quantity}], or None.
    Supports multiple selections for the same product (e.g., user wants both options).
    """
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-4:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:600]}")
        history_text = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = f"{history_text}User's selection message: {prompt}"

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=MULTI_ORDER_SELECTION_PROMPT,
            temperature=0.0,
            max_completion_tokens=300,
        )
    except Exception as e:
        print(f"[parse_multi_order_selection error] {e}")
        return None
    if result is None:
        return None

    selections = []
    for line in result.strip().split("\n"):
        line = line.strip()
        if not line.upper().startswith("PRODUCT:"):
            continue
        parts = line.split("|")
        product_name = None
        selection = None
        quantity = 1
        for part in parts:
            part = part.strip()
            if part.upper().startswith("PRODUCT:"):
                product_name = part.split(":", 1)[1].strip()
            elif part.upper().startswith("SELECTION:"):
                val = part.split(":", 1)[1].strip()
                if val.upper() != "UNKNOWN":
                    try:
                        selection = int(val)
                    except ValueError:
                        pass
            elif part.upper().startswith("QUANTITY:"):
                try:
                    quantity = int(part.split(":", 1)[1].strip())
                except ValueError:
                    quantity = 1
        if product_name and selection is not None:
            selections.append({"product": product_name.lower(), "selection": selection, "quantity": quantity})

    return selections if selections else None


def generate_data_collection_message(product_name: str, quantity: int, prompt: str, history: list[dict] | None = None, language: str = "es") -> str:
    """Generates the message asking the customer for their personal data."""
    # Map language code to explicit instruction
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    # Build conversation history for context
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"The customer wants to order: {product_name} (quantity: {quantity}).\n"
        f"Customer's latest message: \"{prompt}\"\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n"
        f"Ask them for their personal information to generate the invoice."
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_DATA_COLLECTION_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
    except Exception as e:
        return ("Para generar tu factura, necesito los siguientes datos:\n\n"
                "1. Nombre completo\n"
                "2. Tipo de documento (CC, CE, Pasaporte)\n"
                "3. Numero de documento\n"
                "4. Correo electronico\n"
                "5. Direccion completa\n"
                "6. Ciudad\n"
                "7. Celular o telefono")
    if result is None:
        return ("Para generar tu factura, necesito los siguientes datos:\n\n"
                "1. Nombre completo\n"
                "2. Tipo de documento (CC, CE, Pasaporte)\n"
                "3. Numero de documento\n"
                "4. Correo electronico\n"
                "5. Direccion completa\n"
                "6. Ciudad\n"
                "7. Celular o telefono")
    return result.strip()


def parse_customer_data(prompt: str) -> dict | None:
    """Parses customer data from their message.
    Returns dict with customer fields or None if data is incomplete.
    """
    try:
        result = generate_content(
            contents=f"User message with their data:\n{prompt}",
            system_prompt=ORDER_PARSE_CUSTOMER_DATA_PROMPT,
            temperature=0.0,
            max_completion_tokens=300,
        )
    except Exception as e:
        print(f"[parse_customer_data error] {e}")
        return None
    if result is None:
        return None

    # Parse the structured response
    data = {}
    field_map = {
        "NOMBRE": "nombre",
        "TIPO_DOCUMENTO": "tipo_documento",
        "CEDULA": "cedula",
        "CORREO": "correo",
        "DIRECCION": "direccion",
        "CIUDAD": "ciudad",
        "CELULAR": "celular",
    }

    for line in result.strip().split("\n"):
        line = line.strip()
        for key, field in field_map.items():
            if line.upper().startswith(f"{key}:"):
                value = line.split(":", 1)[1].strip()
                if value.upper() != "MISSING":
                    data[field] = value
                break

    # Check if we have all required fields
    required = ["nombre", "cedula", "correo", "direccion", "ciudad", "celular"]
    missing = [f for f in required if f not in data]

    if missing:
        data["_missing"] = missing

    # Default tipo_documento if not provided
    if "tipo_documento" not in data:
        data["tipo_documento"] = "Cedula de Ciudadania"

    return data


def generate_data_confirmation_message(customer_data: dict, product_name: str, quantity: int, unit_price: float, prompt: str, history: list[dict] | None = None, language: str = "es") -> str:
    """Generates a message showing the customer their data for confirmation."""
    total = unit_price * quantity

    # Map language code to explicit instruction
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    # Build conversation history for context
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"Customer data to confirm:\n"
        f"- Nombre: {customer_data.get('nombre', 'N/A')}\n"
        f"- Tipo de documento: {customer_data.get('tipo_documento', 'N/A')}\n"
        f"- Cedula: {customer_data.get('cedula', 'N/A')}\n"
        f"- Correo: {customer_data.get('correo', 'N/A')}\n"
        f"- Direccion: {customer_data.get('direccion', 'N/A')}\n"
        f"- Ciudad: {customer_data.get('ciudad', 'N/A')}\n"
        f"- Celular: {customer_data.get('celular', 'N/A')}\n\n"
        f"Product: {product_name}\n"
        f"Quantity: {quantity}\n"
        f"Unit price: {unit_price:,.2f} COP\n"
        f"Total: {total:,.2f} COP\n\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n"
        f"Present this data back to the customer and ask if everything is correct."
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_CONFIRM_DATA_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
    except Exception as e:
        # Fallback manual message
        total = unit_price * quantity
        return (
            f"Estos son los datos para tu factura:\n\n"
            f"Nombre: {customer_data.get('nombre', 'N/A')}\n"
            f"Tipo de documento: {customer_data.get('tipo_documento', 'N/A')}\n"
            f"Cedula: {customer_data.get('cedula', 'N/A')}\n"
            f"Correo: {customer_data.get('correo', 'N/A')}\n"
            f"Direccion: {customer_data.get('direccion', 'N/A')}\n"
            f"Ciudad: {customer_data.get('ciudad', 'N/A')}\n"
            f"Celular: {customer_data.get('celular', 'N/A')}\n\n"
            f"Producto: {product_name} x{quantity}\n"
            f"Total: {total:,.2f} COP\n\n"
            f"Todos los datos son correctos?"
        )
    if result is None:
        total = unit_price * quantity
        return (
            f"Estos son los datos para tu factura:\n\n"
            f"Nombre: {customer_data.get('nombre', 'N/A')}\n"
            f"Tipo de documento: {customer_data.get('tipo_documento', 'N/A')}\n"
            f"Cedula: {customer_data.get('cedula', 'N/A')}\n"
            f"Correo: {customer_data.get('correo', 'N/A')}\n"
            f"Direccion: {customer_data.get('direccion', 'N/A')}\n"
            f"Ciudad: {customer_data.get('ciudad', 'N/A')}\n"
            f"Celular: {customer_data.get('celular', 'N/A')}\n\n"
            f"Producto: {product_name} x{quantity}\n"
            f"Total: {total:,.2f} COP\n\n"
            f"Todos los datos son correctos?"
        )
    return result.strip()


def classify_data_confirmation(prompt: str) -> str:
    """Determines if the user is confirming their data is correct."""
    try:
        result = generate_content(
            contents=f"User message: {prompt}",
            system_prompt=ORDER_DATA_CONFIRMED_PROMPT,
            temperature=0.0,
            max_completion_tokens=20,
        )
    except Exception as e:
        print(f"[classify_data_confirmation error] {e}")
        return "DATA_NOT_CONFIRMED"
    if result is None:
        return "DATA_NOT_CONFIRMED"
    result = result.strip().upper()
    if "DATA_CONFIRMED" in result:
        return "DATA_CONFIRMED"
    return "DATA_NOT_CONFIRMED"


ORDER_PRESENT_OPTIONS_PROMPT = """You are a friendly pharmacy assistant presenting product options to a customer who wants to place an order.
The customer wants to order a specific medication. Show them the available options from our inventory.

Rules:
- If there is ONLY ONE option: present it clearly with all details (name, dosage, form, laboratory, price, stock) and ask if they want to order that one and how many units.
- If there are MULTIPLE options: number each option (1, 2, 3...) with all details and ask which one they'd like to order and how many units.
- ALL prices are in Colombian Pesos (COP). Write prices as the number followed by COP. Do NOT use the $ symbol.
- CRITICAL: Detect the language from the conversation history and respond ENTIRELY in that language. The customer may speak English, Spanish, French, or any other language.
- Do NOT use markdown formatting. Plain text only.
- Be warm and professional.
"""

ORDER_SELECT_PRODUCT_PROMPT = """You are an assistant that determines which product a customer selected from a list of options.
Given the conversation history (which contains product options) and the user's selection message, determine:
1. Which product they selected (by number, name, or laboratory)
2. The quantity they want

Rules:
- Look at the previous assistant message which listed product options.
- If there was ONLY ONE option and the user says "yes", "si", "oui", "that one", "esa", or any confirmation, select option 1.
- If there were multiple options, the user might say:
  - A number: "the first one", "option 2", "1", "le premier"
  - A laboratory name: "the Genfar one", "I prefer Bayer", "Je prefere le genfar", "el de Bayer"
  - A dosage: "the 500mg one", "el de 200mg"
  - A preference: "the cheaper one", "the one with more stock"
- Match the user's selection to the correct option number by comparing against the options listed in the conversation history.
- If the user specifies a quantity (e.g., "2 boxes", "3 units", "quiero 2"), use that quantity.
- The user may respond in ANY language (English, Spanish, French, etc.). Understand their intent regardless of language.
- Respond in this EXACT format (no extra text):
  SELECTION: <number of the option selected, starting from 1>
  QUANTITY: <number, default 1 if not specified>
- If you cannot determine which product they selected, respond with: UNKNOWN
"""


def generate_product_options_message(products_data: list[dict], prompt: str, history: list[dict] | None = None, language: str = "es") -> str:
    """Generates a message presenting available product options to the customer."""
    products_text = "\n".join(
        f"{i+1}. {p.get('name', 'N/A')} - Dosis: {p.get('medication_dosage', 'N/A')} - "
        f"Forma: {p.get('dosage_form', 'N/A')} - Laboratorio: {p.get('laboratory', 'N/A')} - "
        f"Precio: {p.get('price', 'N/A')} COP - Stock: {p.get('actual_stock', 'N/A')} unidades"
        for i, p in enumerate(products_data)
    )

    # Map language code to explicit instruction
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    # Build conversation history for context
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:200]}")
        history_text = "Recent conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = (
        f"{history_text}"
        f"Customer's latest message: \"{prompt}\"\n\n"
        f"Available product options:\n{products_text}\n\n"
        f"LANGUAGE INSTRUCTION: {lang_instruction}\n"
        f"Present these options to the customer and ask which one they want to order and how many."
    )

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_PRESENT_OPTIONS_PROMPT + "\n\n" + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
    except Exception:
        return f"Tenemos las siguientes opciones disponibles:\n\n{products_text}\n\nCual deseas ordenar y cuantas unidades?"
    if result is None:
        return f"Tenemos las siguientes opciones disponibles:\n\n{products_text}\n\nCual deseas ordenar y cuantas unidades?"
    return result.strip()


def parse_product_selection(prompt: str, history: list[dict] | None = None) -> dict | None:
    """Parses which product the customer selected from the options list.
    Returns dict with 'selection' (1-based index) and 'quantity', or None if unknown.
    """
    history_text = ""
    if history:
        history_lines = []
        # Use more history to ensure the options message is included
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:500]}")
        history_text = "Conversation history:\n" + "\n".join(history_lines) + "\n\n"

    user_message = f"{history_text}User's selection message: {prompt}"

    try:
        result = generate_content(
            contents=user_message,
            system_prompt=ORDER_SELECT_PRODUCT_PROMPT,
            temperature=0.0,
            max_completion_tokens=50,
        )
    except Exception as e:
        print(f"[parse_product_selection error] {e}")
        return None
    if result is None or "UNKNOWN" in result.upper():
        return None

    selection = None
    quantity = 1
    for line in result.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("SELECTION:"):
            try:
                selection = int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
        elif line.upper().startswith("QUANTITY:"):
            try:
                quantity = int(line.split(":", 1)[1].strip())
            except ValueError:
                quantity = 1

    if selection is not None:
        return {"selection": selection, "quantity": quantity}
    return None
