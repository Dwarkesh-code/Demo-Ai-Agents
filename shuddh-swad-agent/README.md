# 🍪 Shuddh Swad — AI Customer Support Agent (Demo)

A working, hostable AI customer support + product-recommendation agent
for **Shuddh Swad** (https://shuddhswad.shop/) — an authentic Bihari
Thekua brand.

Built as a **sales demo** to show a real business what a production-
quality AI support agent looks like. It's small, clean, and you can
read every file in 15 minutes.

---

## ✨ What it does

- **Answers in the user's language automatically** — English, Hinglish,
  or Hindi (Devanagari) — without any UI switch. Detected per turn.
- **Grounded answers** from a real SQLite knowledge base built from the
  store's data: products, variants, prices, FAQs, policies, press
  mentions, contact info.
- **Never invents** products, prices, or policies. If the data doesn't
  cover something, it gives the WhatsApp number.
- **Multi-model LLM fallback chain** — tries 5 Groq models in order,
  then 4 Gemini models, so the demo never goes dark during a client call.
- **Safe SQL** — the raw-SQL path is a guarded read-only tool that
  rejects anything that isn't a SELECT.
- **LangGraph StateGraph** — proper nodes + conditional edges, not a
  plain LangChain chain.

---

## 🗂️ Project structure

```
shuddh-swad-agent/
├── app.py                              # Streamlit entrypoint
├── setup_db.py                         # builds shuddh_swad.db from .sql
├── shuddh_swad_business_data.sql       # source-of-truth data dump
├── requirements.txt
├── .env.example                        # copy → .env locally
├── .gitignore
├── README.md
│
├── db/
│   └── retrievers.py                   # pre-built query helpers + safe-SQL guard
│
├── llm/
│   └── fallback_manager.py             # LLMFallbackManager (Groq + Gemini chains)
│
├── graph/
│   ├── state.py                        # LangGraph state schema (TypedDict)
│   ├── nodes.py                        # 4 node functions
│   └── build_graph.py                  # StateGraph assembly + run_agent()
│
└── prompts/
    └── system_prompt.py                # agent persona + classifier prompt
```

---

## 🧠 Architecture in 30 seconds

```
START
  ↓
classify_and_route        # fast LLM call → query_type + language_style
  ↓
[conditional edge]
  ├── greeting_smalltalk / out_of_scope → generate_response
  ↓                                    ↑
retrieve_data                            │ (pre-built SQL helpers,
  ↓                                      │  e.g. get_all_products,
generate_response                        │  get_faqs, get_company_info)
  ↓                                    ↓
format_and_guard            # hallucination guard + soft CTA
  ↓
END
```

**LLM call site** is a single `LLMFallbackManager.generate(...)` call.
The manager tries, in order: `llama-3.3-70b-versatile` → `gpt-oss-120b`
→ `llama-3.1-8b-instant` → `gpt-oss-20b` → `qwen3.6-27b` (all Groq),
then Gemini `3.1-flash-lite` → `3.5-flash-lite` → `2.5-flash-lite` →
`3.5-flash`. On any rate-limit / auth / timeout, it moves to the next.
The Streamlit sidebar shows which model actually answered.

---

## 🚀 Run it locally

### 1. Clone and enter the project

```bash
cd shuddh-swad-agent
```

### 2. Create a virtual env (recommended)

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API keys

```bash
cp .env.example .env
# then edit .env and paste your real GROQ_API_KEY (and optionally GEMINI_API_KEY)
```

Get keys from:
- Groq:    https://console.groq.com/keys
- Gemini:  https://aistudio.google.com/apikey

### 5. Build the database (or let the app do it)

The app builds `shuddh_swad.db` automatically on first run from
`shuddh_swad_business_data.sql`. If you want to do it manually:

```bash
python setup_db.py
# or force-rebuild:
python setup_db.py --force
```

### 6. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

---

## ☁️ Deploy to Streamlit Community Cloud (free)

This is the deploy path you want to share with the client.

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial Shuddh Swad AI agent"
git branch -M main
git remote add origin https://github.com/<you>/shuddh-swad-agent.git
git push -u origin main
```

Commit only:
- All `.py` files
- `shuddh_swad_business_data.sql`  ← **this is the source of truth**
- `requirements.txt`
- `.gitignore`
- `README.md`

Do **not** commit `.env` or `shuddh_swad.db` — `.gitignore` already
handles both.

### 2. Create the app on share.streamlit.io

1. Go to https://share.streamlit.io and sign in with GitHub.
2. Click **"New app"**.
3. Pick your repo, branch `main`, and main file path: `app.py`.
4. Click **"Advanced settings"** → **"Secrets"**.
5. Paste this (with your real keys):

   ```toml
   GROQ_API_KEY = "gsk_your_real_groq_key"
   GEMINI_API_KEY = "your_real_gemini_key"
   ```

6. Click **Deploy**. First deploy takes ~2 minutes.

On first cold start the app builds `shuddh_swad.db` from
`shuddh_swad_business_data.sql` automatically — no extra config needed.

### 3. Share the URL

You'll get a `https://<your-app>.streamlit.app` URL. Send that to the
client. The sidebar in the app shows which provider/model answered the
last message, so you can demo the fallback system live.

---

## 🧪 Test prompts to demo the agent

Try these in order — they show off different capabilities:

| What it shows | Try saying |
|---|---|
| Bilingual detection | "Hi, what varieties of Thekua do you have?" |
| Hindi script reply | "Thekua ki shelf life kitne din hai?" |
| Devanagari reply | "आपकी Thekua की कीमत क्या है?" |
| Policy lookup | "What's your return policy if the product is damaged?" |
| Order routing | "Where is my order #ABC123?" |
| Out-of-scope handling | "Who will win the next election?" |
| Small talk | "Thank you!" |

---

## 🔧 Customization knobs

All the demo-tuning surfaces are at the top of their respective files:

- **Provider order** — `PROVIDER_ORDER` in `llm/fallback_manager.py`.
  Flip `["groq", "gemini"]` → `["gemini", "groq"]` if you want Gemini first.
- **Model list** — `GROQ_CHAIN` and `GEMINI_CHAIN` in
  `llm/fallback_manager.py`. Add or remove `ModelSpec` entries freely.
- **Persona / language rules** — `SYSTEM_PROMPT` in
  `prompts/system_prompt.py`.
- **Classifier prompt** — `CLASSIFIER_PROMPT` in the same file. The
  strict two-line reply format keeps it reliable.

---

## 🛡️ Safety notes

- The raw SQL path (`run_safe_select` in `db/retrievers.py`) rejects
  any statement that isn't a SELECT, contains destructive keywords
  (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `ATTACH`, `PRAGMA`,
  `CREATE`, `RENAME`, `VACUUM`, `REINDEX`, …), or contains multiple
  statements. Even if a user managed to inject something via the LLM,
  the guard would refuse to run it.
- The SQLite connection is opened in read-only URI mode
  (`file:...?mode=ro`) as a second line of defense.
- The `format_and_guard` node post-processes the LLM output: any
  specific number (₹, "X days") in the reply that doesn't appear in
  the retrieved data is replaced with a WhatsApp CTA. This is a soft
  guard — it won't catch every hallucination, but it makes price /
  policy drift very visible.

---

## 🛠️ Tech stack (for the client pitch slide)

| Layer | Choice | Why |
|---|---|---|
| Orchestration | **LangGraph** (StateGraph) | Real conditional graph, debuggable, production-friendly |
| LLM | **Groq** primary, **Gemini** fallback | Best $/throughput + zero-downtime demo |
| Data | **SQLite** + pre-built retrievers | Fast, deterministic, no LLM-written SQL for the common path |
| UI | **Streamlit** | 1 file, shareable, free deploy tier |
| Language | **Auto-detect** (EN / Hinglish / हिंदी) | Real Bihari customer base, not English-only |

---

## 📄 License

Built as a sales pitch. The data file `shuddh_swad_business_data.sql`
belongs to Shuddh Swad. The agent code is yours to use however you
want.
