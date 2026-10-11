# Unified LLM Gateway

A production-style, provider-agnostic proxy for LLM APIs. It mirrors the OpenAI `chat/completions` contract, so any existing OpenAI SDK client can point at it with zero code changes. Behind that single endpoint, the gateway routes requests across multiple providers, caches repeated and near-duplicate prompts, enforces per-user budgets, and automatically fails over when a provider is down.

Built as a hands-on learning project to understand how real LLM infrastructure (the kind used by tools like LiteLLM and Portkey) works under the hood.

**Authors:** [Ritesh Kolte](https://github.com/RiKol007) and Pranav Kakde

## Features

- **Provider-agnostic routing:** accepts standard OpenAI-shaped requests and routes them to OpenAI, Groq or Anthropic based on the model name, then normalizes every provider's response into one consistent shape.
- **Two-layer caching:** an exact-match layer (SHA-256 hash of the request, stored in Redis) catches identical repeats; a semantic layer (local sentence-transformer embeddings + cosine similarity, threshold 0.92) catches differently worded near-duplicates. Both use Redis with TTL-based expiry.
- **Per-user cost metering:** token usage is converted into a real USD cost using per-model pricing tables, logged to a database, and checked against a per-user budget cap.
- **Automatic provider fallback:** if the requested provider fails (auth error, rate limit, outage), the gateway retries through a fallback chain on other providers, so the caller still gets a successful response.
- **Observability:** Prometheus-format metrics at `/metrics` (latency, cache hits, provider success/failure, cost per user), plus a lightweight live dashboard at `/dashboard`.
- **Load tested:** validated with Locust under 100 concurrent simulated users.

## Architecture

```
Client (OpenAI SDK or raw HTTP)
        │
        ▼
  FastAPI /v1/chat/completions
        │
        ├─► Exact-match cache check (Redis, SHA-256 key)
        ├─► Semantic cache check (local embeddings, cosine similarity ≥ 0.92)
        │
        ▼ (cache miss)
  Provider router (model name → provider)
        │
        ├─► Groq adapter ──────┐
        ├─► OpenAI adapter ────┼─► Normalizer → unified response shape
        └─► Anthropic adapter ─┘
        │
        ▼ (on failure)
  Fallback chain → retry on next provider
        │
        ▼
  Cost calculation → budget check → DB log (SQLite / Postgres-ready)
        │
        ▼
  Prometheus metrics + live dashboard
```

### Model routing and fallback

| Model name contains | Provider | Fallback order |
|---|---|---|
| `llama`, `mixtral`, `gemma` | Groq | OpenAI (`gpt-4o-mini`) → Anthropic (`claude-3-5-haiku`) |
| `claude` | Anthropic | Groq (`llama-3.1-8b-instant`) → OpenAI (`gpt-4o-mini`) |
| anything else | OpenAI | Groq (`llama-3.1-8b-instant`) → Anthropic (`claude-3-5-haiku`) |

## Tech stack

Python, FastAPI, Redis, SQLAlchemy (SQLite locally, Postgres-ready), Prometheus client, sentence-transformers, Locust, Docker Compose, OpenAI / Groq / Anthropic SDKs.

## Results from testing

These numbers come from an actual local Locust run against this codebase, not estimates:

| Metric | Result |
|---|---|
| Concurrent simulated users | 100 |
| Total requests | 480 |
| Failure rate | 0% |
| Sustained throughput | ~32.8 requests/sec |
| Median latency | 63 ms |
| p95 latency | 2.1 s |
| p99 latency | 2.4 s |

The low median versus the higher p95 reflects the cache working as intended: most repeated or similar prompts resolve in milliseconds from Redis, while genuine cache misses pay the full cost of a real upstream LLM call.

Caching and fallback were also verified directly:

- An identical prompt sent twice produced a `CACHE HIT` on the second call, with no upstream request.
- A differently worded but equivalent prompt ("What is the capital of France?" vs. "Tell me what city is the capital of France") scored 0.93 cosine similarity and was served from cache.
- A request routed to a provider with no billing configured was automatically retried through the fallback chain and still returned a successful response.

## Project structure

```
app/
├── main.py              # FastAPI app, /health, /metrics, /dashboard
├── routers/
│   ├── chat.py          # POST /v1/chat/completions
│   └── dashboard.py     # GET /dashboard/data (feeds the live dashboard)
├── providers/           # OpenAI, Groq and Anthropic adapters
├── core/
│   ├── router.py        # model → provider routing and fallback chain
│   ├── cache.py         # exact-match + semantic caching (Redis)
│   ├── embeddings.py    # sentence-transformer embeddings, cosine similarity
│   ├── normalizer.py    # unified response format
│   ├── pricing.py       # per-model token pricing
│   ├── billing.py       # cost calculation and budget checks
│   ├── database.py      # SQLAlchemy models and session
│   ├── metrics.py       # Prometheus metrics
│   └── config.py        # environment configuration
├── models/chat.py       # request/response schemas
└── static/dashboard.html
locustfile.py            # load test
set_low_budget.py        # sets a near-zero budget to test budget enforcement
check_user.py            # prints a user's budget and total spend
docker-compose.yml       # Redis (and Postgres) containers
```

## Setup

```bash
# clone and enter the repo
git clone https://github.com/RiKol007/Unified-LLM-Gateway.git
cd Unified-LLM-Gateway

# create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# install dependencies
pip install -r requirements.txt

# configure environment
cp .env.example .env
# then fill in OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY

# start Redis (requires Docker)
docker compose up -d redis

# run the server
uvicorn app.main:app --reload
```

Then visit:

- `http://127.0.0.1:8000/docs`: interactive API docs
- `http://127.0.0.1:8000/dashboard`: live metrics dashboard
- `http://127.0.0.1:8000/metrics`: raw Prometheus metrics

## Usage

Point any OpenAI SDK client at the gateway. The optional `X-User` header identifies the user for cost metering (it defaults to `testuser`).

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")

response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    extra_headers={"X-User": "testuser"},
)
print(response.choices[0].message.content)
```

Or with curl:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-User: testuser" \
  -d '{"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "Hello!"}]}'
```

## Load testing

```bash
pip install locust
locust -f locustfile.py --host http://127.0.0.1:8000
```

Then open `http://localhost:8089` and set the number of users.

## Known limitations

This was built as a learning project, and a few things are deliberately simplified rather than production-hardened:

- **Database:** runs on SQLite locally instead of Postgres, because of local disk constraints during development. The data layer uses SQLAlchemy, so switching to Postgres is a connection-string change.
- **OpenAI / Anthropic billing:** both adapters are fully implemented and were verified to build correct requests, but live end-to-end testing was mainly done against Groq, since OpenAI and Anthropic require funded billing accounts. This is also how the fallback chain was proven: requests to the unfunded providers correctly failed over to Groq.
- **Semantic cache index:** stored as a simple capped list in Redis with brute-force cosine similarity. This works at demo scale, but production scale would need a vector database (e.g. pgvector, Qdrant or Pinecone).
- **Auth:** users are identified by a simple `X-User` header rather than issued API keys, since a full auth system was out of scope.
- **Observability:** metrics are exposed in Prometheus format, ready to be scraped by a real Prometheus + Grafana stack; the `/dashboard` page is a lightweight substitute used to avoid installing Grafana on a space-constrained dev machine.

## License

MIT
