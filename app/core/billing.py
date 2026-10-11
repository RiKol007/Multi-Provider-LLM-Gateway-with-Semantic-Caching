from sqlalchemy import select
from app.core.database import AsyncSessionLocal, User, RequestLog
from app.core.pricing import calculate_cost


class BudgetExceededError(Exception):
    pass


async def check_and_charge_user(username: str, model: str, provider: str,
                                  prompt_tokens: int, completion_tokens: int,
                                  cache_status: str) -> float:
    cost = calculate_cost(model, prompt_tokens, completion_tokens)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"User '{username}' not found")

        if user.total_spent + cost > user.budget_limit:
            raise BudgetExceededError(
                f"User '{username}' would exceed budget: "
                f"${user.total_spent:.4f} + ${cost:.4f} > ${user.budget_limit:.2f}"
            )

        # Deduct from budget
        user.total_spent += cost

        # Log this request
        log_entry = RequestLog(
            username=username,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
            cache_status=cache_status,
        )
        session.add(log_entry)

        await session.commit()

    return cost