"""
db/retrievers.py
----------------
Pre-built, safe, read-only query helpers against the Shuddh Swad SQLite DB.

Why this layer exists:
- Free-hand LLM SQL is the #1 source of breakage in customer-support demos.
- For a sales demo, hitting the LLM with a giant schema dump is fragile.
- Instead, we expose a small set of typed helpers the LangGraph node can
  pick from deterministically. We also expose a *guarded* raw-SQL tool
  (run_safe_select) that the LLM may use only as a last-resort fallback
  for queries the helpers can't answer.

Safety:
- The raw SQL path REJECTS any statement that isn't a SELECT and that
  contains destructive keywords (INSERT, UPDATE, DELETE, DROP, ALTER,
  ATTACH, PRAGMA, etc.). Case-insensitive.
"""

from __future__ import annotations

import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

# ---------- DB path resolution --------------------------------------------

# Project root = parent of the `db/` directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "shuddh_swad.db")

# Keywords that should never appear in a query this layer will run.
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
    "ATTACH", "DETACH", "PRAGMA", "REPLACE", "TRUNCATE",
    "CREATE", "RENAME", "VACUUM", "REINDEX",
)

_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Allow only single-statement SELECTs (no semicolons separating other cmds).
_MULTISTATEMENT_RE = re.compile(r";\s*\S", re.DOTALL)


# ---------- Connection helper ---------------------------------------------

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a read-only SQLite connection. Use one connection per call site."""
    path = db_path or DEFAULT_DB_PATH
    # uri=True with mode=ro gives us OS-level read-only; defense in depth.
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows) -> List[Dict[str, Any]]:
    return [{k: row[k] for k in row.keys()} for row in rows]


# ---------- Safety guard --------------------------------------------------

def _is_safe_select(sql: str) -> tuple[bool, str]:
    """Return (ok, reason). If not ok, reason explains why."""
    if not sql or not sql.strip():
        return False, "Empty query."

    # Strip leading whitespace and SQL comments for the leading-token check
    stripped = sql.strip()
    # Allow a leading WITH ... SELECT (CTE) or plain SELECT
    if not re.match(r"^\s*(SELECT|WITH)\b", stripped, re.IGNORECASE):
        return False, "Only SELECT/WITH queries are allowed."

    if _FORBIDDEN_RE.search(stripped):
        # Find which one for a useful error
        m = _FORBIDDEN_RE.search(stripped)
        bad = m.group(0) if m else "?"
        return False, f"Disallowed keyword detected: {bad.upper()}."

    if _MULTISTATEMENT_RE.search(stripped.rstrip(";")):
        return False, "Multiple statements are not allowed."

    # Cap row count to be polite even on wide SELECTs
    if not re.search(r"\bLIMIT\b", stripped, re.IGNORECASE):
        # add implicit LIMIT; rewrite is done in run_safe_select
        pass

    return True, "ok"


# ---------- Pre-built retriever functions --------------------------------

def get_company_info(db_path: Optional[str] = None) -> Dict[str, Any]:
    """Return the single company_info row (brand, contact, socials, etc.)."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM company_info LIMIT 1")
        row = cur.fetchone()
        if row is None:
            return {}
        return {k: row[k] for k in row.keys()}
    finally:
        conn.close()


def get_all_products(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """All products with their variants inlined. Used for 'show me everything'."""
    products = _fetch_products(db_path)
    for p in products:
        p["variants"] = get_variants_for_product(p["id"], db_path)
    return products


def _fetch_products(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, name, slug, url, category, description,
                   shelf_life_days, storage_instructions, shipping_info,
                   preservatives, rating, rating_count, units_sold,
                   review_count, base_price_inr, mrp_inr, discount_pct,
                   primary_image_url
            FROM products
            ORDER BY id
            """
        )
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_variants_for_product(product_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            SELECT id, product_id, variant_label, weight_grams,
                   price_inr, savings_inr, is_best_seller, availability
            FROM product_variants
            WHERE product_id = ?
            ORDER BY weight_grams
            """,
            (product_id,),
        )
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_product_by_name(name: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fuzzy-ish product lookup. We do a LIKE match on name and category,
    case-insensitive. Returns a list because 'thekua' matches all variants.
    """
    conn = get_connection(db_path)
    try:
        like = f"%{name.strip()}%"
        cur = conn.execute(
            """
            SELECT id, name, slug, url, category, description,
                   shelf_life_days, storage_instructions, shipping_info,
                   preservatives, rating, rating_count, units_sold,
                   review_count, base_price_inr, mrp_inr, discount_pct,
                   primary_image_url
            FROM products
            WHERE LOWER(name) LIKE LOWER(?)
               OR LOWER(category) LIKE LOWER(?)
               OR LOWER(slug) LIKE LOWER(?)
            ORDER BY id
            """,
            (like, like, like),
        )
        products = _rows_to_dicts(cur.fetchall())
        for p in products:
            p["variants"] = get_variants_for_product(p["id"], db_path)
        return products
    finally:
        conn.close()


def get_product_by_id(product_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if row is None:
            return None
        out = {k: row[k] for k in row.keys()}
        out["variants"] = get_variants_for_product(product_id, db_path)
        return out
    finally:
        conn.close()


def get_reviews_for_product(product_id: int, limit: int = 5, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """
            SELECT reviewer_name, star_rating, review_text
            FROM product_reviews
            WHERE product_id = ?
            ORDER BY id
            LIMIT ?
            """,
            (product_id, limit),
        )
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_faqs(category: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """All FAQs, optionally filtered by category (case-insensitive contains)."""
    conn = get_connection(db_path)
    try:
        if category:
            like = f"%{category.strip()}%"
            cur = conn.execute(
                """
                SELECT id, category, question, answer
                FROM faqs
                WHERE LOWER(category) LIKE LOWER(?)
                   OR LOWER(question) LIKE LOWER(?)
                   OR LOWER(answer) LIKE LOWER(?)
                ORDER BY id
                """,
                (like, like, like),
            )
        else:
            cur = conn.execute("SELECT id, category, question, answer FROM faqs ORDER BY id")
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_marketplaces(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT marketplace_name, url FROM marketplaces ORDER BY id")
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_press_mentions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT publication, url FROM press_mentions ORDER BY id")
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


def get_site_pages(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("SELECT page_name, url FROM site_pages ORDER BY id")
        return _rows_to_dicts(cur.fetchall())
    finally:
        conn.close()


# ---------- The "last resort" raw SQL tool (LLM fallback only) ------------

def run_safe_select(sql: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Run a user/LLM-supplied SELECT against the DB. Returns a dict like:
        {"ok": True, "rows": [...], "columns": [...]}
    or
        {"ok": False, "error": "..."}.

    Used only as a last-resort path when the pre-built retrievers above
    don't fit. Always validates the SQL first.
    """
    ok, reason = _is_safe_select(sql)
    if not ok:
        return {"ok": False, "error": reason}

    # Implicit LIMIT for safety if the query didn't include one
    final_sql = sql.rstrip().rstrip(";")
    if not re.search(r"\bLIMIT\b", final_sql, re.IGNORECASE):
        final_sql = f"{final_sql} LIMIT 50"

    conn = get_connection(db_path)
    try:
        cur = conn.execute(final_sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        return {
            "ok": True,
            "columns": cols,
            "rows": _rows_to_dicts(rows),
            "row_count": len(rows),
        }
    except sqlite3.Error as e:
        return {"ok": False, "error": f"SQLite error: {e}"}
    finally:
        conn.close()


# ---------- Dispatcher used by the graph ---------------------------------

# Maps the classify_and_route label → the helper function(s) to call.
# Each entry is a list because some intents benefit from joining two helpers.
RETRIEVER_DISPATCH = {
    "product_info":   [("get_all_products", {})],
    "pricing":        [("get_all_products", {})],
    "faq_policy":     [("get_faqs", {}), ("get_company_info", {})],
    "order_tracking": [("get_company_info", {}), ("get_site_pages", {})],
    # greeting_smalltalk and out_of_scope don't hit the DB
}


def run_dispatch(query_type: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Given a query_type from classify_and_route, call the matching
    helpers and bundle the results under a single dict the LLM can
    consume in its system prompt context.
    """
    plan = RETRIEVER_DISPATCH.get(query_type, [])
    if not plan:
        return {}

    helpers = {
        "get_all_products": lambda **kw: get_all_products(db_path, **kw),
        "get_product_by_name": lambda **kw: None,  # routed by name below
        "get_faqs": lambda **kw: get_faqs(db_path=db_path, **kw),
        "get_company_info": lambda **kw: get_company_info(db_path, **kw),
        "get_marketplaces": lambda **kw: get_marketplaces(db_path, **kw),
        "get_press_mentions": lambda **kw: get_press_mentions(db_path, **kw),
        "get_site_pages": lambda **kw: get_site_pages(db_path, **kw),
    }

    out: Dict[str, Any] = {}
    for name, kwargs in plan:
        fn = helpers.get(name)
        if fn is None:
            continue
        try:
            out[name] = fn(**kwargs)
        except Exception as e:
            out[name] = {"error": str(e)}
    return out
