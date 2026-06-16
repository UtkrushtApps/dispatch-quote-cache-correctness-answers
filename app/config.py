from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Settings:
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    cache_ttl_seconds: int = 120
    agent_timeout_seconds: float = 2.0
