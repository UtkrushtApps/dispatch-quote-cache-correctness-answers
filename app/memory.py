from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuoteWorkingState:
    """Holds the intermediate agent values gathered while building a single quote."""

    eta: Optional[float] = None
    capacity: Optional[float] = None
    delay_risk: Optional[float] = None
    notes: list[str] = field(default_factory=list)
