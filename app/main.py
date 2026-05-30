import streamlit as st
import plotly.express as px
import pandas as pd
import uuid

from app.services.ai_service import (
    classify_intent,
    generate_conversational_response,
    generate_conversational_with_products,
    generate_symptom_sql,
    extract_product_term,
    generate_sql,
    classify_chart_type,
    validate_sql,
)
from app.services.db_service import execute_query, find_matching_products
from app.services.auth_service import (
    login_user,
    register_user,
    get_user_conversations,
    create_conversation,
    update_conversation_title,
    save_message,
    get_conversation_messages,
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
        </style>
        """,
        unsafe_allow_html=True,
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

    # 1. Centered Input (replaces chat_input on the welcome screen)
    st.text_input(
        "Ask me anything about our pharmacy...",
        placeholder="Ask me anything about our pharmacy...",
        label_visibility="collapsed",
        key="welcome_input",
    )

    if st.session_state.welcome_input:
        st.session_state.input_to_process = st.session_state.welcome_input
        st.session_state.chat_started = True
        st.rerun()

    # Short spacer
    st.write("")

    # 2. Suggestion buttons below the input
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
    """Renders a chart based on the classified type."""
    if chart_type == "BAR":
        st.bar_chart(df.set_index(df.columns[0])[df.columns[1]])
    elif chart_type == "LINE":
        st.line_chart(df.set_index(df.columns[0])[df.columns[1]])
    elif chart_type == "PIE":
        fig = px.pie(df, names=df.columns[0], values=df.columns[1])
        st.plotly_chart(fig, use_container_width=True, key=f"pie_{uuid.uuid4().hex[:8]}")


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

            if products_data:
                response = generate_conversational_with_products(prompt, products_data)
            else:
                response = generate_conversational_response(prompt)

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_results = None

    # Persist response in DB
    if st.session_state.user and st.session_state.current_conversation_id:
        save_message(st.session_state.current_conversation_id, "assistant", response)


def handle_database_query(prompt: str):
    """Handles questions that require a database query."""
    with st.spinner("Analyzing your question..."):
        try:
            product_term = extract_product_term(prompt)
        except Exception as e:
            st.error(f"Error analyzing your question: {e}")
            return

    selected_product = None

    if product_term:
        matches = find_matching_products(product_term)

        if len(matches) == 0:
            msg = f"No products found matching '{product_term}'."
            st.warning(msg)
            st.session_state.messages.append({"role": "assistant", "content": msg})
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
            sql = generate_sql(prompt, selected_product)
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

        response_text = (
            f"I found {len(rows)} result(s) for your query.\n\n"
            "Is there anything else I can help you with? 😊"
        )
    else:
        if not response_text:
            response_text = "No results found for your query."
            st.info(response_text)

    st.session_state.messages.append({
        "role": "assistant",
        "content": response_text,
        "sql": sql if rows else None,
        "chart_type": chart_type if rows else None,
    })
    st.session_state.last_results = (
        {"columns": columns, "rows": rows, "chart_type": chart_type} if rows else None
    )

    # Persist response in DB (save SQL|||chart_type in the images field for re-execution)
    if st.session_state.user and st.session_state.current_conversation_id:
        metadata = f"{sql}|||{chart_type}" if rows else None
        save_message(
            st.session_state.current_conversation_id, "assistant", response_text,
            image=metadata
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

        # Streamlit's traditional chat_input ONLY appears when chat has started
        if prompt := st.chat_input("Ask me anything about our pharmacy..."):
            process_user_input(prompt)

    # --- Process inputs captured from the welcome screen (Suggestions or Central Input) ---
    if st.session_state.input_to_process:
        prompt_to_run = st.session_state.input_to_process
        st.session_state.input_to_process = None  # Clear buffer
        process_user_input(prompt_to_run)
        st.rerun()


if __name__ == "__main__":
    main()
