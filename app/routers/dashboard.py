from fastapi import APIRouter
from prometheus_client import REGISTRY
from app.core.database import AsyncSessionLocal, RequestLog
from sqlalchemy import select, func

router = APIRouter()


@router.get("/dashboard/data")
async def dashboard_data():
    # Pull aggregate data straight from our database — simpler and more reliable
    # than re-parsing Prometheus's text format for a small custom dashboard
    async with AsyncSessionLocal() as session:
        total_requests = await session.scalar(select(func.count(RequestLog.id)))
        total_cost = await session.scalar(select(func.sum(RequestLog.cost_usd))) or 0.0

        cache_hits = await session.scalar(
            select(func.count(RequestLog.id)).where(RequestLog.cache_status != "miss")
        )
        cache_misses = await session.scalar(
            select(func.count(RequestLog.id)).where(RequestLog.cache_status == "miss")
        )

        # Per-provider breakdown
        provider_rows = await session.execute(
            select(RequestLog.provider, func.count(RequestLog.id))
            .group_by(RequestLog.provider)
        )
        provider_counts = {row[0]: row[1] for row in provider_rows}

        # Per-user cost breakdown
        user_rows = await session.execute(
            select(RequestLog.username, func.sum(RequestLog.cost_usd))
            .group_by(RequestLog.username)
        )
        user_costs = {row[0]: row[1] for row in user_rows}

        total = (cache_hits or 0) + (cache_misses or 0)
        cache_hit_rate = (cache_hits / total * 100) if total > 0 else 0.0

    return {
        "total_requests": total_requests or 0,
        "total_cost_usd": round(total_cost, 6),
        "cache_hit_rate_percent": round(cache_hit_rate, 2),
        "cache_hits": cache_hits or 0,
        "cache_misses": cache_misses or 0,
        "provider_counts": provider_counts,
        "user_costs": {k: round(v, 6) for k, v in user_costs.items()},
    }