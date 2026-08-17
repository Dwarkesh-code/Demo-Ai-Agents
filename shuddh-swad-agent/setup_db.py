"""
setup_db.py
-----------
Builds shuddh_swad.db from shuddh_swad_business_data.sql.

Idempotent: if the DB file already exists, it does nothing unless
--force is passed. Safe to call on every app startup.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQL = os.path.join(PROJECT_ROOT, "shuddh_swad_business_data.sql")
DEFAULT_DB = os.path.join(PROJECT_ROOT, "shuddh_swad.db")


def build_db(sql_path: str = DEFAULT_SQL, db_path: str = DEFAULT_DB) -> None:
    if not os.path.exists(sql_path):
        print(f"[setup_db] SQL file not found: {sql_path}", file=sys.stderr)
        sys.exit(1)

    # The .sql file uses PRAGMA foreign_keys = ON which is connection-scoped
    # (it has no effect inside execute_script, but we honour it after open).
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"[setup_db] Removed existing {os.path.basename(db_path)}")

    conn = sqlite3.connect(db_path)
    try:
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # SQLite's executescript() handles multiple statements and the
        # CREATE/INSERT pairs in our dump. PRAGMA is allowed by executescript
        # because it parses/handles its own pragma statements.
        conn.executescript(sql_script)
        conn.commit()
        conn.execute("PRAGMA foreign_keys = ON")

        # Quick sanity check
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        print(f"[setup_db] Built {os.path.basename(db_path)} with tables: {', '.join(tables)}")

        cur = conn.execute("SELECT COUNT(*) FROM products")
        n_products = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) FROM faqs")
        n_faqs = cur.fetchone()[0]
        print(f"[setup_db] products: {n_products}, faqs: {n_faqs}")
    finally:
        conn.close()


def ensure_db(db_path: str = DEFAULT_DB, sql_path: str = DEFAULT_SQL) -> None:
    """Build the DB if it doesn't exist. Used by app.py at startup."""
    if not os.path.exists(db_path):
        print(f"[setup_db] {os.path.basename(db_path)} missing — building from SQL…")
        build_db(sql_path=sql_path, db_path=db_path)
    else:
        print(f"[setup_db] {os.path.basename(db_path)} already exists, skipping.")


def main():
    parser = argparse.ArgumentParser(description="Build shuddh_swad.db from the SQL dump.")
    parser.add_argument("--sql", default=DEFAULT_SQL, help="Path to the .sql file")
    parser.add_argument("--db",  default=DEFAULT_DB,  help="Path to the .db file to write")
    parser.add_argument("--force", action="store_true", help="Rebuild even if the .db exists")
    args = parser.parse_args()

    if args.force or not os.path.exists(args.db):
        build_db(sql_path=args.sql, db_path=args.db)
    else:
        print(f"[setup_db] {args.db} already exists. Pass --force to rebuild.")


if __name__ == "__main__":
    main()
