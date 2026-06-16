from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.messages import QuoteRequest
from app.orchestrator import DispatchManager


@pytest.fixture
def manager() -> DispatchManager:
    return DispatchManager(Settings())


def _heavy_refrigerated() -> QuoteRequest:
    return QuoteRequest(
        origin="BLR",
        destination="DEL",
        cargo_weight_kg=6000,
        service_tier="refrigerated",
    )


def _light_dry() -> QuoteRequest:
    return QuoteRequest(
        origin="BLR",
        destination="DEL",
        cargo_weight_kg=500,
        service_tier="standard",
    )


def test_distinct_requests_get_distinct_quotes(manager: DispatchManager) -> None:
    heavy = asyncio.get_event_loop().run_until_complete(manager.build_quote(_heavy_refrigerated()))
    light = asyncio.get_event_loop().run_until_complete(manager.build_quote(_light_dry()))

    assert heavy.service_tier == "refrigerated"
    assert light.service_tier == "standard"
    assert heavy.eta_hours != light.eta_hours
    assert heavy.capacity_score != light.capacity_score


def test_concurrent_mixed_requests_do_not_bleed(manager: DispatchManager) -> None:
    async def run() -> list:
        requests = []
        for _ in range(10):
            requests.append(_heavy_refrigerated())
            requests.append(_light_dry())
        return await asyncio.gather(*(manager.build_quote(r) for r in requests))

    responses = asyncio.get_event_loop().run_until_complete(run())

    for resp in responses:
        if resp.service_tier == "refrigerated":
            assert resp.capacity_score is not None and resp.capacity_score < 1.0
        if resp.service_tier == "standard":
            assert resp.eta_hours is not None
            assert resp.eta_hours < 36.0

    refrigerated_etas = {r.eta_hours for r in responses if r.service_tier == "refrigerated"}
    standard_etas = {r.eta_hours for r in responses if r.service_tier == "standard"}
    assert refrigerated_etas.isdisjoint(standard_etas)


def test_identical_requests_reuse_cache(manager: DispatchManager) -> None:
    call_counter = {"count": 0}
    original = manager._eta_agent.get_eta

    async def counting(request):
        call_counter["count"] += 1
        return await original(request)

    manager._eta_agent.get_eta = counting

    req = _light_dry()
    asyncio.get_event_loop().run_until_complete(manager.build_quote(req))
    asyncio.get_event_loop().run_until_complete(manager.build_quote(req))

    assert call_counter["count"] == 1


def test_unavailable_agent_returns_degraded(manager: DispatchManager) -> None:
    req = QuoteRequest(origin="BLR", destination="DEL", cargo_weight_kg=9000, service_tier="standard")
    resp = asyncio.get_event_loop().run_until_complete(manager.build_quote(req))
    assert resp.status == "degraded"
    assert "capacity_unavailable" in resp.notes
    assert resp.price is None
