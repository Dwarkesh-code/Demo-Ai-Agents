"""
db/retrievers.py
Pre-built query functions for the Kindred Pets SQLite database.
The LangGraph retrieve_data node calls these instead of letting the LLM
freehand SQL every time — more reliable for a demo.

Also provides a guarded raw-SQL fallback for edge-case queries.
"""

import sqlite3
import json
import re
from typing import Optional, List

# Path is resolved at call time via set_db_path()
_DB_PATH: Optional[str] = None


def set_db_path(path: str) -> None:
    """Called once at startup (from app.py) so retrievers know where the DB is."""
    global _DB_PATH
    _DB_PATH = path


def _get_conn() -> sqlite3.Connection:
    if not _DB_PATH:
        raise RuntimeError("DB path not set. Call set_db_path() first.")
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── READ-ONLY GUARD ────────────────────────────────────────────────────────

_FORBIDDEN = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA|CREATE|REPLACE|TRUNCATE)\b',
    re.IGNORECASE
)


def _safe_query(sql: str) -> str:
    """
    Run a raw SQL query only if it passes the read-only guard.
    Returns JSON-serialized results or an error string.
    """
    if _FORBIDDEN.search(sql):
        return "⚠️ Query rejected: only SELECT statements are allowed."
    try:
        conn = _get_conn()
        cur = conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return json.dumps(rows, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"SQL error: {e}"


# ─── PRE-BUILT RETRIEVERS ────────────────────────────────────────────────────

def get_company_info() -> str:
    """Returns brand details, contact info, social links, promo codes."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM company_info LIMIT 1").fetchone()
    conn.close()
    if not row:
        return "Company info not found."
    d = dict(row)
    return (
        f"Brand: {d['brand_name']}\n"
        f"Tagline: {d['tagline']}\n"
        f"Description: {d['description']}\n"
        f"Website: {d['website_url']}\n"
        f"Welcome Code: {d['welcome_code']} — {d['welcome_discount']}\n"
        f"Support Hours: {d['support_hours']}\n"
        f"Contact: {d['address']}\n"
        f"Founded Story: {d['founded_story']}\n"
    )


def get_all_products() -> str:
    """Returns all products with their variants (colors, sizes + prices)."""
    conn = _get_conn()
    products = conn.execute(
        "SELECT id, name, slug, url, category, description, product_type, tags, "
        "primary_image_url, base_price_usd, mrp_usd "
        "FROM products WHERE is_active = 1 ORDER BY name"
    ).fetchall()

    result = []
    for p in products:
        p = dict(p)
        variants = conn.execute(
            "SELECT variant_label, sku, price_usd, in_stock, availability "
            "FROM product_variants WHERE product_id = ? "
            "ORDER BY price_usd, variant_label",
            (p["id"],)
        ).fetchall()
        if not variants:
            variants_text = "    (no variants)"
        else:
            variants_text = "\n".join([
                f"    • {v['variant_label']}: ${v['price_usd']:.2f} — {v['availability']}"
                for v in variants[:8]   # cap to top 8 variants per product to stay readable
            ])
            if len(variants) > 8:
                variants_text += f"\n    • … and {len(variants) - 8} more variants on the product page"
        result.append(
            f"🐾 {p['name']}\n"
            f"  URL: {p['url']}\n"
            f"  Category: {p['category']} | Type: {p['product_type']}\n"
            f"  Description: {p['description']}\n"
            f"  Base Price: ${p['base_price_usd']:.2f} (MRP ${p['mrp_usd']:.2f})\n"
            f"  Variants:\n{variants_text}\n"
        )
    conn.close()
    return "\n".join(result)


def get_product_by_name(name: str) -> str:
    """Fuzzy-search a product by name (case-insensitive, partial match)."""
    conn = _get_conn()
    products = conn.execute(
        "SELECT id, name, slug, url, category, description, product_type, tags, "
        "primary_image_url, base_price_usd, mrp_usd "
        "FROM products WHERE LOWER(name) LIKE ? AND is_active = 1",
        (f"%{name.lower()}%",)
    ).fetchall()

    if not products:
        return f"No product found matching '{name}'."

    result = []
    for p in products:
        p = dict(p)
        variants = conn.execute(
            "SELECT variant_label, sku, price_usd, in_stock, availability "
            "FROM product_variants WHERE product_id = ? "
            "ORDER BY price_usd, variant_label",
            (p["id"],)
        ).fetchall()
        if not variants:
            variants_text = "    (no variants)"
        else:
            variants_text = "\n".join([
                f"    • {v['variant_label']}: ${v['price_usd']:.2f} — {v['availability']}"
                for v in variants[:10]
            ])
            if len(variants) > 10:
                variants_text += f"\n    • … and {len(variants) - 10} more variants"
        result.append(
            f"🐾 {p['name']}\n"
            f"  URL: {p['url']}\n"
            f"  Category: {p['category']} | Type: {p['product_type']}\n"
            f"  Description: {p['description']}\n"
            f"  Base Price: ${p['base_price_usd']:.2f} (MRP ${p['mrp_usd']:.2f})\n"
            f"  Variants:\n{variants_text}\n"
        )
    conn.close()
    return "\n".join(result)


def get_products_by_category(category: str) -> str:
    """Returns products filtered by collection / category."""
    conn = _get_conn()
    products = conn.execute(
        "SELECT id, name, url, category, base_price_usd FROM products "
        "WHERE LOWER(category) LIKE ? AND is_active = 1 ORDER BY name",
        (f"%{category.lower()}%",)
    ).fetchall()
    conn.close()
    if not products:
        return f"No products found in category '{category}'."
    lines = []
    for p in products:
        lines.append(f"• {p['name']} — from ${p['base_price_usd']:.2f} | {p['url']}")
    return f"Products in '{category}':\n" + "\n".join(lines)


def get_categories() -> str:
    """Returns all store categories / collections with descriptions."""
    conn = _get_conn()
    rows = conn.execute("SELECT name, description FROM categories ORDER BY name").fetchall()
    conn.close()
    return "\n".join([f"• {r['name']}: {r['description']}" for r in rows])


def get_faqs(category: Optional[str] = None) -> str:
    """
    Returns FAQ entries, optionally filtered by category.
    Known categories: 'Product & Quality', 'Ordering & Payment',
                      'Shipping & Delivery', 'Returns & Refunds',
                      'Customer Support'
    """
    conn = _get_conn()
    if category:
        rows = conn.execute(
            "SELECT category, question, answer FROM faqs "
            "WHERE LOWER(category) LIKE ? ORDER BY id",
            (f"%{category.lower()}%",)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT category, question, answer FROM faqs ORDER BY id"
        ).fetchall()
    conn.close()

    if not rows:
        return "No FAQs found."
    return "\n".join([
        f"[{r['category']}]\nQ: {r['question']}\nA: {r['answer']}\n"
        for r in rows
    ])


def get_policies() -> str:
    """Returns all store policies (shipping, returns, privacy, terms, promo)."""
    conn = _get_conn()
    rows = conn.execute("SELECT name, description FROM policies ORDER BY id").fetchall()
    conn.close()
    return "\n\n".join([f"📜 {r['name']}:\n{r['description']}" for r in rows])


def get_policy(policy_name: str) -> str:
    """Returns a single policy by partial name match."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT name, description FROM policies WHERE LOWER(name) LIKE ?",
        (f"%{policy_name.lower()}%",)
    ).fetchall()
    conn.close()
    if not rows:
        return f"No policy found matching '{policy_name}'."
    return "\n\n".join([f"📜 {r['name']}:\n{r['description']}" for r in rows])


def get_site_pages() -> str:
    """Returns key site page URLs (useful for directing users)."""
    conn = _get_conn()
    rows = conn.execute("SELECT page_name, url FROM site_pages ORDER BY id").fetchall()
    conn.close()
    return "\n".join([f"• {r['page_name']}: {r['url']}" for r in rows])


def search_products_by_tag(tag: str) -> str:
    """Fuzzy search products by tag keyword (e.g. 'waterproof', 'cat toy')."""
    conn = _get_conn()
    products = conn.execute(
        "SELECT name, url, base_price_usd, tags FROM products "
        "WHERE LOWER(tags) LIKE ? AND is_active = 1 ORDER BY name",
        (f"%{tag.lower()}%",)
    ).fetchall()
    conn.close()
    if not products:
        return f"No products matched the tag '{tag}'."
    return "\n".join([
        f"• {p['name']} — from ${p['base_price_usd']:.2f} | {p['url']}"
        for p in products
    ])


def raw_sql_query(sql: str) -> str:
    """Fallback: run an arbitrary read-only SELECT query."""
    return _safe_query(sql)
