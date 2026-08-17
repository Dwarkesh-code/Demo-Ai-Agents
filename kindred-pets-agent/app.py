"""
app.py — Kindred Pets AI Shopping Assistant (Streamlit UI)
Single-page chat interface powered by LangGraph + Groq + Gemini.
"""

import os
import sys
import logging
import streamlit as st
from langchain_core.messages import HumanMessage

# ─── Path setup (so relative imports work in both local + Streamlit Cloud) ───
sys.path.insert(0, os.path.dirname(__file__))

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ─── Load secrets from .env (local) or st.secrets (Streamlit Cloud) ──────────
def load_secrets():
    """
    Load API keys.  On Streamlit Cloud, st.secrets is populated from the
    Secrets manager UI.  Locally, python-dotenv loads the .env file.
    Always prefer st.secrets > .env > existing env vars.
    """
    # Try Streamlit secrets first (available on Streamlit Cloud)
    try:
        if "GROQ_API_KEY" in st.secrets:
            os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
        if "GEMINI_API_KEY" in st.secrets:
            os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # Fall back to .env for local development
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    except ImportError:
        pass


load_secrets()

# ─── Streamlit page config (must be first st call) ───────────────────────────
st.set_page_config(
    page_title="Kindred Pets — AI Shopping Assistant",
    page_icon="🐾",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Brand accent: warm pet-store green + amber */
:root {
    --accent: #2d8a5f;
    --accent-light: #b6e0c5;
    --bg-dark: #0f1f17;
}

[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f1f17 0%, #1a2e22 100%);
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] .stMarkdown {
    color: #b6e0c5 !important;
}

.stChatInput input {
    border-radius: 12px !important;
    border: 1.5px solid #2d8a5f !important;
}

[data-testid="stChatMessageUser"] {
    background: linear-gradient(135deg, #1a3a26, #2d8a5f) !important;
    border-radius: 14px 14px 4px 14px !important;
    color: #f0fdf4 !important;
}

[data-testid="stChatMessageAssistant"] {
    background: linear-gradient(135deg, #f8fafc, #ecfdf5) !important;
    border-left: 3px solid #2d8a5f !important;
    border-radius: 4px 14px 14px 14px !important;
    color: #1a2e22 !important;
}

.stSpinner > div { border-top-color: #2d8a5f !important; }

.footer-caption {
    font-size: 0.7rem;
    color: #888;
    text-align: center;
    margin-top: 1.5rem;
    padding: 0.5rem;
    border-top: 1px solid #ddd;
}

.welcome-banner {
    background: linear-gradient(135deg, #2d8a5f, #b6e0c5);
    color: #0f1f17;
    padding: 0.75rem 1rem;
    border-radius: 10px;
    font-weight: 600;
    text-align: center;
    margin: 0.5rem 0 1rem 0;
}
</style>
""", unsafe_allow_html=True)


# ─── Cached initialisation (runs once per session) ───────────────────────────

@st.cache_resource(show_spinner="🔧 Setting up Kindred Pets AI…")
def initialise():
    """Build the DB, wire up the LLM manager, and compile the graph."""
    # 1. Ensure database exists
    from setup_db import ensure_database
    db_path = ensure_database()

    # 2. Set DB path for retrievers
    from db.retrievers import set_db_path
    set_db_path(db_path)

    # 3. Create LLM fallback manager
    from llm.fallback_manager import LLMFallbackManager
    llm_manager = LLMFallbackManager()

    # 4. Inject manager into nodes
    from graph.nodes import set_llm_manager
    set_llm_manager(llm_manager)

    # 5. Compile LangGraph
    from graph.build_graph import build_graph
    graph = build_graph()

    return graph, llm_manager


try:
    graph, llm_manager = initialise()
except Exception as e:
    st.error(f"❌ Failed to initialise: {e}")
    st.stop()


# ─── Session state ────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []         # list of LangChain BaseMessage objects
if "last_model" not in st.session_state:
    st.session_state.last_model = "—"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []     # list of (role, text) for display only


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    # Pet image from the actual shop
    st.image(
        "https://cdn.shopify.com/s/files/1/0748/0822/9978/files/5b039e00498ba3834ee39abb8556.jpg?v=1786750710",
        width=180,
    )
    st.markdown("## 🐾 Kindred Pets")
    st.markdown("**Comfort and connection for the pets who share our lives.**")
    st.divider()

    st.markdown("""
### About This Demo

This is a live AI shopping assistant for **Kindred Pets** —
an everyday-essentials store for life with dogs and cats.

**You can ask about:**
- 🛒 Products & pricing
- 🐕 Recommendations for your pet
- 📦 Shipping & delivery
- 🔄 Returns & refunds
- 🎁 The WELCOME15 discount
- 👋 Anything about the brand!

**Supports:** English, Hindi (हिंदी), Hinglish
""")

    st.divider()

    st.markdown("### 🤖 Last Response Via")
    model_badge = st.empty()
    model_badge.info(st.session_state.last_model)

    st.divider()

    st.markdown("""
**Quick links:**
- [🏠 Store](https://kindred-pets-store.myshopify.com)
- [🛍️ Catalog](https://kindred-pets-store.myshopify.com/collections/all)
- [📦 Track Order](https://kindred-pets-store.myshopify.com/pages/track-your-order)
- [💬 Contact](https://kindred-pets-store.myshopify.com/pages/contact)
""")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = []
        st.session_state.last_model = "—"
        st.rerun()


# ─── Main chat area ───────────────────────────────────────────────────────────

st.markdown(
    "<h1 style='text-align:center; color:#2d8a5f;'>🐾 Kindred Pets AI Assistant</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#666; margin-top:-12px;'>"
    "Your friendly guide to everyday essentials for your dog or cat</p>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div class='welcome-banner'>🎁 Use code <strong>WELCOME15</strong> at checkout for 15% off your first order</div>",
    unsafe_allow_html=True,
)

# Render existing chat history
for role, text in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(text)

# Welcome message (shown only on fresh start)
if not st.session_state.chat_history:
    with st.chat_message("assistant"):
        welcome = (
            "Hi there! 🐾 I'm **Kindred**, your shopping buddy for **Kindred Pets**.\n\n"
            "I can help you find the right product for your dog or cat, "
            "check prices and variants, or answer questions about shipping, returns, or your order. "
            "I understand **English, Hindi, और Hinglish** too!\n\n"
            "Try: *\"What toy is good for an indoor cat?\"* or *\"Cat ke liye cooling mat chahiye\"*"
        )
        st.markdown(welcome)


# ─── Chat input & processing ──────────────────────────────────────────────────

if user_input := st.chat_input("Ask anything about Kindred Pets…"):

    # Show user message immediately
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    # Add to LangChain message history
    st.session_state.messages.append(HumanMessage(content=user_input))

    # Run LangGraph
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = graph.invoke(
                    {
                        "messages":    st.session_state.messages,
                        "user_query":  user_input,
                        # These will be filled by the nodes:
                        "detected_language_style": "",
                        "query_type":              "",
                        "retrieved_data":          "",
                        "final_response":          "",
                        "llm_provider_used":       "",
                    }
                )
                answer = result.get("final_response", "I'm sorry, I ran into a problem. Please try again.")
                provider = result.get("llm_provider_used", "unknown")

                # Update state with the NEW messages list from the graph result
                # (format_and_guard appended the AIMessage)
                st.session_state.messages = result.get("messages", st.session_state.messages)
                st.session_state.last_model = provider

            except Exception as e:
                import logging as _logging
                _logging.getLogger(__name__).error(f"Graph invoke error: {e}", exc_info=True)
                answer = (
                    "Oops, I hit a snag! 😅 Please try rephrasing your question, "
                    "or reach us directly on the "
                    "[Contact page](https://kindred-pets-store.myshopify.com/pages/contact)."
                )
                provider = "error"

        st.markdown(answer)

    st.session_state.chat_history.append(("assistant", answer))

    # Update sidebar model badge without full rerun
    model_badge.info(st.session_state.last_model)


# ─── Footer ──────────────────────────────────────────────────────────────────

st.markdown(
    "<div class='footer-caption'>"
    "Powered by <strong>Kindred Pets</strong> business data · "
    "<strong>LangGraph</strong> · <strong>Groq</strong> + <strong>Gemini</strong> fallback<br>"
    "Demo built with love for pets 🐾 · Data captured 2026-08-15"
    "</div>",
    unsafe_allow_html=True,
)
