from openai import AsyncOpenAI
from app.core.config import GROQ_API_KEY

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)


async def call_groq(model: str, messages: list[dict], temperature: float = 1.0, max_tokens: int | None = None):
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response