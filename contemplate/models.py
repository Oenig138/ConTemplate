"""Pydantic data shapes for every harness boundary (spec §A.2).

These are the contracts between stages. Raw dicts never cross a stage
boundary; everything is a validated model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "empty", "malformed"]
Confidence = Literal["high", "medium", "low"]
Trust = Literal["high", "low"]


class Usage(BaseModel):
    """Token + cost accounting captured from one OpenRouter response.

    `cached_tokens` is what validates the §9 cost story — it should be
    near `prompt_tokens` once the shared prefix is warm.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None

    @classmethod
    def sum(cls, usages: list["Usage"]) -> "Usage":
        """Aggregate a list of usages; cost is None unless at least one is set."""
        costs = [u.cost_usd for u in usages if u.cost_usd is not None]
        return cls(
            prompt_tokens=sum(u.prompt_tokens for u in usages),
            completion_tokens=sum(u.completion_tokens for u in usages),
            cached_tokens=sum(u.cached_tokens for u in usages),
            cost_usd=sum(costs) if costs else None,
        )


class CompletionResult(BaseModel):
    """Raw return from the LLM client: text plus accounting and any citations."""

    text: str
    usage: Usage = Field(default_factory=Usage)
    citations: list[str] = Field(default_factory=list)
    model: str = ""


class BaselineResult(BaseModel):
    answer: str
    status: Status = "ok"
    usage: Usage = Field(default_factory=Usage)


class RoutingManifest(BaseModel):
    """Orchestrator output (strict JSON)."""

    fast_path: bool = False
    selected: list[str] = Field(default_factory=list)
    rationale: dict[str, str] = Field(default_factory=dict)


class DiagnosticResult(BaseModel):
    tool_id: str
    output: str = ""
    self_confidence: Confidence = "medium"
    status: Status = "ok"
    citations: list[str] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)


class GateDecision(BaseModel):
    tool_id: str
    admitted: bool
    trust: Trust = "high"
    reason: str = ""


class AdmittedDiagnostic(BaseModel):
    """A diagnostic that cleared the gate, as synthesis sees it."""

    tool_id: str
    output: str
    trust: Trust


class RunRecord(BaseModel):
    """The full audit artifact for one harness run (spec §6)."""

    id: str = ""
    created_at: str = ""  # ISO 8601; stamped at finalize
    prompt: str
    dial: str
    answer: str
    fast_path: bool = False
    fallback: str | None = None  # set if the harness aborted to a fallback path
    baseline: BaselineResult | None = None
    manifest: RoutingManifest | None = None
    guards: list[str] = Field(default_factory=list)
    diagnostics: list[DiagnosticResult] = Field(default_factory=list)
    gate_decisions: list[GateDecision] = Field(default_factory=list)
    total_usage: Usage = Field(default_factory=Usage)
