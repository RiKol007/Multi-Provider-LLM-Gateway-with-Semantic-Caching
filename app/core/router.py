import json
from app.providers.groq_provider import call_groq
from app.providers.openai_provider import call_openai
from app.providers.anthropic_provider import call_anthropic
from app.core.normalizer import normalize_openai_like, normalize_anthropic
from app.core.cache import generate_cache_key, get_cached_response, set_cached_response
from app.models.chat import ChatCompletionResponse


GROQ_MODELS = ["llama", "mixtral", "gemma"]
ANTHROPIC_MODELS = ["claude"]



from app.core.cache import (
    generate_cache_key, get_cached_response, set_cached_response,
    find_semantic_match, store_semantic_entry
)

# If the primary provider fails, try these models on other providers, in order
FALLBACK_CHAIN = {
    "groq": [("openai", "gpt-4o-mini"), ("anthropic", "claude-3-5-haiku-20241022")],
    "openai": [("groq", "llama-3.1-8b-instant"), ("anthropic", "claude-3-5-haiku-20241022")],
    "anthropic": [("groq", "llama-3.1-8b-instant"), ("openai", "gpt-4o-mini")],
}

async def call_with_fallback(model: str, messages: list[dict], temperature: float, max_tokens):
    """Tries the primary provider, then falls back through the chain on failure."""
    primary_provider = detect_provider(model)

    attempts = [(primary_provider, model)] + FALLBACK_CHAIN.get(primary_provider, [])

    last_error = None

    for provider_name, attempt_model in attempts:
        try:
            print(f"Attempting provider={provider_name} model={attempt_model}")
            if provider_name == "groq":
                raw_response = await call_groq(attempt_model, messages, temperature, max_tokens)
                normalized = normalize_openai_like(raw_response, attempt_model)
            elif provider_name == "anthropic":
                raw_response = await call_anthropic(attempt_model, messages, temperature, max_tokens)
                normalized = normalize_anthropic(raw_response, attempt_model)
            else:
                raw_response = await call_openai(attempt_model, messages, temperature, max_tokens)
                normalized = normalize_openai_like(raw_response, attempt_model)

            return normalized, provider_name

        except Exception as e:
            print(f"Provider {provider_name} failed: {e}")
            last_error = e
            continue  # try the next provider in the chain

    # If we get here, every provider in the chain failed
    raise last_error


def detect_provider(model: str) -> str:
    model_lower = model.lower()
    if any(model_lower.startswith(prefix) for prefix in ANTHROPIC_MODELS):
        return "anthropic"
    if any(model_lower.startswith(prefix) for prefix in GROQ_MODELS):
        return "groq"
    return "openai"

def extract_prompt_text(messages: list[dict]) -> str:
    """Grabs the last user message's content, used for semantic comparison."""
    for m in reversed(messages):
        if m["role"] == "user":
            return m["content"]
    return ""


async def route_chat_completion(model: str, messages: list[dict], temperature: float, max_tokens):
    cache_key = generate_cache_key(model, messages, temperature)
    cached = await get_cached_response(cache_key)

    if cached is not None:
        print(f"CACHE HIT (exact): {cache_key}")
        return ChatCompletionResponse.model_validate_json(cached), "cache", "exact_hit"

    print(f"CACHE MISS (exact): {cache_key}")

    prompt_text = extract_prompt_text(messages)
    semantic_match = await find_semantic_match(prompt_text)

    if semantic_match is not None:
        return ChatCompletionResponse.model_validate_json(semantic_match), "cache", "semantic_hit"

    normalized, provider = await call_with_fallback(model, messages, temperature, max_tokens)

    response_json = normalized.model_dump_json()
    await set_cached_response(cache_key, response_json)
    await store_semantic_entry(prompt_text, response_json)

    return normalized, provider, "miss"