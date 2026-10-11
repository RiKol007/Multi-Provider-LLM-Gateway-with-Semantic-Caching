import time
import uuid
from app.models.chat import ChatCompletionResponse, Choice, ChatMessage, Usage


def normalize_openai_like(provider_response, requested_model: str) -> ChatCompletionResponse:
    """Works for both OpenAI and Groq — their response shapes already match ours closely."""
    choice = provider_response.choices[0]
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=requested_model,
        choices=[
            Choice(
                index=0,
                message=ChatMessage(role="assistant", content=choice.message.content),
                finish_reason=choice.finish_reason or "stop"
            )
        ],
        usage=Usage(
            prompt_tokens=provider_response.usage.prompt_tokens,
            completion_tokens=provider_response.usage.completion_tokens,
            total_tokens=provider_response.usage.total_tokens,
        )
    )


def normalize_anthropic(provider_response, requested_model: str) -> ChatCompletionResponse:
    """Anthropic's response shape is different — content is a list of blocks, usage field names differ."""
    text_content = provider_response.content[0].text
    prompt_tokens = provider_response.usage.input_tokens
    completion_tokens = provider_response.usage.output_tokens

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=requested_model,
        choices=[
            Choice(
                index=0,
                message=ChatMessage(role="assistant", content=text_content),
                finish_reason=provider_response.stop_reason or "stop"
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    )