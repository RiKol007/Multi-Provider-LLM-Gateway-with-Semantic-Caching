from fastapi import FastAPI
from fastapi.responses import Response, FileResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.routers import chat, dashboard
from app.core.database import init_db

app = FastAPI(title="LLM Inference Gateway")

app.include_router(chat.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("app/static/dashboard.html")