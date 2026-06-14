import streamlit as st
import pandas as pd
import base64

from app.services.ai_service import (
    classify_intent,
    generate_conversational_with_products,
    generate_symptom_sql,
    extract_product_term,
    generate_sql,
    classify_chart_type,
    summarize_query_results,
    analyze_image,
    generate_image_recommendation,
    analyze_multiple_images,
    generate_multi_image_recommendation,
    validate_sql,
    classify_order_intent,
    extract_multi_order_products,
    extract_order_product,
)
from app.services.db_service import execute_query, find_matching_products, get_connection
from app.services.auth_service import (
    create_conversation,
    update_conversation_title,
    save_message,
)
from app.services.report_pdf_service import generate_report_pdf
from app.services.report_email_service import send_report_email
from app.ui_components import render_chart, sanitize_response, _detect_conversation_language


def handle_conversational(prompt: str):
    """Handles conversational questions: responds with natural language + recommends products from the DB."""
    with st.chat_message("assistant"):
        with st.spinner("Searching for recommendations..."):
            products_data = []
            try:
                symptom_sql = generate_symptom_sql(prompt)
                is_valid, _ = validate_sql(symptom_sql)
                if is_valid:
                    columns, rows = execute_query(symptom_sql)
                    if rows:
                        products_data = [dict(zip(columns, row)) for row in rows]
            except Exception:
                pass

            # Pass recent conversation history for context
            history = st.session_state.messages[-6:] if st.session_state.messages else []
            response = sanitize_response(generate_conversational_with_products(prompt, products_data, history=history))

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_results = None

    # Persist response in DB
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_image_query(image_bytes: bytes, user_text: str):
    """Handles image-based queries: identifies medication and recommends products."""
    # If user is logged in, create conversation if it doesn't exist
    if st.session_state.user and not st.session_state.current_conversation_id:
        conv_id = create_conversation(st.session_state.user["id"])
        st.session_state.current_conversation_id = conv_id

    # Save user message with image
    display_text = user_text if user_text else "📷 [Image uploaded]"
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    st.session_state.messages.append({"role": "user", "content": display_text, "image": image_bytes})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "user", display_text, image=image_b64)

    with st.chat_message("user"):
        st.markdown(display_text)
        st.image(image_bytes, width=250)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing image..."):
            # Step 1: Encode image to base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Step 2: Analyze the image to identify the medication
            image_analysis = analyze_image(image_base64, user_text)
            print(f"[DEBUG handle_image_query] image_analysis = '{image_analysis}'")

            if image_analysis is None or image_analysis == "NOT_MEDICATION":
                response = "I couldn't identify a medication in the image. Please try uploading a clearer photo of the medication packaging, or describe what you need help with."
                st.markdown(response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": response}
                )
                if st.session_state.user and st.session_state.current_conversation_id:
                    save_message(
                        st.session_state.current_conversation_id, "assistant", response
                    )
                return

            # Step 3: Search for matching products in our DB
            products_data = []
            try:
                # Extract the drug name from the analysis.
                # Format: "Drug Name 400mg tablets by Bayer" or "Drug Name | dosage | form | lab"
                import re

                if "|" in image_analysis:
                    drug_name = image_analysis.split("|")[0].strip()
                else:
                    # Clean punctuation that might interfere with parsing
                    analysis_clean = re.sub(r'[(),\[\]{}"\'`]', ' ', image_analysis)
                    analysis_lower = analysis_clean.lower().strip()
                    noise_words = ["tablets", "capsules", "units", "by", "from", "with",
                                   "sachet", "sachets", "syrup", "cream", "drops", "injection",
                                   "tabletas", "cápsulas", "unidades", "por", "de", "con",
                                   "mg", "ml", "iu", "mcg", "g", "forte", "containing",
                                   "box", "pack", "package", "blister", "bottle", "over",
                                   "the", "counter", "supplement", "dietary"]
                    words = analysis_lower.split()
                    name_parts = []
                    for w in words:
                        if any(ch.isdigit() for ch in w) or w in noise_words:
                            break
                        name_parts.append(w)
                    # Check if next word is a single letter (like "C" in "Vitamin C")
                    if name_parts and len(name_parts) < len(words):
                        next_w = words[len(name_parts)]
                        if len(next_w) == 1 and next_w.isalpha():
                            name_parts.append(next_w)
                    drug_name = " ".join(name_parts) if name_parts else image_analysis.split()[0]

                # Remove any trailing punctuation from drug_name
                drug_name = drug_name.strip(" .,;:-\"'`")
                print(f"[DEBUG handle_image_query] drug_name = '{drug_name}', search_terms will be built from this")

                # Build search terms: full name, cross-language variations, first word
                search_terms = [drug_name]
                drug_name_lower = drug_name.lower()
                if "vitamina" in drug_name_lower:
                    search_terms.append(drug_name_lower.replace("vitamina", "vitamin"))
                elif "vitamin" in drug_name_lower and "vitamina" not in drug_name_lower:
                    search_terms.append(drug_name_lower.replace("vitamin", "vitamina"))

                # If the extracted name has more than 2 words, also try just the first 2 words
                # This handles cases like "vitamin c ascorbic acid" where extra info was captured
                drug_words = drug_name.split()
                if len(drug_words) > 2:
                    short_name = " ".join(drug_words[:2])
                    search_terms.append(short_name)

                first_word = drug_words[0] if drug_words else ""
                if first_word and first_word != drug_name:
                    search_terms.append(first_word)

                for term in search_terms:
                    matches = find_matching_products(term)
                    if matches:
                        placeholders = ",".join([f"'{m}'" for m in matches])
                        sql = f"""
                            SELECT p.name, p.medication_dosage, p.dosage_form, p.laboratory, 
                                   p.price, i.actual_stock, p.indication_and_symptoms
                            FROM products p
                            JOIN inventory i ON i.products_id = p.id
                            WHERE p.name IN ({placeholders}) AND i.actual_stock > 0
                        """
                        columns, rows = execute_query(sql)
                        if rows:
                            products_data = [
                                dict(zip(columns, row)) for row in rows
                            ]
                        break
            except Exception as e:
                print(f"[handle_image_query] Error searching products: {e}")
                pass

            # Step 4: Generate recommendation response
            language = _detect_conversation_language()
            response = sanitize_response(generate_image_recommendation(
                user_text, image_analysis, products_data, language=language
            ))

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)

    # Generate conversation title if first message
    if (
        st.session_state.user
        and st.session_state.current_conversation_id
        and len(st.session_state.messages) == 2
    ):
        title = (user_text[:50] if user_text else "Image analysis") + (
            "..." if len(user_text) > 50 else ""
        )
        update_conversation_title(st.session_state.current_conversation_id, title)


def handle_multi_image_query(images_list: list[bytes], user_text: str):
    """Handles multi-image queries: identifies medications in all images, searches DB, and integrates with multi-order flow."""
    # If user is logged in, create conversation if it doesn't exist
    if st.session_state.user and not st.session_state.current_conversation_id:
        conv_id = create_conversation(st.session_state.user["id"])
        st.session_state.current_conversation_id = conv_id

    # Save user message with first image as preview
    display_text = user_text if user_text else f"📷 [{len(images_list)} images uploaded]"
    st.session_state.messages.append({"role": "user", "content": display_text, "images": images_list})
    if st.session_state.user and st.session_state.current_conversation_id:
        # Save first image as reference
        image_b64 = base64.b64encode(images_list[0]).decode("utf-8")
        save_message(st.session_state.current_conversation_id, "user", display_text, image=image_b64)

    with st.chat_message("user"):
        st.markdown(display_text)
        # Show thumbnails of all uploaded images
        cols_per_row = min(len(images_list), 5)
        img_cols = st.columns(cols_per_row)
        for idx, img_bytes in enumerate(images_list[:cols_per_row]):
            with img_cols[idx]:
                st.image(img_bytes, width=120)
        if len(images_list) > 5:
            st.caption(f"+ {len(images_list) - 5} more images")

    with st.chat_message("assistant"):
        with st.spinner(f"Analyzing {len(images_list)} images..."):
            # Step 1: Encode all images to base64
            images_base64 = [base64.b64encode(img).decode("utf-8") for img in images_list]

            # Step 2: Analyze all images to identify medications
            image_analyses = analyze_multiple_images(images_base64, user_text)

            if not image_analyses:
                response = "I couldn't identify medications in the uploaded images. Please try uploading clearer photos of the medication packaging."
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                if st.session_state.user and st.session_state.current_conversation_id:
                    save_message(st.session_state.current_conversation_id, "assistant", response)
                return

            # Step 3: For each identified medication, search for matching products in DB
            products_by_image = []
            all_products_found = []  # For multi-order flow: products with exactly 1 match
            all_products_with_options = []  # Products with multiple options needing selection
            all_not_found = []  # Medications not found in DB

            for i, analysis in enumerate(image_analyses):
                if analysis.upper() == "NOT_MEDICATION":
                    products_by_image.append([])
                    continue

                # Extract the drug name from the analysis.
                # The analysis format is now: "Drug Name | dosage | form | laboratory"
                # OR legacy format: "Drug Name 400mg tablets by Bayer"
                products_data = []
                matched_product_name = None
                try:
                    # Try structured format first (pipe-separated)
                    if "|" in analysis:
                        drug_name = analysis.split("|")[0].strip()
                    else:
                        # Legacy format: extract words before first number/noise
                        import re
                        analysis_clean = re.sub(r'[(),\[\]{}"\'`]', ' ', analysis)
                        analysis_lower = analysis_clean.lower().strip()
                        noise_words = ["tablets", "capsules", "units", "by", "from", "with",
                                       "sachet", "sachets", "syrup", "cream", "drops", "injection",
                                       "tabletas", "cápsulas", "unidades", "por", "de", "con",
                                       "mg", "ml", "iu", "mcg", "g", "forte", "containing",
                                       "box", "pack", "package", "blister", "bottle", "over",
                                       "the", "counter", "supplement", "dietary"]
                        words = analysis_lower.split()
                        name_parts = []
                        for w in words:
                            if any(ch.isdigit() for ch in w) or w in noise_words:
                                break
                            name_parts.append(w)
                        # Check if next word is a single letter (like "C" in "Vitamin C")
                        if name_parts and len(name_parts) < len(words):
                            next_w = words[len(name_parts)]
                            if len(next_w) == 1 and next_w.isalpha():
                                name_parts.append(next_w)
                        drug_name = " ".join(name_parts) if name_parts else analysis.split()[0]

                    # Remove any trailing punctuation from drug_name
                    drug_name = drug_name.strip(" .,;:-\"'`")

                    # Build search terms with cross-language variations
                    search_terms = [drug_name]
                    if "vitamina" in drug_name.lower():
                        search_terms.append(drug_name.lower().replace("vitamina", "vitamin"))
                    elif "vitamin" in drug_name.lower() and "vitamina" not in drug_name.lower():
                        search_terms.append(drug_name.lower().replace("vitamin", "vitamina"))
                    # If name has more than 2 words, also try just the first 2
                    drug_words = drug_name.split()
                    if len(drug_words) > 2:
                        search_terms.append(" ".join(drug_words[:2]))
                    first_word = drug_words[0] if drug_words else ""
                    if first_word and first_word != drug_name:
                        search_terms.append(first_word)

                    for term in search_terms:
                        matches = find_matching_products(term)
                        if matches:
                            # If we searched with a multi-word term and got results,
                            # those results are already filtered. Use them directly.
                            placeholders = ",".join([f"'{m}'" for m in matches])
                            sql = f"""
                                SELECT p.name, p.medication_dosage, p.dosage_form, p.laboratory, 
                                       p.price, i.actual_stock, p.indication_and_symptoms
                                FROM products p
                                JOIN inventory i ON i.products_id = p.id
                                WHERE p.name IN ({placeholders}) AND i.actual_stock > 0
                            """
                            columns, rows = execute_query(sql)
                            if rows:
                                products_data = [dict(zip(columns, row)) for row in rows]
                                matched_product_name = matches[0] if len(matches) == 1 else drug_name
                            break
                except Exception:
                    pass

                products_by_image.append(products_data)

                # Categorize for multi-order flow
                if not products_data:
                    all_not_found.append(analysis)
                elif len(products_data) == 1:
                    # Exactly 1 match — confirmed product
                    p = dict(products_data[0])
                    p["quantity"] = 1
                    all_products_found.append(p)
                else:
                    # Multiple options — need user selection
                    # Use the clean matched product name for selection matching later
                    clean_search = matched_product_name if matched_product_name else drug_name
                    all_products_with_options.append({
                        "search_term": clean_search,
                        "quantity": 1,
                        "options": products_data,
                    })

            # Step 4: Generate recommendation response
            language = _detect_conversation_language()
            response = sanitize_response(generate_multi_image_recommendation(
                user_text, image_analyses, products_by_image, language=language
            ))

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)

    # Step 5: Set up multi-order flow state so the user can proceed to order
    # Only set up if we found at least some products
    if all_products_found or all_products_with_options:
        st.session_state.multi_order_products = all_products_found
        st.session_state.multi_order_pending_options = all_products_with_options if all_products_with_options else None

        if all_products_with_options:
            # Some products need selection — set state to await selection
            st.session_state.order_flow = "multi_awaiting_selection"
        # If all products are confirmed (no options), we don't auto-enter the order flow.
        # The user will say "yes I want to order" and the normal ORDER_CONFIRMED flow will handle it,
        # picking up the already-set multi_order_products state.

    # Generate conversation title if first message
    if (
        st.session_state.user
        and st.session_state.current_conversation_id
        and len(st.session_state.messages) == 2
    ):
        title = (user_text[:50] if user_text else f"Multi-image analysis ({len(images_list)} images)") + (
            "..." if len(user_text) > 50 else ""
        )
        update_conversation_title(st.session_state.current_conversation_id, title)


def handle_product_not_found(prompt: str, product_term: str):
    """Handles the case when a product is not found — uses AI to respond in the user's language and suggest alternatives."""
    from app.services.ai_service import generate_conversational_with_products

    with st.chat_message("assistant"):
        with st.spinner("Searching for alternatives..."):
            # Try to find similar products to suggest
            similar_products = []
            try:
                # Search with a very short prefix to find anything related
                conn = get_connection()
                cur = conn.cursor()
                # Get a few products from the same general category
                prefix = product_term.lower()[:3] if len(product_term) >= 3 else product_term.lower()
                cur.execute(
                    """SELECT p.name, p.price, p.medication_dosage, p.dosage_form, p.laboratory, 
                              p.indication_and_symptoms, i.actual_stock
                       FROM products p
                       JOIN inventory i ON i.products_id = p.id
                       WHERE i.actual_stock > 0
                       ORDER BY p.name
                       LIMIT 5""",
                )
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                if rows:
                    similar_products = [dict(zip(columns, row)) for row in rows]
                cur.close()
                conn.close()
            except Exception:
                pass

            # Generate a response that explains the product wasn't found and suggests alternatives
            not_found_prompt = f"{prompt}\n\n[NOTE: The product '{product_term}' was NOT found in our inventory. Inform the user we don't carry this specific product and suggest they check with us for alternatives or similar products.]"
            history = st.session_state.messages[-4:] if st.session_state.messages else []
            response = sanitize_response(generate_conversational_with_products(not_found_prompt, [], history=history))

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_database_query(prompt: str):
    """Handles questions that require a database query."""
    with st.spinner("Analyzing your question..."):
        try:
            # Include recent history so the AI can resolve references like "it", "the first one"
            history = st.session_state.messages[-4:] if st.session_state.messages else []
            history_context = ""
            if history:
                history_lines = [f"{'Customer' if m['role'] == 'user' else 'Assistant'}: {m['content'][:150]}" for m in history]
                history_context = "\n\nRecent conversation:\n" + "\n".join(history_lines)

            product_term = extract_product_term(prompt + history_context)
        except Exception as e:
            st.error(f"Error analyzing your question: {e}")
            return

    selected_product = None

    if product_term:
        # Check if multiple products are mentioned (separated by |)
        if "|" in product_term:
            product_terms = [t.strip() for t in product_term.split("|") if t.strip()]
            all_matched = []
            not_found = []
            for term in product_terms:
                matches = find_matching_products(term)
                if matches:
                    all_matched.append(matches[0])
                else:
                    not_found.append(term)

            if not_found:
                for term in not_found:
                    st.warning(f"No products found matching '{term}'.")

            if not all_matched:
                # Use AI to respond about not finding products and suggest alternatives
                handle_product_not_found(prompt, product_term)
                return

            # Pass all matched products to SQL generation
            selected_product = ", ".join(all_matched)
            st.info(f"Products identified: **{selected_product}**")
        else:
            matches = find_matching_products(product_term)

            if len(matches) == 0:
                # Use AI to respond about not finding the product and suggest alternatives
                handle_product_not_found(prompt, product_term)
                return
            elif len(matches) == 1:
                selected_product = matches[0]
                st.info(f"Product identified: **{selected_product}**")
            else:
                st.info(f"Multiple products found for '{product_term}':")
                selected_product = st.radio(
                    "Which product would you like to know about?",
                    options=matches,
                    key="product_selection",
                )
                if not st.button("Continue", key="btn_continue"):
                    return

    with st.spinner("Generating query..."):
        try:
            history = st.session_state.messages[-4:] if st.session_state.messages else []
            sql = generate_sql(prompt, selected_product, history=history)
        except Exception as e:
            st.error(f"Error generating SQL query: {e}")
            return

    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        msg = f"⚠️ The generated query was rejected for safety: {error_msg}"
        st.error(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})
        return

    st.code(sql, language="sql")

    columns, rows = [], []
    response_text = ""
    chart_type = "NONE"

    with st.spinner("Running query..."):
        try:
            columns, rows = execute_query(sql)
        except Exception as e:
            st.error(f"Error running query: {e}")
            response_text = f"Error while running the query: {e}"

    if rows:
        chart_type = classify_chart_type(prompt)
        df = pd.DataFrame(rows, columns=columns)
        render_chart(df, chart_type)

        if st.session_state.get("theme") == "light":
            st.table(df)
        else:
            st.dataframe(
                [dict(zip(columns, row)) for row in rows],
                use_container_width=True,
            )

        response_text = sanitize_response(summarize_query_results(prompt, columns, rows, history=st.session_state.messages[-4:], language=_detect_conversation_language()))
    else:
        if not response_text:
            response_text = "No results found for your query."
            st.info(response_text)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_text,
            "sql": sql if rows else None,
            "chart_type": chart_type if rows else None,
            "offer_email": True if (rows and (chart_type != "NONE" or len(rows) > 1)) else False,
        }
    )
    st.session_state.last_results = (
        {"columns": columns, "rows": rows, "chart_type": chart_type} if rows else None
    )

    # Store report data for potential email sending
    if rows:
        st.session_state.last_report_data = {
            "query": prompt,
            "summary": response_text,
            "columns": columns,
            "rows": rows,
            "chart_type": chart_type,
            "sql": sql,
            "language": _detect_conversation_language(),
        }

    # Persist response in DB (save SQL|||chart_type in the images field for re-execution)
    if st.session_state.user and st.session_state.current_conversation_id:
        metadata = f"{sql}|||{chart_type}" if rows else None
        save_message(
            st.session_state.current_conversation_id,
            "assistant",
            response_text,
            image=metadata,
        )

    with st.chat_message("assistant"):
        st.markdown(response_text)


def process_user_input(prompt: str):
    """Processes user input: classifies intent and routes accordingly. Persists in DB if logged in."""
    # If user is logged in, create conversation if it doesn't exist
    if st.session_state.user and not st.session_state.current_conversation_id:
        conv_id = create_conversation(st.session_state.user["id"])
        st.session_state.current_conversation_id = conv_id

    # Save user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    # --- ORDER FLOW: Check if we're in an active order process ---
    if st.session_state.order_flow == "awaiting_product_selection":
        from app.order_handlers import handle_order_product_selection
        handle_order_product_selection(prompt)
        return

    if st.session_state.order_flow == "awaiting_data" or st.session_state.order_flow == "multi_awaiting_data":
        # Data collection is now handled by the form dialog in main.py.
        # If user types something while the form is open, check if it's a cancellation.
        cancel_indicators = ["cancelar", "cancel", "no quiero", "nevermind", "no thanks", "no gracias", "dejalo", "olvidalo", "forget it", "ya no"]
        if any(indicator in prompt.lower() for indicator in cancel_indicators):
            st.session_state.order_flow = None
            st.session_state.order_product = None
            st.session_state.order_product_options = None
            st.session_state.multi_order_products = None
            st.session_state.multi_order_pending_options = None
            st.session_state.order_customer_data = None
            from app.ui_components import _detect_conversation_language as _detect_lang
            language = _detect_lang()
            cancel_msgs = {
                "es": "Pedido cancelado. Si necesitas algo mas, no dudes en preguntar.",
                "en": "Order cancelled. Let me know if you need anything else.",
                "fr": "Commande annulee. N'hesitez pas si vous avez besoin d'autre chose.",
            }
            response = cancel_msgs.get(language, cancel_msgs["es"])
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.user and st.session_state.current_conversation_id:
                save_message(st.session_state.current_conversation_id, "assistant", response)
        else:
            # Not a cancel — remind user to fill the form (form will re-open on rerun)
            from app.ui_components import _detect_conversation_language as _detect_lang
            language = _detect_lang()
            reminder_msgs = {
                "es": "Por favor completa el formulario que aparece en pantalla para continuar con tu pedido.",
                "en": "Please fill out the form on screen to continue with your order.",
                "fr": "Veuillez remplir le formulaire a l'ecran pour continuer votre commande.",
            }
            response = reminder_msgs.get(language, reminder_msgs["es"])
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.user and st.session_state.current_conversation_id:
                save_message(st.session_state.current_conversation_id, "assistant", response)
        return

    if st.session_state.order_flow == "awaiting_confirmation":
        from app.order_handlers import handle_order_data_confirmation
        handle_order_data_confirmation(prompt)
        return

    if st.session_state.order_flow == "multi_awaiting_selection":
        from app.multi_order_handlers import handle_multi_order_selection
        handle_multi_order_selection(prompt)
        return

    if st.session_state.order_flow == "multi_awaiting_confirmation":
        from app.multi_order_handlers import handle_multi_order_data_confirmation
        handle_multi_order_data_confirmation(prompt)
        return

    # --- Check if user is confirming an order ---
    history = st.session_state.messages[-8:] if st.session_state.messages else []
    order_intent = classify_order_intent(prompt, history=history)

    if order_intent == "ORDER_CONFIRMED":
        from app.order_handlers import handle_order_confirmed
        handle_order_confirmed(prompt)
        return

    # --- Normal flow ---
    with st.spinner("Understanding your question..."):
        try:
            intent = classify_intent(prompt)
        except Exception as e:
            st.error(f"Error classifying your question: {e}")
            return

    if intent == "CONVERSATIONAL":
        handle_conversational(prompt)
    else:
        handle_database_query(prompt)

    # After the first response, generate a title for the conversation
    if (
        st.session_state.user
        and st.session_state.current_conversation_id
        and len(st.session_state.messages) == 2  # user + assistant
    ):
        # Use the first 50 chars of the prompt as the title
        title = prompt[:50] + ("..." if len(prompt) > 50 else "")
        update_conversation_title(st.session_state.current_conversation_id, title)


def handle_send_report_email(email: str):
    """Generates a report PDF from the last query results and sends it via email."""
    import uuid as _uuid

    report_data = st.session_state.get("last_report_data")
    if not report_data:
        return

    language = report_data.get("language", _detect_conversation_language())
    query = report_data["query"]
    summary = report_data["summary"]
    columns = report_data["columns"]
    rows = report_data["rows"]
    chart_type = report_data["chart_type"]

    # Generate chart image if applicable
    chart_image_bytes = None
    if chart_type != "NONE" and rows and columns:
        chart_image_bytes = _generate_chart_image(columns, rows, chart_type)

    # Generate the PDF
    pdf_bytes = generate_report_pdf(
        user_query=query,
        summary_text=summary,
        columns=columns,
        rows=rows,
        chart_image_bytes=chart_image_bytes,
        language=language,
    )

    # Determine recipient name
    recipient_name = "User"
    if st.session_state.user:
        recipient_name = st.session_state.user.get("name", "User")

    # Send the email
    result = send_report_email(
        recipient_email=email,
        recipient_name=recipient_name,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"reporte_{_uuid.uuid4().hex[:8]}.pdf",
        report_summary={
            "query": query,
            "summary": summary,
            "row_count": len(rows),
            "chart_type": chart_type,
        },
        language=language,
    )

    # Add result message to chat history
    if result["success"]:
        success_messages = {
            "es": f"Reporte enviado exitosamente a {email}",
            "en": f"Report sent successfully to {email}",
            "fr": f"Rapport envoye avec succes a {email}",
        }
        msg = success_messages.get(language, success_messages["es"])
        st.session_state.messages.append({"role": "assistant", "content": msg})
        if st.session_state.user and st.session_state.current_conversation_id:
            save_message(st.session_state.current_conversation_id, "assistant", msg)
    else:
        error_messages = {
            "es": f"Error al enviar el reporte: {result.get('error', 'Unknown error')}",
            "en": f"Error sending report: {result.get('error', 'Unknown error')}",
            "fr": f"Erreur lors de l'envoi du rapport: {result.get('error', 'Unknown error')}",
        }
        msg = error_messages.get(language, error_messages["es"])
        st.session_state.messages.append({"role": "assistant", "content": msg})

    # Reset the flow
    st.session_state.report_email_flow = False


def _generate_chart_image(columns: list[str], rows: list[tuple], chart_type: str) -> bytes | None:
    """Generates a chart image as PNG bytes using plotly/kaleido for embedding in the PDF."""
    try:
        import plotly.express as px
        import plotly.io as pio

        df = pd.DataFrame(rows, columns=columns)

        if df.empty or len(df.columns) < 2:
            return None

        # Convert Decimal columns to float
        for col in df.columns:
            if df[col].dtype == "object":
                try:
                    df[col] = pd.to_numeric(df[col])
                except (ValueError, TypeError):
                    pass

        # --- Same intelligent column selection as render_chart ---
        skip_as_value = set()
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in ("id", "products_id", "orders_id", "customers_id", "supplier_id", "category_id"):
                skip_as_value.add(col)
            elif col_lower.endswith("_id") or col_lower == "id":
                skip_as_value.add(col)

        # Find label column
        label_col = None
        label_priority = ["name", "product", "producto", "category", "status", "order_state", "laboratory", "supplier"]
        for preferred in label_priority:
            for col in df.columns:
                if col.lower() == preferred:
                    label_col = col
                    break
            if label_col:
                break
        if label_col is None:
            for col in df.columns:
                if df[col].dtype == "object":
                    avg_len = df[col].astype(str).str.len().mean()
                    if avg_len < 50:
                        label_col = col
                        break
        if label_col is None:
            label_col = df.columns[0]

        # Find value column
        value_col = None
        value_priority = ["total_sold", "total_quantity", "quantity", "total", "revenue", "sales",
                          "count", "actual_stock", "stock", "total_sales", "units_sold", "sum"]
        for preferred in value_priority:
            for col in df.columns:
                if col.lower() == preferred and pd.api.types.is_numeric_dtype(df[col]):
                    value_col = col
                    break
            if value_col:
                break
        if value_col is None:
            for col in df.columns:
                if col.lower() == "price" and pd.api.types.is_numeric_dtype(df[col]):
                    value_col = col
                    break
        if value_col is None:
            for col in df.columns:
                if col == label_col or col in skip_as_value:
                    continue
                if pd.api.types.is_numeric_dtype(df[col]):
                    value_col = col
                    break
        if value_col is None:
            value_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

        chart_df = df[[label_col, value_col]].copy()
        chart_df[label_col] = chart_df[label_col].astype(str)

        if chart_type == "BAR":
            fig = px.bar(chart_df, x=label_col, y=value_col)
            fig.update_layout(xaxis={'categoryorder': 'array', 'categoryarray': chart_df[label_col].tolist()})
        elif chart_type == "LINE":
            fig = px.line(chart_df, x=label_col, y=value_col)
        elif chart_type == "PIE":
            fig = px.pie(chart_df, names=label_col, values=value_col)
        else:
            return None

        # Style the chart
        fig.update_layout(
            template="plotly_white",
            title_font_size=14,
            width=800,
            height=450,
        )

        # Export to PNG bytes
        img_bytes = pio.to_image(fig, format="png", scale=2)
        return img_bytes

    except ImportError:
        print("[_generate_chart_image] plotly or kaleido not available for image export")
        return None
    except Exception as e:
        print(f"[_generate_chart_image] Error generating chart image: {e}")
        return None