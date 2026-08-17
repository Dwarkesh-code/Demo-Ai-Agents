# 🐾 Kindred Pets — AI Shopping Assistant

> **A production-quality AI agent demo** built for [Kindred Pets](https://kindred-pets-store.myshopify.com/) — an everyday-essentials pet store for dogs and cats.

---

## What This Does

This is a fully-functional AI shopping assistant + product-recommendation chatbot for Kindred Pets.
It can answer questions about:

- 🛒 **Products & pricing** — 39 products, 300+ variants across 6 core collections
- 🐕 **Personalized recommendations** — for puppies, kittens, dogs, cats based on use case
- 📦 **Shipping & delivery** — 1–2 business days processing, 7–15 business days delivery
- 🔄 **Returns & refunds** — case-by-case policy for unused/damaged items
- 🎁 **Discounts & promos** — WELCOME15 first-order code
- 📦 **Order tracking** — redirect to the tracking page / Contact form

**Language-adaptive**: automatically detects Hindi (हिंदी), Hinglish (Roman script), or English and replies in the same style — no language selector needed.

---

## Architecture

```
User message
    │
    ▼
┌─────────────────────────────────────────────────────┐
│           LangGraph StateGraph                      │
│                                                     │
│  [classify_and_route] ──(smalltalk)──┐              │
│          │                           │              │
│   (all other)                        │              │
│          ▼                           │              │
│   [retrieve_data]                    │              │
│          │                           ▼              │
│          └──────────► [generate_response]           │
│                               │                     │
│                               ▼                     │
│                       [format_and_guard]            │
└─────────────────────────────────────────────────────┘
    │
    ▼
Streamlit UI response
```

**LLM Fallback Chain:**  
`Groq/llama-3.3-70b` → `Groq/gpt-oss-120b` → `Groq/llama-3.1-8b` → `Groq/gpt-oss-20b` → `Groq/qwen3-27b` → `Gemini/gemini-2.0-flash-lite` → `Gemini/gemini-2.0-flash` → `Gemini/gemini-1.5-flash` → `Gemini/gemini-1.5-pro`

---

## Project Structure

```
kindred-pets-agent/
├── app.py                                # Streamlit entrypoint
├── setup_db.py                           # Builds kindred_pets.db from .sql on first run
├── kindred_pets_business_data.sql        # Source of truth (business data)
├── db/
│   ├── __init__.py
│   └── retrievers.py                     # Pre-built DB query functions + SQL guard
├── llm/
│   ├── __init__.py
│   └── fallback_manager.py               # LLMFallbackManager (Groq → Gemini chain)
├── graph/
│   ├── __init__.py
│   ├── state.py                          # LangGraph AgentState schema
│   ├── nodes.py                          # 4 node functions
│   └── build_graph.py                    # Assembles & compiles the StateGraph
├── prompts/
│   ├── __init__.py
│   └── system_prompt.py                  # Agent persona & instructions
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Local Setup

### 1. Clone / navigate to the project
```bash
cd kindred-pets-agent
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your API keys
```bash
cp .env.example .env
# Open .env and fill in:
#   GROQ_API_KEY=your_groq_api_key
#   GEMINI_API_KEY=your_gemini_api_key
```

**Get API keys:**
- Groq: https://console.groq.com (free tier, very generous)
- Gemini: https://aistudio.google.com/app/apikey (free tier)

### 5. Run the app
```bash
streamlit run app.py
```

The app will:
1. Detect that `kindred_pets.db` doesn't exist yet
2. Build it automatically from `kindred_pets_business_data.sql`
3. Start the Streamlit chat interface at `http://localhost:8501`

---

## 🚀 Deploy to Streamlit Community Cloud (Free)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit: Kindred Pets AI agent"

# Create a repo on github.com (e.g. kindred-pets-agent)
git remote add origin https://github.com/YOUR_USERNAME/kindred-pets-agent.git
git push -u origin main
```

> **Note:** `.env` is gitignored. `kindred_pets.db` is also gitignored — the app builds it at startup from the committed `.sql` file, so you only need to commit the `.sql` file.

### Step 2 — Connect on Streamlit Cloud
1. Go to **https://share.streamlit.io**
2. Click **"New app"**
3. Select your GitHub repo → branch `main` → main file `app.py`
4. Click **"Deploy"**

### Step 3 — Set API Keys as Secrets
In the Streamlit Cloud dashboard for your app:
1. Click **"⚙️ Settings"** → **"Secrets"**
2. Add the following (replace with your real keys):
```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
GEMINI_API_KEY = "AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxx"
```
3. Click **"Save"** — the app will reboot automatically.

That's it! Share the public URL with your team. 🎉

---

## 🛠️ Customisation Notes

| What to change | Where |
|---|---|
| LLM model order / provider priority | `llm/fallback_manager.py` → `PROVIDER_ORDER`, `GROQ_MODELS`, `GEMINI_MODELS` |
| Agent persona & instructions | `prompts/system_prompt.py` |
| Query routing logic | `graph/nodes.py` → `retrieve_data()` |
| UI colors / branding | `app.py` → `<style>` block |
| Add more DB tables / data | `kindred_pets_business_data.sql` + `db/retrievers.py` |
| Product/category keyword map | `graph/nodes.py` → `CATEGORY_KEYWORDS` |

---

## 📊 Data Source

| Source | URL | Captured |
|---|---|---|
| Shopify products API | `https://kindred-pets-store.myshopify.com/products.json?limit=250` | 2026-08-15 |
| Shopify collections API | `https://kindred-pets-store.myshopify.com/collections.json` | 2026-08-15 |
| Homepage content | `https://kindred-pets-store.myshopify.com/` | 2026-08-15 |

**Catalog snapshot:** 39 products · 306 variants · 8 collections · 16 FAQs · 5 policies

---

## 📝 Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph) |
| LLM providers | Groq API + Google Gemini API |
| Database | SQLite (built from .sql at startup) |
| UI | Streamlit |
| Language | Python 3.10+ |

---

## ⚠️ Known Limitations (Demo)

- **No live order data** — the demo can't look up actual orders; it redirects to the tracking page and Contact form.
- **Stock availability** — the DB was captured on 2026-08-15; some variants may show "sold out" as of that date. Refresh the `.sql` periodically.
- **Store policy content** — the live store does not publish detailed FAQ/policy pages; the demo synthesises reasonable defaults from the product copy and standard e-commerce conventions, clearly marked as such.

---

*Built as a portfolio demo for AI agent consulting. Store: [kindred-pets-store.myshopify.com](https://kindred-pets-store.myshopify.com)*
