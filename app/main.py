import streamlit as st
import os
import psycopg2
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from google import genai

st.set_page_config(
    page_title="AI Explorer - Farmacia", page_icon="💊", layout="centered"
)
st.title("Hi how can I help you?")
st.subheader("I'm your AI assistant for any question do you have about our products")

DDL = """
CREATE TABLE IF NOT EXISTS categories(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppliers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL
);
CREATE TABLE IF NOT EXISTS customers(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    contact_number VARCHAR(20) NOT NULL,
    address VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS products(
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    medication_dosage VARCHAR(255) NOT NULL,
    dosage_form VARCHAR(255) NOT NULL,
    laboratory VARCHAR(255) NOT NULL,
    indication_and_symptoms TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    supplier_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_indications_categories FOREIGN KEY (category_id) REFERENCES categories(id),
    CONSTRAINT fk_indications_supliers FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);
CREATE TABLE IF NOT EXISTS product_images(
    id SERIAL PRIMARY KEY,
    products_id INTEGER NOT NULL,
    image_url VARCHAR(500),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
);
CREATE TABLE IF NOT EXISTS inventory(
    id SERIAL PRIMARY KEY,
    actual_stock INTEGER NOT NULL DEFAULT 0,
    products_id INTEGER NOT NULL,
    minimum_stock INTEGER NOT NULL,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
    /*CONSTRAINT fk_updated_date_products FOREIGN KEY (products_last_update) REFERENCES products(updated_at)*/
);
CREATE TABLE IF NOT EXISTS orders(
    id SERIAL PRIMARY KEY,
    customers_id INTEGER,
    contact_email VARCHAR(255),
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_customers FOREIGN KEY (customers_id) REFERENCES customers(id),
    CHECK (
        order_state IN ('pending', 'confirmed', 'delivered', 'cancelled')
    )
);
CREATE TABLE IF NOT EXISTS order_items(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    products_id INTEGER NOT NULL,
    products_price DECIMAL(10, 2) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CONSTRAINT fk_id_products FOREIGN KEY (products_id) REFERENCES products(id)
    /*CONSTRAINT fk_price_products FOREIGN KEY (products_price) REFERENCES products(price),
     CONSTRAINT fk_stock_inventory FOREIGN KEY (inventory_stock) REFERENCES inventory(actual_stock)*/
);
CREATE TABLE IF NOT EXISTS order_status_history(
    id SERIAL PRIMARY KEY,
    orders_id INTEGER NOT NULL,
    order_state VARCHAR(255) NOT NULL DEFAULT 'pending',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    note TEXT,
    CONSTRAINT fk_id_orders FOREIGN KEY (orders_id) REFERENCES orders(id),
    CHECK (
        order_state IN ('pending', 'confirmed', 'delivered', 'cancelled')
    )
    /*CONSTRAINT fk_state_orders FOREIGN KEY (orders_state) REFERENCES orders(order_state), 
     CONSTRAINT fk_update_orders FOREIGN KEY (orders_update) REFERENCES orders(updated_at)*/
);

CREATE TABLE IF NOT EXISTS conversations(
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NULL,
    costumers_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_costumers FOREIGN KEY (costumers_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS messages(
    id SERIAL PRIMARY KEY,
    sender VARCHAR(255) NOT NULL,
    conversations_id INTEGER NOT NULL,
    message_content TEXT,
    images VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_id_conversation FOREIGN KEY (conversations_id) REFERENCES conversations(id),
    CHECK (
        sender IN ('assistant', 'user')
    )
);
"""
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": 5432,
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}

SYSTEM_PROMPT = f"""Eres un asistente experto en SQL para PostgreSQL.
Tu única tarea es generar consultas SQL SELECT válidas basándote en el siguiente DDL:

{DDL}

Reglas:
- Solo genera consultas SELECT (nunca INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
- Responde ÚNICAMENTE con la consulta SQL, sin explicaciones ni markdown.
- No uses comillas de código ni backticks en tu respuesta.
- Las tablas donde debes hacer las consultas se llaman categories, suppliers, customers, products, product_images, inventory, orders, order_items, order_status_history, conversations, messages.
- Cuando filtres por nombre de producto, usa SIEMPRE el nombre EXACTO que se te proporcione entre comillas.
"""

EXTRACT_PRODUCT_PROMPT = f"""Eres un asistente que analiza preguntas sobre ventas de una farmacia.
Dada la siguiente pregunta del usuario, determina si la pregunta hace referencia a un producto específico.

Si la pregunta menciona un producto (o parte de su nombre), responde ÚNICAMENTE con el término de búsqueda del producto, sin explicaciones.
Si la pregunta NO hace referencia a un producto específico (ej: "top 5 productos", "total de ventas del mes"), responde ÚNICAMENTE con: NONE

Ejemplos:
- "¿Cuánto se vendió de ibuprofeno?" -> ibuprofeno
- "ventas de paracetamol" -> paracetamol
- "¿Cuáles son los 5 productos más vendidos?" -> NONE
- "total de ventas del último mes" -> NONE
- "muéstrame las ventas de vitamina d3" -> vitamina d3
"""

CHART_CLASSIFICATION_PROMPT = """You are a data visualization expert for a pharmacy system.
Given a user question, determine if the results would benefit from a chart.

Rules:
- Respond ONLY with one word: BAR, LINE, PIE, or NONE
- BAR: rankings, comparisons, top N products, quantities by category
- LINE: trends over time, sales evolution, monthly/weekly data
- PIE: distributions, percentages, proportions of a whole
- NONE: single values, prices, specific product info, yes/no questions

Examples:
- "top 10 best selling products" -> BAR
- "sales trend over the last 6 months" -> LINE
- "distribution of products by category" -> PIE
- "what is the price of ibuprofen" -> NONE
- "how many units of amoxicillin do we have" -> NONE
- "orders by status" -> PIE
- "monthly revenue this year" -> LINE
- "which supplier has most products" -> BAR
"""


def get_gemini_client():
    """Crea el cliente de Gemini."""
    return genai.Client()


def extract_product_term(prompt: str) -> str | None:
    """Extrae el término de producto de la pregunta del usuario, o None si no aplica."""
    client = get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"{EXTRACT_PRODUCT_PROMPT}\n\nPregunta del usuario: {prompt}",
    )
    result = response.text
    if result is None:
        return None
    result = result.strip()
    if result.upper() == "NONE":
        return None
    return result


def find_matching_products(term: str) -> list[str]:
    """Busca productos en la DB cuyo nombre coincida parcialmente con el término."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT name FROM products WHERE LOWER(name) LIKE %s ORDER BY name",
            (f"%{term.lower()}%",),
        )
        results = [row[0] for row in cur.fetchall()]
        cur.close()
        return results
    finally:
        if conn:
            conn.close()


def generate_sql(prompt: str, product_name: str | None = None) -> str:
    """Envía el prompt a Gemini y obtiene una consulta SQL."""
    client = get_gemini_client()

    context = SYSTEM_PROMPT
    if product_name:
        context += f'\n\nIMPORTANTE: El usuario se refiere al producto exacto: "{product_name}". Usa este nombre exacto en el WHERE.'

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"{context}\n\nPregunta del usuario: {prompt}",
    )
    sql = response.text
    if sql is None:
        raise ValueError("Gemini no devolvió una respuesta")
    return sql.strip()


def classify_chart_type(prompt: str) -> str:
    client = get_gemini_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"{CHART_CLASSIFICATION_PROMPT}\n\nUser question: {prompt}",
    )
    result = response.text
    if result is None:
        return "NONE"
    result = result.strip().upper()
    if result not in ["BAR", "LINE", "PIE"]:
        return "NONE"
    return result


def execute_query(sql: str):
    """Ejecuta una consulta SQL y retorna los resultados."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return columns, rows
    finally:
        if conn:
            conn.close()


def friendly_wrap(raw_text: str) -> str:
    return f"{raw_text.strip()}\n\n" "Is there anything else I can help you with? 😊"


def main():

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hi! I'm your personal assistant. Ask me anything about the price of a medicin, an order, or an especific medication. you can say 'I need a pill for the headache'",
            }
        ]

    if "last_results" not in st.session_state:
        st.session_state.last_results = None

    with st.sidebar:
        st.title("💊 AI Explorer")
        if st.button("New chat"):
            st.session_state.messages = []
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.last_results is not None:
        data = st.session_state.last_results
        df = pd.DataFrame(data["rows"], columns=data["columns"])
        if data["chart_type"] == "BAR":
            st.bar_chart(df.set_index(df.columns[0])[df.columns[1]])
        elif data["chart_type"] == "LINE":
            st.line_chart(df.set_index(df.columns[0])[df.columns[1]])
        elif data["chart_type"] == "PIE":
            fig = px.pie(df, names=df.columns[0], values=df.columns[1])
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            [dict(zip(data["columns"], row)) for row in data["rows"]],
            use_container_width=True,
        )

    if prompt := st.chat_input("Ask me anything about our pharmacy..."):
        # Anotar mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Mostrar mensaje del usuario inmediatamente
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.write("🤔 Thinking...")
        # Paso 1: Detectar si la pregunta menciona un producto
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
                st.warning(f"No products found matching '{product_term}'.")
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
        with st.spinner("Generating SQL query..."):
            try:
                sql = generate_sql(prompt, selected_product)
                st.code(sql, language="sql")
            except Exception as e:
                st.error(f"Error generating SQL query: {e}")
                return

        # Paso 4: Ejecutar la consulta
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

            if chart_type == "BAR":
                st.bar_chart(df.set_index(df.columns[0])[df.columns[1]])
            elif chart_type == "LINE":
                st.line_chart(df.set_index(df.columns[0])[df.columns[1]])
            elif chart_type == "PIE":
                fig = px.pie(df, names=df.columns[0], values=df.columns[1])
                st.plotly_chart(fig, use_container_width=True)

            response_text = friendly_wrap(
                f"I found {len(rows)} result(s) for your query."
            )
        else:
            if not response_text:  # solo si no hubo error antes
                st.info("No results found for your query.")
                response_text = "No results found for your query."

        # Anotar respuesta del asistente
        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )
        st.session_state.last_results = (
            {"columns": columns, "rows": rows, "chart_type": chart_type}
            if rows
            else None
        )

        with st.chat_message("assistant"):
            st.markdown(response_text)

        st.rerun()


if __name__ == "__main__":
    main()
