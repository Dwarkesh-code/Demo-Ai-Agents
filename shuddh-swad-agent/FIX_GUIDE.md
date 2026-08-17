# Shuddh Swad Agent — Error Fix Guide

## What the errors mean

Tera log mein 9 warnings aa rahe hain — sab ek hi problem ki wajah se:

```
GROQ_API_KEY is not set in the environment
GEMINI_API_KEY is not set in the environment
```

`LLMFallbackManager` ek-ek karke 5 Groq + 4 Gemini models try karta hai.
Har baar env variable nahi milta, toh "non-retriable" mark karke next pe
chala jaata hai. Aakhir mein sab fail → `AllProvidersExhausted` exception.

**TL;DR: API keys set nahi hain. Models ke naam sahi hain.**

---

## Latest model chain (refreshed 2026-08-11)

| Priority | Provider | Model | Why |
|---|---|---|---|
| 1 | Groq | `llama-3.3-70b-versatile` | Best quality, workhorse |
| 2 | Groq | `openai/gpt-oss-120b` | Strong, 500 t/s |
| 3 | Groq | `qwen/qwen3.6-27b` | Newest Qwen (Jul 2026) |
| 4 | Groq | `llama-3.1-8b-instant` | 840 t/s, cheap |
| 5 | Groq | `openai/gpt-oss-20b` | 1000 t/s, ultra-cheap last resort |
| 6 | Gemini | `gemini-3.5-flash` | GA, smartest Flash for agentic |
| 7 | Gemini | `gemini-3.6-flash` | Newest stable Flash |
| 8 | Gemini | `gemini-3.5-flash-lite` | Ultra-cheap |
| 9 | Gemini | `gemini-3.1-flash-lite` | Stable Flash-Lite |

⚠️ **`gemini-2.5-flash-lite` retired on 2026-06-01** — replaced with 3.x in the new chain.

---

## How to fix (do this in order)

### Option A — Local development

```bash
cd shuddh-swad-agent
cp .env.example .env
nano .env   # ya VS Code se edit kar
```

Paste apni real keys:

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx
```

Keys kahan se le:
- Groq: https://console.groq.com/keys (free, 1 min signup)
- Gemini: https://aistudio.google.com/apikey (free, Google account se)

Phir run kar:

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Option B — Streamlit Cloud deploy

1. https://share.streamlit.io pe apna app open kar
2. App → **Settings** → **Secrets**
3. Yeh paste kar (apni real keys ke saath):

```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxx"
GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxxx"
```

4. **Save** → app auto-reboot hoga. Sidebar mein "Groq ✓ · Gemini ✓" dikhega.

### Verify it works

App open kar → sidebar mein green check marks dikhne chahiye. Phir sample
question pooch, e.g. *"Thekua ki shelf life kitni hai?"*. Response ke
neeche ya sidebar mein "Last answered by" dikhega konsa model actually
chala.

---

## What changed in the new `fallback_manager.py`

- Added `gemini-3.6-flash` (latest stable, Aug 2026)
- Added `gemini-3.5-flash` (GA agentic powerhouse)
- Removed `gemini-2.5-flash-lite` (retired 1 June 2026)
- Added `qwen/qwen3.6-27b` (newest Qwen on Groq)
- Reordered chain so best quality comes first, cheaper ones as final fallback
- Updated module docstring with model list + dates

Baaki sab code (classify, retrieve, guard, LangGraph wiring) — same hai.
Bas `llm/fallback_manager.py` replace kar de.
