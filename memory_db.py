import sqlite3

DB_NAME = "memory.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)

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
