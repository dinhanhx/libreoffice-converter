import asyncio
import os

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

ACTIVE_KEY = "conv:active"
QUEUED_KEY = "conv:queued"

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", 2))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", 20))
QUEUE_TIMEOUT = float(os.getenv("QUEUE_TIMEOUT_SECONDS", 60))
POLL_INTERVAL = float(os.getenv("QUEUE_POLL_INTERVAL_MS", 200)) / 1000


class ConversionQueueMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        redis: Redis = request.app.state.redis

        queued = await redis.incr(QUEUED_KEY)
        if queued > MAX_QUEUE_SIZE:
            await redis.decr(QUEUED_KEY)
            active = int(await redis.get(ACTIVE_KEY) or 0)
            return JSONResponse(
                status_code=503,
                content={"detail": "Queue full", "active": active, "queued": queued - 1},
                headers={"Retry-After": "5"},
            )

        try:
            acquired = await self._wait_for_slot(redis)
        except asyncio.TimeoutError:
            await redis.decr(QUEUED_KEY)
            active = int(await redis.get(ACTIVE_KEY) or 0)
            return JSONResponse(
                status_code=503,
                content={"detail": "Queue timeout", "active": active, "queued": MAX_QUEUE_SIZE},
                headers={"Retry-After": "5"},
            )

        if not acquired:
            await redis.decr(QUEUED_KEY)
            active = int(await redis.get(ACTIVE_KEY) or 0)
            return JSONResponse(
                status_code=503,
                content={"detail": "Queue full", "active": active, "queued": MAX_QUEUE_SIZE},
                headers={"Retry-After": "5"},
            )

        await redis.decr(QUEUED_KEY)
        await redis.incr(ACTIVE_KEY)
        try:
            return await call_next(request)
        finally:
            await redis.decr(ACTIVE_KEY)

    async def _wait_for_slot(self, redis: Redis) -> bool:
        deadline = asyncio.get_event_loop().time() + QUEUE_TIMEOUT
        while True:
            active = int(await redis.get(ACTIVE_KEY) or 0)
            if active < MAX_CONCURRENT:
                return True
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            await asyncio.sleep(min(POLL_INTERVAL, remaining))
