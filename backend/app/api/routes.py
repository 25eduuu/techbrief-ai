import asyncio
import logging
import secrets
from collections import deque
from time import monotonic

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict, Field
from app.services.ai.ollama import AIResult

router = APIRouter()
logger = logging.getLogger(__name__)
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class TestPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=2000)


class RateLimiter:
    # Single operator, single process: bounded memory, no Redis required.
    def __init__(self, limit: int):
        self.limit = limit
        self.requests: deque[float] = deque()

    def check(self) -> None:
        now = monotonic()
        while self.requests and self.requests[0] <= now - 60:
            self.requests.popleft()
        if len(self.requests) >= self.limit:
            raise HTTPException(429, "AI rate limit exceeded", headers={"Retry-After": "60"})
        self.requests.append(now)


async def authorize(request: Request, key: str | None = Depends(key_header)) -> None:
    expected = request.app.state.settings.api_key.get_secret_value()
    if not key or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Invalid API key")
    request.app.state.limiter.check()


@router.get("/health")
async def health(request: Request):
    try:
        await asyncio.wait_for(request.app.state.database.ping(), timeout=6)
    except Exception:
        logger.warning("Database health check failed")
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ok", "database": "ok"}


@router.post("/api/ai/test", response_model=AIResult, dependencies=[Depends(authorize)])
async def test_ai(payload: TestPrompt, request: Request):
    # Avoid concurrent generations on a local machine; fail fast instead of queuing.
    lock = request.app.state.ai_lock
    if lock.locked():
        raise HTTPException(429, "AI generation already running")
    async with lock:
        try:
            return await request.app.state.ai.generate(payload.prompt)
        except httpx.TimeoutException:
            raise HTTPException(504, "Ollama timed out") from None
        except httpx.RequestError:
            raise HTTPException(503, "Ollama unreachable") from None
        except (httpx.HTTPStatusError, ValueError):
            logger.warning("Ollama generation failed")
            raise HTTPException(502, "Ollama failed: check server and configured model") from None
