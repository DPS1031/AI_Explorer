import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def _get_db_config() -> dict | str:
    """Returns connection config. Prefers DATABASE_URL if set (for RDS/production)."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


def get_connection():
    """Creates and returns a PostgreSQL connection."""
    config = _get_db_config()
    if isinstance(config, str):
        return psycopg2.connect(config)
    return psycopg2.connect(**config)


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
            # If the search term has multiple words (e.g., "Vitamina C"), filter results
            # to only include products that match ALL words, not just any word.
            # This prevents "Vitamina C" from matching "Vitamina D3".
            if " " in term.strip():
                words = term.lower().split()
                filtered = []
                for r in results:
                    r_lower = r.lower()
                    r_words = r_lower.split()
                    match_all = True
                    for w in words:
                        if len(w) <= 2:
                            # Short words (like "C", "D3") must appear as whole words
                            # to avoid "c" matching as substring of "vitamina"
                            if w not in r_words:
                                match_all = False
                                break
                        else:
                            # Longer words can match as substrings
                            if w not in r_lower:
                                match_all = False
                                break
                    if match_all:
                        filtered.append(r)
                if filtered:
                    cur.close()
                    return filtered
            cur.close()
            return results

        # If no exact match, try common cross-language name variations
        # This handles cases like "vitamina c" (Spanish) -> "Vitamin C" (English in DB)
        cross_lang_map = {
            "vitamina": "vitamin",
            "vitamin": "vitamina",
            "acetaminofen": "acetaminophen",
            "acetaminophen": "acetaminofen",
            "ibuprofeno": "ibuprofen",
            "ibuprofen": "ibuprofeno",
            "amoxicilina": "amoxicillin",
            "amoxicillin": "amoxicilina",
            "loratadina": "loratadine",
            "loratadine": "loratadina",
            "cetirizina": "cetirizine",
            "cetirizine": "cetirizina",
            "naproxeno": "naproxen",
            "naproxen": "naproxeno",
        }
        term_lower = term.lower()
        for original, replacement in cross_lang_map.items():
            if original in term_lower:
                alt_term = term_lower.replace(original, replacement)
                cur.execute(
                    "SELECT DISTINCT name FROM products WHERE LOWER(name) LIKE %s ORDER BY name",
                    (f"%{alt_term}%",),
                )
                alt_results = [row[0] for row in cur.fetchall()]
                if alt_results:
                    # Apply multi-word filtering for the alternative term
                    if " " in alt_term.strip():
                        alt_words = alt_term.split()
                        filtered = []
                        for r in alt_results:
                            r_lower = r.lower()
                            r_words = r_lower.split()
                            match_all = True
                            for w in alt_words:
                                if len(w) <= 2:
                                    if w not in r_words:
                                        match_all = False
                                        break
                                else:
                                    if w not in r_lower:
                                        match_all = False
                                        break
                            if match_all:
                                filtered.append(r)
                        if filtered:
                            cur.close()
                            return filtered
                    cur.close()
                    return alt_results

        # If no exact match, try each word individually for partial match
        # This handles cross-language cases like "vitamina C" matching "Vitamin C"
        words = term.lower().split()
        if len(words) > 1:
            # Find products that match ALL significant words (length >= 2)
            # For "vitamina C" -> search products containing both something like "vitamin" AND "c" as a word
            significant_words = sorted([w for w in words if len(w) >= 2], key=len, reverse=True)
            short_words = [w for w in words if len(w) == 1]  # Single character words like "c"
            
            if significant_words:
                # Search by the longest word first (most specific)
                primary_word = significant_words[0]
                # Use trigram for the primary word to handle language variations
                cur.execute(
                    """SELECT DISTINCT name, similarity(LOWER(name), %s) as sim
                       FROM products
                       WHERE similarity(LOWER(name), %s) > 0.3
                       ORDER BY sim DESC
                       LIMIT 10""",
                    (primary_word, primary_word),
                )
                candidates = [row[0] for row in cur.fetchall()]
                
                if candidates:
                    # Filter candidates by other significant words AND short words
                    filtered = []
                    for candidate in candidates:
                        candidate_lower = candidate.lower()
                        # Check significant words (len >= 2) as substrings
                        sig_match = all(w in candidate_lower for w in significant_words[1:])
                        # Check short words (len == 1) as whole words (surrounded by spaces or at boundaries)
                        short_match = True
                        for sw in short_words:
                            # Check if the single char appears as a separate word in the name
                            candidate_words = candidate_lower.split()
                            if sw not in candidate_words:
                                short_match = False
                                break
                        if sig_match and short_match:
                            filtered.append(candidate)
                    if filtered:
                        cur.close()
                        return filtered
                
                # If filtering removed everything but we have candidates, return best match only
                if candidates:
                    cur.close()
                    return candidates[:1]

        # If no exact match, use trigram similarity (fuzzy search)
        # This handles typos and language variations like acetaminofen -> Acetaminophen
        cur.execute(
            """SELECT DISTINCT name, similarity(LOWER(name), %s) as sim
               FROM products
               WHERE similarity(LOWER(name), %s) > 0.3
               ORDER BY sim DESC
               LIMIT 3""",
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
