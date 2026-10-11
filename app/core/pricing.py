# Prices are in USD per 1 million tokens (a common way providers quote pricing)
# These are approximate — for a learning project, exact accuracy matters less than the mechanism being correct

PRICING = {
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
}

DEFAULT_PRICING = {"input": 0.50, "output": 1.50}  # fallback for unknown models


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = PRICING.get(model, DEFAULT_PRICING)
    input_cost = (prompt_tokens / 1_000_000) * rates["input"]
    output_cost = (completion_tokens / 1_000_000) * rates["output"]
    return round(input_cost + output_cost, 6)