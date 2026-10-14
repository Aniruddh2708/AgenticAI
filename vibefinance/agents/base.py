import asyncio
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Dimension = Literal["momentum", "volume", "sentiment", "filings", "risk"]


class Citation(BaseModel):
    source_id: str
    doc_title: str
    chunk_id: str
    excerpt: str
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    date: str = ""


class AgentOutput(BaseModel):
    agent: str
    ticker: str
    dimension: Dimension
    label: str
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence: list[str]
    citations: list[Citation] = Field(default_factory=list)
    status: Literal["ok", "degraded", "failed"] = "ok"
    degraded_reason: str | None = None
    latency_ms: float = Field(default=0, ge=0)


class UserProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=100)
    risk_tolerance: Literal["conservative", "moderate", "aggressive"]
    horizon_months: int = Field(ge=1, le=600)
    holdings: dict[str, float]
    max_single_stock_pct: float = Field(gt=0, le=1, allow_inf_nan=False)
    behavior: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_weights(self):
        import math
        if any(not math.isfinite(w) or w < 0 or w > 1 for w in self.holdings.values()):
            raise ValueError("Holdings must be finite portfolio fractions between 0 and 1.")
        if sum(self.holdings.values()) > 1.000001:
            raise ValueError("Holdings cannot total more than 100%; unallocated weight is cash.")
        for key in ("panic_sell_count", "avg_hold_days"):
            if key in self.behavior:
                value = self.behavior[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key} must be a finite nonnegative number")
        if "chases_momentum" in self.behavior and not isinstance(self.behavior["chases_momentum"], bool):
            raise ValueError("chases_momentum must be a boolean")
        return self


class Recommendation(BaseModel):
    user_id: str
    ticker: str
    action: Literal["BUY", "ACCUMULATE", "HOLD", "REDUCE", "AVOID", "WATCH"]
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    reasoning_chain: list[str]
    citations: list[Citation]
    agent_outputs: list[AgentOutput]
    conflicts: list[str]
    personalization_notes: list[str]
    disclaimer: str


async def run_agent(dimension: Dimension, ticker: str, fn: Callable[[], AgentOutput],
                    timeout: float) -> AgentOutput:
    """Isolate exceptions and bound waiting; timed-out worker threads may finish later."""
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
        if result.dimension != dimension or result.ticker != ticker:
            raise ValueError("Agent returned mismatched contract")
    except Exception as exc:
        reason = "Agent timed out" if isinstance(exc, TimeoutError) else f"Agent failed ({type(exc).__name__})"
        result = AgentOutput(agent=f"{dimension}_agent", ticker=ticker, dimension=dimension,
                             label="UNKNOWN", confidence=0, evidence=[], status="failed",
                             degraded_reason=reason)
    result.latency_ms = (time.perf_counter() - start) * 1000
    return result
