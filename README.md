# LLM Inference Gateway

A production-style, provider-agnostic proxy for LLM APIs. It mirrors the OpenAI `chat/completions` contract so any existing OpenAI SDK client can point at it with zero code changes, while transparently routing requests across multiple providers, caching repeated and near-duplicate prompts, enforcing per-user budgets, and automatically failing over when a provider is down.

Built as a hands-on learning project to understand how real LLM infrastructure (the kind used by tools like LiteLLM and Portkey) actually works under the hood.

## What it does

- **Provider-agnostic routing** — accepts standard OpenAI-shaped requests and routes them to OpenAI, Groq, or Anthropic based on the requested model name, normalizing every provider's response back into a single consistent shape.
- **Two-layer caching** — an exact-match layer (SHA-256 hash of the request, stored in Redis) catches identical repeats; a semantic layer (local sentence-transformer embeddings + cosine similarity, threshold 0.92) catches differently-worded near-duplicates. Both are backed by Redis with TTL-based expiry.
- **Per-user cost metering** — every request's token usage is converted into a real USD cost using per-model pricing tables, logged to a database, and checked against a per-user budget cap before being charged.
- **Automatic provider fallback** — if the requested provider fails for any reason (auth, rate limit, outage), the gateway automatically retries through a fallback chain to a different provider before giving up, so the caller still gets a successful response.
- **Observability** — instrumented with Prometheus-format metrics (`/metrics`): p95 latency, cache hit rate, provider success/failure rate, and cost per user. A lightweight custom live dashboard (`/dashboard`) visualizes the same data without requiring a separate Grafana install.
- **Load tested** — validated with Locust under 100 concurrent simulated users.

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
        ├─► Groq adapter ──┐
        ├─► OpenAI adapter ─┼─► Normalizer → unified response shape
        └─► Anthropic adapter ┘
        │
        ▼ (on failure)
  Fallback chain → retry on next provider
        │
        ▼
  Cost calculation → budget check → DB log (SQLite/Postgres)
        │
        ▼
  Prometheus metrics + live dashboard
```

## Tech stack

Python, FastAPI, Redis, SQLAlchemy (SQLite locally / Postgres-ready), Prometheus client, sentence-transformers, Locust, OpenAI/Groq/Anthropic SDKs.

## Real results from testing

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

The low median vs. higher p95 reflects the cache working as intended — most repeated/similar prompts resolve in milliseconds from Redis, while genuine cache misses pay the full cost of a real upstream LLM call.

Caching and fallback were also verified directly: an identical prompt sent twice produced a `CACHE HIT` on the second call with no upstream request; a differently-worded but semantically identical prompt ("What is the capital of France?" vs. "Tell me what city is the capital of France") scored 0.93 cosine similarity and was served from cache. A request routed to a provider with no billing configured was automatically retried through the fallback chain and still returned a successful response.

## Setup

```bash
# clone and enter the repo
git clone https://github.com/PRANAVKAKDE613/Unified-LLM-Gateway.git
cd Unified-LLM-Gateway

# create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# install dependencies
pip install -r requirements.txt

# configure environment
cp .env.example .env
# then fill in OPENAI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, REDIS_URL

# make sure Redis is running locally (redis-cli ping should return PONG)

# run the server
uvicorn app.main:app --reload
```

Then visit:
- `http://127.0.0.1:8000/docs` — interactive API docs
- `http://127.0.0.1:8000/dashboard` — live metrics dashboard
- `http://127.0.0.1:8000/metrics` — raw Prometheus metrics

### Load testing

```bash
pip install locust
locust -f locustfile.py --host http://127.0.0.1:8000
```
Then open `http://localhost:8089` and set the desired number of users.

## Known limitations / honest notes

This was built as a learning project, and a few things are deliberately simplified rather than production-hardened:

- **Database**: runs on SQLite locally instead of Postgres, purely due to local disk constraints during development. The data layer is built with SQLAlchemy, so switching to Postgres is a one-line connection string change with no other code changes required.
- **OpenAI / Anthropic billing**: the adapters for both are fully implemented and were verified to construct correct requests, but live end-to-end testing was primarily done against Groq, since OpenAI and Anthropic require funded billing accounts. The fallback chain was proven *because* of this — requests to the unfunded providers correctly fail over to Groq automatically.
- **Semantic cache index**: stored as a simple capped list in Redis with brute-force cosine similarity comparison. This is fine at small scale (project/demo traffic) but would need a proper vector database (e.g. pgvector, Pinecone, Qdrant) to stay performant at production scale.
- **Auth**: user identification is done via a simple `X-User` header rather than real API key issuance/auth, since building a full auth system was out of scope for this project's goals.
- **Observability**: Prometheus metrics are exposed in the correct format and ready to be scraped by a real Prometheus + Grafana stack; the `/dashboard` page is a custom-built lightweight substitute used here to avoid the disk footprint of a full Grafana install on a space-constrained dev machine.

## License

MIT
