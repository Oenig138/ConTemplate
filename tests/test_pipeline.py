"""Pipeline: fast-path, dial cap, guard injection, full run, baseline fallback."""

from __future__ import annotations

import json

from contemplate.pipeline import run_harness
from tests.conftest import FakeClient, make_config


def orchestrator_handler(selected, fast_path=False):
    """A handler whose orchestrator JSON returns a fixed selection."""

    def handler(model, messages, json_mode, web):
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        if json_mode:
            return json.dumps(
                {"fast_path": fast_path, "selected": selected, "rationale": {t: "r" for t in selected}}
            )
        if "coherent, on-topic attempt" in user:
            return "YES"
        if "NOVEL or REDUNDANT" in user:
            return "NOVEL"
        if "synthesis" in system:
            return "FINAL synthesized answer."
        if "analysis" in system or "test" in system or "expansion" in system:
            return "diagnostic finding\nCONFIDENCE: high"
        return "A coherent baseline answer long enough to pass the sanity check."

    return handler


async def test_fast_path_returns_baseline():
    client = FakeClient(handler=orchestrator_handler([], fast_path=True))
    record = await run_harness(client, make_config(), "trivial prompt", dial="high", persist_record=False)
    assert record.fast_path is True
    assert "baseline" in record.answer.lower()
    assert record.diagnostics == []


async def test_dial_caps_selection():
    selected = ["framing", "premise", "empirical", "adversarial", "abductive"]
    client = FakeClient(handler=orchestrator_handler(selected))
    record = await run_harness(client, make_config(), "a prompt", dial="medium", persist_record=False)
    # medium ceiling = 3; exactly three diagnostics actually ran
    assert len(record.diagnostics) == 3


async def test_full_run_synthesizes_and_records_usage():
    client = FakeClient(handler=orchestrator_handler(["adversarial"]))
    record = await run_harness(client, make_config(), "a real prompt", dial="high", persist_record=False)
    assert record.answer == "FINAL synthesized answer."
    assert [d.tool_id for d in record.diagnostics] == ["adversarial"]
    assert record.gate_decisions[0].admitted is True
    assert record.total_usage.prompt_tokens > 0
    assert record.total_usage.cached_tokens > 0


async def test_guard_injects_empirical_when_not_selected():
    # Orchestrator picks only framing; a force-on guard must add empirical.
    client = FakeClient(handler=orchestrator_handler(["framing"]))
    record = await run_harness(
        client, make_config(), "neutral prompt", dial="high",
        force_empirical=True, persist_record=False,
    )
    ran = {d.tool_id for d in record.diagnostics}
    assert "empirical" in ran and "framing" in ran


async def test_force_off_blocks_selected_empirical():
    client = FakeClient(handler=orchestrator_handler(["empirical", "framing"]))
    record = await run_harness(
        client, make_config(), "the latest 2030 news", dial="high",
        force_empirical=False, persist_record=False,
    )
    ran = {d.tool_id for d in record.diagnostics}
    assert "empirical" not in ran
    assert "framing" in ran


async def test_bad_baseline_aborts_to_fallback():
    def handler(model, messages, json_mode, web):
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        if json_mode:
            return json.dumps({"fast_path": False, "selected": ["framing"], "rationale": {"framing": "r"}})
        if "coherent, on-topic attempt" in user:
            return "NO"  # baseline always judged incoherent
        return "garbage baseline that the coherence check rejects"

    client = FakeClient(handler=handler)
    record = await run_harness(client, make_config(), "a prompt", dial="high", persist_record=False)
    assert record.fallback == "bad_baseline"
    assert record.diagnostics == []  # never ran the fan-out
