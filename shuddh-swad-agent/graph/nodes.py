"""
graph/nodes.py
--------------
The four LangGraph node functions:

  1. classify_and_route : cheap LLM call → sets query_type + language style
  2. retrieve_data      : calls the right pre-built DB helper(s)
  3. generate_response  : main LLM call with the agent persona + retrieved context
  4. format_and_guard   : post-processing, hallucination guard, link injection

Each node receives the AgentState, returns a partial dict to merge back in.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from langgraph.graph import END  # not used here, but commonly imported in build_graph

from graph.state import AgentState, LanguageStyle, QueryType
from prompts.system_prompt import CLASSIFIER_PROMPT, SYSTEM_PROMPT
from llm.fallback_manager import LLMFallbackManager, AllProvidersExhausted

# The DB helpers
from db.retrievers import (
    run_dispatch,
    get_company_info,
    get_product_by_name,
    run_safe_select,
)


# --------------------------------------------------------------------------
# Lazy, single LLMFallbackManager per process. Created on first use.
# --------------------------------------------------------------------------
_manager_singleton: Optional[LLMFallbackManager] = None


def get_manager() -> LLMFallbackManager:
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = LLMFallbackManager()
    return _manager_singleton


# --------------------------------------------------------------------------
# Light language-style detection (no LLM call).
#
# We do this BEFORE the LLM classifier so that even if the LLM
# misclassifies, the language hint is reliable. The LLM is only
# used as a tie-breaker / refinement.
# --------------------------------------------------------------------------

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")  # Devanagari Unicode block


def detect_language_style(text: str) -> LanguageStyle:
    """
    Cheap deterministic detection:
      - If the text contains Devanagari chars → 'hindi'.
      - Else, if it contains common Hinglish markers → 'hinglish'.
      - Else → 'english'.
    """
    if not text:
        return "english"

    if _DEVANAGARI_RE.search(text):
        return "hindi"

    # Hinglish detection: two tiers of markers.
    #
    # STRONG markers are distinctly Hindi-origin and rarely appear in
    # English. A single STRONG hit is enough to call it Hinglish.
    #
    # WEAK markers also come from Hindi but overlap with common
    # English words ("the", "me", "ka", "ki", etc.). We need at least
    # TWO weak hits, OR one strong + one weak, to call it Hinglish.
    #
    # This prevents English sentences that just happen to mention the
    # brand "thekua" from being misclassified.
    strong_markers = (
        # question / copula / pronouns
        "kya", "kyu", "kyon", "kyunki", "kaise", "kaisa", "kaisi",
        "hai", "hain", "hota", "hoti", "hoga", "hogi", "honge",
        "tha", "thi",
        "aap", "tum", "tu", "main", "mujhe", "hum", "humara",
        "mera", "meri", "mere", "tera", "teri", "tere",
        "apna", "apni",
        "yeh", "woh", "yah", "wo", "yaha", "waha",
        "chahiye", "chaahiye", "wala", "wali", "wale",
        "karna", "karo", "karein", "kare", "karta", "karti",
        "batao", "batana", "bhej", "bhejna",
        "milega", "milegi", "milenge",
        "kitne", "kitna", "kitni", "konsa", "kaun", "kaunsa",
        "kabhi", "kahin",
        # Hinglish-only discourse words
        "bhai", "yaar", "ji", "arey", "arre", "chalo",
        "shuddh", "swad",
        # Hindi product nouns
        "gud", "chini", "elaichi",
    )
    # NOTE: "thekua" deliberately NOT in strong list — the brand name
    # is widely used in English sentences too. We only count it as a
    # weak signal that needs corroboration.
    # NOTE: "me" and "do" deliberately NOT in weak markers — they're
    # so common in English that requiring 2+ weak hits still produces
    # false positives like "Tell me about thekua" → hinglish.
    weak_markers = (
        "ka", "ki", "ke", "ko", "se", "mein",
        "kab", "kuch", "sab", "koi", "sabhi", "bahut",
        "de", "lo", "le", "lena", "dena", "lijiye", "kijiye",
        "jao", "jana", "aao", "aana", "gaya", "gayi", "gaye",
        "thekua",
    )

    lower = text.lower()
    tokens = re.findall(r"[a-zA-Z']+", lower)
    strong_hits = [t for t in tokens if t in strong_markers]
    weak_hits = [t for t in tokens if t in weak_markers]

    # One strong hit alone is decisive
    if strong_hits:
        return "hinglish"
    # Two or more weak hits (e.g. "kuch thekua" or "thekua chahiye")
    if len(weak_hits) >= 2:
        return "hinglish"
    # One weak + the brand name "thekua" also doesn't count alone
    return "english"


# --------------------------------------------------------------------------
# NODE 1: classify_and_route
# --------------------------------------------------------------------------

def classify_and_route(state: AgentState) -> Dict[str, Any]:
    """
    Cheap LLM call (system prompt is small) that:
      - picks the language style
      - picks the query type
    We also call our local `detect_language_style` and only let the LLM
    refine the language choice if it disagrees.
    """
    messages = state.get("messages", [])
    user_query = state.get("user_query", "")
    if not user_query and messages:
        # Fallback: take last user turn
        for m in reversed(messages):
            if m.get("role") == "user":
                user_query = m.get("content", "")
                break

    local_lang = detect_language_style(user_query)

    # Provide the last few turns for context (helps with follow-ups)
    recent = messages[-6:] if len(messages) > 6 else messages
    recent_text = "\n".join(f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in recent)
    user_text = f"CONVERSATION (most recent last):\n{recent_text}\n\nLATEST USER MESSAGE:\n{user_query}"

    raw = ""
    try:
        raw = get_manager().generate(
            system_prompt=CLASSIFIER_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
    except AllProvidersExhausted:
        # Classifier is best-effort. If everything is down, just use heuristics.
        pass

    # Parse the strict two-line format
    parsed_type: Optional[QueryType] = None
    parsed_lang: Optional[LanguageStyle] = None

    if raw:
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("LANGUAGE:"):
                v = line.split(":", 1)[1].strip().lower()
                if v in ("english", "hinglish", "hindi"):
                    parsed_lang = v  # type: ignore[assignment]
            elif line.startswith("TYPE:"):
                v = line.split(":", 1)[1].strip().lower()
                if v in (
                    "product_info", "pricing", "faq_policy",
                    "order_tracking", "greeting_smalltalk", "out_of_scope",
                ):
                    parsed_type = v  # type: ignore[assignment]

    final_lang = parsed_lang or local_lang
    final_type = parsed_type or _fallback_query_type(user_query)

    return {
        "detected_language_style": final_lang,
        "query_type": final_type,
    }


def _fallback_query_type(user_query: str) -> QueryType:
    """Heuristic fallback if the LLM classifier blew up."""
    q = (user_query or "").lower()
    if not q.strip():
        return "greeting_smalltalk"
    if any(w in q for w in ("hi", "hello", "hey", "namaste", "namaskar", "thanks", "thank you", "bye", "ok", "okay", "good morning", "good evening")):
        return "greeting_smalltalk"
    if any(w in q for w in ("track", "tracking", "where is my order", "where's my order", "mera order", "order status", "kab tak aayega", "kab aayega", "delivery date")):
        return "order_tracking"
    if any(w in q for w in ("price", "kitne", "kitna", "cost", "rate", "discount", "offer", "mrp", "savings")):
        return "pricing"
    if any(w in q for w in ("return", "refund", "shipping", "delivery", "cod", "payment", "policy", "track", "contact", "hours", "address", "email", "phone", "whatsapp")):
        return "faq_policy"
    if any(w in q for w in ("product", "thekua", "ingredients", "shelf life", "kaisa", "kaisi", "varieties", "flavour", "flavor", "taste", "quality", "fresh")):
        return "product_info"
    return "product_info"  # safe default for the demo


# --------------------------------------------------------------------------
# NODE 2: retrieve_data
# --------------------------------------------------------------------------

# Map query_type → helper. We override some of the dispatcher defaults
# so we can do a name-specific product lookup when the user mentions a
# product by name.
def retrieve_data(state: AgentState) -> Dict[str, Any]:
    """
    Calls the right pre-built DB helper(s) for the classified query_type.
    For product_info and pricing, we also try to match the user's query
    against known product names for a tighter answer.
    """
    qtype: QueryType = state.get("query_type", "out_of_scope")
    user_query = state.get("user_query", "")

    out: Dict[str, Any] = {}

    if qtype in ("product_info", "pricing"):
        # Try a name match first if the user said something specific
        name_match = _extract_product_name(user_query)
        if name_match:
            matches = get_product_by_name(name_match) or []
            if matches:
                out["get_product_by_name"] = {"query": name_match, "matches": matches}

        # Also pull the full catalog so the LLM can recommend / cross-sell
        out.update(run_dispatch(qtype))

    elif qtype in ("faq_policy", "order_tracking"):
        out.update(run_dispatch(qtype))

    # For order tracking, also try a guarded raw SQL lookup if the user
    # gave an Order ID (very common follow-up).
    if qtype == "order_tracking":
        order_id = _extract_order_id(user_query)
        if order_id:
            sql = f"""
                SELECT 1 AS found, 'order_id' AS label
                WHERE EXISTS (
                  SELECT 1 FROM products WHERE LOWER(name) LIKE LOWER('%{order_id}%')
                )
            """
            out["order_id_lookup_attempt"] = run_safe_select(sql)

    return {"retrieved_data": out}


def _extract_product_name(text: str) -> Optional[str]:
    """Look for a known product keyword in the user's message."""
    if not text:
        return None
    known = ("traditional", "jaggery", "elaichi", "elachi", "thekua", "coconut")
    lower = text.lower()
    for kw in known:
        if kw in lower:
            return kw
    return None


def _extract_order_id(text: str) -> Optional[str]:
    """
    Pull something that looks like an order id. We require either:
      - a '#' prefix, OR
      - the literal word "order" within 1 word before the token, OR
      - a token that is mostly digits (>= 4 digits).
    This prevents common English words like "WHERE" from being matched.
    """
    if not text:
        return None

    # Pattern 1: explicit #XYZ123 form
    m = re.search(r"#\s*([A-Za-z0-9][A-Za-z0-9\-]{3,})", text)
    if m:
        return m.group(1)

    # Pattern 2: "order <id>" with optional words in between
    m = re.search(
        r"order\s*(?:number|id|no\.?|#)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9\-]{3,})",
        text, re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # Pattern 3: bare numeric token (4+ digits) — common in
    # "track 99887766" or "99887766" alone.
    m = re.search(r"\b(\d{4,})\b", text)
    if m:
        return m.group(1)

    return None


# --------------------------------------------------------------------------
# NODE 3: generate_response
# --------------------------------------------------------------------------

def generate_response(state: AgentState) -> Dict[str, Any]:
    """
    Main LLM call. We feed it:
      - the system prompt (persona + language rule)
      - a user-side context block with retrieved data + language hint
      - the conversation history
    """
    system_prompt = SYSTEM_PROMPT
    lang: LanguageStyle = state.get("detected_language_style", "english")
    retrieved = state.get("retrieved_data") or {}
    user_query = state.get("user_query", "")
    messages = state.get("messages", [])

    context_block = _build_context_block(retrieved, lang)
    user_first_turn = (
        f"LANGUAGE STYLE FOR THIS REPLY: {lang}\n"
        f"{context_block}\n"
        f"USER MESSAGE:\n{user_query or '(no message)'}\n\n"
        f"Reply now in {lang}, following the grounding rules in the system prompt."
    )

    # Build the messages list for the LLM: history (drop empty) + the
    # structured user turn we just built.
    llm_messages: List[Dict[str, str]] = [m for m in messages if m.get("content")]
    if not llm_messages or llm_messages[-1].get("content") != user_first_turn:
        llm_messages.append({"role": "user", "content": user_first_turn})

    try:
        text = get_manager().generate(
            system_prompt=system_prompt,
            messages=llm_messages,
        )
        return {
            "final_response": text.strip(),
            "llm_provider_used": get_manager().last_used or "unknown",
        }
    except AllProvidersExhausted as e:
        # Last-ditch: hand the user the contact info so they're never stranded.
        company = get_company_info() or {}
        wa = company.get("whatsapp_number") or "+91 8016380734"
        wa_link = company.get("whatsapp_link") or "https://wa.me/918016380734"
        fallback = (
            f"I'm having a little trouble reaching my brain right now 😅 "
            f"For immediate help, please WhatsApp us at {wa} or visit {wa_link}. "
            f"Try again in a minute!"
        )
        # Translate the fallback into the user's language roughly
        if lang == "hindi":
            fallback = (
                "अभी मेरे पास जवाब देने की सुविधा नहीं है 😅 "
                f"तुरंत मदद के लिए WhatsApp करें {wa} या देखें {wa_link}। "
                "कुछ देर बाद फिर कोशिश करें!"
            )
        elif lang == "hinglish":
            fallback = (
                "Abhi mere paas jawab dene ki suvidha nahi hai 😅 "
                f"Turant madad ke liye WhatsApp karo {wa} ya dekho {wa_link}. "
                "Thodi der baad phir try karo!"
            )
        return {
            "final_response": fallback,
            "llm_provider_used": "(all models unavailable)",
            "error": str(e),
        }


def _build_context_block(retrieved: Dict[str, Any], lang: LanguageStyle) -> str:
    """
    Compact JSON-ish text the LLM can use as ground truth. We cap the
    size aggressively so we don't blow token budgets on noisy demos.
    """
    if not retrieved:
        return "RETRIEVED_DATA: (none — this is smalltalk or out-of-scope)"

    # Cap each helper's payload size to keep things sane
    capped: Dict[str, Any] = {}
    for k, v in retrieved.items():
        capped[k] = _truncate(v, max_items=10, max_str_len=500)

    pretty = json.dumps(capped, ensure_ascii=False, indent=2, default=str)
    return f"RETRIEVED_DATA (use this as the source of truth for any factual claim):\n{pretty}"


def _truncate(value: Any, max_items: int, max_str_len: int) -> Any:
    if isinstance(value, list):
        return [_truncate(v, max_items, max_str_len) for v in value[:max_items]]
    if isinstance(value, dict):
        return {k: _truncate(v, max_items, max_str_len) for k, v in value.items()}
    if isinstance(value, str) and len(value) > max_str_len:
        return value[: max_str_len - 3] + "..."
    return value


# --------------------------------------------------------------------------
# NODE 4: format_and_guard
# --------------------------------------------------------------------------

# Things that, if the LLM says them, we know it made up. We strip them
# and replace with a safer "I don't have that — here's WhatsApp" line.
_NUMERIC_HALLUCINATION_PATTERNS = [
    re.compile(r"₹\s*\d{1,5}"),            # ₹  / ₹299  / ₹1,299
    re.compile(r"\bRs\.?\s*\d{1,5}"),       # Rs  / Rs. / Rs 299 / Rs. 1,500
    re.compile(r"\bINR\s*\d{1,5}", re.IGNORECASE),  # INR 299
    re.compile(r"\b\d{1,3}\s*days?\b", re.IGNORECASE),  # "30 days" / "90 day"
    re.compile(r"\b\d{1,3}\s*%\s*off\b", re.IGNORECASE),  # "50% off"
]


def format_and_guard(state: AgentState) -> Dict[str, Any]:
    """
    Final pass:
      - For factual query types, we verify any specific number/URL mentioned
        in the LLM reply actually appears in retrieved_data. If not, we
        either strip the line or replace with the WhatsApp CTA.
      - We append a small WhatsApp CTA at the end for product/pricing/FAQ types.
      - Keep the tone tight.
    """
    qtype: QueryType = state.get("query_type", "out_of_scope")
    retrieved = state.get("retrieved_data") or {}
    response = state.get("final_response", "").strip()
    lang: LanguageStyle = state.get("detected_language_style", "english")

    # Fact types: apply a soft guard
    if qtype in ("product_info", "pricing", "faq_policy"):
        response = _strip_ungrounded_numbers(response, retrieved)

    # Append a soft CTA when relevant
    if qtype in ("product_info", "pricing", "faq_policy", "order_tracking"):
        cta = _build_cta(lang)
        if cta and cta not in response:
            response = f"{response}\n\n{cta}"

    return {"final_response": response}


def _strip_ungrounded_numbers(response: str, retrieved: Dict[str, Any]) -> str:
    """
    For each rupee amount / day-count in the response, check if the
    underlying NUMBER appears anywhere in the retrieved payload. If not,
    replace the sentence that contains it with a "ask WhatsApp" hedge.

    Normalisation:
      - "₹299" / "Rs 299" / "Rs. 299" all strip the currency label and
        check the number 299 against the data.
      - This avoids false positives when the LLM uses a currency symbol
        but the data stores the bare numeric.
    """
    if not response:
        return response

    haystack = json.dumps(retrieved, ensure_ascii=False, default=str)
    # Also strip the currency symbol from the haystack to mirror the
    # LLM-side: if data has 299.00, the LLM's "₹299" is considered
    # grounded because 299 appears as a numeric token.
    haystack_bare = re.sub(r"[^0-9.]", " ", haystack)

    cleaned_lines: List[str] = []
    for line in response.splitlines():
        suspect = False
        for pat in _NUMERIC_HALLUCINATION_PATTERNS:
            for m in pat.finditer(line):
                token = m.group(0)
                # Extract the numeric portion of the matched token
                digits = re.findall(r"\d+", token)
                if not digits:
                    suspect = True
                    break
                if not any(d in haystack_bare for d in digits):
                    suspect = True
                    break
            if suspect:
                break
        if suspect:
            # Replace the suspicious sentence with a safe hedge
            cleaned_lines.append(
                "For the exact current price/figure, please check the product page or WhatsApp +91 8016380734."
            )
        else:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _build_cta(lang: LanguageStyle) -> str:
    if lang == "hindi":
        return "ऑर्डर या सवाल के लिए WhatsApp करें: +91 8016380734 🙏"
    if lang == "hinglish":
        return "Order ya sawaal ke liye WhatsApp karo: +91 8016380734 🙏"
    return "To order or for anything else, WhatsApp us: +91 8016380734 🙏"
