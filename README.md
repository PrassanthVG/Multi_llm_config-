# MuruganAI — Dynamic Provider Gateway

Unified AI provider management layer built on **LiteLLM Proxy**.

Your `main.py` talks to **one fixed URL** (`http://localhost:8000`).  
Providers (Vast AI, Scaleway, vLLM, Ollama, OpenAI…) are managed via a React Admin UI and stored in SQLite.  
Adding a new provider → zero code changes in `main.py`.

---

## Architecture

```
Admin UI (React)
    │  configure providers
    ▼
FastAPI Gateway :8000   ←── main.py calls this (one URL, one key, always)
    │  generates config + hot-registers
    ▼
LiteLLM Proxy :4000
    ├── Vast AI VLM  (port 30204, token A)
    ├── Vast AI LLM  (port 30203, token A)
    ├── vLLM on VM   (own IP,    token B)
    └── Scaleway     (SaaS URL,  token C)
```

---

## Quick Start

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
# FastAPI on :8000, LiteLLM proxy auto-starts on :4000
```

### 2. Frontend (optional, served by FastAPI if built)

```bash
cd frontend
npm install
npm run dev        # dev mode on :5173
# or: npm run build && cp -r dist ../backend/frontend/dist
```

### 3. Open the Admin UI

```
http://localhost:8000   (after building frontend)
http://localhost:5173   (dev mode)
```

---

## Adding a Provider via UI

1. Click **+ Add provider**
2. Choose a preset (Vast AI / Scaleway / vLLM / Ollama / OpenAI)
3. Fill in: alias name, model name, API Base URL, API Key
4. Click **Save** — provider is **instantly live** in LiteLLM (no restart)
5. Click **★** to set as default LLM or VLM

---

## Using in main.py

```python
import httpx, os

GATEWAY_URL = "http://localhost:8000"
GATEWAY_KEY  = "sk-murugan-gateway-2024"

_client = httpx.AsyncClient(
    base_url=GATEWAY_URL,
    headers={"Authorization": f"Bearer {GATEWAY_KEY}"},
    timeout=120,
)

# Use default LLM (marked ★ in UI)
async def call_llm(messages):
    r = await _client.post("/api/proxy/chat", json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]

# Use default VLM
async def call_vlm(messages):
    r = await _client.post("/api/proxy/chat/vlm", json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]

# Use a specific provider by alias
async def call_provider(alias, messages):
    r = await _client.post(f"/api/proxy/chat/model/{alias}", json={"messages": messages})
    return r.json()["choices"][0]["message"]["content"]
```

That's it. No URLs, no tokens, no payload format concerns in main.py.

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/providers/` | Create provider |
| GET  | `/api/providers/` | List all providers |
| PUT  | `/api/providers/{id}` | Update provider |
| DELETE | `/api/providers/{id}` | Delete provider |
| POST | `/api/providers/{id}/activate` | Activate provider |
| POST | `/api/providers/{id}/deactivate` | Deactivate provider |
| POST | `/api/providers/{id}/set-default` | Set as default LLM/VLM |
| GET  | `/api/providers/defaults/active` | Get current default aliases |
| POST | `/api/proxy/chat` | Chat via default LLM |
| POST | `/api/proxy/chat/vlm` | Chat via default VLM |
| POST | `/api/proxy/chat/model/{alias}` | Chat via explicit provider |
| GET  | `/api/proxy/models` | List LiteLLM registered models |
| GET  | `/api/health/` | Health check |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_MASTER_KEY` | `sk-murugan-gateway-2024` | LiteLLM proxy auth key |
| `LITELLM_PORT` | `4000` | LiteLLM proxy port |
| `GATEWAY_URL` | `http://localhost:8000` | Gateway base URL (for main.py) |
| `ACTIVE_LLM_ALIAS` | *(DB default)* | Override default LLM alias |
| `ACTIVE_VLM_ALIAS` | *(DB default)* | Override default VLM alias |

---

## File Structure

```
murugan-provider-gateway/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── database.py                # SQLAlchemy async setup
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── models/
│   │   └── provider.py            # Provider DB model
│   ├── routers/
│   │   ├── providers.py           # CRUD API
│   │   ├── proxy.py               # Unified AI call endpoint
│   │   └── health.py
│   ├── services/
│   │   └── litellm_manager.py     # LiteLLM process + hot-reload
│   └── main_updated.py            # Your updated main.py example
├── frontend/
│   └── src/
│       └── App.jsx                # React Admin UI
├── docker-compose.yml
└── README.md
```
