from openai import AsyncOpenAI
from app.core.config import OPENAI_API_KEY

client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)


async def call_openai(model: str, messages: list[dict], temperature: float = 1.0, max_tokens: int | None = None):
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response