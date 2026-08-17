"""
diagnose_streamlit.py
---------------------
Run INSIDE Streamlit Cloud to see what your secrets look like from
inside the running app. Drop this in your repo, then visit /diagnose
or run `streamlit run diagnose_streamlit.py` for a local check.

It tells you:
  - Which keys Streamlit sees (length + prefix only, never the secret)
  - Whether load_keys_into_env() would copy them to os.environ
  - A live ping to Groq + Gemini
"""

import os
import sys
import streamlit as st

st.set_page_config(page_title="🔧 Key Diagnostic", page_icon="🔧", layout="centered")

st.title("🔧 API Key Diagnostic")

st.markdown(
    "Yeh page check karta hai ki aapke Streamlit secrets theek se "
    "configure hain ya nahi, aur live ping karta hai dono providers ko."
)

st.divider()

# --- Secret visibility ---
st.subheader("1. Secrets visibility")

# Direct from st.secrets
groq_direct = ""
gem_direct = ""
try:
    if "GROQ_API_KEY" in st.secrets:
        groq_direct = str(st.secrets["GROQ_API_KEY"])
except Exception as e:
    st.error(f"Could not read GROQ_API_KEY from secrets: {e}")

try:
    if "GEMINI_API_KEY" in st.secrets:
        gem_direct = str(st.secrets["GEMINI_API_KEY"])
    elif "GOOGLE_API_KEY" in st.secrets:
        gem_direct = str(st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error(f"Could not read GEMINI_API_KEY from secrets: {e}")

# From os.environ (after load_keys_into_env)
groq_env = os.getenv("GROQ_API_KEY", "")
gem_env = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Groq**")
    st.write(f"In `st.secrets`: {'✅ found' if groq_direct else '❌ missing'}")
    if groq_direct:
        st.code(f"length={len(groq_direct)}  prefix={groq_direct[:6]}…  ends_with=…{groq_direct[-4:]}")
    st.write(f"In `os.environ`: {'✅ loaded' if groq_env else '❌ missing'}")

with c2:
    st.markdown("**Gemini**")
    st.write(f"In `st.secrets`: {'✅ found' if gem_direct else '❌ missing'}")
    if gem_direct:
        st.code(f"length={len(gem_direct)}  prefix={gem_direct[:6]}…  ends_with=…{gem_direct[-4:]}")
    st.write(f"In `os.environ`: {'✅ loaded' if gem_env else '❌ missing'}")

if groq_direct and not groq_env:
    st.error(
        "🛑 Key is in `st.secrets` but `load_keys_into_env()` did NOT copy it to "
        "`os.environ`. This is the cause of the failure. "
        "The fix is in `app.py` — make sure `bootstrap()` is called and that "
        "you're running an updated `llm/fallback_manager.py`."
    )

st.divider()

# --- Live ping ---
st.subheader("2. Live API ping")

col_groq, col_gem = st.columns(2)

with col_groq:
    st.markdown("**Groq**")
    if st.button("Test Groq", use_container_width=True):
        if not groq_env:
            st.error("No GROQ_API_KEY in env — cannot ping")
        else:
            try:
                from groq import Groq
                client = Groq(api_key=groq_env, timeout=20)
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": "Reply with one word: OK"}],
                    max_tokens=5,
                )
                st.success(f"✅ OK: {resp.choices[0].message.content!r}")
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {e}")

with col_gem:
    st.markdown("**Gemini**")
    if st.button("Test Gemini", use_container_width=True):
        if not gem_env:
            st.error("No GEMINI_API_KEY in env — cannot ping")
        else:
            try:
                from google import genai
                client = genai.Client(api_key=gem_env)
                resp = client.models.generate_content(
                    model="gemini-3.5-flash",
                    contents="Reply with one word: OK",
                )
                st.success(f"✅ OK: {resp.text!r}")
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {e}")

st.divider()

# --- Common mistakes ---
with st.expander("🛠 Common mistakes when configuring Streamlit secrets"):
    st.markdown(
        """
**1. Wrong TOML quoting**

```toml
# ❌ wrong — single quotes are NOT valid TOML strings
GROQ_API_KEY = 'gsk_abc123'

# ✅ correct — double quotes
GROQ_API_KEY = "gsk_abc123"
```

**2. Quoted-with-extra-quotes**

```toml
# ❌ wrong — Streamlit treats the whole `"gsk_..."` as the value
GROQ_API_KEY = ""gsk_abc123""

# ✅ correct
GROQ_API_KEY = "gsk_abc123"
```

**3. Spaces around `=` are fine, but stray newlines / indentation can break it**

```toml
# ✅ this works
GROQ_API_KEY = "gsk_abc123"
GEMINI_API_KEY = "AIzaSy..."

# ❌ this often silently fails parsing
GROQ_API_KEY = "gsk_abc123"
GEMINI_API_KEY = "AIza..."
[some_other_section]
foo = "bar"
```

**4. You forgot to click "Save" then waited — Streamlit takes 5-10 seconds to restart**

**5. The key was created in the wrong dashboard**

- Groq: https://console.groq.com/keys (NOT a GroqCloud "service account")
- Gemini: https://aistudio.google.com/apikey (NOT a GCP service account key)
        """
    )
