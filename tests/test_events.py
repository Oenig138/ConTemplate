"""The pipeline emits a coherent ordered event stream when an emitter is given."""

from __future__ import annotations

from contemplate.events import StageEvent
from contemplate.pipeline import run_harness
from tests.test_pipeline import orchestrator_handler
from tests.conftest import FakeClient, make_config


async def test_emits_ordered_stage_events():
    events: list[StageEvent] = []
    client = FakeClient(handler=orchestrator_handler(["framing", "adversarial"]))
    record = await run_harness(
        client, make_config(), "a prompt", dial="high",
        persist_record=False, emit=events.append,
    )

    types = [e.type for e in events]
    assert types[0] == "run_started"
    assert "baseline_done" in types and "orchestrator_done" in types
    assert types.count("diagnostic_done") == 2  # one per selected tool
    assert types[-1] == "run_complete"
    # the terminal event carries the full record
    assert events[-1].payload["record"]["id"] == record.id
    assert record.id and record.created_at


async def test_no_emitter_is_safe_default():
    client = FakeClient(handler=orchestrator_handler([], fast_path=True))
    # No emit kwarg → noop; must not raise.
    record = await run_harness(client, make_config(), "trivial", persist_record=False)
    assert record.fast_path is True
