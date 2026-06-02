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

    # --- Process inputs captured from the welcome screen (Suggestions or Central Input) ---
    if st.session_state.input_to_process:
        prompt_to_run = st.session_state.input_to_process
        st.session_state.input_to_process = None  # Clear buffer
        process_user_input(prompt_to_run)
        st.rerun()


if __name__ == "__main__":
    main()
