import streamlit as st
import uuid

from app.services.ai_service import (
    classify_data_confirmation,
    generate_multi_order_summary,
    parse_multi_order_selection,
    parse_customer_data,
)
from app.services.db_service import find_matching_products, get_connection
from app.services.auth_service import save_message
from app.services.pdf_service import generate_invoice_pdf
from app.services.email_service import send_invoice_email
from app.ui_components import sanitize_response, _detect_conversation_language


# MULTI-PRODUCT ORDER FLOW
# ============================================================

def handle_multi_order_confirmed(prompt: str, multi_products: list[dict]):
    """Handles a multi-product order request. Searches all products, shows summary with budget."""
    language = _detect_conversation_language()

    products_found = []  # Products with exactly 1 match (confirmed)
    products_not_found = []  # Product names not found in DB
    products_with_options = []  # Products with multiple presentations needing selection

    for item in multi_products:
        product_name = item["product"]
        quantity = item.get("quantity", 1)
        preferred_lab = item.get("laboratory")

        matches = find_matching_products(product_name)

        if not matches:
            products_not_found.append(product_name)
            continue

        # Get product details from DB
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
            product_options = [dict(zip(columns, row)) for row in rows]
        except Exception:
            product_options = []

        if not product_options:
            products_not_found.append(product_name)
            continue

        # Filter by preferred lab if specified
        if preferred_lab:
            filtered = [p for p in product_options if preferred_lab.lower() in p.get("laboratory", "").lower()]
            if filtered:
                product_options = filtered

        if len(product_options) == 1:
            # Exactly 1 option — confirmed
            p = product_options[0]
            p["quantity"] = quantity
            products_found.append(p)
        else:
            # Multiple options — need user selection
            products_with_options.append({
                "search_term": product_name,
                "quantity": quantity,
                "options": product_options,
            })

    # Store state
    st.session_state.multi_order_products = products_found
    st.session_state.multi_order_pending_options = products_with_options

    if products_with_options:
        # Need user to select options for some products
        st.session_state.order_flow = "multi_awaiting_selection"
    else:
        # All products confirmed — go to data collection
        st.session_state.order_flow = "multi_awaiting_data"

    # Generate summary message
    response = sanitize_response(
        generate_multi_order_summary(products_found, products_not_found, products_with_options, prompt, language=language)
    )

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_multi_order_selection(prompt: str):
    """Handles when the user selects options for products with multiple presentations in a multi-order."""
    # Check if the user wants to cancel
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it", "ya no quiero", "no, ya no"]
    if any(indicator in prompt.lower() for indicator in cancel_indicators):
        st.session_state.order_flow = None
        st.session_state.multi_order_products = None
        st.session_state.multi_order_pending_options = None
        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            msg = generate_content(
                contents=f"The customer wants to cancel their order. Acknowledge politely.\nLANGUAGE INSTRUCTION: {lang_instruction}",
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

    history = st.session_state.messages[-6:] if st.session_state.messages else []
    pending = st.session_state.multi_order_pending_options

    if not pending:
        # No pending selections, move to data collection
        st.session_state.order_flow = "multi_awaiting_data"
        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            msg = generate_content(
                contents=f"All products are confirmed. Ask the customer for their personal data to generate the invoice.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "All products confirmed. Please provide your personal data."
        except Exception:
            response = "All products confirmed. Please provide your personal data."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Quick check: if the user wants ALL options for ALL pending products
    # (e.g., "todos", "all", "ordenarlos todos", "quiero todos", "los quiero todos", "want them all")
    select_all_indicators = [
        "todos", "todas", "all of them", "want them all", "order them all",
        "ordenarlos todos", "ordenarlas todas", "quiero todos", "quiero todas",
        "los quiero todos", "las quiero todas", "one of each", "una de cada",
        "uno de cada", "each one", "cada uno", "cada una",
    ]
    prompt_lower = prompt.lower()
    user_wants_all = any(indicator in prompt_lower for indicator in select_all_indicators)

    # Also detect "los 2" / "los dos" / "ambos" / "both" when there's only 1 pending product with 2 options
    both_indicators = ["ambos", "both", "los 2", "los dos", "las 2", "las dos"]
    user_wants_both = any(indicator in prompt_lower for indicator in both_indicators)

    if user_wants_all or (user_wants_both and len(pending) == 1 and len(pending[0].get("options", [])) == 2):
        # Automatically select ALL options for ALL pending products
        confirmed = st.session_state.multi_order_products or []
        for item in pending:
            for opt in item["options"]:
                chosen = dict(opt)
                chosen["quantity"] = item.get("quantity", 1)
                # Avoid duplicates
                is_duplicate = any(
                    c.get("name") == chosen.get("name") and c.get("laboratory") == chosen.get("laboratory")
                    for c in confirmed
                )
                if not is_duplicate:
                    confirmed.append(chosen)

        st.session_state.multi_order_products = confirmed
        st.session_state.multi_order_pending_options = []

        # All confirmed — ask for data
        st.session_state.order_flow = "multi_awaiting_data"
        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")

        total = sum(float(p["price"]) * p["quantity"] for p in confirmed)
        products_summary = "\n".join(f"- {p['name']} ({p.get('laboratory', '')}) x{p['quantity']} = {float(p['price']) * p['quantity']:,.2f} COP" for p in confirmed)

        try:
            msg = generate_content(
                contents=(
                    f"All products are confirmed for the order:\n{products_summary}\n"
                    f"Grand Total: {total:,.2f} COP\n\n"
                    f"Now ask the customer for their personal data to generate the invoice "
                    f"(full name, document type, document number, email, address, city, phone).\n"
                    f"LANGUAGE INSTRUCTION: {lang_instruction}"
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "All products confirmed. Please provide your personal data."
        except Exception:
            response = f"Order confirmed. Total: {total:,.2f} COP. Please provide your personal data."

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Parse user's selections
    with st.spinner("Processing your selections..."):
        selections = parse_multi_order_selection(prompt, history=history)

    # Fallback: if model couldn't parse but user mentions a lab name or product name 
    # that matches pending options, try to resolve directly
    if not selections and pending:
        prompt_lower = prompt.lower()
        fallback_selections = []
        for item in pending:
            matched = False
            for i, opt in enumerate(item["options"]):
                lab = opt.get("laboratory", "").lower()
                opt_name = opt.get("name", "").lower()
                # Match by laboratory name mentioned in user's message
                if lab and lab in prompt_lower:
                    fallback_selections.append({
                        "product": item["search_term"].lower(),
                        "selection": i + 1,
                        "quantity": item["quantity"],
                    })
                    matched = True
                    break
            if not matched:
                # Try matching by product name in the user's message
                for i, opt in enumerate(item["options"]):
                    opt_name = opt.get("name", "").lower()
                    if opt_name and opt_name in prompt_lower:
                        fallback_selections.append({
                            "product": item["search_term"].lower(),
                            "selection": i + 1,
                            "quantity": item["quantity"],
                        })
                        matched = True
                        break
            if not matched:
                # Try cross-language: use find_matching_products on words from the prompt
                # to see if any resolve to an option name
                prompt_words = [w for w in prompt_lower.split() if len(w) >= 4]
                for pw in prompt_words:
                    try:
                        fuzzy = find_matching_products(pw)
                        if fuzzy:
                            for i, opt in enumerate(item["options"]):
                                if opt.get("name", "") in fuzzy:
                                    fallback_selections.append({
                                        "product": item["search_term"].lower(),
                                        "selection": i + 1,
                                        "quantity": item["quantity"],
                                    })
                                    matched = True
                                    break
                    except Exception:
                        pass
                    if matched:
                        break
        if fallback_selections:
            selections = fallback_selections

    if not selections:
        # Additional fallback: if user typed just a number and there's only one pending item,
        # treat it as the option number for that item
        prompt_stripped = prompt.strip()
        if pending and prompt_stripped.isdigit():
            num = int(prompt_stripped)
            if len(pending) == 1 and 1 <= num <= len(pending[0]["options"]):
                selections = [{
                    "product": pending[0]["search_term"].lower(),
                    "selection": num,
                    "quantity": pending[0]["quantity"],
                }]

    if not selections:
        # Couldn't parse — ask again
        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            msg = generate_content(
                contents=f"The customer needs to select options for products with multiple presentations. Ask them to specify which option they want for each product (by number or laboratory name).\nCustomer said: \"{prompt}\"\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "Could you please specify which option you'd like for each product?"
        except Exception:
            response = "Could you please specify which option you'd like for each product?"
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Apply selections — now supports multiple selections per product
    confirmed = st.session_state.multi_order_products or []
    still_pending = []

    for item in pending:
        search_lower = item["search_term"].lower().strip()
        # Find all selections that match this pending product.
        # We check against the search_term AND the actual option names in the DB.
        matching_selections = []
        
        # Collect the actual product names from this item's options for matching
        option_names_lower = [opt.get("name", "").lower() for opt in item.get("options", [])]
        
        for s in selections:
            s_product = s["product"].lower().strip()
            
            # Match strategies (from most to least specific):
            # 1. Exact match with search term
            if s_product == search_lower:
                matching_selections.append(s)
                continue
            # 2. Selection product name matches one of the actual option names (exact or substring)
            if any(s_product in opt_name or opt_name in s_product for opt_name in option_names_lower if opt_name):
                matching_selections.append(s)
                continue
            # 3. Selection product is contained in search term or vice versa
            if s_product in search_lower or search_lower in s_product:
                matching_selections.append(s)
                continue
            # 4. They share a significant common word (>= 4 chars)
            s_words = set(w for w in s_product.split() if len(w) >= 4)
            search_words = set(w for w in search_lower.split() if len(w) >= 4)
            common_words = s_words & search_words
            if common_words:
                matching_selections.append(s)
                continue
            # 5. Cross-language fuzzy match: use find_matching_products to check if 
            #    the selection product name resolves to any of the option names
            try:
                fuzzy_matches = find_matching_products(s_product)
                if fuzzy_matches and any(fm.lower() in option_names_lower for fm in fuzzy_matches):
                    matching_selections.append(s)
                    continue
            except Exception:
                pass

        if matching_selections:
            for sel in matching_selections:
                idx = sel["selection"] - 1
                qty = sel.get("quantity", item["quantity"])
                if 0 <= idx < len(item["options"]):
                    chosen = dict(item["options"][idx])  # Copy to avoid mutation
                    chosen["quantity"] = qty
                    # Avoid adding duplicates (same product name + lab already in confirmed)
                    is_duplicate = any(
                        c.get("name") == chosen.get("name") and c.get("laboratory") == chosen.get("laboratory")
                        for c in confirmed
                    )
                    if not is_duplicate:
                        confirmed.append(chosen)
            # Product resolved — don't add to still_pending
        else:
            # No selection found for this product
            still_pending.append(item)

    st.session_state.multi_order_products = confirmed
    st.session_state.multi_order_pending_options = still_pending

    if still_pending:
        # Still have pending selections — show remaining options
        language = _detect_conversation_language()
        response = sanitize_response(
            generate_multi_order_summary(confirmed, [], still_pending, prompt, language=language)
        )
    else:
        # All confirmed — ask for data
        st.session_state.order_flow = "multi_awaiting_data"
        language = _detect_conversation_language()
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")

        # Build order summary for the data request
        total = sum(float(p["price"]) * p["quantity"] for p in confirmed)
        products_summary = "\n".join(f"- {p['name']} ({p.get('laboratory', '')}) x{p['quantity']} = {float(p['price']) * p['quantity']:,.2f} COP" for p in confirmed)

        try:
            msg = generate_content(
                contents=(
                    f"All products are confirmed for the order:\n{products_summary}\n"
                    f"Grand Total: {total:,.2f} COP\n\n"
                    f"Now ask the customer for their personal data to generate the invoice "
                    f"(full name, document type, document number, email, address, city, phone).\n"
                    f"LANGUAGE INSTRUCTION: {lang_instruction}"
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(msg.strip()) if msg else "All products confirmed. Please provide your personal data."
        except Exception:
            response = f"Order confirmed. Total: {total:,.2f} COP. Please provide your personal data."

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_multi_order_data_received(prompt: str):
    """Handles when the user provides their personal data for a multi-product order."""
    # Check if the user wants to cancel the order
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it", "ya no quiero", "no, ya no"]
    if any(indicator in prompt.lower() for indicator in cancel_indicators):
        # User wants to cancel — exit multi-order flow
        st.session_state.order_flow = None
        st.session_state.multi_order_products = None
        st.session_state.multi_order_pending_options = None
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

    with st.spinner("Processing your information..."):
        customer_data = parse_customer_data(prompt)

    if not customer_data:
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        language = _detect_conversation_language()
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            fallback = generate_content(
                contents=f"The customer tried to provide their personal data but we couldn't parse it. Ask them to send it again in format: Name, Document type, Document number, Email, Address, City, Phone.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else "I couldn't process your data. Please send it again."
        except Exception:
            response = "I couldn't process your data. Please send it again in format: Name, Document type, Document number, Email, Address, City, Phone."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # Check for missing fields
    missing = customer_data.get("_missing", [])
    if missing:
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        language = _detect_conversation_language()
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        missing_text = ", ".join(missing)
        try:
            fallback = generate_content(
                contents=f"Some fields are missing: {missing_text}. Ask the customer to provide them.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else f"Missing data: {missing_text}. Please provide these."
        except Exception:
            response = f"Missing data: {missing_text}. Please provide these to continue."
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    # All data collected — show confirmation
    customer_data.pop("_missing", None)
    st.session_state.order_customer_data = customer_data
    st.session_state.order_flow = "multi_awaiting_confirmation"

    # Build confirmation message with all products
    products = st.session_state.multi_order_products
    total = sum(float(p["price"]) * p["quantity"] for p in products)
    language = _detect_conversation_language()

    from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
    lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")

    products_summary = "\n".join(
        f"- {p['name']} ({p.get('laboratory', 'N/A')}) x{p['quantity']} - Unit: {float(p['price']):,.2f} COP - Subtotal: {float(p['price']) * p['quantity']:,.2f} COP"
        for p in products
    )

    try:
        msg = generate_content(
            contents=(
                f"Customer data:\n"
                f"- Name: {customer_data.get('nombre', 'N/A')}\n"
                f"- Document: {customer_data.get('tipo_documento', 'N/A')} {customer_data.get('cedula', 'N/A')}\n"
                f"- Email: {customer_data.get('correo', 'N/A')}\n"
                f"- Address: {customer_data.get('direccion', 'N/A')}, {customer_data.get('ciudad', 'N/A')}\n"
                f"- Phone: {customer_data.get('celular', 'N/A')}\n\n"
                f"Products:\n{products_summary}\n\n"
                f"Grand Total: {total:,.2f} COP\n\n"
                f"Present all this data to the customer and ask if everything is correct.\n"
                f"LANGUAGE INSTRUCTION: {lang_instruction}"
            ),
            system_prompt="You are a friendly pharmacy assistant confirming a multi-product order. Show all customer data and all products with prices. Ask if everything is correct. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
        )
        response = sanitize_response(msg.strip()) if msg else f"Order total: {total:,.2f} COP. Is everything correct?"
    except Exception:
        response = f"Order total: {total:,.2f} COP. Is everything correct?"

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_multi_order_data_confirmation(prompt: str):
    """Handles when the user confirms or denies their data for a multi-product order."""
    # Check if the user wants to cancel the order entirely
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it", "ya no quiero", "no, ya no"]
    if any(indicator in prompt.lower() for indicator in cancel_indicators):
        # User wants to cancel — exit multi-order flow
        st.session_state.order_flow = None
        st.session_state.multi_order_products = None
        st.session_state.multi_order_pending_options = None
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
        st.session_state.order_flow = "multi_awaiting_data"
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

    # DATA_CONFIRMED — Generate the PDF with all products
    products = st.session_state.multi_order_products
    customer_data = st.session_state.order_customer_data
    language = _detect_conversation_language()

    with st.spinner("Generating your invoice..."):
        products_for_pdf = [
            {
                "nombre": p["name"],
                "cantidad": p["quantity"],
                "precio_unitario": float(p["price"]),
                "subtotal": float(p["price"]) * p["quantity"],
                "laboratorio": p.get("laboratory", "N/A"),
                "dosis": p.get("dosage", p.get("medication_dosage", "N/A")),
            }
            for p in products
        ]

        pdf_bytes = generate_invoice_pdf(
            customer_data=customer_data,
            products=products_for_pdf,
            language=language,
        )

    # Send invoice via email
    total = sum(float(p["price"]) * p["quantity"] for p in products)
    products_names = ", ".join(p["name"] for p in products)

    email_result = send_invoice_email(
        recipient_email=customer_data.get("correo", ""),
        customer_name=customer_data.get("nombre", "Customer"),
        pdf_bytes=pdf_bytes,
        pdf_filename=f"factura_{customer_data.get('cedula', 'order')}.pdf",
        order_summary={
            "product": products_names,
            "quantity": sum(p["quantity"] for p in products),
            "total": total,
        },
        language=language,
    )

    if email_result["success"]:
        print(f"[multi_order_flow] Invoice email sent to {customer_data.get('correo')}")
    else:
        print(f"[multi_order_flow] Failed to send email: {email_result.get('error')}")

    # Generate success message
    from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
    lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")

    products_summary = "\n".join(f"- {p['name']} x{p['quantity']}: {float(p['price']) * p['quantity']:,.2f} COP" for p in products)

    try:
        success_msg = generate_content(
            contents=(
                f"The customer's invoice has been generated successfully for a multi-product order.\n"
                f"Order summary:\n{products_summary}\n"
                f"Grand Total: {total:,.2f} COP\n"
                f"Email: {customer_data.get('correo', 'N/A')}\n\n"
                f"Tell them their invoice is ready, show the full summary with all products, "
                f"mention they can download it with the button below, and a copy will be sent to their email.\n"
                f"LANGUAGE INSTRUCTION: {lang_instruction}"
            ),
            system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
            temperature=0.7,
            max_completion_tokens=400,
        )
        response = sanitize_response(success_msg.strip()) if success_msg else f"Invoice generated. Total: {total:,.2f} COP"
    except Exception:
        response = sanitize_response(f"Invoice generated successfully.\n\n{products_summary}\n\nTotal: {total:,.2f} COP\n\nDownload below. Copy sent to: {customer_data.get('correo', 'N/A')}")

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

    # Reset all order flow state
    st.session_state.order_flow = None
    st.session_state.order_product = None
    st.session_state.order_customer_data = None
    st.session_state.order_product_options = None
    st.session_state.multi_order_products = None
    st.session_state.multi_order_pending_options = None


