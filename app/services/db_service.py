import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": 5432,
    "dbname": os.getenv("POSTGRES_DB"),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
}


def get_connection():
    """Crea y retorna una conexión a PostgreSQL."""
    return psycopg2.connect(**DB_CONFIG)


def execute_query(sql: str) -> tuple[list[str], list[tuple]]:
    """Ejecuta una consulta SQL SELECT y retorna (columns, rows)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        return columns, rows
    finally:
        if conn:
            conn.close()


def find_matching_products(term: str) -> list[str]:
    """Busca productos en la DB cuyo nombre coincida parcialmente con el término."""
    conn = None
    try:
        conn = get_connection()
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
