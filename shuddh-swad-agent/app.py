"""
app.py
------
Streamlit entrypoint for the Shuddh Swad AI Agent demo.

Run locally:
    streamlit run app.py

Deploy to Streamlit Community Cloud:
    See README.md
"""

from __future__ import annotations

import os
import sys
import streamlit as st

# --- Make sibling packages importable when run as `streamlit run app.py` --
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# --- Local imports after path fixup ----------------------------------------
from setup_db import ensure_db
from llm.fallback_manager import load_keys_into_env
from graph.build_graph import run_agent


# --------------------------------------------------------------------------
# Page config
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Shuddh Swad — AI Assistant",
    page_icon="🍪",
    layout="centered",
)


# --------------------------------------------------------------------------
# First-run setup
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def bootstrap():
    """
    Run once per process. Build the DB from the .sql file if needed,
    pull API keys from Streamlit secrets into os.environ, and report
    which models are configured.
    """
    ensure_db()
    load_keys_into_env()

    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return {"has_groq": has_groq, "has_gemini": has_gemini}


status = bootstrap()


# --------------------------------------------------------------------------
# Header / brand
# --------------------------------------------------------------------------
st.markdown(
    """
    <div style="text-align:center; padding: 0.5rem 0 0.25rem 0;">
      <h1 style="margin-bottom:0;">🍪 Shuddh Swad — AI Assistant</h1>
      <p style="color:#666; margin-top:0.25rem;">
        Authentic Bihari Thekua · Pure · Traditional · Home-made
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### About this demo")
    st.write(
        "A live AI customer support & product guide for **Shuddh Swad**, "
        "an authentic Bihari Thekua brand. Built as a sales pitch — feel "
        "free to ask about products, pricing, shipping, returns, or "
        "anything else you see on [shuddhswad.shop](https://shuddhswad.shop)."
    )

    st.markdown("### How it works")
    st.markdown(
        "- **LangGraph** orchestrating 4 nodes: classify → retrieve → generate → guard\n"
        "- **SQLite** read-only knowledge base built from real store data\n"
        "- **Groq** primary, **Gemini** fallback, multi-model chain on each\n"
        "- Auto language detection: replies in **English / Hindi / Hinglish**"
    )

    st.markdown("### Last answered by")
    provider_used = st.session_state.get("last_provider", "—")
    st.code(provider_used or "—", language="text")

    st.markdown("### API keys")
    if status["has_groq"] and status["has_gemini"]:
        st.success("Groq ✓  ·  Gemini ✓")
    elif status["has_groq"]:
        st.warning("Groq ✓  ·  Gemini ✗ (set GEMINI_API_KEY for full fallback)")
    elif status["has_gemini"]:
        st.warning("Groq ✗  ·  Gemini ✓ (set GROQ_API_KEY for primary chain)")
    else:
        st.error(
            "No API keys found. Set GROQ_API_KEY (and optionally GEMINI_API_KEY) "
            "in .env locally, or in Streamlit secrets when deployed."
        )

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_provider = "—"
        st.rerun()


# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_provider" not in st.session_state:
    st.session_state.last_provider = "—"


# --------------------------------------------------------------------------
# Welcome / first-run sample prompts
# --------------------------------------------------------------------------
if not st.session_state.messages:
    st.markdown("##### Try one of these to get started:")
    cols = st.columns(2)
    samples = [
        "What varieties of Thekua do you have and what are the prices?",
        "Tell me about your shipping and return policy.",
        "Thekua ki shelf life kitni hai?",
        "Where can I track my order?",
    ]
    for i, s in enumerate(samples):
        if cols[i % 2].button(s, key=f"sample_{i}", use_container_width=True):
            st.session_state.pending_sample = s


# --------------------------------------------------------------------------
# Render chat history
# --------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# --------------------------------------------------------------------------
# Handle input
# --------------------------------------------------------------------------
user_input = st.chat_input("Type your message in English, Hinglish, or हिंदी…")
if not user_input and st.session_state.get("pending_sample"):
    user_input = st.session_state.pop("pending_sample")

if user_input:
    # 1. Show the user's message immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Build the history (everything except the last user turn we just appended
    #    goes into 'history' because run_agent appends the new query itself).
    history_for_agent = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[:-1]
    ]

    # 3. Run the agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = run_agent(user_input, history_for_agent)
            except Exception as e:  # noqa: BLE001
                st.error(
                    "Something went sideways. Please try again, or WhatsApp us at "
                    "+91 8016380734."
                )
                st.exception(e)
                result = {
                    "final_response": "I'm having a brief hiccup. Please try again 🙏",
                    "llm_provider_used": "(error)",
                    "query_type": "out_of_scope",
                    "language_style": "english",
                    "error": str(e),
                }

        st.markdown(result["final_response"])
        st.session_state.messages.append(
            {"role": "assistant", "content": result["final_response"]}
        )
        st.session_state.last_provider = result.get("llm_provider_used", "—")


# --------------------------------------------------------------------------
# Footer
# --------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "Powered by **Shuddh Swad** business data · **LangGraph** · "
    "**Groq + Gemini** multi-model fallback chain."
)
