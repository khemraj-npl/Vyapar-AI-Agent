from memory_db import DATABASE_URL, init_db

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully: {DATABASE_URL}")
