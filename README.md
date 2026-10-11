# Multi-Provider LLM Gateway with Semantic Caching

An OpenAI-compatible gateway that sits between your application and multiple LLM providers. Point any OpenAI SDK client at it, and the gateway routes each request to OpenAI, Groq or Anthropic Claude, serves repeated and reworded prompts from a Redis cache, tracks cost per user, and automatically switches providers when one fails.

> Built as a hands-on project to learn how real LLM infrastructure (similar to LiteLLM or Portkey) works under the hood.

## Highlights

| Capability | How it works |
|---|---|
| **One API, three providers** | A single `/v1/chat/completions` endpoint in the OpenAI format; the model name decides whether OpenAI, Groq or Anthropic handles the request |
| **Automatic fallback** | If a provider fails (auth error, rate limit, outage), the request is retried on the next provider in a fallback chain |
| **Two-layer caching** | Exact match via a SHA-256 hash of the request, plus semantic match via sentence-transformer embeddings (cosine similarity ≥ 0.92), both stored in Redis with TTL expiry |
| **Cost tracking** | Token usage is converted to USD with per-model pricing, logged per user, and checked against a budget cap |
| **Monitoring** | Prometheus-format metrics at `/metrics` and a live dashboard at `/dashboard` |

## How a request flows

```
Client (OpenAI SDK / HTTP)
        │
        ▼
FastAPI  /v1/chat/completions
        │
        ├── 1. Exact-match cache (Redis, SHA-256 key) ──── hit ──► return cached answer
        ├── 2. Semantic cache (embeddings, cos ≥ 0.92) ─── hit ──► return cached answer
        │
        ▼ miss
Router: model name → provider (Groq / OpenAI / Anthropic)
        │
        ├── success ──► normalize response to OpenAI format
        └── failure ──► fallback chain → next provider
        │
        ▼
Cost calculation → budget check → log to database
        │
        ▼
Metrics (/metrics) and dashboard (/dashboard)
```

### Routing table

| Model name contains | Primary provider | Fallback order |
|---|---|---|
| `llama`, `mixtral`, `gemma` | Groq | OpenAI (`gpt-4o-mini`) → Anthropic (`claude-3-5-haiku`) |
| `claude` | Anthropic | Groq (`llama-3.1-8b-instant`) → OpenAI (`gpt-4o-mini`) |
| anything else | OpenAI | Groq (`llama-3.1-8b-instant`) → Anthropic (`claude-3-5-haiku`) |

## Tech stack

**Backend:** Python, FastAPI, Pydantic
**Caching:** Redis, sentence-transformers
**Database:** SQLAlchemy (SQLite for local development, PostgreSQL-ready via Docker Compose)
**Providers:** OpenAI, Groq and Anthropic SDKs
**Monitoring and testing:** Prometheus client, Locust

## Test results

Measured with Locust on a local machine:

| Metric | Result |
|---|---|
| Concurrent users | 100 |
| Total requests | 480 |
| Failure rate | **0%** |
| Throughput | ~32.8 requests/sec |
| Median latency | **63 ms** |
| p95 / p99 latency | 2.1 s / 2.4 s |

Cached prompts return in milliseconds, which keeps the median low; the higher p95 comes from genuine cache misses that wait for a real LLM response.

Verified behaviour:

- **Exact cache:** sending the same prompt twice returned a cache hit the second time, with no provider call.
- **Semantic cache:** "What is the capital of France?" and "Tell me what city is the capital of France" scored 0.93 similarity, so the second was served from cache.
- **Fallback:** a request sent to a provider without billing set up was retried automatically on another provider and still succeeded.

## Getting started

```bash
git clone https://github.com/RiKol007/Unified-LLM-Gateway.git
cd Unified-LLM-Gateway

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt

cp .env.example .env             # add your OPENAI, GROQ and ANTHROPIC API keys

docker compose up -d redis       # start Redis
uvicorn app.main:app --reload    # start the gateway
```

| URL | What you get |
|---|---|
| `http://127.0.0.1:8000/docs` | Interactive API docs |
| `http://127.0.0.1:8000/dashboard` | Live dashboard |
| `http://127.0.0.1:8000/metrics` | Raw Prometheus metrics |

## Example request

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed")

reply = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    extra_headers={"X-User": "testuser"},   # identifies the user for cost tracking
)
print(reply.choices[0].message.content)
```

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
# open http://localhost:8089 and choose the number of users
```

## Project structure

```
app/
├── main.py              FastAPI app: /health, /metrics, /dashboard
├── routers/
│   ├── chat.py          POST /v1/chat/completions
│   └── dashboard.py     data for the live dashboard
├── providers/           OpenAI, Groq and Anthropic adapters
├── core/
│   ├── router.py        model → provider routing and fallback chain
│   ├── cache.py         exact-match and semantic caching (Redis)
│   ├── embeddings.py    sentence-transformer embeddings and similarity
│   ├── normalizer.py    converts every provider's reply to one format
│   ├── pricing.py       per-model token prices
│   ├── billing.py       cost calculation and budget checks
│   ├── database.py      SQLAlchemy models and session
│   ├── metrics.py       Prometheus metrics
│   └── config.py        environment settings
├── models/chat.py       request and response schemas
└── static/dashboard.html
locustfile.py            load test
set_low_budget.py        sets a tiny budget to test budget enforcement
check_user.py            shows a user's budget and spend
docker-compose.yml       Redis and PostgreSQL containers
```

## Limitations and next steps

- **Database:** runs on SQLite locally; moving to PostgreSQL only needs a new connection string, since the data layer uses SQLAlchemy.
- **Provider testing:** OpenAI and Anthropic adapters are implemented, but live testing used mainly Groq because the others need paid accounts. This is also how the fallback chain was proven.
- **Semantic cache scale:** embeddings are compared one by one; larger traffic would need a vector database such as pgvector or Qdrant.
- **Authentication:** users are identified by an `X-User` header; real API keys would be the next step.
- **Monitoring:** metrics are Prometheus-ready for a full Prometheus + Grafana setup; the built-in dashboard is a lightweight alternative.

## Contributors

- **[Ritesh Kolte](https://github.com/RiKol007):** FastAPI service, provider routing and fallback, Redis caching (exact and semantic), SQLAlchemy data layer
