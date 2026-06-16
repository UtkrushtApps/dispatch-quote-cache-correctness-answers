from __future__ import annotations

import redis

from app.config import Settings


def clear_cache() -> None:
    settings = Settings()
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )
    for key in client.scan_iter("dispatch:*"):
        client.delete(key)
    print("Cleared dispatch cache keys.")


if __name__ == "__main__":
    clear_cache()
