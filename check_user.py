import asyncio
from app.core.database import AsyncSessionLocal, User
from sqlalchemy import select


async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "testuser"))
        user = result.scalar_one_or_none()
        if user:
            print(f"Username: {user.username}")
            print(f"Budget limit: ${user.budget_limit}")
            print(f"Total spent: ${user.total_spent}")
        else:
            print("User not found")


asyncio.run(check())