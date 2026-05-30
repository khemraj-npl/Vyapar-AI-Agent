import sqlite3

DB_NAME = "memory.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            business_type TEXT,
            last_topic TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT user_id, name, business_type, last_topic FROM users WHERE user_id = ?",
        (str(user_id),),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "user_id": str(user_id),
            "name": None,
            "business_type": None,
            "last_topic": None,
        }

    return {
        "user_id": row[0],
        "name": row[1],
        "business_type": row[2],
        "last_topic": row[3],
    }


def save_user_memory(user_id, name=None, business_type=None, last_topic=None):
    existing = get_user(user_id)

    name = name if name is not None else existing.get("name")
    business_type = business_type if business_type is not None else existing.get("business_type")
    last_topic = last_topic if last_topic is not None else existing.get("last_topic")

    conn = get_connection()
    conn.execute("""
        INSERT INTO users (user_id, name, business_type, last_topic)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = excluded.name,
            business_type = excluded.business_type,
            last_topic = excluded.last_topic
    """, (str(user_id), name, business_type, last_topic))
    conn.commit()
    conn.close()
