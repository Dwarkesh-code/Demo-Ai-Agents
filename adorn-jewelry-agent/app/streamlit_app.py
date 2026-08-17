import streamlit as st
import uuid
import sys
import os

# --- Path setup so this file can import your graph regardless of where it's run from ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # adjust if streamlit_app.py sits elsewhere
sys.path.append(PROJECT_ROOT)

from main import workflow  # <-- replace with however you expose your compiled graph


def extract_text(response):
    """Handles Gemini responses whether .content is a plain string or a list of blocks."""
    content = response.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list) and len(content) > 0:
        first = content[0]
        if isinstance(first, dict) and "text" in first:
            return first["text"]
        return str(first)
    return str(content)


# ---------------- Page config ----------------
# NOTE: theme (colors, light/dark base) is now set in .streamlit/config.toml
# next to this file. That's the reliable way to theme Streamlit — fighting
# Streamlit's own dark-theme CSS with !important overrides caused broken
# layout (letters wrapping vertically, mismatched dark/light sections).
st.set_page_config(
    page_title="Hello Adorn | Style Assistant",
    page_icon="💎",
    layout="centered",
)

# ---------------- Light custom styling (accents only, not fighting the theme) ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&display=swap');

.adorn-header {
    text-align: center;
    padding: 2.2rem 0 1rem 0;
}

.adorn-title {
    font-family: 'Cormorant Garamond', serif;
    font-size: 2.6rem;
    font-weight: 700;
    color: #4A3B2A;
    letter-spacing: 0.03em;
    margin-bottom: 0.1rem;
}

.adorn-subtitle {
    font-size: 0.95rem;
    color: #9C8B72;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.adorn-divider {
    width: 60px;
    height: 2px;
    background: linear-gradient(90deg, #C9A96E, #E8C88F);
    margin: 0.8rem auto 0 auto;
}

.stChatMessage {
    border-radius: 14px;
}

[data-testid="stChatMessageContent"] a {
    color: #B8863F;
    font-weight: 600;
}

.suggestion-pill {
    display: inline-block;
    background: #FFFFFF;
    border: 1px solid #E8DFCE;
    border-radius: 20px;
    padding: 6px 14px;
    margin: 4px 6px 4px 0;
    font-size: 0.85rem;
    color: #6B5B45;
}
</style>
""", unsafe_allow_html=True)

# ---------------- Header ----------------
st.markdown("""
<div class="adorn-header">
    <div class="adorn-title">Hello Adorn</div>
    <div class="adorn-subtitle">Your Personal Style Assistant</div>
    <div class="adorn-divider"></div>
</div>
""", unsafe_allow_html=True)

# ---------------- Session state ----------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({
        "role": "assistant",
        "content": (
            "Hi! I'm here to help you find the perfect piece from Hello Adorn — "
            "handmade, waterproof jewelry in 14kt gold fill and sterling silver. 💎\n\n"
            "Ask me about rings, necklaces, earrings, gifts, or anything about our pieces!"
        )
    })

config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ---------------- Suggested prompts (only before first user message) ----------------
if len(st.session_state.messages) == 1:
    st.markdown("""
    <div style="text-align:center; margin-bottom: 1rem;">
        <span class="suggestion-pill">Best gift under $100 💝</span>
        <span class="suggestion-pill">Show me gold rings 💍</span>
        <span class="suggestion-pill">What's trending right now ✨</span>
    </div>
    """, unsafe_allow_html=True)

# ---------------- Render chat history ----------------
for msg in st.session_state.messages:
    avatar = "💎" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ---------------- Chat input ----------------
user_query = st.chat_input("Ask about rings, necklaces, gifts...")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant", avatar="💎"):
        # Using Streamlit's built-in spinner — reliable, no custom CSS/flex
        # bugs like the broken vertical-letter one we hit before.
        with st.spinner("Finding the perfect piece..."):
            initial_state = {
                "query": user_query,
                "response": "",
                "conversation_history": [],
                "product_data": None,
                "product_view": None,
                "responser_prompt": None,
            }
            result = workflow.invoke(initial_state, config=config)

            # Adjust this if your graph returns the answer under a different key
            raw_response = result["response"]
            answer = extract_text(raw_response)

        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
