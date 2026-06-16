from __future__ import annotations

from app.messages import QuoteRequest


class QuotePlanner:
    """Decomposes a quote request into the set of worker agent lookups required."""

    def required_lookups(self, request: QuoteRequest) -> list[str]:
        # All current quote variants require the same read-only worker lookups.
        return ["eta", "capacity", "weather"]
