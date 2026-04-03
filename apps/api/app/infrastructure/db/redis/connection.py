from __future__ import annotations

from redis.asyncio import Redis


class RedisConnectionManager:
    def __init__(self) -> None:
        self.client: Redis | None = None

    async def connect(self, url: str) -> None:
        if self.client is None:
            self.client = Redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def ping(self) -> bool:
        if self.client is None:
            return False
        return bool(await self.client.ping())
