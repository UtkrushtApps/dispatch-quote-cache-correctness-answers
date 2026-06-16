from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis

from app.agents.worker import CapacityAgent, EtaAgent, WeatherAgent
from app.config import Settings
from app.memory import QuoteWorkingState
from app.messages import AgentResult, QuoteRequest, QuoteResponse
from app.observability import new_correlation_id

logger = logging.getLogger("dispatch.orchestrator")

AgentCompute = Callable[[QuoteRequest], Awaitable[AgentResult]]


class DispatchManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self._eta_agent = EtaAgent()
        self._capacity_agent = CapacityAgent()
        self._weather_agent = WeatherAgent()

        # Per-cache-key locks prevent duplicate work for concurrent identical
        # requests without storing any per-request quote state on the manager.
        self._cache_locks: dict[str, asyncio.Lock] = {}
        self._cache_locks_guard = asyncio.Lock()

    def _request_fingerprint(self, request: QuoteRequest) -> str:
        """Return a stable fingerprint for every input that can affect agents.

        The previous implementation keyed only by lane, so a refrigerated heavy
        load and a standard light load on the same lane shared ETA/capacity. The
        cache key must include the full request input contract because multiple
        worker results depend on cargo weight and service tier.
        """
        canonical = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _cache_key(self, agent: str, request: QuoteRequest) -> tuple[str, str]:
        fingerprint = self._request_fingerprint(request)
        return f"dispatch:v2:{agent}:{fingerprint}", fingerprint

    async def _lock_for_key(self, key: str) -> asyncio.Lock:
        async with self._cache_locks_guard:
            lock = self._cache_locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._cache_locks[key] = lock
            return lock

    def _decode_cached_result(self, agent_name: str, fingerprint: str, raw: str) -> AgentResult | None:
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return None

        # New safe envelope. It records the request fingerprint as defense in
        # depth, so an accidental key collision or future key-format regression
        # cannot silently return another request's worker output.
        if "result" in data:
            if data.get("agent") != agent_name or data.get("request_fingerprint") != fingerprint:
                return None
            return AgentResult(**data["result"])

        # Backward-compatible support for bare AgentResult payloads that may be
        # present in a developer's local Redis under a v2 key. Old v1 keys are
        # never read because the key prefix changed to dispatch:v2.
        return AgentResult(**data)

    def _cache_payload(self, agent_name: str, fingerprint: str, result: AgentResult) -> str:
        return json.dumps(
            {
                "agent": agent_name,
                "request_fingerprint": fingerprint,
                "result": result.model_dump(),
            },
            sort_keys=True,
        )

    async def _memoized(
        self,
        agent_name: str,
        request: QuoteRequest,
        compute: AgentCompute,
        correlation_id: str,
    ) -> AgentResult:
        key, fingerprint = self._cache_key(agent_name, request)

        cached = self._redis.get(key)
        if cached is not None:
            result = self._decode_cached_result(agent_name, fingerprint, cached)
            if result is not None:
                logger.info("agent cache hit cid=%s agent=%s key=%s", correlation_id, agent_name, key)
                return result
            logger.warning("agent cache invalid cid=%s agent=%s key=%s", correlation_id, agent_name, key)
            self._redis.delete(key)

        lock = await self._lock_for_key(key)
        async with lock:
            # Re-check after acquiring the lock. Another identical request may
            # have populated the cache while this coroutine was waiting.
            cached = self._redis.get(key)
            if cached is not None:
                result = self._decode_cached_result(agent_name, fingerprint, cached)
                if result is not None:
                    logger.info("agent cache hit cid=%s agent=%s key=%s", correlation_id, agent_name, key)
                    return result
                logger.warning("agent cache invalid cid=%s agent=%s key=%s", correlation_id, agent_name, key)
                self._redis.delete(key)

            logger.info("agent cache miss cid=%s agent=%s key=%s", correlation_id, agent_name, key)
            try:
                result = await asyncio.wait_for(compute(request), timeout=self._settings.agent_timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning("agent timeout cid=%s agent=%s", correlation_id, agent_name)
                return AgentResult(agent=agent_name, status="unavailable", detail="timeout")
            except Exception:
                logger.exception("agent error cid=%s agent=%s", correlation_id, agent_name)
                return AgentResult(agent=agent_name, status="unavailable", detail="error")

            if result.status == "ok":
                self._redis.setex(
                    key,
                    self._settings.cache_ttl_seconds,
                    self._cache_payload(agent_name, fingerprint, result),
                )
                logger.info(
                    "agent cache store cid=%s agent=%s key=%s ttl=%s",
                    correlation_id,
                    agent_name,
                    key,
                    self._settings.cache_ttl_seconds,
                )
            return result

    async def build_quote(self, request: QuoteRequest) -> QuoteResponse:
        correlation_id = new_correlation_id()
        logger.info(
            "build_quote start cid=%s lane=%s->%s tier=%s weight=%s",
            correlation_id,
            request.origin,
            request.destination,
            request.service_tier,
            request.cargo_weight_kg,
        )

        eta_task = self._memoized("eta", request, self._eta_agent.get_eta, correlation_id)
        capacity_task = self._memoized("capacity", request, self._capacity_agent.check_capacity, correlation_id)
        weather_task = self._memoized("weather", request, self._weather_agent.get_delay_risk, correlation_id)
        eta, capacity, weather = await asyncio.gather(eta_task, capacity_task, weather_task)

        # All intermediate values live in a request-local state object. Nothing
        # mutable on DispatchManager is used to assemble or price a quote.
        state = QuoteWorkingState(
            eta=eta.value,
            capacity=capacity.value,
            delay_risk=weather.value,
        )

        status = "ok"
        for result in (eta, capacity, weather):
            if result.status == "unavailable":
                status = "degraded"
                state.notes.append(f"{result.agent}_unavailable")

        price = None
        if status == "ok":
            price = self._compute_price(request, state)

        response = QuoteResponse(
            origin=request.origin,
            destination=request.destination,
            service_tier=request.service_tier,
            eta_hours=state.eta,
            capacity_score=state.capacity,
            delay_risk=state.delay_risk,
            price=price,
            status=status,
            notes=state.notes,
        )
        logger.info(
            "build_quote done cid=%s status=%s tier=%s eta=%s capacity=%s delay_risk=%s price=%s notes=%s",
            correlation_id,
            status,
            response.service_tier,
            response.eta_hours,
            response.capacity_score,
            response.delay_risk,
            response.price,
            response.notes,
        )
        return response

    def _compute_price(self, request: QuoteRequest, state: QuoteWorkingState) -> float:
        base = 100.0 + request.cargo_weight_kg * 0.5
        tier_factor = {"standard": 1.0, "express": 1.6, "refrigerated": 2.1}[request.service_tier]
        eta = state.eta or 24.0
        capacity = state.capacity or 1.0
        risk = state.delay_risk or 0.0
        return round(base * tier_factor * (1 + risk) / max(capacity, 0.1) + eta, 2)
