import streamlit as st
import extra_streamlit_components as stx

from app.services.auth_service import get_user_by_id
from app.ui_components import (
    inject_custom_css,
    render_sidebar,
    render_welcome_screen,
    render_chat_history,
)
from app.chat_handlers import (
    process_user_input,
    handle_image_query,
    handle_multi_image_query,
    handle_send_report_email,
)

# --- Page Config ---
st.set_page_config(
    page_title="AI Explorer - Pharmacy",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="expanded",
)


def on_chat_input_submit():
    """Callback for chat text_input. Moves the value to a pending buffer and clears the widget.
    Only triggered on Enter key press (form submission), not on blur.
    """
    value = st.session_state.get("chat_text_input", "")
    if value:
        st.session_state.pending_chat_input = value


def main():
    # --- Initialize state ---
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "last_results" not in st.session_state:
        st.session_state.last_results = None

    if "chat_started" not in st.session_state:
        st.session_state.chat_started = False

    if "input_to_process" not in st.session_state:
        st.session_state.input_to_process = None

    if "user" not in st.session_state:
        st.session_state.user = None

    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None

    if "show_auth_forms" not in st.session_state:
        st.session_state.show_auth_forms = False

    if "show_account_panel" not in st.session_state:
        st.session_state.show_account_panel = False

    if "staged_image" not in st.session_state:
        st.session_state.staged_image = None

    if "staged_images" not in st.session_state:
        st.session_state.staged_images = []  # List of image bytes for multi-image upload

    if "pending_chat_input" not in st.session_state:
        st.session_state.pending_chat_input = None

    # Order flow states
    if "order_flow" not in st.session_state:
        st.session_state.order_flow = None  # None, "awaiting_product_selection", "awaiting_data", "awaiting_confirmation", "multi_awaiting_selection", "multi_awaiting_data", "multi_awaiting_confirmation"

    if "order_product" not in st.session_state:
        st.session_state.order_product = None  # {product, quantity, price} for single product orders

    if "order_customer_data" not in st.session_state:
        st.session_state.order_customer_data = None  # customer data dict

    if "order_product_options" not in st.session_state:
        st.session_state.order_product_options = None  # list of product dicts from DB

    # Multi-product order states
    if "multi_order_products" not in st.session_state:
        st.session_state.multi_order_products = None  # list of confirmed products [{name, quantity, price, ...}]

    if "multi_order_pending_options" not in st.session_state:
        st.session_state.multi_order_pending_options = None  # list of products that need user selection

    # Report email flow states
    if "last_report_data" not in st.session_state:
        st.session_state.last_report_data = None  # stores last chart/table data for email sending

    if "report_email_flow" not in st.session_state:
        st.session_state.report_email_flow = False  # True when user wants to send a report by email

    # --- Session persistence via cookies ---
    cookie_manager = stx.CookieManager(key="cookie_manager")

    # Handle pending cookie operations (set from login/register, delete from logout)
    if st.session_state.get("_set_cookie_user_id"):
        cookie_manager.set("ai_explorer_user_id", st.session_state._set_cookie_user_id, max_age=30*24*60*60)
        st.session_state._set_cookie_user_id = None

    _just_logged_out = False
    if st.session_state.get("_delete_cookie"):
        try:
            cookie_manager.delete("ai_explorer_user_id")
        except (KeyError, Exception):
            pass
        st.session_state._delete_cookie = False
        st.session_state._logout_cycles = 2  # Need 2 cycles for cookie to be fully removed from browser
        _just_logged_out = True

    if st.session_state.get("_logout_cycles", 0) > 0:
        _just_logged_out = True
        st.session_state._logout_cycles -= 1

    if st.session_state.user is None and not _just_logged_out:
        # Try to restore session from cookie
        saved_user_id = cookie_manager.get("ai_explorer_user_id")
        if saved_user_id:
            try:
                user = get_user_by_id(int(saved_user_id))
                if user:
                    st.session_state.user = user
            except (ValueError, TypeError):
                pass

    # --- CSS + Sidebar ---
    inject_custom_css()
    render_sidebar()

    # --- Determine which screen to show ---
    has_messages = len(st.session_state.messages) > 0

    if not has_messages and not st.session_state.chat_started:
        # Welcome screen with centered input and suggestions below
        render_welcome_screen()
    else:
        # Active chat view (history + previous results)
        render_chat_history()

        # File uploader appears pinned above the input area when clip is clicked
        if st.session_state.get("show_uploader", False):
            with st.container(key="chat_uploader_container"):
                uploaded = st.file_uploader(
                    "Upload medication images (up to 15)",
                    type=["jpg", "jpeg", "png", "webp"],
                    key="chat_file_uploader",
                    accept_multiple_files=True,
                )
                if uploaded:
                    if len(uploaded) == 1 and st.session_state.get("staged_image") is None:
                        st.session_state.staged_image = uploaded[0].getvalue()
                        st.session_state.show_uploader = False
                        st.rerun()
                    elif len(uploaded) > 1:
                        new_images = [f.getvalue() for f in uploaded[:15]]
                        if new_images != st.session_state.get("staged_images"):
                            st.session_state.staged_images = new_images
                            st.session_state.staged_image = None
                            st.session_state.show_uploader = False
                            st.rerun()

        # Input area pinned to bottom via CSS on the container key
        with st.container(key="chat_input_container"):
            # Image preview (if a single image is staged)
            if st.session_state.get("staged_image"):
                col_preview, col_remove = st.columns([5, 1])
                with col_preview:
                    st.image(st.session_state.staged_image, width=150)
                with col_remove:
                    if st.button("✕", key="remove_staged_image"):
                        st.session_state.staged_image = None
                        st.rerun()

            # Image previews (if multiple images are staged)
            if st.session_state.get("staged_images"):
                cols_per_row = min(len(st.session_state.staged_images), 5)
                img_cols = st.columns(cols_per_row + 1)
                for idx, img_bytes in enumerate(st.session_state.staged_images[:cols_per_row]):
                    with img_cols[idx]:
                        st.image(img_bytes, width=80, caption=f"{idx + 1}")
                with img_cols[cols_per_row]:
                    if st.button("✕", key="remove_staged_images"):
                        st.session_state.staged_images = []
                        st.rerun()
                if len(st.session_state.staged_images) > 5:
                    st.caption(f"+ {len(st.session_state.staged_images) - 5} more")

            # Input row: clip on the left, text input on the right
            col_clip, col_input = st.columns([1, 12])
            with col_clip:
                if st.button("📎", key="chat_attach_btn", help="Attach a medication image"):
                    st.session_state.show_uploader = not st.session_state.get("show_uploader", False)
                    st.rerun()
            with col_input:
                with st.form(key="chat_form", clear_on_submit=True, border=False):
                    st.text_input(
                        "Ask me anything about our pharmacy...",
                        placeholder="Ask me anything about our pharmacy...",
                        label_visibility="collapsed",
                        key="chat_text_input",
                    )
                    submitted = st.form_submit_button("Send", type="primary")
                    if submitted:
                        on_chat_input_submit()

    # --- Process inputs captured from chat_text_input via callback ---
    if st.session_state.get("pending_chat_input"):
        prompt = st.session_state.pending_chat_input
        st.session_state.pending_chat_input = None
        if st.session_state.get("staged_images"):
            # Multi-image flow
            images_list = st.session_state.staged_images[:]
            st.session_state.staged_images = []
            st.session_state.staged_image = None
            st.session_state.show_uploader = False
            handle_multi_image_query(images_list, prompt)
            st.rerun()
        elif st.session_state.get("staged_image"):
            image_bytes = st.session_state.staged_image
            st.session_state.staged_image = None
            st.session_state.show_uploader = False
            handle_image_query(image_bytes, prompt)
            st.rerun()
        else:
            process_user_input(prompt)
            st.rerun()

    # --- Handle report email flow ---
    if st.session_state.get("report_email_flow"):
        _handle_report_email_dialog()

    # --- Handle order data collection via form dialog ---
    if st.session_state.get("order_flow") in ("awaiting_data", "multi_awaiting_data"):
        _handle_order_data_form_dialog()

    # --- Process inputs captured from the welcome screen (Suggestions or Central Input) ---
    if st.session_state.input_to_process:
        prompt_to_run = st.session_state.input_to_process
        st.session_state.input_to_process = None  # Clear buffer
        process_user_input(prompt_to_run)
        st.rerun()


@st.dialog("📧")
def _handle_report_email_dialog():
    """Shows a dialog to capture the email address and send the report."""
    # Use language stored in last_report_data (set at the time the button was clicked)
    report_data = st.session_state.get("last_report_data") or {}
    language = report_data.get("language", "es")

    labels = {
        "es": {
            "instruction": "Ingresa el correo electronico donde deseas recibir el reporte:",
            "placeholder": "tu@email.com",
            "send": "Enviar reporte",
            "cancel": "Cancelar",
            "invalid": "Por favor ingresa un correo electronico valido.",
        },
        "en": {
            "instruction": "Enter the email address where you want to receive the report:",
            "placeholder": "your@email.com",
            "send": "Send report",
            "cancel": "Cancel",
            "invalid": "Please enter a valid email address.",
        },
        "fr": {
            "instruction": "Entrez l'adresse email ou vous souhaitez recevoir le rapport:",
            "placeholder": "votre@email.com",
            "send": "Envoyer le rapport",
            "cancel": "Annuler",
            "invalid": "Veuillez entrer une adresse email valide.",
        },
    }
    t = labels.get(language, labels["es"])

    st.write(t["instruction"])

    # Pre-fill with user's email if logged in
    default_email = ""
    if st.session_state.user:
        default_email = st.session_state.user.get("email", "")

    email = st.text_input(
        "Email",
        value=default_email,
        placeholder=t["placeholder"],
        label_visibility="collapsed",
        key="report_email_input",
    )

    col_send, col_cancel = st.columns(2)
    with col_send:
        if st.button(t["send"], type="primary", use_container_width=True, key="report_send_btn"):
            if email and "@" in email and "." in email:
                handle_send_report_email(email)
                st.session_state.report_email_flow = False
                st.rerun()
            else:
                st.error(t["invalid"])
    with col_cancel:
        if st.button(t["cancel"], use_container_width=True, key="report_cancel_btn"):
            st.session_state.report_email_flow = False
            st.rerun()


@st.dialog("🧾")
def _handle_order_data_form_dialog():
    """Shows a form dialog to collect customer data for an order."""
    from app.ui_components import _detect_conversation_language
    from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
    from app.services.auth_service import save_message

    language = _detect_conversation_language()

    labels = {
        "es": {
            "title": "Datos para la factura",
            "name": "Nombre completo",
            "doc_type": "Tipo de documento",
            "doc_number": "Numero de documento",
            "email": "Correo electronico",
            "address": "Direccion completa",
            "city": "Ciudad",
            "phone": "Celular / Telefono",
            "submit": "Enviar datos",
            "cancel": "Cancelar pedido",
            "doc_options": ["Cedula de Ciudadania", "Cedula de Extranjeria", "Pasaporte"],
            "required": "Todos los campos son obligatorios.",
        },
        "en": {
            "title": "Invoice information",
            "name": "Full name",
            "doc_type": "Document type",
            "doc_number": "Document number",
            "email": "Email address",
            "address": "Full address",
            "city": "City",
            "phone": "Phone number",
            "submit": "Submit",
            "cancel": "Cancel order",
            "doc_options": ["National ID", "Foreign ID", "Passport"],
            "required": "All fields are required.",
        },
        "fr": {
            "title": "Informations pour la facture",
            "name": "Nom complet",
            "doc_type": "Type de document",
            "doc_number": "Numero de document",
            "email": "Adresse email",
            "address": "Adresse complete",
            "city": "Ville",
            "phone": "Telephone",
            "submit": "Envoyer",
            "cancel": "Annuler la commande",
            "doc_options": ["Carte d'identite", "Carte de sejour", "Passeport"],
            "required": "Tous les champs sont obligatoires.",
        },
    }
    t = labels.get(language, labels["es"])

    st.subheader(t["title"])

    # Pre-fill email if user is logged in
    default_email = ""
    if st.session_state.user:
        default_email = st.session_state.user.get("email", "")

    nombre = st.text_input(t["name"], key="order_form_name")
    tipo_documento = st.selectbox(t["doc_type"], options=t["doc_options"], key="order_form_doc_type")
    cedula = st.text_input(t["doc_number"], key="order_form_doc_number")
    correo = st.text_input(t["email"], value=default_email, key="order_form_email")
    direccion = st.text_input(t["address"], key="order_form_address")
    ciudad = st.text_input(t["city"], key="order_form_city")
    celular = st.text_input(t["phone"], key="order_form_phone")

    col_submit, col_cancel = st.columns(2)
    with col_submit:
        if st.button(t["submit"], type="primary", use_container_width=True, key="order_form_submit_btn"):
            # Validate all fields
            if not all([nombre.strip(), cedula.strip(), correo.strip(), direccion.strip(), ciudad.strip(), celular.strip()]):
                st.error(t["required"])
            elif "@" not in correo or "." not in correo:
                st.error(t["required"])
            else:
                # Save customer data and advance to confirmation
                customer_data = {
                    "nombre": nombre.strip(),
                    "tipo_documento": tipo_documento,
                    "cedula": cedula.strip(),
                    "correo": correo.strip(),
                    "direccion": direccion.strip(),
                    "ciudad": ciudad.strip(),
                    "celular": celular.strip(),
                }
                st.session_state.order_customer_data = customer_data

                # Determine if single or multi order
                is_multi = st.session_state.get("order_flow") == "multi_awaiting_data"

                if is_multi:
                    st.session_state.order_flow = "multi_awaiting_confirmation"
                    products = st.session_state.multi_order_products
                    total = sum(float(p["price"]) * p["quantity"] for p in products)
                    products_summary = "\n".join(
                        f"- {p['name']} ({p.get('laboratory', 'N/A')}) x{p['quantity']} - {float(p['price']) * p['quantity']:,.2f} COP"
                        for p in products
                    )
                else:
                    st.session_state.order_flow = "awaiting_confirmation"
                    order_product = st.session_state.order_product
                    total = order_product["price"] * order_product["quantity"]
                    products_summary = f"- {order_product['product']} ({order_product.get('laboratory', 'N/A')}) x{order_product['quantity']} - {total:,.2f} COP"

                # Generate confirmation message via AI
                lang_instruction = {
                    "en": "You MUST respond ENTIRELY in English.",
                    "fr": "You MUST respond ENTIRELY in French.",
                    "es": "You MUST respond ENTIRELY in Spanish.",
                }.get(language, "You MUST respond ENTIRELY in Spanish.")

                try:
                    msg = generate_content(
                        contents=(
                            f"Customer data received:\n"
                            f"- Name: {customer_data['nombre']}\n"
                            f"- Document: {customer_data['tipo_documento']} {customer_data['cedula']}\n"
                            f"- Email: {customer_data['correo']}\n"
                            f"- Address: {customer_data['direccion']}, {customer_data['ciudad']}\n"
                            f"- Phone: {customer_data['celular']}\n\n"
                            f"Products:\n{products_summary}\n"
                            f"Total: {total:,.2f} COP\n\n"
                            f"Present all this data to the customer and ask if everything is correct. "
                            f"If correct they should confirm, if not they can correct it.\n"
                            f"LANGUAGE INSTRUCTION: {lang_instruction}"
                        ),
                        system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                        temperature=0.7,
                    )
                    response = msg.strip() if msg else "Please confirm your data is correct."
                except Exception:
                    response = (
                        f"Data received:\n"
                        f"Name: {customer_data['nombre']}\n"
                        f"Document: {customer_data['tipo_documento']} {customer_data['cedula']}\n"
                        f"Email: {customer_data['correo']}\n"
                        f"Address: {customer_data['direccion']}, {customer_data['ciudad']}\n"
                        f"Phone: {customer_data['celular']}\n"
                        f"Total: {total:,.2f} COP\n\n"
                        f"Is this correct?"
                    )

                from app.ui_components import sanitize_response
                response = sanitize_response(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                if st.session_state.user and st.session_state.current_conversation_id:
                    save_message(st.session_state.current_conversation_id, "assistant", response)
                st.rerun()

    with col_cancel:
        if st.button(t["cancel"], use_container_width=True, key="order_form_cancel_btn"):
            # Cancel the order
            st.session_state.order_flow = None
            st.session_state.order_product = None
            st.session_state.order_product_options = None
            st.session_state.multi_order_products = None
            st.session_state.multi_order_pending_options = None
            st.session_state.order_customer_data = None

            lang_instruction = {
                "en": "You MUST respond ENTIRELY in English.",
                "fr": "You MUST respond ENTIRELY in French.",
                "es": "You MUST respond ENTIRELY in Spanish.",
            }.get(language, "You MUST respond ENTIRELY in Spanish.")

            try:
                msg = generate_content(
                    contents=f"The customer cancelled their order. Acknowledge politely.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                    system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                    temperature=0.7,
                )
                response = msg.strip() if msg else "Order cancelled."
            except Exception:
                response = "Order cancelled. Let me know if you need anything else."

            from app.ui_components import sanitize_response
            response = sanitize_response(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            if st.session_state.user and st.session_state.current_conversation_id:
                save_message(st.session_state.current_conversation_id, "assistant", response)
            st.rerun()


if __name__ == "__main__":
    main()
