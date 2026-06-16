from __future__ import annotations

import pytest
import redis

from app.config import Settings


@pytest.fixture(autouse=True)
def clean_cache():
    settings = Settings()
    client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True,
    )
    for key in client.scan_iter("dispatch:*"):
        client.delete(key)
    yield
    for key in client.scan_iter("dispatch:*"):
        client.delete(key)
