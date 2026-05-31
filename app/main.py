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
    validate_sql,
)
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
            bottom: 85px !important;
            left: 50% !important;
            transform: translateX(calc(-50% + 171px)) !important;
            width: 704px !important;
            right: auto !important;
            padding: 0.5rem 0 !important;
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

    # Image preview (if an image is staged)
    if st.session_state.get("staged_image"):
        col_preview, col_remove = st.columns([5, 1])
        with col_preview:
            st.image(st.session_state.staged_image, width=150)
        with col_remove:
            if st.button("✕", key="remove_welcome_staged_image"):
                st.session_state.staged_image = None
                st.rerun()

    # Input row: clip on the left, text input on the right
    col_clip, col_input = st.columns([1, 12])
    with col_clip:
        if st.button("📎", key="welcome_attach_btn", help="Attach a medication image"):
            st.session_state.show_uploader = not st.session_state.get("show_uploader", False)
            st.rerun()
    with col_input:
        st.text_input(
            "Ask me anything about our pharmacy...",
            placeholder="Ask me anything about our pharmacy...",
            label_visibility="collapsed",
            key="welcome_input",
        )

    # File uploader appears only after clicking the clip button
    if st.session_state.get("show_uploader", False):
        uploaded = st.file_uploader(
            "Upload a medication image",
            type=["jpg", "jpeg", "png", "webp"],
            key="welcome_file_uploader",
        )
        if uploaded is not None and st.session_state.get("staged_image") is None:
            st.session_state.staged_image = uploaded.getvalue()
            st.session_state.show_uploader = False
            st.rerun()

    if st.session_state.welcome_input:
        if st.session_state.get("staged_image"):
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
            history = st.session_state.messages[-4:] if st.session_state.messages else []
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
                # Extract a search term from the analysis
                search_terms = image_analysis.lower().split()
                # Try the first meaningful word (usually the drug name)
                for term in search_terms:
                    if len(term) >= 4 and term not in [
                        "tablets",
                        "capsules",
                        "units",
                        "by",
                        "from",
                        "with",
                    ]:
                        matches = find_matching_products(term)
                        if matches:
                            # Get full product details
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


def on_chat_input_submit():
    """Callback for chat text_input. Moves the value to a pending buffer and clears the widget."""
    value = st.session_state.get("chat_text_input", "")
    if value:
        st.session_state.pending_chat_input = value
        st.session_state.chat_text_input = ""


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

    if "pending_chat_input" not in st.session_state:
        st.session_state.pending_chat_input = None

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
                    "Upload a medication image",
                    type=["jpg", "jpeg", "png", "webp"],
                    key="chat_file_uploader",
                )
                if uploaded is not None and st.session_state.get("staged_image") is None:
                    st.session_state.staged_image = uploaded.getvalue()
                    st.session_state.show_uploader = False
                    st.rerun()

        # Input area pinned to bottom via CSS on the container key
        with st.container(key="chat_input_container"):
            # Image preview (if an image is staged)
            if st.session_state.get("staged_image"):
                col_preview, col_remove = st.columns([5, 1])
                with col_preview:
                    st.image(st.session_state.staged_image, width=150)
                with col_remove:
                    if st.button("✕", key="remove_staged_image"):
                        st.session_state.staged_image = None
                        st.rerun()

            # Input row: clip on the left, text input on the right
            col_clip, col_input = st.columns([1, 12])
            with col_clip:
                if st.button("📎", key="chat_attach_btn", help="Attach a medication image"):
                    st.session_state.show_uploader = not st.session_state.get("show_uploader", False)
                    st.rerun()
            with col_input:
                st.text_input(
                    "Ask me anything about our pharmacy...",
                    placeholder="Ask me anything about our pharmacy...",
                    label_visibility="collapsed",
                    key="chat_text_input",
                    on_change=on_chat_input_submit,
                )

    # --- Process inputs captured from chat_text_input via callback ---
    if st.session_state.get("pending_chat_input"):
        prompt = st.session_state.pending_chat_input
        st.session_state.pending_chat_input = None
        if st.session_state.get("staged_image"):
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
