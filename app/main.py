import streamlit as st
import streamlit.components.v1 as components
import extra_streamlit_components as stx
import plotly.express as px
import pandas as pd
import uuid
import base64

from app.services.ai_service import (
    classify_intent,
    generate_conversational_response,
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
from app.services.pdf_service import generate_invoice_pdf
from app.services.email_service import send_invoice_email
from app.services.db_service import execute_query, find_matching_products, get_connection
from app.services.auth_service import (
    login_user,
    register_user,
    get_user_conversations,
    create_conversation,
    update_conversation_title,
    save_message,
    get_conversation_messages,
    get_user_by_id,
)

# --- Page Config ---
st.set_page_config(
    page_title="AI Explorer - Pharmacy",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --- Suggestion buttons for the welcome screen ---
SUGGESTIONS = [
    "💊 What's good for a headache?",
    "📦 Show me top 5 selling products",
    "💰 What's the price of Ibuprofen?",
    "📊 Orders by status this month",
]


def sanitize_response(text: str) -> str:
    """Sanitizes AI responses to prevent Streamlit rendering issues."""
    # Remove backticks that cause code highlighting
    text = text.replace("`", "")
    # Escape $ signs to prevent Streamlit from interpreting them as LaTeX math delimiters
    text = text.replace("$", "")
    return text


def inject_custom_css():
    """Injects custom CSS for the chat layout and sidebar structure."""
    st.markdown(
        """
        <style>
        /* --- SIDEBAR HEADER --- */
        div[data-testid="stSidebarHeader"] {
            padding: 0rem !important;
            margin: 0rem !important;
            min-height: 0px !important;
            height: 0px !important;
            display: none !important;
        }
        
        /* --- SIDEBAR FLEXBOX STRUCTURE --- */
        /* 1. Force the main container to fill the full viewport height without rogue paddings */
        div[data-testid="stSidebarUserContent"] {
            padding-top: 1.5rem !important;
            padding-bottom: 0rem !important;
            height: 100vh !important;
            display: flex !important;
            flex-direction: column !important;
        }

        /* 2. Force stVerticalBlock to become the real Flexbox parent controlling full height */
        div[data-testid="stSidebarUserContent"] > div > div[data-testid="stVerticalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            height: calc(100vh - 2.5rem) !important; /* Full height minus top padding */
            gap: 0.5rem !important; /* Control native margin */
        }

        /* 3. The key trick: Find the container of the element right AFTER 
           our invisible anchor, and apply margin-top: auto to push 
           the entire bottom block to the bottom of the screen */
        div[data-testid="stVerticalBlock"] > div:has(#sidebar-bottom-anchor) + div {
            margin-top: auto !important;
        }

        /* Minor adjustments to clean up residual spacing in the bottom block */
        div[data-testid="stVerticalBlock"] > div:last-child,
        div[data-testid="stVerticalBlock"] div[data-testid="stLayoutWrapper"] {
            padding-bottom: 0rem !important;
            margin-bottom: 0rem !important;
        }

        /* Welcome screen centering */
        .welcome-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding-top: 4rem;
            text-align: center;
        }
        .welcome-title {
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #4285f4, #9b72cb, #d96570);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .welcome-subtitle {
            font-size: 1.1rem;
            color: #9aa0a6;
            margin-bottom: 2rem;
        }

        /* Suggestion chips */
        .suggestions-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            justify-content: center;
            margin-top: 1.5rem;
            margin-bottom: 2rem;
        }

        /* Style the suggestion buttons */
        div[data-testid="stHorizontalBlock"] > div > div > button {
            border: 1px solid #3c4043;
            border-radius: 24px;
            padding: 0.5rem 1rem;
            background-color: transparent;
            color: #e8eaed;
            font-size: 0.85rem;
            transition: background-color 0.2s;
            white-space: nowrap;
        }
        div[data-testid="stHorizontalBlock"] > div > div > button:hover {
            background-color: #3c4043;
        }

        /* --- Input styling --- */
        div[data-testid="stTextInput"] > div {
            height: 58px !important;
            min-height: 58px !important;
            border-radius: 0.5rem !important;
            display: flex !important;
            align-items: center !important;
        }
        
        div[data-testid="stTextInput"] input {
            height: 58px !important;
            line-height: 58px !important;
            padding: 0rem 1.5rem !important;
            font-size: 1.05rem !important;
            background-color: transparent !important;
        }

        /* Hide Streamlit default header/footer for cleaner look */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Chat input styling */
        .stChatInput {
            border-radius: 24px;
        }

        /* User avatar circle at bottom of sidebar */
        .user-avatar-circle {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(135deg, #4285f4, #9b72cb);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 1rem;
            cursor: pointer;
            margin: 0;
        }
        .user-avatar-circle:hover {
            opacity: 0.85;
        }
        .login-circle {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #3c4043;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #9aa0a6;
            font-size: 1.2rem;
            cursor: pointer;
            margin: 0;
        }
        .login-circle:hover {
            background: #4a4a4a;
        }

        /* User info popover style */
        .user-info-panel {
            padding: 0.75rem;
            background-color: #2d2d2d;
            border-radius: 8px;
            margin-top: 0.5rem;
        }
        .user-info-panel .user-name {
            font-weight: 600;
            color: #e8eaed;
            font-size: 0.9rem;
        }
        .user-info-panel .user-email {
            color: #9aa0a6;
            font-size: 0.75rem;
        }
        div[data-testid="InputInstructions"] {
        visibility: hidden;
        }

        /* Hide the form submit button — Enter key submits the form */
        .st-key-chat_input_container [data-testid="stFormSubmitButton"],
        .st-key-chat_input_container .stFormSubmitButton,
        .st-key-welcome_form [data-testid="stFormSubmitButton"],
        .st-key-welcome_form .stFormSubmitButton,
        [data-testid="stForm"] [data-testid="stFormSubmitButton"] {
            display: none !important;
            height: 0 !important;
            overflow: hidden !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        /* Also hide the container wrapping the submit button */
        .st-key-FormSubmitter-chat_form-Send,
        .st-key-FormSubmitter-welcome_form-Send {
            display: none !important;
            height: 0 !important;
        }
        /* Remove form padding/border */
        .st-key-chat_input_container [data-testid="stForm"],
        .st-key-welcome_form [data-testid="stForm"],
        .stForm {
            border: none !important;
            padding: 0 !important;
        }

        /* --- Attachment button styling (targets by key) --- */
        .st-key-welcome_attach_btn button,
        .st-key-chat_attach_btn button {
            width: 58px !important;
            height: 58px !important;
            min-width: 58px !important;
            min-height: 58px !important;
            max-width: 58px !important;
            max-height: 58px !important;
            padding: 0 !important;
            font-size: 1.3rem !important;
            border: 1px solid #3c4043 !important;
            border-radius: 0.5rem !important;
            background: transparent !important;
            line-height: 58px !important;
            box-sizing: border-box !important;
        }
        .st-key-welcome_attach_btn button:hover,
        .st-key-chat_attach_btn button:hover {
            background: #3c4043 !important;
        }

        /* Fix vertical alignment of clip column with text input */
        .st-key-welcome_attach_btn,
        .st-key-chat_attach_btn {
            display: flex !important;
            align-items: flex-end !important;
        }

        /* Pin the chat input area to the bottom */
        .st-key-chat_input_container {
            position: fixed !important;
            bottom: 0 !important;
            /* Default: center a 704px container within the stMain area (viewport minus sidebar) */
            left: 50% !important;
            transform: translateX(calc(-50% + 171px)) !important;
            width: 704px !important;
            right: auto !important;
            padding: 1rem 0 1.5rem !important;
            z-index: 999 !important;
            background: var(--background-color, #0e1117) !important;
        }
        /* Constrain and center the inner content to match chat messages width */
        .st-key-chat_input_container > div[data-testid="stLayoutWrapper"] {
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            box-sizing: border-box !important;
        }
        /* Add bottom padding to main content so it doesn't hide behind fixed input */
        section[data-testid="stMain"] .block-container {
            padding-bottom: 120px !important;
        }

        /* File uploader in chat: pin above the fixed input */
        .st-key-chat_uploader_container {
            position: fixed !important;
            bottom: 90px !important;
            left: 50% !important;
            transform: translateX(calc(-50% + 171px)) !important;
            width: 704px !important;
            right: auto !important;
            padding: 0.5rem 1rem !important;
            z-index: 998 !important;
            background: var(--background-color, #0e1117) !important;
        }
        .st-key-chat_uploader_container > div {
            width: 100% !important;
            margin: 0 !important;
            padding: 0 !important;
            box-sizing: border-box !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Inject JS via components.html to dynamically align fixed input with stMain
    components.html(
        """
        <script>
        function alignFixedInput() {
            // Use stMainBlockContainer as reference - this is what centers the chat messages
            const blockContainer = parent.document.querySelector('[data-testid="stMainBlockContainer"]');
            const container = parent.document.querySelector('.st-key-chat_input_container');
            const uploader = parent.document.querySelector('.st-key-chat_uploader_container');
            if (blockContainer && container) {
                const rect = blockContainer.getBoundingClientRect();
                // Get computed padding of blockContainer to match exactly
                const style = parent.window.getComputedStyle(blockContainer);
                const paddingLeft = parseFloat(style.paddingLeft) || 0;
                const paddingRight = parseFloat(style.paddingRight) || 0;
                const contentLeft = rect.left + paddingLeft;
                const contentWidth = rect.width - paddingLeft - paddingRight;
                container.style.setProperty('left', contentLeft + 'px', 'important');
                container.style.setProperty('width', contentWidth + 'px', 'important');
                container.style.setProperty('right', 'auto', 'important');
                container.style.setProperty('transform', 'none', 'important');
            }
            if (blockContainer && uploader) {
                const rect = blockContainer.getBoundingClientRect();
                const style = parent.window.getComputedStyle(blockContainer);
                const paddingLeft = parseFloat(style.paddingLeft) || 0;
                const paddingRight = parseFloat(style.paddingRight) || 0;
                const contentLeft = rect.left + paddingLeft;
                const contentWidth = rect.width - paddingLeft - paddingRight;
                uploader.style.setProperty('left', contentLeft + 'px', 'important');
                uploader.style.setProperty('width', contentWidth + 'px', 'important');
                uploader.style.setProperty('right', 'auto', 'important');
            }
        }
        // Run immediately and multiple times to minimize flash
        alignFixedInput();
        setTimeout(alignFixedInput, 50);
        setTimeout(alignFixedInput, 150);
        setTimeout(alignFixedInput, 400);
        setTimeout(alignFixedInput, 1000);
        // Observe resize
        new ResizeObserver(alignFixedInput).observe(parent.document.body);
        </script>
        """,
        height=0,
    )


def render_sidebar():
    """Renders the sidebar with New Chat at top, conversations in middle, and user avatar at bottom."""
    with st.sidebar:
        st.title("💊 AI Explorer")

        # --- New Chat button always at the top ---
        if st.button("New chat", use_container_width=True, key="new_chat_btn"):
            st.session_state.messages = []
            st.session_state.last_results = None
            st.session_state.chat_started = False
            st.session_state.current_conversation_id = None
            st.rerun()

        st.divider()

        # --- Conversation history (middle section) ---
        if st.session_state.user:
            st.markdown("**Conversations**")
            conversations = get_user_conversations(st.session_state.user["id"])

            if not conversations:
                st.caption("No conversations yet. Start chatting!")
            else:
                for conv in conversations:
                    title = conv["title"] or "Untitled conversation"
                    if st.button(
                        f"💬 {title[:35]}{'...' if len(title) > 35 else ''}",
                        key=f"conv_{conv['id']}",
                        use_container_width=True,
                    ):
                        load_conversation(conv["id"])
        else:
            st.caption("Log in to save and view your conversations.")

        # --- Spacer to push user section to bottom ---
        st.markdown('<div id="sidebar-bottom-anchor"></div>', unsafe_allow_html=True)

        # --- User section at the very bottom ---
        st.divider()
        render_user_avatar_section()


def render_user_avatar_section():
    """Renders the user avatar circle at the bottom of the sidebar with login/logout functionality."""
    if st.session_state.user:
        # Logged in: show account panel ABOVE the avatar
        if "show_account_panel" not in st.session_state:
            st.session_state.show_account_panel = False

        if st.session_state.show_account_panel:
            if st.button("🚪 Log out", use_container_width=True, key="logout_btn"):
                st.session_state.user = None
                st.session_state.messages = []
                st.session_state.last_results = None
                st.session_state.chat_started = False
                st.session_state.current_conversation_id = None
                st.session_state.show_account_panel = False
                # Flag cookie to be deleted on next rerun
                st.session_state._delete_cookie = True
                st.rerun()

        # Account button
        if st.button("👤 Account", use_container_width=True, key="account_toggle_btn"):
            st.session_state.show_account_panel = (
                not st.session_state.show_account_panel
            )
            st.rerun()

        # Avatar + user info at the very bottom
        user = st.session_state.user
        initial = user["name"][0].upper() if user["name"] else "U"

        col_avatar, col_info = st.columns([1, 4])
        with col_avatar:
            st.markdown(
                f'<div class="user-avatar-circle">{initial}</div>',
                unsafe_allow_html=True,
            )
        with col_info:
            st.markdown(
                f"**{user['name']}**  \n<small style='color:#9aa0a6'>{user['email']}</small>",
                unsafe_allow_html=True,
            )
    else:
        # Not logged in: auth forms ABOVE button ABOVE avatar
        if "show_auth_forms" not in st.session_state:
            st.session_state.show_auth_forms = False

        # Auth forms appear ABOVE the login button
        if st.session_state.show_auth_forms:
            render_auth_forms()

        # Login button above the avatar
        if st.button(
            "Log in / Register", use_container_width=True, key="auth_toggle_btn"
        ):
            st.session_state.show_auth_forms = not st.session_state.show_auth_forms
            st.rerun()

        # Avatar + Guest text at the very bottom
        col_avatar, col_label = st.columns([1, 4])
        with col_avatar:
            st.markdown(
                '<div class="login-circle">👤</div>',
                unsafe_allow_html=True,
            )
        with col_label:
            st.markdown(
                "**Guest**  \n<small style='color:#9aa0a6'>Click to log in</small>",
                unsafe_allow_html=True,
            )


def render_auth_forms():
    """Renders the login and register forms in the sidebar."""
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form", clear_on_submit=True):
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields.")
                else:
                    user = login_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.messages = []
                        st.session_state.chat_started = False
                        st.session_state.current_conversation_id = None
                        st.session_state.show_auth_forms = False
                        # Flag cookie to be set on next rerun
                        st.session_state._set_cookie_user_id = str(user["id"])
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form", clear_on_submit=True):
            name = st.text_input("Name", placeholder="Your name")
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            password_confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button(
                "Create account", use_container_width=True
            )

            if submitted:
                if not name or not email or not password:
                    st.error("Please fill in all fields.")
                elif password != password_confirm:
                    st.error("Passwords don't match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    user = register_user(name, email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.messages = []
                        st.session_state.chat_started = False
                        st.session_state.current_conversation_id = None
                        st.session_state.show_auth_forms = False
                        # Flag cookie to be set on next rerun
                        st.session_state._set_cookie_user_id = str(user["id"])
                        st.rerun()
                    else:
                        st.error("Email already registered.")


def load_conversation(conversation_id: int):
    """Loads an existing conversation from the DB."""
    messages = get_conversation_messages(conversation_id)
    st.session_state.messages = []
    for m in messages:
        msg = {"role": m["role"], "content": m["content"]}
        # If the message has stored SQL|||chart_type metadata, parse it
        if m.get("image") and m["role"] == "assistant" and "|||" in m["image"]:
            parts = m["image"].split("|||", 1)
            msg["sql"] = parts[0]
            msg["chart_type"] = parts[1] if len(parts) > 1 else "NONE"
        # If user message has a base64 image, decode it
        elif m.get("image") and m["role"] == "user":
            try:
                msg["image"] = base64.b64decode(m["image"])
            except Exception:
                pass
        st.session_state.messages.append(msg)
    st.session_state.current_conversation_id = conversation_id
    st.session_state.chat_started = True
    st.session_state.last_results = None
    st.rerun()


def render_welcome_screen():
    """Renders the welcome screen with a centered input and suggestion buttons below."""
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-title">Hi, how can I help you today?</div>
            <div class="welcome-subtitle">Ask me about medications, orders, inventory, or health advice</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Image preview (if an image is staged - single)
    if st.session_state.get("staged_image"):
        col_preview, col_remove = st.columns([5, 1])
        with col_preview:
            st.image(st.session_state.staged_image, width=150)
        with col_remove:
            if st.button("✕", key="remove_welcome_staged_image"):
                st.session_state.staged_image = None
                st.rerun()

    # Image previews (if multiple images are staged)
    if st.session_state.get("staged_images"):
        cols_per_row = min(len(st.session_state.staged_images), 5)
        img_cols = st.columns(cols_per_row + 1)
        for idx, img_bytes in enumerate(st.session_state.staged_images[:cols_per_row]):
            with img_cols[idx]:
                st.image(img_bytes, width=100, caption=f"Image {idx + 1}")
        with img_cols[cols_per_row]:
            if st.button("✕ Clear all", key="remove_welcome_staged_images"):
                st.session_state.staged_images = []
                st.rerun()
        if len(st.session_state.staged_images) > 5:
            st.caption(f"+ {len(st.session_state.staged_images) - 5} more images")

    # Input row: clip on the left, text input on the right
    col_clip, col_input = st.columns([1, 12])
    with col_clip:
        if st.button("📎", key="welcome_attach_btn", help="Attach a medication image"):
            st.session_state.show_uploader = not st.session_state.get("show_uploader", False)
            st.rerun()
    with col_input:
        with st.form(key="welcome_form", clear_on_submit=True, border=False):
            st.text_input(
                "Ask me anything about our pharmacy...",
                placeholder="Ask me anything about our pharmacy...",
                label_visibility="collapsed",
                key="welcome_input",
            )
            welcome_submitted = st.form_submit_button("Send", type="primary")

    # File uploader appears only after clicking the clip button
    if st.session_state.get("show_uploader", False):
        uploaded = st.file_uploader(
            "Upload medication images (up to 15)",
            type=["jpg", "jpeg", "png", "webp"],
            key="welcome_file_uploader",
            accept_multiple_files=True,
        )
        if uploaded:
            if len(uploaded) == 1 and st.session_state.get("staged_image") is None:
                # Single image — use existing single-image flow
                st.session_state.staged_image = uploaded[0].getvalue()
                st.session_state.show_uploader = False
                st.rerun()
            elif len(uploaded) > 1:
                # Multiple images — use multi-image flow (max 15)
                new_images = [f.getvalue() for f in uploaded[:15]]
                if new_images != st.session_state.get("staged_images"):
                    st.session_state.staged_images = new_images
                    st.session_state.staged_image = None  # Clear single image
                    st.session_state.show_uploader = False
                    st.rerun()

    if welcome_submitted and st.session_state.welcome_input:
        if st.session_state.get("staged_images"):
            # Multi-image flow
            images_list = st.session_state.staged_images[:]
            st.session_state.staged_images = []
            st.session_state.staged_image = None
            st.session_state.chat_started = True
            st.session_state.show_uploader = False
            handle_multi_image_query(images_list, st.session_state.welcome_input)
            st.rerun()
        elif st.session_state.get("staged_image"):
            image_bytes = st.session_state.staged_image
            st.session_state.staged_image = None
            st.session_state.chat_started = True
            st.session_state.show_uploader = False
            handle_image_query(image_bytes, st.session_state.welcome_input)
            st.rerun()
        else:
            st.session_state.input_to_process = st.session_state.welcome_input
            st.session_state.chat_started = True
            st.rerun()

    # Short spacer
    st.write("")

    # Suggestion buttons below the input
    cols = st.columns(len(SUGGESTIONS))
    for i, suggestion in enumerate(SUGGESTIONS):
        with cols[i]:
            if st.button(suggestion, key=f"suggestion_{i}", use_container_width=True):
                st.session_state.input_to_process = suggestion
                st.session_state.chat_started = True
                st.rerun()


def render_chat_history():
    """Renders the chat message history, including charts from saved queries."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Show image if the user message has one attached
            if message.get("image") and message["role"] == "user":
                st.image(message["image"], width=250)
            # Show multiple images if the user message has them
            if message.get("images") and message["role"] == "user":
                imgs = message["images"]
                cols_per_row = min(len(imgs), 5)
                img_cols = st.columns(cols_per_row)
                for idx, img_bytes in enumerate(imgs[:cols_per_row]):
                    with img_cols[idx]:
                        st.image(img_bytes, width=120)
                if len(imgs) > 5:
                    st.caption(f"+ {len(imgs) - 5} more images")
            # Show PDF download button if this message has a generated invoice
            if message.get("pdf_bytes") and message["role"] == "assistant":
                st.download_button(
                    label="📄 Descargar Factura PDF",
                    data=message["pdf_bytes"],
                    file_name=message.get("pdf_filename", "factura.pdf"),
                    mime="application/pdf",
                    key=f"download_pdf_{uuid.uuid4().hex[:8]}",
                )
            # If this assistant message has a stored SQL query, re-execute and show results
            if message.get("sql") and message["role"] == "assistant":
                try:
                    sql = message["sql"]
                    chart_type = message.get("chart_type", "NONE")
                    columns, rows = execute_query(sql)
                    if rows:
                        df = pd.DataFrame(rows, columns=columns)
                        render_chart(df, chart_type)
                        st.dataframe(
                            [dict(zip(columns, row)) for row in rows],
                            use_container_width=True,
                        )
                except Exception:
                    pass


def render_chart(df: pd.DataFrame, chart_type: str):
    """Renders a chart based on the classified type.
    Automatically detects the best label (categorical) and value (numeric) columns.
    """
    if chart_type == "NONE" or df.empty or len(df.columns) < 2:
        return

    # Find the best label column (first string/object column) and value column (first numeric column)
    label_col = None
    value_col = None

    for col in df.columns:
        if label_col is None and df[col].dtype == "object":
            label_col = col
        if value_col is None and pd.api.types.is_numeric_dtype(df[col]):
            # Skip ID-like columns (all unique integers that look like sequential IDs)
            if df[col].dtype in ["int64", "int32"] and col.lower().endswith("id"):
                continue
            value_col = col

    # Fallback: if no string column found, use first column as label
    if label_col is None:
        label_col = df.columns[0]
    # Fallback: if no numeric column found, use second column
    if value_col is None:
        for col in df.columns:
            if col != label_col and pd.api.types.is_numeric_dtype(df[col]):
                value_col = col
                break
    if value_col is None:
        value_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    try:
        chart_df = df[[label_col, value_col]].copy()
        chart_df[label_col] = chart_df[label_col].astype(str)

        if chart_type == "BAR":
            st.bar_chart(chart_df.set_index(label_col)[value_col])
        elif chart_type == "LINE":
            st.line_chart(chart_df.set_index(label_col)[value_col])
        elif chart_type == "PIE":
            fig = px.pie(chart_df, names=label_col, values=value_col)
            st.plotly_chart(
                fig, use_container_width=True, key=f"pie_{uuid.uuid4().hex[:8]}"
            )
    except Exception:
        # If chart rendering fails, silently skip — the data table is still shown
        pass


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
                if "|" in image_analysis:
                    drug_name = image_analysis.split("|")[0].strip()
                else:
                    analysis_lower = image_analysis.lower().strip()
                    noise_words = ["tablets", "capsules", "units", "by", "from", "with",
                                   "sachet", "sachets", "syrup", "cream", "drops", "injection",
                                   "tabletas", "cápsulas", "unidades", "por", "de", "con",
                                   "mg", "ml", "iu", "mcg", "g", "forte"]
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

                # Search with full drug name first, then first word as fallback
                search_terms = [drug_name]
                first_word = drug_name.split()[0] if drug_name else ""
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
            except Exception:
                pass

            # Step 4: Generate recommendation response
            response = sanitize_response(generate_image_recommendation(
                user_text, image_analysis, products_data
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
                        analysis_lower = analysis.lower().strip()
                        noise_words = ["tablets", "capsules", "units", "by", "from", "with",
                                       "sachet", "sachets", "syrup", "cream", "drops", "injection",
                                       "tabletas", "cápsulas", "unidades", "por", "de", "con",
                                       "mg", "ml", "iu", "mcg", "g", "forte"]
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

                    # Search the DB with the extracted drug name
                    # Try the full name first, then just the first word as fallback
                    search_terms = [drug_name]
                    first_word = drug_name.split()[0] if drug_name else ""
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

        st.dataframe(
            [dict(zip(columns, row)) for row in rows],
            use_container_width=True,
        )

        response_text = sanitize_response(summarize_query_results(prompt, columns, rows, history=st.session_state.messages[-4:]))
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
        }
    )
    st.session_state.last_results = (
        {"columns": columns, "rows": rows, "chart_type": chart_type} if rows else None
    )

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
        handle_order_product_selection(prompt)
        return

    if st.session_state.order_flow == "awaiting_data":
        handle_order_data_received(prompt)
        return

    if st.session_state.order_flow == "awaiting_confirmation":
        handle_order_data_confirmation(prompt)
        return

    if st.session_state.order_flow == "multi_awaiting_selection":
        handle_multi_order_selection(prompt)
        return

    if st.session_state.order_flow == "multi_awaiting_data":
        handle_multi_order_data_received(prompt)
        return

    if st.session_state.order_flow == "multi_awaiting_confirmation":
        handle_multi_order_data_confirmation(prompt)
        return

    # --- Check if user is confirming an order ---
    history = st.session_state.messages[-8:] if st.session_state.messages else []
    order_intent = classify_order_intent(prompt, history=history)

    if order_intent == "ORDER_CONFIRMED":
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


def _detect_conversation_language() -> str:
    """Detects the language of the current conversation segment based on recent user messages.
    Returns 'es', 'en', or 'fr'.
    Prioritizes the most recent user messages heavily, since the user may switch languages mid-conversation.
    """
    user_messages = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if not user_messages:
        return "es"

    # English indicators
    en_words = ["i want", "yes", "please", "thank", "order", "how much", "what", "the", "my", "can i", "i'd like", "correct", "they're", "i wan"]
    # French indicators
    fr_words = ["je veux", "je voudrais", "je souhaite", "je prefere", "s'il vous", "merci", "combien", "bonjour", "oui", "commande", "ici mon", "va oui"]
    # Spanish indicators
    es_words = ["quiero", "por favor", "gracias", "cuanto", "dame", "ordenar", "necesito", "hola", "buenos dias", "opciones", "si"]

    # Only look at the last 4 user messages, with exponentially more weight to recent ones
    messages_to_check = user_messages[-4:]
    
    en_score = 0.0
    fr_score = 0.0
    es_score = 0.0

    for i, msg in enumerate(messages_to_check):
        msg_lower = msg.lower()
        
        # Skip messages that are purely data (contain @, lots of numbers, commas separating data)
        # These are customer data entries and don't indicate language
        if "@" in msg and "," in msg and any(c.isdigit() for c in msg):
            continue
        
        # Skip very short messages (< 8 chars) as they're usually confirmations
        if len(msg) < 8:
            continue

        # More recent messages get exponentially more weight
        # Last message = weight 8, second to last = 4, third = 2, fourth = 1
        recency_weight = 2 ** (i)

        en_count = sum(1 for w in en_words if w in msg_lower)
        fr_count = sum(1 for w in fr_words if w in msg_lower)
        es_count = sum(1 for w in es_words if w in msg_lower)

        en_score += en_count * recency_weight
        fr_score += fr_count * recency_weight
        es_score += es_count * recency_weight

    if en_score > fr_score and en_score > es_score:
        return "en"
    elif fr_score > en_score and fr_score > es_score:
        return "fr"
    return "es"


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
            from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
            lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
            total = sum(float(p["price"]) * p["quantity"] for p in products_found)
            products_summary = "\n".join(f"- {p['name']} ({p.get('laboratory', '')}) x{p['quantity']} = {float(p['price']) * p['quantity']:,.2f} COP" for p in products_found)
            try:
                msg = generate_content(
                    contents=(
                        f"The customer confirmed they want to order these products (identified from images):\n{products_summary}\n"
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
    
    # Use only messages after the last completed order, limited to 4
    if last_order_complete_idx >= 0:
        relevant_messages = all_messages[last_order_complete_idx + 1:]
    else:
        relevant_messages = all_messages
    
    history = relevant_messages[-4:] if relevant_messages else []

    with st.spinner("Processing your order..."):
        # First, check if this is a multi-product order
        multi_products = extract_multi_order_products(prompt, history=history)
        
        if multi_products and len(multi_products) > 1:
            # This is a multi-product order — route to multi-order flow
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
        response = sanitize_response(
            generate_data_collection_message(selected["name"], quantity, prompt, history=history, language=language)
        )

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
                handle_conversational(prompt)
            else:
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

    # Ask for customer data
    language = _detect_conversation_language()
    response = sanitize_response(
        generate_data_collection_message(selected["name"], quantity, prompt, history=history, language=language)
    )

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_order_data_received(prompt: str):
    """Handles when the user provides their personal data for the order."""
    # Check if the user wants to cancel the order
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it"]
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
    confirmation = classify_data_confirmation(prompt)

    if confirmation == "DATA_NOT_CONFIRMED":
        # Reset to awaiting_data so they can provide corrected info
        st.session_state.order_flow = "awaiting_data"
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        try:
            fallback = generate_content(
                contents=(
                    f"The customer said their data is NOT correct. Their message: \"{prompt}\"\n"
                    f"Ask them to send all their corrected data again (name, document type, document number, email, address, city, phone).\n"
                    f"Respond in the same language as the customer's message."
                ),
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION,
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else sanitize_response(
                "Understood. Please send me all your corrected data again:\n\n"
                "1. Full name\n2. Document type (CC, CE, Passport)\n3. Document number\n"
                "4. Email\n5. Full address\n6. City\n7. Phone number"
            )
        except Exception:
            response = sanitize_response(
                "Understood. Please send me all your corrected data again:\n\n"
                "1. Full name\n2. Document type (CC, CE, Passport)\n3. Document number\n"
                "4. Email\n5. Full address\n6. City\n7. Phone number"
            )
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
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it"]
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
    cancel_indicators = ["ya no", "no gracias", "cancelar", "cancel", "no quiero", "nevermind", "no thanks", "dejalo", "olvidalo", "forget it"]
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
    confirmation = classify_data_confirmation(prompt)

    if confirmation == "DATA_NOT_CONFIRMED":
        st.session_state.order_flow = "multi_awaiting_data"
        from app.services.ai_service import generate_content, RESPONSE_LANGUAGE_INSTRUCTION
        language = _detect_conversation_language()
        lang_instruction = {"en": "You MUST respond ENTIRELY in English.", "fr": "You MUST respond ENTIRELY in French.", "es": "You MUST respond ENTIRELY in Spanish."}.get(language, "You MUST respond ENTIRELY in Spanish.")
        try:
            fallback = generate_content(
                contents=f"The customer said their data is NOT correct. Ask them to send corrected data.\nLANGUAGE INSTRUCTION: {lang_instruction}",
                system_prompt="You are a friendly pharmacy assistant. Respond in plain text, no markdown. " + RESPONSE_LANGUAGE_INSTRUCTION + f"\n\n{lang_instruction}",
                temperature=0.7,
            )
            response = sanitize_response(fallback.strip()) if fallback else "Please send your corrected data."
        except Exception:
            response = "Please send your corrected data (name, document type, document number, email, address, city, phone)."
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
