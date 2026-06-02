"""AI service functions for the order flow (single and multi-product)."""

from app.services.key_manager import generate_content
from app.services.ai_prompts import RESPONSE_LANGUAGE_INSTRUCTION


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
Given the user's message AND the conversation history, identify ALL products they want to order with their quantities.

Rules:
- Extract EVERY product the user wants to order.
- For each product, extract the name and quantity (default 1 if not specified).
- If the user specifies a laboratory for a specific product, include it.
- CRITICAL: If the user references products from the conversation history using phrases like "all of them", "one of each", "each one", "the 4 options", "those", "todos", "una de cada uno", "cada una de las opciones", "esos", "los que me mostraste", look at the CONVERSATION HISTORY to find which products were previously presented by the assistant. Extract ALL those products.
- When the assistant previously listed products with details (name, dosage, laboratory, price), and the user says they want to order them, extract each product individually with its laboratory.
- If the user says "one box of each" or "una caja de cada uno", extract each product that was listed in the assistant's previous message with quantity 1.
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
- (History shows assistant listed: Acetaminofen 500mg Genfar, Acetaminofen 200mg Bayer, Tramadol 50mg Grünenthal, Tramadol 70mg Novartis)
  "Me gustaria pedir una caja de cada uno de las 4 opciones" ->
  PRODUCT: Acetaminofen | QUANTITY: 1 | LABORATORY: Genfar
  PRODUCT: Acetaminofen | QUANTITY: 1 | LABORATORY: Bayer
  PRODUCT: Tramadol | QUANTITY: 1 | LABORATORY: Grünenthal
  PRODUCT: Tramadol | QUANTITY: 1 | LABORATORY: Novartis
- (History shows assistant recommended Ibuprofen and Vitamin C)
  "Quiero ordenarlos todos" ->
  PRODUCT: Ibuprofen | QUANTITY: 1 | LABORATORY: NONE
  PRODUCT: Vitamin C | QUANTITY: 1 | LABORATORY: NONE
"""


def extract_multi_order_products(prompt: str, history: list[dict] | None = None) -> list[dict] | None:
    """Extracts multiple products from a multi-product order request.
    Returns list of dicts with 'product', 'quantity', and optionally 'laboratory' keys, or None if unknown.
    """
    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:
            role = "Customer" if msg["role"] == "user" else "Assistant"
            history_lines.append(f"{role}: {msg['content'][:500]}")
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
- CRITICAL: If the user says "both" or "all" or "one of each" or "una de cada una" or "todos" or "ordenarlos todos" or "all of them" or "los quiero todos" or "quiero todos" or "want them all" for a product, select ALL options for that product with quantity 1 each.
- CRITICAL: If the user says "los 2" or "los dos" or "ambos" (referring to a product with 2 options), this means they want ONE of EACH option (quantity 1 each), NOT 2 of the same. Example: "los 2 tramadoles" = 1 Tramadol option 1 + 1 Tramadol option 2.
- CRITICAL: If the user's message is a general statement like "Quiero ordenarlos todos", "I want to order all of them", "todos", "all", this means they want ALL options for ALL pending products. Select every single option for every pending product with quantity 1 each.
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

Examples:
- User says "Quiero ordenarlos todos" (pending: Tramadol with options 1=Grünenthal, 2=Novartis) ->
  PRODUCT: Tramadol | SELECTION: 1 | QUANTITY: 1
  PRODUCT: Tramadol | SELECTION: 2 | QUANTITY: 1
- User says "los 2 tramadoles" (pending: Tramadol with options 1=Grünenthal, 2=Novartis) ->
  PRODUCT: Tramadol | SELECTION: 1 | QUANTITY: 1
  PRODUCT: Tramadol | SELECTION: 2 | QUANTITY: 1
- User says "Quiero el de Grünenthal" (pending: Tramadol with options 1=Grünenthal, 2=Novartis) ->
  PRODUCT: Tramadol | SELECTION: 1 | QUANTITY: 1
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
