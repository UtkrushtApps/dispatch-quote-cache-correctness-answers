from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings
from app.messages import QuoteRequest, QuoteResponse
from app.orchestrator import DispatchManager
from app.observability import configure_logging

configure_logging()

app = FastAPI(title="Dispatch Quote Service")
_settings = Settings()
_manager = DispatchManager(_settings)


@app.post("/api/agents/dispatch/quote", response_model=QuoteResponse)
async def dispatch_quote(request: QuoteRequest) -> QuoteResponse:
    return await _manager.build_quote(request)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
