import streamlit as st
import plotly.express as px
import pandas as pd

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

# --- Page Config ---
st.set_page_config(
    page_title="AI Explorer - Farmacia", page_icon="💊", layout="centered"
)


def render_sidebar():
    """Renderiza el sidebar con título y botón de nuevo chat."""
    with st.sidebar:
        st.title("💊 AI Explorer")
        if st.button("New chat"):
            st.session_state.messages = []
            st.session_state.last_results = None
            st.rerun()


def render_chat_history():
    """Renderiza el historial de mensajes del chat."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def render_chart(df: pd.DataFrame, chart_type: str):
    """Renderiza un gráfico basado en el tipo clasificado."""
    if chart_type == "BAR":
        st.bar_chart(df.set_index(df.columns[0])[df.columns[1]])
    elif chart_type == "LINE":
        st.line_chart(df.set_index(df.columns[0])[df.columns[1]])
    elif chart_type == "PIE":
        fig = px.pie(df, names=df.columns[0], values=df.columns[1])
        st.plotly_chart(fig, use_container_width=True)


def render_last_results():
    """Renderiza los últimos resultados guardados (gráficos + tabla)."""
    if st.session_state.last_results is not None:
        data = st.session_state.last_results
        df = pd.DataFrame(data["rows"], columns=data["columns"])
        render_chart(df, data["chart_type"])
        st.dataframe(
            [dict(zip(data["columns"], row)) for row in data["rows"]],
            use_container_width=True,
        )


def handle_conversational(prompt: str):
    """Maneja preguntas conversacionales: responde con lenguaje natural + recomienda productos de la DB."""
    with st.chat_message("assistant"):
        with st.spinner("Searching for recommendations..."):
            # Paso 1: Generar SQL para buscar productos relevantes según síntomas
            products_data = []
            try:
                symptom_sql = generate_symptom_sql(prompt)
                is_valid, _ = validate_sql(symptom_sql)
                if is_valid:
                    columns, rows = execute_query(symptom_sql)
                    if rows:
                        products_data = [dict(zip(columns, row)) for row in rows]
            except Exception:
                # Si falla la búsqueda de productos, seguimos con respuesta conversacional pura
                pass

            # Paso 2: Generar respuesta con o sin productos
            if products_data:
                response = generate_conversational_with_products(prompt, products_data)
            else:
                response = generate_conversational_response(prompt)

        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.last_results = None


def handle_database_query(prompt: str):
    """Maneja preguntas que requieren consulta a la base de datos."""
    # Paso 1: Detectar si menciona un producto específico
    with st.spinner("Analyzing your question..."):
        try:
            product_term = extract_product_term(prompt)
        except Exception as e:
            st.error(f"Error analyzing your question: {e}")
            return

    selected_product = None

    # Paso 2: Si menciona un producto, buscar coincidencias en la DB
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

    # Paso 3: Generar SQL con contexto del producto exacto
    with st.spinner("Generating query..."):
        try:
            sql = generate_sql(prompt, selected_product)
        except Exception as e:
            st.error(f"Error generating SQL query: {e}")
            return

    # Paso 4: Validar que el SQL sea seguro
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        msg = f"⚠️ The generated query was rejected for safety: {error_msg}"
        st.error(msg)
        st.session_state.messages.append({"role": "assistant", "content": msg})
        return

    st.code(sql, language="sql")

    # Paso 5: Ejecutar la consulta
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

    # Guardar respuesta y resultados
    st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.session_state.last_results = (
        {"columns": columns, "rows": rows, "chart_type": chart_type}
        if rows
        else None
    )

    with st.chat_message("assistant"):
        st.markdown(response_text)


def main():
    # --- Inicializar estado ---
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Hi! I'm your personal assistant. Ask me anything about the price "
                    "of a medicine, an order, or a specific medication. You can also ask "
                    "general health questions like 'What's good for a headache?'"
                ),
            }
        ]

    if "last_results" not in st.session_state:
        st.session_state.last_results = None

    # --- Layout ---
    render_sidebar()

    st.title("Hi how can I help you?")
    st.subheader(
        "I'm your AI assistant for any question you have about our products"
    )

    render_chat_history()
    render_last_results()

    # --- Input del usuario ---
    if prompt := st.chat_input("Ask me anything about our pharmacy..."):
        # Mostrar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Paso 1: Clasificar intención
        with st.spinner("Understanding your question..."):
            try:
                intent = classify_intent(prompt)
            except Exception as e:
                st.error(f"Error classifying your question: {e}")
                return

        # Paso 2: Enrutar según intención
        if intent == "CONVERSATIONAL":
            handle_conversational(prompt)
        else:
            handle_database_query(prompt)


if __name__ == "__main__":
    main()
