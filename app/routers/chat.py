import time
from fastapi import APIRouter, Header, HTTPException
from app.models.chat import ChatCompletionRequest, ChatCompletionResponse
from app.core.router import route_chat_completion
from app.core.billing import check_and_charge_user, BudgetExceededError
from app.core.metrics import REQUEST_LATENCY, COST_TOTAL, CACHE_RESULT, PROVIDER_RESULT

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest, x_user: str = Header(default="testuser")):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    start_time = time.time()

    try:
        response, provider, cache_status = await route_chat_completion(
            model=request.model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        PROVIDER_RESULT.labels(provider=provider, outcome="success").inc()
    except Exception as e:
        PROVIDER_RESULT.labels(provider="unknown", outcome="failure").inc()
        raise

    elapsed = time.time() - start_time
    REQUEST_LATENCY.labels(provider=provider).observe(elapsed)
    CACHE_RESULT.labels(status=cache_status).inc()

    try:
        cost = await check_and_charge_user(
            username=x_user,
            model=request.model,
            provider=provider,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            cache_status=cache_status,
        )
        COST_TOTAL.labels(username=x_user).inc(cost)
    except BudgetExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))

    return response