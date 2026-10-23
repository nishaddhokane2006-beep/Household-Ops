# 🏠 Household Ops

> **Amazon Alexa+ Hackathon 2026 · Alexa+ Track**  
> A self-hosted MCP server that gives Alexa+ the ability to run a home — reducing food waste with expiry-aware meal suggestions, pantry tracking, shopping lists, and bill reminders.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![MCP Spec](https://img.shields.io/badge/MCP-2025--11--25-purple)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)

---

## 🎯 The Hook

Every household wastes food because no one knows what's about to expire. Household Ops solves this: one sentence to Alexa+ triggers a chain of tool calls that checks your pantry, surfaces expiring items, and suggests tonight's dinner from what you already have.

**Example session:**
```
You: "I bought two dozen eggs and a litre of milk"
→ add_pantry_item called twice

You: "What's about to expire?"
→ check_pantry(filter="expiring") returns items expiring in ≤5 days

You: "Plan dinner for tonight"
→ suggest_meals ranks recipes by most-expiring-ingredients-used

You: "My electricity bill of 1800 is due on the 28th"
→ add_bill stores the reminder
```

---

## 🏗 Architecture

```
┌─────────────┐     MCP 2025-11-25      ┌──────────────────┐
│   Alexa+    │ ◄── Streamable HTTP ──► │  server.py       │
│  (MCP client│     (production path)   │  FastMCP server  │
│   + Add-on) │                         │                  │
└─────────────┘                         │  6 Tools         │
                                        │  1 Resource      │
┌─────────────┐     MCP client call     │  1 Prompt        │
│  backend.py │ ◄─────────────────────► │                  │
│  FastAPI    │                         └───────┬──────────┘
│  + Bedrock  │                                 │
│  Converse   │                         ┌───────▼──────────┐
└──────┬──────┘                         │  SQLite          │
       │                                │  + recipes.json  │
┌──────▼──────┐                         └──────────────────┘
│  index.html │
│  Chat UI    │
│  + Voice I/O│
└─────────────┘
```

**Two paths, one server:**
- **Production**: Alexa+ ↔ Add-on (Alexa AI CLI) ↔ `server.py`  
- **Demo/test**: Browser chat UI ↔ `backend.py` ↔ Bedrock Converse API ↔ `server.py`

---

## 🛠 MCP Tools

| Tool | Purpose |
|------|---------|
| `add_pantry_item` | Add or update a pantry item with optional expiry date |
| `check_pantry` | List items; filter by name or `"expiring"` |
| `suggest_meals` | Rank recipes by ingredients-on-hand, weight expiring items |
| `build_shopping_list` | Generate shopping list for chosen recipes |
| `add_bill` | Store a bill reminder with amount and due date |
| `upcoming_bills` | List bills due within N days |

**Resource:** `pantry://shopping-list` – live read-only shopping list  
**Prompt:** `weekly_review` – reusable weekly household review template

---

## 🚀 Quick Start

### 1 · Prerequisites

- Python 3.11+
- Node.js (for MCP Inspector)
- AWS account with Bedrock model access *(see below)*

### 2 · Install

```bash
git clone https://github.com/YOUR_USERNAME/household-ops-alexa
cd household-ops-alexa

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3 · Configure

```bash
cp .env.example .env
# Edit .env with your AWS credentials and region
```

### 4 · Seed demo data

```bash
python seed.py
# → 23 pantry items (several expiring within 5 days) + 3 bills
```

### 5 · Start the MCP server

```bash
python server.py
# Listening at http://localhost:8000/mcp
```

### 6 · Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

### 7 · Run automated smoke tests

```bash
# (with server.py still running)
python test_client.py
```

### 8 · Start the demo chat UI

```bash
# In a new terminal:
uvicorn backend:app --reload --port 7860
# Open http://localhost:7860
```

---

## ☁️ Enable Amazon Bedrock

1. Log in to the [AWS Console](https://console.aws.amazon.com/)
2. Search **Bedrock** → open Amazon Bedrock
3. Left menu → **Model access** → **Modify model access**
4. Enable **Anthropic → Claude 3.5 Haiku** (instant approval)
5. Set `BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0` in `.env`

Default region is `us-east-1`. Claude 3.5 Haiku is fast and low-cost.

---

## 🔌 Connect to Alexa+

### Option A: Add-on Agent Skill (recommended)

Use Claude Code, Kiro, Codex, or Cursor. Give it your MCP server's public HTTPS URL and ask it to onboard using the Alexa+ Add-on Agent Skill. It walks through the process automatically.

### Option B: Alexa AI CLI (manual)

```bash
npm install -g @alexa-ai/cli   # or use npx

alexa-ai configure
alexa-ai new mcp \
  --name "Household Ops" \
  --locale en-US \
  --mcp-server-url "https://your-server.render.com/mcp"
alexa-ai deploy
```

Redeploy whenever you change tools or configuration.

> **Note:** The server needs a public HTTPS URL for the add-on. See deployment options below.

---

## 🌐 Deployment

### Render (recommended for free tier)

1. Push this repo to GitHub
2. Create a new Render account → **New Blueprint**
3. Connect your repo — Render reads `render.yaml` automatically
4. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` as secret env vars
5. Deploy. Your MCP URL will be `https://household-ops-mcp.onrender.com/mcp`

### Fly.io

```bash
fly auth login
fly launch   # reads fly.toml
fly secrets set AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_REGION=us-east-1
fly deploy
```

### Local tunnel (development)

```bash
# ngrok:
ngrok http 8000
# Your HTTPS URL: https://xxxx.ngrok.io/mcp

# cloudflared:
cloudflared tunnel --url http://localhost:8000
```

---

## 📁 File Structure

```
household-ops-alexa/
├── server.py          ← MCP server (6 tools, 1 resource, 1 prompt)
├── backend.py         ← FastAPI + Bedrock demo backend
├── database.py        ← SQLite schema and connection helper
├── seed.py            ← Demo data seed script (run before recording)
├── test_client.py     ← Automated smoke tests
├── recipes.json       ← 15 regional recipes
├── requirements.txt
├── .env.example       ← Config template
├── Dockerfile
├── render.yaml        ← Render deployment blueprint
├── fly.toml           ← Fly.io deployment config
├── LICENSE            ← MIT
├── static/
│   └── index.html     ← Chat UI with tool-call side panel + voice
└── FRICTION_LOG.md    ← Developer friction log (for hackathon submission)
```

---

## 🎬 Demo Script

Before recording, run:
```bash
python seed.py   # reset to clean demo state
```

**Suggested voice/text flow (under 3 minutes):**

1. *"What's about to expire in my pantry?"* → `check_pantry(filter="expiring")` lists 4 items
2. *"Plan dinner tonight using what's about to go bad"* → `suggest_meals` picks Scrambled Eggs + Banana Pancakes
3. *"Build a shopping list for Banana Pancakes"* → `build_shopping_list` adds missing items
4. *"My electricity bill of 1800 is due on the 28th"* → `add_bill` stores it
5. *"Any bills due this week?"* → `upcoming_bills(days_ahead=7)` returns it

Each step shows the tool name, JSON input, and JSON output in the side panel.

---

## 🔬 Testing Without Alexa

Work up this ladder:

1. **MCP Inspector** – `npx @modelcontextprotocol/inspector http://localhost:8000/mcp`
2. **Smoke tests** – `python test_client.py` (covers all tools + error cases)
3. **Chat UI + Bedrock** – `uvicorn backend:app --port 7860` then open the browser
4. **Real Alexa+** – if you have the CLI and account access

---

## 🗺 What's Next

- Per-user authentication and multi-household support
- Real grocery API integration (e.g. Instacart, BigBasket) for one-tap shopping
- Push notifications for bills and expiry warnings
- Barcode scan → `add_pantry_item` shortcut via the Alexa app

---

## 🤝 Contributing

Pull requests welcome. Please open an issue first for major changes.

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.
