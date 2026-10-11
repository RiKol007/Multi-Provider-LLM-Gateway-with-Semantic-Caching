import asyncio
from app.core.database import AsyncSessionLocal, User
from sqlalchemy import select


async def set_budget():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "testuser"))
        user = result.scalar_one_or_none()
        user.budget_limit = 0.000001  # essentially zero, to force the next real call to exceed it
        await session.commit()
        print(f"Set budget_limit to ${user.budget_limit} for testing")


asyncio.run(set_budget())