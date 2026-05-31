import hashlib
import os
import secrets
from app.services.db_service import get_connection


def hash_password(password: str) -> str:
    """Generates a secure password hash using SHA-256 with salt."""
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + pwd_hash.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a password against the stored hash."""
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return pwd_hash.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


def generate_session_token() -> str:
    """Generates a secure random session token."""
    return secrets.token_hex(32)


def get_user_by_id(user_id: int) -> dict | None:
    """Gets a user by their ID."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        return {"id": row[0], "name": row[1], "email": row[2], "created_at": row[3]}
    finally:
        if conn:
            conn.close()


def register_user(name: str, email: str, password: str) -> dict | None:
    """Registers a new user. Returns the created user or None if the email already exists."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            return None

        password_hashed = hash_password(password)
        cur.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id, name, email, created_at",
            (name, email, password_hashed),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()

        return {"id": row[0], "name": row[1], "email": row[2], "created_at": row[3]}
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def login_user(email: str, password: str) -> dict | None:
    """Authenticates a user. Returns user data or None on failure."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s",
            (email,),
        )
        row = cur.fetchone()
        cur.close()

        if not row:
            return None

        stored_hash = row[3]
        if not verify_password(password, stored_hash):
            return None

        return {"id": row[0], "name": row[1], "email": row[2], "created_at": row[4]}
    finally:
        if conn:
            conn.close()


def get_user_conversations(user_id: int) -> list[dict]:
    """Gets all conversations for a user, ordered by date."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, title, created_at FROM conversations 
               WHERE user_id = %s 
               ORDER BY created_at DESC""",
            (user_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]
    finally:
        if conn:
            conn.close()


def create_conversation(user_id: int, title: str | None = None) -> int:
    """Creates a new conversation for the user. Returns the ID."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, title),
        )
        conv_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        return conv_id
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def update_conversation_title(conversation_id: int, title: str):
    """Updates the title of a conversation."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE conversations SET title = %s WHERE id = %s",
            (title, conversation_id),
        )
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def save_message(conversation_id: int, sender: str, content: str, image: str | None = None):
    """Saves a message to the conversation."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO messages (sender, conversations_id, message_content, images) 
               VALUES (%s, %s, %s, %s)""",
            (sender, conversation_id, content, image),
        )
        conn.commit()
        cur.close()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def get_conversation_messages(conversation_id: int) -> list[dict]:
    """Gets all messages from a conversation."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT sender, message_content, images, created_at 
               FROM messages 
               WHERE conversations_id = %s 
               ORDER BY created_at ASC""",
            (conversation_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {"role": r[0], "content": r[1], "image": r[2], "created_at": r[3]}
            for r in rows
        ]
    finally:
        if conn:
            conn.close()
