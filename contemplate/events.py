"""Pipeline stage events for live observation (used by the streaming API).

The harness is a few sequential stages with a parallel fan-out. Emitting a
small event at each transition lets a UI animate the pipeline as it runs. The
emitter is optional and defaults to a no-op, so the core path and the test
suite are unaffected.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "run_started",
    "baseline_done",
    "orchestrator_done",
    "selection_done",
    "fanout_started",
    "diagnostic_done",
    "gate_done",
    "synthesis_started",
    "run_complete",
]


class StageEvent(BaseModel):
    """One transition in the pipeline, with a small type-specific payload."""

    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)


# An emitter is any sink that accepts a StageEvent. Kept synchronous so the
# pipeline never awaits the UI; the streaming layer pushes onto a queue.
Emitter = Callable[[StageEvent], None]


def noop_emitter(_event: StageEvent) -> None:
    """Default emitter: discard everything."""
