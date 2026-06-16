from __future__ import annotations

import asyncio

from app.messages import AgentResult, QuoteRequest

_LANE_BASE_ETA = {
    ("BLR", "DEL"): 30.0,
    ("DEL", "BLR"): 31.0,
    ("BLR", "BOM"): 14.0,
    ("BOM", "BLR"): 15.0,
}


class EtaAgent:
    async def get_eta(self, request: QuoteRequest) -> AgentResult:
        await asyncio.sleep(0.01)
        base = _LANE_BASE_ETA.get((request.origin, request.destination), 24.0)
        weight_penalty = request.cargo_weight_kg / 1000.0
        tier_penalty = 4.0 if request.service_tier == "refrigerated" else 0.0
        return AgentResult(agent="eta", status="ok", value=round(base + weight_penalty + tier_penalty, 2))


class CapacityAgent:
    async def check_capacity(self, request: QuoteRequest) -> AgentResult:
        await asyncio.sleep(0.01)
        if request.cargo_weight_kg > 8000:
            return AgentResult(agent="capacity", status="unavailable", detail="no_capacity")
        score = max(0.2, 1.5 - request.cargo_weight_kg / 10000.0)
        if request.service_tier == "refrigerated":
            score = score * 0.7
        return AgentResult(agent="capacity", status="ok", value=round(score, 3))


class WeatherAgent:
    async def get_delay_risk(self, request: QuoteRequest) -> AgentResult:
        await asyncio.sleep(0.01)
        risk = 0.05
        if request.destination in ("DEL",):
            risk = 0.18
        return AgentResult(agent="weather", status="ok", value=round(risk, 3))
