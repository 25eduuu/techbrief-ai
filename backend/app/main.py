import asyncio
import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from app.api.routes import RateLimiter, router
from app.core.config import Settings
from app.core.database import Database
from app.services.ai.ollama import OllamaProvider


class BodyLimitMiddleware:
    def __init__(self, app, limit=16384):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.limit:
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        async def replay():
            return messages.pop(0) if messages else await receive()
        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        logging.basicConfig(level=logging.INFO)
        database = Database(settings.database_url.get_secret_value())
        app.state.database = database
        try:
            async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=settings.ollama_timeout,
                                         trust_env=False) as client:
                app.state.ai = OllamaProvider(client, settings.ollama_model)
                yield
        finally:
            await database.close()

    app = FastAPI(title="TECHBRIEF AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = RateLimiter(settings.ai_requests_per_minute)
    app.state.ai_lock = asyncio.Lock()
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])
    app.include_router(router)
    return app
