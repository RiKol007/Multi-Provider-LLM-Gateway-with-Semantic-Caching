from anthropic import AsyncAnthropic
from app.core.config import ANTHROPIC_API_KEY

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def call_anthropic(model: str, messages: list[dict], temperature: float = 1.0, max_tokens: int | None = None):
    # Anthropic separates "system" messages from the main message list
    system_prompt = None
    user_messages = []
    for m in messages:
        if m["role"] == "system":
            system_prompt = m["content"]
        else:
            user_messages.append(m)

    response = await client.messages.create(
        model=model,
        messages=user_messages,
        system=system_prompt if system_prompt else "",
        max_tokens=max_tokens or 1024,  # Anthropic REQUIRES max_tokens, unlike OpenAI
        temperature=temperature,
    )
    return response