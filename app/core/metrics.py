from prometheus_client import Counter, Histogram

# p95 latency — a Histogram tracks request durations in buckets, letting Prometheus calculate percentiles later
REQUEST_LATENCY = Histogram(
    "llm_gateway_request_latency_seconds",
    "Time taken to process a chat completion request",
    ["provider"]
)

# Cost per user — a Counter that only ever goes up, tracking cumulative $ spent
COST_TOTAL = Counter(
    "llm_gateway_cost_usd_total",
    "Total cost in USD",
    ["username"]
)

# Cache hit rate — separate counters for hits vs misses; rate is hits / (hits + misses)
CACHE_RESULT = Counter(
    "llm_gateway_cache_result_total",
    "Cache lookup results",
    ["status"]  # "exact_hit", "semantic_hit", or "miss"
)

# Provider error rate — counts successes vs failures per provider
PROVIDER_RESULT = Counter(
    "llm_gateway_provider_result_total",
    "Provider call results",
    ["provider", "outcome"]  # outcome: "success" or "failure"
)