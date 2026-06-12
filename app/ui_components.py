import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import uuid
import base64

from app.services.auth_service import (
    login_user,
    register_user,
    get_user_conversations,
    get_conversation_messages,
)
from app.services.db_service import execute_query


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
            from app.chat_handlers import handle_multi_image_query
            handle_multi_image_query(images_list, st.session_state.welcome_input)
            st.rerun()
        elif st.session_state.get("staged_image"):
            image_bytes = st.session_state.staged_image
            st.session_state.staged_image = None
            st.session_state.chat_started = True
            st.session_state.show_uploader = False
            from app.chat_handlers import handle_image_query
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
    for msg_index, message in enumerate(st.session_state.messages):
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
                    key=f"download_pdf_{msg_index}",
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
                        # Show "send by email" button for charts/tables
                        if message.get("offer_email") or chart_type != "NONE" or len(rows) > 1:
                            _render_send_report_button(message, sql, columns, rows, chart_type, msg_index)
                except Exception:
                    pass


def render_chart(df: pd.DataFrame, chart_type: str):
    """Renders a chart based on the classified type.
    Intelligently detects the best label (categorical) and value (numeric) columns.
    """
    if chart_type == "NONE" or df.empty or len(df.columns) < 2:
        return

    # Convert Decimal columns to float (psycopg2 returns Decimal for DECIMAL fields)
    for col in df.columns:
        if df[col].dtype == "object":
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass

    # --- Intelligent column selection ---
    # Priority for LABEL column (X axis): name > any string column > first non-id column
    # Priority for VALUE column (Y axis): quantity/total/sales/count/stock > price > any numeric non-id

    # Columns to always skip as value
    skip_as_value = set()
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in ("id", "products_id", "orders_id", "customers_id", "supplier_id", "category_id"):
            skip_as_value.add(col)
        elif col_lower.endswith("_id") or (col_lower == "id"):
            skip_as_value.add(col)

    # Find label column (categorical/name column for X axis)
    label_col = None
    label_priority = ["name", "product", "producto", "category", "status", "order_state", "laboratory", "supplier"]
    
    # First try: exact match on known label column names
    for preferred in label_priority:
        for col in df.columns:
            if col.lower() == preferred or col.lower().replace("_", "") == preferred:
                label_col = col
                break
        if label_col:
            break

    # Second try: first string/object column that isn't a long text field
    if label_col is None:
        for col in df.columns:
            if df[col].dtype == "object":
                # Skip description-like columns (average length > 50 chars)
                avg_len = df[col].astype(str).str.len().mean()
                if avg_len < 50:
                    label_col = col
                    break

    # Third try: first column that isn't numeric and isn't in skip list
    if label_col is None:
        for col in df.columns:
            if col not in skip_as_value and not pd.api.types.is_numeric_dtype(df[col]):
                label_col = col
                break

    # Last resort: first column
    if label_col is None:
        label_col = df.columns[0]

    # Find value column (numeric column for Y axis)
    value_col = None
    value_priority = ["total_sold", "total_quantity", "quantity", "total", "revenue", "sales",
                      "count", "actual_stock", "stock", "total_sales", "units_sold", "sum"]

    # First try: exact match on known value column names
    for preferred in value_priority:
        for col in df.columns:
            if col.lower() == preferred or col.lower().replace("_", "") == preferred:
                if pd.api.types.is_numeric_dtype(df[col]):
                    value_col = col
                    break
        if value_col:
            break

    # Second try: "price" if nothing better found
    if value_col is None:
        for col in df.columns:
            if col.lower() == "price" and pd.api.types.is_numeric_dtype(df[col]):
                value_col = col
                break

    # Third try: any numeric column that isn't an ID and isn't the label
    if value_col is None:
        for col in df.columns:
            if col == label_col or col in skip_as_value:
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                value_col = col
                break

    # Last resort
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
            fig = px.bar(chart_df, x=label_col, y=value_col)
            fig.update_layout(xaxis={'categoryorder': 'array', 'categoryarray': chart_df[label_col].tolist()})
            st.plotly_chart(fig, use_container_width=True, key=f"bar_{uuid.uuid4().hex[:8]}")
        elif chart_type == "LINE":
            fig = px.line(chart_df, x=label_col, y=value_col)
            fig.update_layout(xaxis={'categoryorder': 'array', 'categoryarray': chart_df[label_col].tolist()})
            st.plotly_chart(fig, use_container_width=True, key=f"line_{uuid.uuid4().hex[:8]}")
        elif chart_type == "PIE":
            fig = px.pie(chart_df, names=label_col, values=value_col)
            st.plotly_chart(
                fig, use_container_width=True, key=f"pie_{uuid.uuid4().hex[:8]}"
            )
    except Exception:
        # If chart rendering fails, silently skip — the data table is still shown
        pass



def _render_send_report_button(message: dict, sql: str, columns: list, rows: list, chart_type: str, msg_index: int):
    """Renders a '📧' button for sending this report via email. Uses deterministic key based on message index."""
    btn_key = f"send_report_{msg_index}"

    if st.button("📧", key=btn_key, help="Send via email / Enviar por email"):
        # Find the original user query that preceded this message
        messages = st.session_state.messages
        user_query = "Data report"
        if msg_index > 0:
            for i in range(msg_index - 1, -1, -1):
                if messages[i]["role"] == "user":
                    user_query = messages[i]["content"]
                    break

        st.session_state.last_report_data = {
            "query": user_query,
            "summary": message.get("content", ""),
            "columns": columns,
            "rows": rows,
            "chart_type": chart_type,
            "sql": sql,
            "language": _detect_conversation_language(),
        }
        st.session_state.report_email_flow = True
        st.rerun()


def _detect_conversation_language() -> str:
    """Detects the language of the current conversation segment based on recent user messages.
    Returns 'es', 'en', or 'fr'.
    Prioritizes the most recent user messages heavily, since the user may switch languages mid-conversation.
    """
    user_messages = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    if not user_messages:
        return "es"

    # English indicators
    en_words = ["i want", "show me", "top", "selling", "products", "give me", "best", "most", "which", "list", "send", "email", "please", "thank", "how much", "what is", "what are", "order by", "orders", "all products"]
    # French indicators
    fr_words = ["je veux", "je voudrais", "je souhaite", "s'il vous", "merci", "combien", "bonjour", "montrez", "envoyez", "les plus", "donnez", "tous les produits", "commandes"]
    # Spanish indicators
    es_words = ["quiero", "por favor", "gracias", "cuanto cuesta", "dame", "ordenar", "necesito", "hola", "buenos dias", "muestrame", "los mas", "productos mas", "vendidos", "enviar", "correo", "todos los productos"]

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
