"""
test_keys.py
------------
Run this to figure out exactly why your LLM calls are failing.

Usage:
    python test_keys.py

It will:
  1. Check whether GROQ_API_KEY and GEMINI_API_KEY are visible to Python.
  2. Try a 1-token call to your first Groq model — print the actual error.
  3. Try a 1-token call to your first Gemini model — print the actual error.
  4. Tell you what to fix.

If you're on Streamlit Cloud, run this in the "Logs" tab via:
    streamlit run test_keys_streamlit.py
"""

from __future__ import annotations
import os
import sys
import traceback


def header(t):
    print("\n" + "=" * 60)
    print(t)
    print("=" * 60)


# 1. Env visibility
header("1. Environment variables")
groq = os.getenv("GROQ_API_KEY", "")
gem = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

print(f"GROQ_API_KEY   set: {bool(groq)}  (length: {len(groq)})")
if groq:
    print(f"               prefix: {groq[:6]}…   (Groq keys start with 'gsk_')")
print(f"GEMINI_API_KEY set: {bool(gem)}   (length: {len(gem)})")
if gem:
    print(f"               prefix: {gem[:6]}…   (Gemini keys start with 'AIza')")

if not groq and not gem:
    print("\n❌ NEITHER key is set. You need to add them to your .env file")
    print("   or to Streamlit Cloud → Settings → Secrets.")
    sys.exit(1)

# 2. Groq test
header("2. Testing first Groq model (llama-3.3-70b-versatile)")
if not groq:
    print("⏭  Skipping — no GROQ_API_KEY")
else:
    try:
        from groq import Groq
        client = Groq(api_key=groq, timeout=20)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with one word: OK"}],
            max_tokens=5,
        )
        print(f"✅ Groq OK — got: {resp.choices[0].message.content!r}")
    except Exception as e:
        print(f"❌ Groq FAILED:")
        print(f"   {type(e).__name__}: {e}")
        print("\n   Common causes:")
        print("   • Key typo / extra spaces / wrong key pasted")
        print("   • Key revoked at https://console.groq.com/keys")
        print("   • Free-tier rate limit hit (wait a minute)")
        print("   • Wrong key type — make sure it's an API key, not a 'service key'")

# 3. Gemini test
header("3. Testing first Gemini model (gemini-3.5-flash)")
if not gem:
    print("⏭  Skipping — no GEMINI_API_KEY")
else:
    try:
        from google import genai
        client = genai.Client(api_key=gem)
        resp = client.models.generate_content(
            model="gemini-3.5-flash",
            contents="Reply with one word: OK",
        )
        print(f"✅ Gemini OK — got: {resp.text!r}")
    except Exception as e:
        print(f"❌ Gemini FAILED:")
        print(f"   {type(e).__name__}: {e}")
        print("\n   Common causes:")
        print("   • Key typo / wrong key")
        print("   • Key revoked at https://aistudio.google.com/apikey")
        print("   • Gemini API not enabled for the project")
        print("   • Free-tier daily quota hit (1500 req/day)")

# 4. The full chain
header("4. Your current fallback chain (from fallback_manager.py)")
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from llm.fallback_manager import build_default_chain
    for i, spec in enumerate(build_default_chain(), 1):
        print(f"  {i}. {spec.label}")
except Exception as e:
    print(f"⚠️  Could not import fallback_manager: {e}")
    print("   Make sure you're running this from the project root.")

print("\n" + "=" * 60)
print("Done. Share this output with me if you need help debugging.")
print("=" * 60)
