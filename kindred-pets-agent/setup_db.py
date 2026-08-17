"""
setup_db.py — Build kindred_pets.db from the raw .sql file.
Run once manually, or called automatically from app.py on first launch.
"""

import sqlite3
import os

SQL_FILE = os.path.join(os.path.dirname(__file__), "kindred_pets_business_data.sql")
DB_FILE  = os.path.join(os.path.dirname(__file__), "kindred_pets.db")


def build_database(sql_file: str = SQL_FILE, db_file: str = DB_FILE) -> None:
    """Create / overwrite kindred_pets.db by executing the .sql script."""
    if not os.path.exists(sql_file):
        raise FileNotFoundError(
            f"SQL source file not found: {sql_file}\n"
            "Make sure kindred_pets_business_data.sql is in the project root."
        )

    print(f"Building database at: {db_file}")
    with open(sql_file, "r", encoding="utf-8") as f:
        sql_script = f.read()

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(sql_script)
        conn.commit()
        print("✅ Database built successfully.")
    finally:
        conn.close()


def ensure_database() -> str:
    """
    Called at app startup.  If kindred_pets.db doesn't exist yet,
    build it from the .sql file and return the DB path.
    """
    if not os.path.exists(DB_FILE):
        print("DB not found — running first-time setup…")
        build_database()
    else:
        print(f"✅ DB already exists at: {DB_FILE}")
    return DB_FILE


if __name__ == "__main__":
    build_database()
