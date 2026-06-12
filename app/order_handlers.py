import streamlit as st
import uuid

from app.services.ai_service import (
    classify_intent,
    classify_data_confirmation,
    extract_order_product,
    extract_multi_order_products,
    generate_data_collection_message,
    parse_customer_data,
    generate_data_confirmation_message,
    generate_product_options_message,
    generate_multi_order_summary,
    parse_product_selection,
)
from app.services.db_service import find_matching_products, get_connection
from app.services.auth_service import (
    create_conversation,
    save_message,
)
from app.services.pdf_service import generate_invoice_pdf
from app.services.email_service import send_invoice_email
from app.ui_components import sanitize_response, _detect_conversation_language


def handle_order_confirmed(prompt: str):
    """Handles when the user confirms they want to order a product.
    Shows all available presentations/options before asking for personal data.
    """
    # Check if there are pre-loaded products from multi-image analysis
    if st.session_state.get("multi_order_products") and not st.session_state.get("order_flow"):
        # Products were already identified from images — route to multi-order flow directly
        products_found = st.session_state.multi_order_products
        products_with_options = st.session_state.get("multi_order_pending_options") or []

        if products_with_options:
            st.session_state.order_flow = "multi_awaiting_selection"
            language = _detect_conversation_language()
            response = sanitize_response(
                generate_multi_order_summary(products_found, [], products_with_options, prompt, language=language)
            )
        else:
            # All products confirmed — go to data collection
            st.session_state.order_flow = "multi_awaiting_data"
            language = _detect_conversation_language()
            total = sum(float(p["price"]) * p["quantity"] for p in products_found)
            form_msgs = {
                "es": f"Todos los productos confirmados. Total: {total:,.2f} COP. Por favor completa el formulario con tus datos para generar la factura.",
                "en": f"All products confirmed. Total: {total:,.2f} COP. Please fill out the form with your details to generate the invoice.",
                "fr": f"Tous les produits confirmes. Total: {total:,.2f} COP. Veuillez remplir le formulaire avec vos coordonnees pour generer la facture.",
            }
            response = form_msgs.get(language, form_msgs["es"])

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Build history that excludes previous completed orders.
    # Find the last "order completed" marker in messages and only use messages after it.
    all_messages = st.session_state.messages if st.session_state.messages else []
    
    # Find the index of the last order completion message
    last_order_complete_idx = -1
    order_complete_markers = ["factura ha sido generada", "invoice has been generated", "facture a été générée", "pdf", "descargar factura", "download invoice", "telecharger facture"]
    for i, msg in enumerate(all_messages):
        if msg["role"] == "assistant":
            content_lower = msg["content"].lower()
            if any(marker in content_lower for marker in order_complete_markers):
                last_order_complete_idx = i
    
    # Use only messages after the last completed order, limited to 6
    if last_order_complete_idx >= 0:
        relevant_messages = all_messages[last_order_complete_idx + 1:]
    else:
        relevant_messages = all_messages
    
    history = relevant_messages[-6:] if relevant_messages else []

    with st.spinner("Processing your order..."):
        # First, check if this is a multi-product order
        multi_products = extract_multi_order_products(prompt, history=history)
        
        if multi_products and len(multi_products) > 1:
            # This is a multi-product order — route to multi-order flow
            from app.multi_order_handlers import handle_multi_order_confirmed
            handle_multi_order_confirmed(prompt, multi_products)
            return

        # Single product order — extract which product and quantity
        order_info = extract_order_product(prompt, history=history)

    if not order_info:
        # Couldn't determine the product, ask for clarification in user's language
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer wants to order something but we couldn't identify which product. "
                    f"Their message was: \"{prompt}\"\n"
                    f"Ask them to specify the product name and quantity they want to order.\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                "I couldn't identify which product you'd like to order. "
                "Could you please tell me the product name and quantity?"
            )
        except Exception:
            response = sanitize_response(
                "I couldn't identify which product you'd like to order. "
                "Could you please tell me the product name and quantity?"
            )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Find ALL matching products in the database (all presentations, labs, dosages)
    product_name = order_info["product"]
    matches = find_matching_products(product_name)

    if not matches:
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer wants to order '{product_name}' but it was NOT found in our inventory. "
                    f"Their message was: \"{prompt}\"\n"
                    f"Inform them we don't have this product and ask if they'd like to try another product.\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                f"I couldn't find '{product_name}' in our inventory. "
                "Could you verify the name or ask about another product?"
            )
        except Exception:
            response = sanitize_response(
                f"I couldn't find '{product_name}' in our inventory. "
                "Could you verify the name or ask about another product?"
            )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Get ALL product details from DB (all presentations)
    try:
        conn = get_connection()
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(matches))
        cur.execute(
            f"""SELECT p.name, p.price, p.medication_dosage, p.dosage_form, 
                       p.laboratory, i.actual_stock
                FROM products p
                JOIN inventory i ON i.products_id = p.id
                WHERE p.name IN ({placeholders}) AND i.actual_stock > 0
                ORDER BY p.name, p.laboratory""",
            matches,
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()
        products_data = [dict(zip(columns, row)) for row in rows]
    except Exception:
        products_data = []

    # If the user specified a laboratory preference, filter to only that lab
    preferred_lab = order_info.get("laboratory")
    if preferred_lab and products_data:
        filtered_by_lab = [
            p for p in products_data
            if preferred_lab.lower() in p.get("laboratory", "").lower()
        ]
        if filtered_by_lab:
            products_data = filtered_by_lab

    if not products_data:
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer wants to order '{product_name}' but it's currently out of stock. "
                    f"Their message was: \"{prompt}\"\n"
                    f"Inform them the product has no available stock and ask if they'd like another product.\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                f"'{product_name}' is currently out of stock. Would you like to ask about another product?"
            )
        except Exception:
            response = sanitize_response(
                f"'{product_name}' is currently out of stock. Would you like to ask about another product?"
            )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # If user already specified a laboratory and there's exactly 1 match, skip option selection
    # and go directly to data collection
    if preferred_lab and len(products_data) == 1:
        selected = products_data[0]
        quantity = order_info.get("quantity", 1)
        st.session_state.order_product = {
            "product": selected["name"],
            "quantity": quantity,
            "price": float(selected["price"]),
            "laboratory": selected.get("laboratory", "N/A"),
            "dosage": selected.get("medication_dosage", "N/A"),
        }
        st.session_state.order_flow = "awaiting_data"

        language = _detect_conversation_language()
        form_msgs = {
            "es": f"Perfecto, has seleccionado {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Por favor completa el formulario con tus datos para generar la factura.",
            "en": f"Great, you selected {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Please fill out the form with your details to generate the invoice.",
            "fr": f"Parfait, vous avez choisi {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Veuillez remplir le formulaire avec vos coordonnees pour generer la facture.",
        }
        response = form_msgs.get(language, form_msgs["es"])

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Show all options (even if only one) so the customer sees price before providing data
    st.session_state.order_product_options = products_data
    st.session_state.order_flow = "awaiting_product_selection"

    language = _detect_conversation_language()
    response = sanitize_response(
        generate_product_options_message(products_data, prompt, history=history, language=language)
    )

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_order_product_selection(prompt: str):
    """Handles when the user selects a product from the presented options."""
    history = st.session_state.messages[-6:] if st.session_state.messages else []
    options = st.session_state.order_product_options

    # Check if user wants ALL/BOTH options (e.g., "los 2 tramadoles", "ambos", "todos", "both")
    # In that case, convert to multi-order flow with all options selected
    if options and len(options) > 1:
        prompt_lower = prompt.lower()
        select_all_indicators = [
            "todos", "todas", "all of them", "want them all", "order them all",
            "ordenarlos todos", "ordenarlas todas", "quiero todos", "quiero todas",
            "los quiero todos", "las quiero todas", "one of each", "una de cada",
            "uno de cada", "each one", "cada uno", "cada una",
            "ambos", "ambas", "both",
        ]
        both_indicators = ["los 2", "los dos", "las 2", "las dos"]
        
        user_wants_all = any(indicator in prompt_lower for indicator in select_all_indicators)
        user_wants_both = len(options) == 2 and any(indicator in prompt_lower for indicator in both_indicators)

        if user_wants_all or user_wants_both:
            # Convert to multi-order: select all options with quantity 1 each
            all_products = []
            for opt in options:
                p = dict(opt)
                p["quantity"] = 1
                all_products.append(p)

            # Switch to multi-order flow
            st.session_state.order_product_options = None
            st.session_state.multi_order_products = all_products
            st.session_state.multi_order_pending_options = []
            st.session_state.order_flow = "multi_awaiting_data"

            # Tell user to fill the form
            language = _detect_conversation_language()
            total = sum(float(p["price"]) * p["quantity"] for p in all_products)
            form_msgs = {
                "es": f"Todos los productos confirmados. Total: {total:,.2f} COP. Por favor completa el formulario con tus datos para generar la factura.",
                "en": f"All products confirmed. Total: {total:,.2f} COP. Please fill out the form with your details to generate the invoice.",
                "fr": f"Tous les produits confirmes. Total: {total:,.2f} COP. Veuillez remplir le formulaire avec vos coordonnees pour generer la facture.",
            }
            response = form_msgs.get(language, form_msgs["es"])

            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.user and st.session_state.current_conversation_id:
                save_message(st.session_state.current_conversation_id, "assistant", response)
            return

    with st.spinner("Processing your selection..."):
        selection = parse_product_selection(prompt, history=history)

    options = st.session_state.order_product_options

    if not selection or not options:
        # Check if the user is asking to see the options again
        options_request_indicators = ["que opciones", "what options", "cuales", "which", "show me", "muestrame", "opciones hay", "quelles options", "les options"]
        is_asking_options = any(indicator in prompt.lower() for indicator in options_request_indicators)

        if is_asking_options and options:
            # Re-show the product options
            history_for_lang = st.session_state.messages[-6:] if st.session_state.messages else []
            language = _detect_conversation_language()
            response = sanitize_response(
                generate_product_options_message(options, prompt, history=history_for_lang, language=language)
            )
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.user and st.session_state.current_conversation_id:
                save_message(st.session_state.current_conversation_id, "assistant", response)
            return

        # Check if the user wants to cancel the order
        cancel_indicators = ["cancelar", "cancel", "no quiero", "nevermind", "no thanks", "no gracias"]
        is_cancel = any(indicator in prompt.lower() for indicator in cancel_indicators)

        if is_cancel:
            # Exit order flow and process as a normal query
            st.session_state.order_flow = None
            st.session_state.order_product_options = None
            with st.spinner("Understanding your question..."):
                try:
                    intent = classify_intent(prompt)
                except Exception as e:
                    st.error(f"Error classifying your question: {e}")
                    return

            if intent == "CONVERSATIONAL":
                from app.chat_handlers import handle_conversational
                handle_conversational(prompt)
            else:
                from app.chat_handlers import handle_database_query
                handle_database_query(prompt)
            return

        # Not a cancel and not asking for options — just couldn't parse the selection. Ask again in user's language.
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback_response = generate_content(
                contents=(
                    f"The customer said: \"{prompt}\"\n"
                    f"We need them to select from the product options previously shown. "
                    f"Ask them politely to indicate which option number they want "
                    f"(e.g., 'option 1' or 'I want the Genfar one').\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            if fallback_response:
                response = sanitize_response(fallback_response.strip())
            else:
                response = sanitize_response(
                    "Could you please indicate which option you'd like? "
                    "You can say the option number (e.g., 'option 1') or mention the laboratory name."
                )
        except Exception:
            response = sanitize_response(
                "Could you please indicate which option you'd like? "
                "You can say the option number (e.g., 'option 1') or mention the laboratory name."
            )

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    idx = selection["selection"] - 1  # Convert to 0-based
    quantity = selection["quantity"]

    if idx < 0 or idx >= len(options):
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback_response = generate_content(
                contents=(
                    f"The customer selected option number {selection['selection']}, but we only have {len(options)} options. "
                    f"Ask them to choose a valid number between 1 and {len(options)}.\n"
                    f"Customer's message was: \"{prompt}\"\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            if fallback_response:
                response = sanitize_response(fallback_response.strip())
            else:
                response = sanitize_response(
                    f"The selected option is not valid. Please choose a number between 1 and {len(options)}."
                )
        except Exception:
            response = sanitize_response(
                f"The selected option is not valid. Please choose a number between 1 and {len(options)}."
            )

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    selected = options[idx]

    # Store selected product and move to data collection
    st.session_state.order_product = {
        "product": selected["name"],
        "quantity": quantity,
        "price": float(selected["price"]),
        "laboratory": selected.get("laboratory", "N/A"),
        "dosage": selected.get("medication_dosage", "N/A"),
    }
    st.session_state.order_product_options = None
    st.session_state.order_flow = "awaiting_data"

    # Tell user to fill the form
    language = _detect_conversation_language()
    form_msgs = {
        "es": f"Perfecto, has seleccionado {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Por favor completa el formulario con tus datos para generar la factura.",
        "en": f"Great, you selected {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Please fill out the form with your details to generate the invoice.",
        "fr": f"Parfait, vous avez choisi {selected['name']} ({selected.get('laboratory', 'N/A')}) x{quantity}. Veuillez remplir le formulaire avec vos coordonnees pour generer la facture.",
    }
    response = form_msgs.get(language, form_msgs["es"])

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_order_data_received(prompt: str):
    """Handles when the user provides their personal data for the order."""
    # Check if the user wants to cancel the order
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it", "ya no quiero", "no, ya no"]
    if any(indicator in prompt.lower() for indicator in cancel_indicators):
        # User wants to cancel — exit order flow
        st.session_state.order_flow = None
        st.session_state.order_product = None
        st.session_state.order_product_options = None

        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            msg = generate_content(
                contents=f"The customer wants to cancel their order. Their message: \"{prompt}\". Acknowledge the cancellation politely and let them know they can order again anytime.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "Order cancelled. Let me know if you need anything else."
        except Exception:
            response = "Order cancelled. Let me know if you need anything else."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    with st.spinner("Processing your information..."):
        customer_data = parse_customer_data(prompt)

    if not customer_data:
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer tried to provide their personal data but we couldn't parse it. "
                    f"Their message was: \"{prompt}\"\n"
                    f"Ask them to send the data again in this format: "
                    f"Name, Document type, Document number, Email, Address, City, Phone.\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                "I couldn't process your data. Please send it again in this format:\n\n"
                "Name, Document type, Document number, Email, Address, City, Phone"
            )
        except Exception:
            response = sanitize_response(
                "I couldn't process your data. Please send it again in this format:\n\n"
                "Name, Document type, Document number, Email, Address, City, Phone"
            )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Check for missing fields
    missing = customer_data.get("_missing", [])
    if missing:
        missing_labels = {
            "nombre": "Full name / Nombre completo",
            "cedula": "Document number / Numero de documento",
            "correo": "Email / Correo electronico",
            "direccion": "Address / Direccion",
            "ciudad": "City / Ciudad",
            "celular": "Phone / Celular",
        }
        missing_text = ", ".join(missing_labels.get(f, f) for f in missing)
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer provided their data but some fields are missing: {missing_text}. "
                    f"Their message was: \"{prompt}\"\n"
                    f"Ask them to provide the missing fields.\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                f"Some data is missing: {missing_text}. Please provide these to continue."
            )
        except Exception:
            response = sanitize_response(
                f"Some data is missing: {missing_text}. Please provide these to continue."
            )
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # All data collected - store and ask for confirmation
    customer_data.pop("_missing", None)
    st.session_state.order_customer_data = customer_data
    st.session_state.order_flow = "awaiting_confirmation"

    order_product = st.session_state.order_product
    history = st.session_state.messages[-8:] if st.session_state.messages else []
    language = _detect_conversation_language()
    response = sanitize_response(
        generate_data_confirmation_message(
            customer_data,
            order_product["product"],
            order_product["quantity"],
            order_product["price"],
            prompt,
            history=history,
            language=language,
        )
    )

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_order_data_confirmation(prompt: str):
    """Handles when the user confirms or denies their data is correct."""
    # Check if the user wants to cancel the order entirely
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it", "ya no quiero", "no, ya no"]
    if any(indicator in prompt.lower() for indicator in cancel_indicators):
        # User wants to cancel — exit order flow
        st.session_state.order_flow = None
        st.session_state.order_product = None
        st.session_state.order_product_options = None
        st.session_state.order_customer_data = None

        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            msg = generate_content(
                contents=f"The customer wants to cancel their order. Their message: \"{prompt}\". Acknowledge the cancellation politely and let them know they can order again anytime.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "Order cancelled. Let me know if you need anything else."
        except Exception:
            response = "Order cancelled. Let me know if you need anything else."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    confirmation = classify_data_confirmation(prompt)

    if confirmation == "DATA_NOT_CONFIRMED":
        # Reset to awaiting_data so the form re-opens for correction
        st.session_state.order_flow = "awaiting_data"
        st.session_state.order_customer_data = None
        language = _detect_conversation_language()
        form_msgs = {
            "es": "Entendido. Por favor corrige tus datos en el formulario que aparecera nuevamente.",
            "en": "Understood. Please correct your data in the form that will appear again.",
            "fr": "Compris. Veuillez corriger vos donnees dans le formulaire qui reapparaitra.",
        }
        response = form_msgs.get(language, form_msgs["es"])
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # DATA_CONFIRMED - Generate the PDF
    order_product = st.session_state.order_product
    customer_data = st.session_state.order_customer_data

    # Detect language from the conversation for the PDF
    language = _detect_conversation_language()

    with st.spinner("Generating your invoice..."):
        products_for_pdf = [
            {
                "nombre": order_product["product"],
                "cantidad": order_product["quantity"],
                "precio_unitario": order_product["price"],
                "subtotal": order_product["price"] * order_product["quantity"],
                "laboratorio": order_product.get("laboratory", "N/A"),
                "dosis": order_product.get("dosage", "N/A"),
            }
        ]

        pdf_bytes = generate_invoice_pdf(
            customer_data=customer_data,
            products=products_for_pdf,
            language=language,
        )

    # Send invoice via email using AWS SES
    total = order_product["price"] * order_product["quantity"]
    email_result = send_invoice_email(
        recipient_email=customer_data.get("correo", ""),
        customer_name=customer_data.get("nombre", "Customer"),
        pdf_bytes=pdf_bytes,
        pdf_filename=f"factura_{customer_data.get('cedula', 'order')}.pdf",
        order_summary={
            "product": order_product["product"],
            "quantity": order_product["quantity"],
            "total": total,
        },
        language=language,
    )

    if email_result["success"]:
        print(f"[order_flow] Invoice email sent to {customer_data.get('correo')}")
    else:
        print(f"[order_flow] Failed to send email: {email_result.get('error')}")

    # Generate success message in user's language
    from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION

    # Use deterministic language detection
    lang_instruction = {
        "en": "You MUST respond ENTIRELY in English.",
        "fr": "You MUST respond ENTIRELY in French.",
        "es": "You MUST respond ENTIRELY in Spanish.",
    }.get(language, "You MUST respond ENTIRELY in Spanish.")

    try:
        success_msg = generate_content(
            contents=(
                f"The customer's invoice has been generated successfully.\n"
                f"Order summary:\n"
                f"- Product: {order_product['product']}\n"
                f"- Quantity: {order_product['quantity']}\n"
                f"- Total: {total:,.2f} COP\n"
                f"- Email: {customer_data.get('correo', 'N/A')}\n\n"
                f"Tell them their invoice is ready, show the summary, mention they can download it with the button below, "
                f"and that a copy will be sent to their email.\n"
                f"LANGUAGE INSTRUCTION: {lang_instruction}"
            ),
            system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
        response = sanitize_response(success_msg.strip()) if success_msg else sanitize_response(
            f"Your invoice has been generated successfully.\n\n"
            f"Order summary:\n"
            f"Product: {order_product['product']}\n"
            f"Quantity: {order_product['quantity']}\n"
            f"Total: {total:,.2f} COP\n\n"
            f"You can download your invoice with the button below. "
            f"A copy will also be sent to: {customer_data.get('correo', 'N/A')}"
        )
    except Exception:
        response = sanitize_response(
            f"Your invoice has been generated successfully.\n\n"
            f"Order summary:\n"
            f"Product: {order_product['product']}\n"
            f"Quantity: {order_product['quantity']}\n"
            f"Total: {total:,.2f} COP\n\n"
            f"You can download your invoice with the button below. "
            f"A copy will also be sent to: {customer_data.get('correo', 'N/A')}"
        )

    with st.chat_message("assistant"):
        st.markdown(response)
        st.download_button(
            label="📄 Download Invoice PDF" if language == "en" else ("📄 Telecharger Facture PDF" if language == "fr" else "📄 Descargar Factura PDF"),
            data=pdf_bytes,
            file_name=f"factura_{customer_data.get('cedula', 'order')}.pdf",
            mime="application/pdf",
            key=f"download_invoice_{uuid.uuid4().hex[:8]}",
        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "pdf_bytes": pdf_bytes,
        "pdf_filename": f"factura_{customer_data.get('cedula', 'order')}.pdf",
    })
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)

    # Reset order flow state
    st.session_state.order_flow = None
    st.session_state.order_product = None
    st.session_state.order_customer_data = None
    st.session_state.order_product_options = None


# ============================================================
