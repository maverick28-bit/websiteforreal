# LLM Chatbot with Key Failover and Response Caching

A production-quality full-stack AI chatbot with automatic API key failover, LiteLLM response caching, and SQLite-backed multi-turn conversation memory.

---

## 1. Live URLs

> **Note:** Deployment requires manual steps (see §Deployment Instructions). After completing them, update this section with live URLs.

| Service  | URL                             |
|----------|---------------------------------|
| Frontend | _Deploy to Vercel/Netlify_      |
| Backend  | _Deploy to Render/Railway_      |
| API Docs | `{BACKEND_URL}/docs`            |
| Health   | `{BACKEND_URL}/health`          |

---

## 2. Run Locally

### With Docker (recommended)

**Prerequisites:** Docker Desktop running, Git

```bash
git clone <repo-url>
cd <project-dir>

# Copy and configure environment
cp .env.example .env
# Edit .env — add your real API keys to LLM_API_KEYS

make up
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

```bash
make down     # Stop the stack
make logs     # Follow logs
make build    # Rebuild images
make test     # Run tests
```

### Without Docker (local dev)

**Prerequisites:** Python 3.11+, Node.js 18+

**Backend:**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Set environment variables
set LLM_API_KEYS=your_key_1,your_key_2       # Windows
# export LLM_API_KEYS=your_key_1,your_key_2  # macOS/Linux

set DATABASE_URL=sqlite:///./local.db
set ENABLE_FAILURE_SIMULATION=true

uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install

# Optional — if backend is not on localhost:8000
# set VITE_API_URL=http://localhost:8000  # Windows (no trailing slash)

npm run dev   # Starts at http://localhost:5173
```

---

## 3. Design Decisions

### Key Failover

The `llm_service.py` implements a sequential retry strategy:

1. API keys are loaded from `LLM_API_KEYS` (comma-separated) and labeled `key_1`, `key_2`, etc.
2. Each request iterates through keys in order.
3. If a key fails with a retryable error (HTTP 429, 500, 502, 503, rate limit, quota, auth), the next key is attempted.
4. `fallback_attempts` in the response counts failed keys.
5. If all keys fail → HTTP 503 `{"detail": "all providers unavailable"}`.
6. Actual API key values are never returned to clients.

The `X-Simulate-Failure` header (when `ENABLE_FAILURE_SIMULATION=true`) injects per-request fake failures to test this logic without exhausting real quotas.

### LiteLLM Caching

LiteLLM's built-in `local` (in-memory) cache is initialized at startup. The cache key is derived from the full message list (system prompt + history + new message) and the model name. When a hit occurs:
- `resolution_source = "LLM_CACHE"`
- `key_id = null`
- `fallback_attempts = 0`
- Response text is identical to the original

This means the second request with the same message in a fresh session will be served from cache.

### SQLite Session Storage

All conversation turns are stored in a single `messages` table with `session_id` as the primary partition key. On every `/chat` request:
1. Previous messages for that `session_id` are fetched (oldest first).
2. They are assembled into a full LiteLLM message list (system → history → new message).
3. Only after a successful LLM response are both the user message and assistant response written to the DB.
4. Failed requests are never persisted.

Sessions survive backend restarts because the SQLite file lives in a Docker named volume at `/data/app.db`.

---

## 4. Verification

### See Failover in Action

```bash
# key_1 fails → key_2 handles the request
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id":"test-fail","message":"Hello"}'
# Response: key_id="key_2", fallback_attempts=1

# All keys fail → 503
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id":"test-503","message":"Hello"}'
# Response: HTTP 503, {"detail":"all providers unavailable"}
```

### See Cache Hits

```bash
# First request — LIVE_INFERENCE
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-A","message":"What is the capital of France?"}'

# Second request (new session, same message) — LLM_CACHE
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"session-B","message":"What is the capital of France?"}'
# metadata.resolution_source = "LLM_CACHE"
# metadata.key_id = null
```

### Per-Message Token Usage

Every response includes `metadata.input_tokens` and `metadata.output_tokens`. These reflect the token counts for that specific request (including history context) and response — never cumulative session totals.

```bash
curl http://localhost:8000/sessions/{session_id}/messages
```

### Health Endpoint

```bash
curl http://localhost:8000/health
# {"status":"ok","keys_configured":2,"cache_enabled":true}
```

---

## 5. Setup Used

- **Editor/IDE:** Antigravity AI IDE (powered by Claude Sonnet 4.6)
- **AI Tools:** Antigravity autonomous agent — generated all backend, frontend, Docker, test, and documentation files
- **Model:** Claude Sonnet 4.6 (Thinking)
- **Build tools:** Python 3.13, pip, Docker Desktop 28.4, Node.js (via Docker)

---

## 6. Bonus Features

Beyond the mandatory requirements, the following extras were added:

| Feature | Description |
|---------|-------------|
| **System prompt editor** | Editable system prompt bar in the UI (locked after first message) |
| **Health badge** | Live backend health indicator in the header (polls every 30s) |
| **Markdown rendering** | AI responses rendered with `react-markdown` + GFM (tables, code blocks, lists) |
| **Suggested prompts** | Welcome screen shows example prompts to click |
| **Auto-resize textarea** | Input field grows with content |
| **New Chat button** | Reloads page to start a fresh session |
| **Scroll-to-bottom** | Auto-scrolls to latest message |
| **FastAPI Swagger UI** | Interactive API docs at `/docs` |

---

## 7. Architecture

```
┌─────────────────────────────────────────────────┐
│                   Docker Network                │
│                                                 │
│  ┌────────────────┐    ┌──────────────────────┐ │
│  │   Frontend     │    │      Backend         │ │
│  │  React + Vite  │───▶│  FastAPI + LiteLLM   │ │
│  │  nginx:80      │    │  uvicorn:8000         │ │
│  │  port 3000     │    │  port 8000            │ │
│  └────────────────┘    └──────────┬───────────┘ │
│                                   │             │
│                         ┌─────────▼──────────┐  │
│                         │  SQLite Volume     │  │
│                         │  /data/app.db      │  │
│                         └────────────────────┘  │
└─────────────────────────────────────────────────┘
              │
              ▼
    ┌──────────────────┐
    │  LiteLLM         │
    │  ┌────────────┐  │
    │  │ Cache (mem)│  │
    │  └────────────┘  │
    │  ┌────────────┐  │
    │  │ key_1      │──▶ Gemini API
    │  │ key_2      │──▶ Gemini API (failover)
    │  └────────────┘  │
    └──────────────────┘
```

---

## 8. Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 5, react-markdown |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| AI | LiteLLM, Gemini 2.0 Flash |
| Database | SQLite (via Python stdlib) |
| Cache | LiteLLM in-memory local cache |
| Testing | pytest, pytest-asyncio |
| Container | Docker, Docker Compose, nginx |

---

## 9. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_API_KEYS` | ✅ | — | Comma-separated API keys (e.g., Gemini) |
| `LLM_MODEL` | — | `gemini/gemini-2.0-flash` | LiteLLM model string |
| `DATABASE_URL` | — | `sqlite:////data/app.db` | SQLite connection URL |
| `ALLOWED_ORIGINS` | — | `http://localhost:3000` | CORS origins (comma-separated) |
| `ENABLE_FAILURE_SIMULATION` | — | `true` | Enable `X-Simulate-Failure` header |
| `DEFAULT_SYSTEM_PROMPT` | — | `You are a helpful AI assistant.` | Default system prompt |

Frontend only:

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend URL for production (e.g., `https://your-backend.onrender.com`) |

---

## 10. API Documentation

### GET /health

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

### POST /chat

**Request:**
```json
{
  "session_id": "s-abc123",
  "message": "What is the capital of France?",
  "system_prompt": "You are a geography expert."
}
```

**Response (live inference):**
```json
{
  "session_id": "s-abc123",
  "reply": "The capital of France is Paris.",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "gemini/gemini-2.0-flash",
    "latency_ms": 812,
    "input_tokens": 42,
    "output_tokens": 9,
    "key_id": "key_1",
    "fallback_attempts": 0
  }
}
```

**Response (cache hit):**
```json
{
  "metadata": {
    "resolution_source": "LLM_CACHE",
    "key_id": null,
    "fallback_attempts": 0,
    ...
  }
}
```

### GET /sessions/{session_id}/messages

```json
{
  "session_id": "s-abc123",
  "messages": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi there!", "metadata": {...}}
  ]
}
```

**404 response:**
```json
{"detail": "session not found"}
```

---

## 11. Testing Instructions

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

**Test coverage (24 tests):**
- Health endpoint structure
- Input validation (empty, too long, missing fields)
- Successful chat response structure
- Message trimming
- Multi-turn history inclusion
- Session isolation
- Session history ordering and metadata
- Failover: key_1 failure → key_2 success
- Failover: all keys fail → 503
- Failed requests not stored in DB
- Cache hit: `LLM_CACHE` resolution source
- Cache hit: `key_id` is null
- Cache hit: token usage returned

---

## 12. Deployment Instructions

### Backend — Render

1. Connect your GitHub repo to [Render](https://render.com)
2. Create a new **Web Service**
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables in Render dashboard:
   - `LLM_API_KEYS=key1,key2`
   - `DATABASE_URL=sqlite:////data/app.db`
   - `ALLOWED_ORIGINS=https://your-frontend.vercel.app`
6. Add a **Disk** mounted at `/data` for SQLite persistence

### Frontend — Vercel

1. Connect your GitHub repo to [Vercel](https://vercel.com)
2. Framework preset: Vite
3. Root directory: `frontend`
4. Set environment variable: `VITE_API_URL=https://your-backend.onrender.com`
5. Deploy

### After deployment

Update `ALLOWED_ORIGINS` in backend to include your Vercel URL.
Update the **Live URLs** section at the top of this README.

---

## 13. Known Limitations

- **SQLite on Render/Railway:** Free tier services have ephemeral file systems. Use a paid Render disk or switch to a managed DB for persistent production storage.
- **In-memory cache resets on restart:** The LiteLLM local cache is not persisted across server restarts. Use Redis cache for production persistence.
- **Single-region:** No multi-region deployment configuration included.
- **No authentication:** Sessions are identified by UUID only — no user accounts.
- **Rate limiting:** No request-level rate limiting on the backend beyond what the LLM providers enforce.
