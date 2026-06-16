from __future__ import annotations

import json

import redis

from app.config import Settings


class RedisCacheAdapter:
    """Thin local Redis adapter for read-through memoization of agent results."""

    def __init__(self, settings: Settings) -> None:
        self._client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self._ttl = settings.cache_ttl_seconds

    def get_json(self, key: str) -> dict | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set_json(self, key: str, value: dict) -> None:
        self._client.setex(key, self._ttl, json.dumps(value, sort_keys=True))

    def ping(self) -> bool:
        return bool(self._client.ping())
