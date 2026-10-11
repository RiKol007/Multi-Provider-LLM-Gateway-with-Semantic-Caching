import redis.asyncio as redis
from app.core.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True, protocol=2)


import hashlib
import json


def generate_cache_key(model: str, messages: list[dict], temperature: float) -> str:
    """Creates a consistent SHA-256 fingerprint of a request."""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # sort_keys=True ensures the same data always produces the same string, regardless of dict ordering
    serialized = json.dumps(payload, sort_keys=True)
    hash_value = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"cache:exact:{hash_value}"

CACHE_TTL_SECONDS = 3600  # cached responses expire after 1 hour


async def get_cached_response(cache_key: str) -> str | None:
    return await redis_client.get(cache_key)


async def set_cached_response(cache_key: str, response_json: str):
    await redis_client.set(cache_key, response_json, ex=CACHE_TTL_SECONDS)

from app.core.embeddings import get_embedding, cosine_similarity

SEMANTIC_INDEX_KEY = "cache:semantic:index"
SIMILARITY_THRESHOLD = 0.92


async def find_semantic_match(prompt_text: str) -> str | None:
    """Looks through previously cached prompts for a near-duplicate match."""
    new_vector = get_embedding(prompt_text)

    # Get all stored semantic cache entries (each stored as a small JSON record)
    entries = await redis_client.lrange(SEMANTIC_INDEX_KEY, 0, -1)

    best_score = 0.0
    best_response = None

    for entry in entries:
        record = json.loads(entry)
        score = cosine_similarity(new_vector, record["vector"])
        if score > best_score:
            best_score = score
            best_response = record["response"]

    if best_score >= SIMILARITY_THRESHOLD:
        print(f"SEMANTIC HIT (score={best_score:.4f})")
        return best_response

    print(f"SEMANTIC MISS (best score={best_score:.4f})")
    return None


async def store_semantic_entry(prompt_text: str, response_json: str):
    vector = get_embedding(prompt_text)
    record = json.dumps({"vector": vector, "response": response_json})
    await redis_client.rpush(SEMANTIC_INDEX_KEY, record)
    # Keep the list from growing forever — cap at last 500 entries
    await redis_client.ltrim(SEMANTIC_INDEX_KEY, -500, -1)
