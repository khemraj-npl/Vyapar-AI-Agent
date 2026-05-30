import sqlite3

DB_NAME = "memory.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def ensure_column(conn, table_name, column_name, column_type):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]

    if column_name not in columns:
        conn.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        )


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

    ensure_column(conn, "users", "city", "TEXT")
    ensure_column(conn, "users", "company_name", "TEXT")
    ensure_column(conn, "users", "phone", "TEXT")
    ensure_column(conn, "users", "package_interest", "TEXT")

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_connection()

    cursor = conn.execute(
        """
        SELECT user_id, name, business_type, last_topic, city, company_name, phone, package_interest
        FROM users
        WHERE user_id = ?
        """,
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
            "city": None,
            "company_name": None,
            "phone": None,
            "package_interest": None,
        }

    return {
        "user_id": row[0],
        "name": row[1],
        "business_type": row[2],
        "last_topic": row[3],
        "city": row[4],
        "company_name": row[5],
        "phone": row[6],
        "package_interest": row[7],
    }


def save_user_memory(
    user_id,
    name=None,
    business_type=None,
    last_topic=None,
    city=None,
    company_name=None,
    phone=None,
    package_interest=None,
):
    existing = get_user(user_id)

    name = name if name is not None else existing.get("name")
    business_type = business_type if business_type is not None else existing.get("business_type")
    last_topic = last_topic if last_topic is not None else existing.get("last_topic")
    city = city if city is not None else existing.get("city")
    company_name = company_name if company_name is not None else existing.get("company_name")
    phone = phone if phone is not None else existing.get("phone")
    package_interest = package_interest if package_interest is not None else existing.get("package_interest")

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO users (
            user_id, name, business_type, last_topic, city, company_name, phone, package_interest
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = excluded.name,
            business_type = excluded.business_type,
            last_topic = excluded.last_topic,
            city = excluded.city,
            company_name = excluded.company_name,
            phone = excluded.phone,
            package_interest = excluded.package_interest
        """,
        (
            str(user_id),
            name,
            business_type,
            last_topic,
            city,
            company_name,
            phone,
            package_interest,
        ),
    )

    conn.commit()
    conn.close()
