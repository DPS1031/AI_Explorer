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
    """Creates and returns a PostgreSQL connection."""
    return psycopg2.connect(**DB_CONFIG)


def run_migrations():
    """Runs necessary migrations to update the schema."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Ensure pg_trgm extension is available for fuzzy search
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        # Ensure images column in messages is TEXT (may have been VARCHAR(255))
        cur.execute("""
            ALTER TABLE messages ALTER COLUMN images TYPE TEXT;
        """)
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


# Run migrations on module load
run_migrations()


def execute_query(sql: str) -> tuple[list[str], list[tuple]]:
    """Executes a SQL SELECT query and returns (columns, rows)."""
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
    """Searches for products in the DB whose name matches the term.
    Uses PostgreSQL pg_trgm for fuzzy matching to handle language variations,
    typos, and alternate spellings (e.g. acetaminofen vs acetaminophen).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # First try exact partial match (fastest)
        cur.execute(
            "SELECT DISTINCT name FROM products WHERE LOWER(name) LIKE %s ORDER BY name",
            (f"%{term.lower()}%",),
        )
        results = [row[0] for row in cur.fetchall()]

        if results:
            cur.close()
            return results

        # If no exact match, use trigram similarity (fuzzy search)
        # This handles typos and language variations like acetaminofen -> Acetaminophen
        cur.execute(
            """SELECT DISTINCT name, similarity(LOWER(name), %s) as sim
               FROM products
               WHERE similarity(LOWER(name), %s) > 0.2
               ORDER BY sim DESC
               LIMIT 5""",
            (term.lower(), term.lower()),
        )
        results = [row[0] for row in cur.fetchall()]

        if results:
            cur.close()
            return results

        # Last resort: try prefix match with first 4 characters
        if len(term) >= 4:
            prefix = term.lower()[:4]
            cur.execute(
                "SELECT DISTINCT name FROM products WHERE LOWER(name) LIKE %s ORDER BY name",
                (f"%{prefix}%",),
            )
            results = [row[0] for row in cur.fetchall()]

        cur.close()
        return results
    finally:
        if conn:
            conn.close()
