"""
graph/nodes.py
The four LangGraph node functions for the Kindred Pets AI Agent:
  1. classify_and_route  — classify intent + detect language
  2. retrieve_data       — fetch relevant DB context
  3. generate_response   — main LLM response generation
  4. format_and_guard    — final polish + link injection
"""

import json
import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, AIMessage

from db.retrievers import (
    get_all_products,
    get_product_by_name,
    get_products_by_category,
    get_categories,
    get_faqs,
    get_company_info,
    get_policies,
    get_policy,
    get_site_pages,
    search_products_by_tag,
    raw_sql_query,
)
from prompts.system_prompt import build_system_prompt

logger = logging.getLogger(__name__)

# ─── Injected at app startup ──────────────────────────────────────────────────
# We store the LLMFallbackManager instance here so all nodes share it.
_llm_manager = None


def set_llm_manager(manager) -> None:
    global _llm_manager
    _llm_manager = manager


# ─── Helper: convert LangChain messages → plain dicts for LLM calls ───────────

def _to_plain_messages(messages, last_n: int = 8) -> list:
    """
    Convert LangChain BaseMessage objects to plain {"role": ..., "content": ...} dicts.
    Keeps only the last `last_n` messages to stay within context limits.
    """
    plain = []
    for msg in messages[-last_n:]:
        if isinstance(msg, HumanMessage):
            plain.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            plain.append({"role": "assistant", "content": msg.content})
    return plain


# ─── NODE 1: classify_and_route ───────────────────────────────────────────────

CLASSIFY_SYSTEM = """You are a query classifier for a pet-store e-commerce chatbot.
Given a customer message, return a JSON object with exactly two keys:
  "query_type": one of ["product_info", "pricing", "recommendation",
                        "faq_policy", "order_tracking",
                        "greeting_smalltalk", "out_of_scope"]
  "language_style": one of ["english", "hindi", "hinglish"]

Definitions:
- product_info: questions about a specific product's features, materials, who it's for, reviews
- pricing: questions about price, discounts, sizes, variants, offers
- recommendation: "what should I get for my X" / "suggest something for my puppy"
- faq_policy: questions about shipping, returns, payment, delivery, store policies
- order_tracking: asking about a specific existing order status/location
- greeting_smalltalk: greetings, thanks, casual chat, "who are you"
- out_of_scope: nothing to do with pets, the store, or shopping

Language detection:
- hindi: message is in Devanagari script
- hinglish: message is in Roman script but mixing Hindi words (e.g. "bhai", "kya", "kutte", "bill", "rate")
- english: clearly English, no Hindi words

Return ONLY valid JSON, no explanation, no markdown.
"""


def classify_and_route(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Light LLM call to classify the query type and detect language.
    Uses the fastest available model since this is just classification.
    """
    user_query = state["user_query"]

    classify_messages = [{"role": "user", "content": user_query}]
    raw = _llm_manager.generate(
        system_prompt=CLASSIFY_SYSTEM,
        messages=classify_messages,
        max_tokens=80,
        temperature=0.0,
    )

    # Parse the JSON response (with fallback)
    try:
        # Strip markdown code fences if present
        clean = raw.strip().strip("```json").strip("```").strip()
        parsed = json.loads(clean)
        query_type = parsed.get("query_type", "out_of_scope")
        language_style = parsed.get("language_style", "english")
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"Classification parse failed on: {raw!r} — falling back to defaults")
        query_type = "greeting_smalltalk"
        language_style = "english"

    logger.info(f"Classified as: {query_type} | Language: {language_style}")

    return {
        "query_type": query_type,
        "detected_language_style": language_style,
    }


# ─── NODE 2: retrieve_data ────────────────────────────────────────────────────

# Simple pet-related keyword → category map (used for the recommendation path)
CATEGORY_KEYWORDS = {
    "toy": "Dog & Cat Toys",
    "play": "Dog & Cat Toys",
    "fetch": "Dog & Cat Toys",
    "ball": "Dog & Cat Toys",
    "laser": "Dog & Cat Toys",
    "chew": "Dog & Cat Toys",
    "walk": "Dog Walking Essentials",
    "leash": "Dog Walking Essentials",
    "collar": "Dog Walking Essentials",
    "harness": "Dog Walking Essentials",
    "treat pouch": "Dog Walking Essentials",
    "waste": "Dog Walking Essentials",
    "brush": "Grooming & Health",
    "shampoo": "Grooming & Health",
    "nail": "Grooming & Health",
    "ear": "Grooming & Health",
    "wipe": "Grooming & Health",
    "paw": "Grooming & Health",
    "groom": "Grooming & Health",
    "bed": "Pet Beds & Comfort",
    "mat": "Pet Beds & Comfort",
    "cushion": "Pet Beds & Comfort",
    "hammock": "Pet Beds & Comfort",
    "cat tree": "Pet Beds & Comfort",
    "scratch": "Pet Beds & Comfort",
    "nest": "Pet Beds & Comfort",
    "feeder": "Feeding & Litter Supplies",
    "bowl": "Feeding & Litter Supplies",
    "litter": "Feeding & Litter Supplies",
    "odor": "Feeding & Litter Supplies",
    "car seat": "Pet Travel & Outdoor Gear",
    "carrier": "Pet Travel & Outdoor Gear",
    "backpack": "Pet Travel & Outdoor Gear",
    "travel": "Pet Travel & Outdoor Gear",
    "splash": "Pet Travel & Outdoor Gear",
}


def _detect_product_keywords(text: str) -> list:
    """Extract product-like keywords from the user query for retrieval."""
    text_l = text.lower()
    # Common product nouns we want to match
    keywords = []
    for kw in [
        "laser", "ball launcher", "ball", "fetch", "chew", "squeak", "toy", "treat pouch",
        "collar", "leash", "harness", "waste scoop", "poop scoop",
        "nail grinder", "paw trimmer", "paw washer", "brush", "shampoo", "wipe",
        "ear cleanser", "ear cleaner", "tear stain",
        "memory foam", "bed", "cushion", "cat tree", "cat climber", "hammock",
        "cat tunnel", "cat nest", "cooling mat", "splash pad",
        "feeder", "smart feed", "slow feeder", "bowl", "litter", "odor",
        "car seat cover", "backpack", "carrier", "pawprint", "keepsake",
    ]:
        if kw in text_l:
            keywords.append(kw)
    return keywords


def retrieve_data(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fetch relevant data from the DB based on query_type.
    Uses pre-built retriever functions; falls back to raw SQL only if needed.
    """
    query_type    = state.get("query_type", "")
    user_query    = state.get("user_query", "").lower()
    retrieved     = ""

    if query_type == "product_info":
        # Try to find a specific product; fall back to listing all
        keywords = _detect_product_keywords(user_query)
        matched = keywords[0] if keywords else None
        if matched:
            retrieved = get_product_by_name(matched)
            if "No product found" in retrieved:
                # Try category-based search
                for cat_kw, cat_name in CATEGORY_KEYWORDS.items():
                    if cat_kw in user_query:
                        retrieved = get_products_by_category(cat_name) + "\n\n"
                        retrieved += get_all_products()
                        break
                else:
                    retrieved = get_all_products()
        else:
            retrieved = get_all_products()

    elif query_type == "pricing":
        # Pricing questions — show the catalog with variants
        retrieved = get_all_products()

    elif query_type == "recommendation":
        # Detect the most likely category from the user's natural language
        chosen_categories = []
        for cat_kw, cat_name in CATEGORY_KEYWORDS.items():
            if cat_kw in user_query and cat_name not in chosen_categories:
                chosen_categories.append(cat_name)

        if not chosen_categories:
            # Heuristic: puppy / dog → walking+toys ; cat → toys+bed
            if any(w in user_query for w in ["puppy", "dog", "pup"]):
                chosen_categories = ["Dog Walking Essentials", "Dog & Cat Toys"]
            elif any(w in user_query for w in ["kitten", "cat"]):
                chosen_categories = ["Pet Beds & Comfort", "Dog & Cat Toys"]
            else:
                chosen_categories = ["Dog & Cat Toys", "Pet Beds & Comfort"]

        cat_blocks = [get_products_by_category(c) for c in chosen_categories[:3]]
        retrieved = (
            f"=== RECOMMENDATION CANDIDATES ({', '.join(chosen_categories[:3])}) ===\n"
            + "\n\n".join(cat_blocks)
            + "\n\n=== FULL CATEGORIES LIST ===\n"
            + get_categories()
        )

    elif query_type == "faq_policy":
        # Figure out which FAQ category is most relevant
        if any(w in user_query for w in ["return", "refund", "damage", "broken", "support", "help", "defect"]):
            retrieved = get_faqs("Returns") + "\n\n" + get_policy("Returns")
        elif any(w in user_query for w in ["ship", "delivery", "cod", "payment", "pay", "charge", "tracking", "track", "ship"]):
            retrieved = get_faqs("Shipping") + "\n\n" + get_policy("Shipping")
        elif any(w in user_query for w in ["order", "place", "discount", "code", "coupon", "promo", "welcome"]):
            retrieved = get_faqs("Ordering")
        elif any(w in user_query for w in ["product", "quality", "material", "safe", "species", "dog and cat", "dog or cat"]):
            retrieved = get_faqs("Product")
        else:
            retrieved = get_faqs()   # all FAQs

        # Always include company contact info + relevant pages for FAQ responses
        retrieved += "\n\n=== CONTACT INFO ===\n" + get_company_info()
        retrieved += "\n\n=== STORE PAGES ===\n" + get_site_pages()

    elif query_type == "order_tracking":
        # No live order data in demo — fetch the tracking page URL + contact info
        pages = get_site_pages()
        contact = get_company_info()
        retrieved = (
            "=== ORDER TRACKING INFO ===\n"
            "This demo does not have access to live order data.\n"
            "Direct the customer to:\n"
            + pages + "\n\n" + contact
        )

    elif query_type == "out_of_scope":
        retrieved = (
            "[OUT OF SCOPE] The user's question is not related to Kindred Pets, pets, or shopping.\n"
            "Politely decline to answer this topic and redirect the customer to what you CAN help with "
            "(products, shipping, returns, recommendations for their pet).\n\n"
        ) + get_company_info()

    # For greeting_smalltalk: no retrieval needed (will be handled by generate_response)

    return {"retrieved_data": retrieved}


# ─── NODE 3: generate_response ────────────────────────────────────────────────

def generate_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main LLM call that produces the final user-facing response.
    Receives the system prompt (with injected retrieved data) + conversation history.
    """
    retrieved_data    = state.get("retrieved_data", "")
    language_style    = state.get("detected_language_style", "english")
    query_type        = state.get("query_type", "")
    messages          = state.get("messages", [])

    # Inject language hint into the system prompt
    lang_hint = {
        "hindi": "⚠️ REPLY IN HINDI (Devanagari script) — the user wrote in Hindi.",
        "hinglish": "⚠️ REPLY IN HINGLISH (Roman script, casual Hindi-English mix) — the user wrote in Hinglish.",
        "english": "Reply in English.",
    }.get(language_style, "Reply in English.")

    sys_prompt = build_system_prompt(retrieved_data) + f"\n\n{lang_hint}"

    # For smalltalk, we don't need context — just respond warmly
    if query_type == "greeting_smalltalk":
        sys_prompt = (
            "You are Kindred 🐾 — the friendly AI shopping assistant for Kindred Pets, "
            "an everyday-essentials store for dogs and cats. Be warm, brief, and use pet-related emojis sparingly. "
            "If the user greets you or chats casually, respond warmly and offer to help with products, "
            "shipping, returns, or recommendations.\n"
            + lang_hint
        )

    plain_messages = _to_plain_messages(messages)
    if not plain_messages:
        # Safety fallback
        plain_messages = [{"role": "user", "content": state.get("user_query", "")}]

    response_text = _llm_manager.generate(
        system_prompt=sys_prompt,
        messages=plain_messages,
        max_tokens=768,
        temperature=0.3,
    )

    return {
        "final_response": response_text,
        "llm_provider_used": _llm_manager.last_used,
    }


# ─── NODE 4: format_and_guard ────────────────────────────────────────────────

WEBSITE_LINK    = "https://kindred-pets-store.myshopify.com"
TRACK_LINK      = "https://kindred-pets-store.myshopify.com/pages/track-your-order"
CONTACT_LINK    = "https://kindred-pets-store.myshopify.com/pages/contact"
CATALOG_LINK    = "https://kindred-pets-store.myshopify.com/collections/all"
WELCOME_CODE    = "WELCOME15"


def format_and_guard(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-processing pass:
    (a) Appends relevant action links when appropriate.
    (b) Keeps the tone warm and concise.
    (c) For order tracking: ensures the tracking URL is present.
    Modifies final_response and appends it to the message history.
    """
    response    = state.get("final_response", "")
    query_type  = state.get("query_type", "")
    language    = state.get("detected_language_style", "english")

    # ── Append tracking link for order queries ────────────────────────────
    if query_type == "order_tracking" and TRACK_LINK not in response:
        suffix = {
            "hindi": f"\n\n📦 अपना ऑर्डर ट्रैक करें: {TRACK_LINK}",
            "hinglish": f"\n\n📦 Track karo yahan: {TRACK_LINK}",
            "english": f"\n\n📦 Track your order here: {TRACK_LINK}",
        }.get(language, f"\n\n📦 Track your order here: {TRACK_LINK}")
        response += suffix

    # ── Append contact nudge for support / return / damage / FAQ queries ──
    if query_type in ("faq_policy",) and CONTACT_LINK not in response:
        if any(w in response.lower() for w in ["contact", "support", "help", "reach"]):
            pass   # already mentioned — don't add duplicate
        else:
            suffix = {
                "hindi": f"\n\n💬 संपर्क करें: {CONTACT_LINK}",
                "hinglish": f"\n\n💬 Humse baat karo: {CONTACT_LINK}",
                "english": f"\n\n💬 Need more help? Contact us: {CONTACT_LINK}",
            }.get(language, f"\n\n💬 Contact us: {CONTACT_LINK}")
            response += suffix

    # ── Append catalog link + welcome code for product / pricing / rec queries ──
    if query_type in ("product_info", "pricing", "recommendation") and CATALOG_LINK not in response:
        suffix = {
            "hindi": f"\n\n🛒 पूरा कैटलॉग देखें: {CATALOG_LINK}\n🎁 पहले ऑर्डर पर 15% छूट: कोड {WELCOME_CODE}",
            "hinglish": f"\n\n🛒 Poora catalog dekho: {CATALOG_LINK}\n🎁 Pehle order pe 15% off: code {WELCOME_CODE}",
            "english": f"\n\n🛒 Browse the full catalog: {CATALOG_LINK}\n🎁 15% off your first order: code {WELCOME_CODE}",
        }.get(language, f"\n\n🛒 Browse the catalog: {CATALOG_LINK}\n🎁 15% off your first order: code {WELCOME_CODE}")
        response += suffix

    # ── Ensure response is never empty ────────────────────────────────────
    if not response.strip():
        response = (
            "Hmm, I didn't quite catch that 😅 Could you rephrase? "
            f"Or reach us anytime at {CONTACT_LINK}"
        )

    # ── Update message history with the final AI response ─────────────────
    new_ai_message = AIMessage(content=response)

    return {
        "final_response": response,
        "messages": [new_ai_message],  # will be appended via Annotated[List, operator.add]
    }
