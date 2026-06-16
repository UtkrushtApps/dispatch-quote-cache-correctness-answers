from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ServiceTier = Literal["standard", "express", "refrigerated"]


class QuoteRequest(BaseModel):
    origin: str = Field(..., min_length=2)
    destination: str = Field(..., min_length=2)
    cargo_weight_kg: float = Field(..., gt=0)
    service_tier: ServiceTier = "standard"


class AgentResult(BaseModel):
    agent: str
    status: Literal["ok", "unavailable"] = "ok"
    value: Optional[float] = None
    detail: Optional[str] = None


class QuoteResponse(BaseModel):
    origin: str
    destination: str
    service_tier: ServiceTier
    eta_hours: Optional[float] = None
    capacity_score: Optional[float] = None
    delay_risk: Optional[float] = None
    price: Optional[float] = None
    status: Literal["ok", "degraded"] = "ok"
    notes: list[str] = Field(default_factory=list)
