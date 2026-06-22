"""Quality gate: each A.7 branch plus baseline sanity-check."""

from __future__ import annotations

from contemplate.gate import (
    admitted_diagnostics,
    quality_gate,
    sanity_check_baseline,
)
from contemplate.models import BaselineResult, DiagnosticResult
from tests.conftest import FakeClient, make_config

OK_BASELINE = BaselineResult(answer="A coherent baseline answer of decent length.", status="ok")


def _diag(tool_id, **kw):
    base = dict(tool_id=tool_id, output="finding", self_confidence="high", status="ok")
    base.update(kw)
    return DiagnosticResult(**base)


async def test_drops_non_ok_status():
    diags = [_diag("framing", status="empty", output="")]
    decisions = await quality_gate(FakeClient(), make_config(), OK_BASELINE, diags)
    assert decisions[0].admitted is False
    assert "status=empty" in decisions[0].reason


async def test_low_confidence_admitted_low_trust():
    diags = [_diag("adversarial", self_confidence="low")]
    decisions = await quality_gate(FakeClient(), make_config(), OK_BASELINE, diags)
    assert decisions[0].admitted is True
    assert decisions[0].trust == "low"


async def test_shielded_tool_redundant_is_dropped():
    client = FakeClient(handler=lambda m, msgs, j, w: "REDUNDANT")
    diags = [_diag("abductive")]
    decisions = await quality_gate(client, make_config(), OK_BASELINE, diags)
    assert decisions[0].admitted is False
    assert decisions[0].reason == "redundant with baseline"


async def test_shielded_tool_novel_is_admitted():
    client = FakeClient(handler=lambda m, msgs, j, w: "NOVEL")
    diags = [_diag("genealogical")]
    decisions = await quality_gate(client, make_config(), OK_BASELINE, diags)
    assert decisions[0].admitted is True


async def test_consumer_tool_skips_redundancy_check():
    # A consumer tool must be admitted without any redundancy LLM call.
    client = FakeClient()
    diags = [_diag("premise")]
    decisions = await quality_gate(client, make_config(), OK_BASELINE, diags)
    assert decisions[0].admitted is True
    assert client.calls == []  # no redundancy check fired for a consumer


async def test_admitted_projection_carries_trust():
    diags = [_diag("framing"), _diag("adversarial", self_confidence="low")]
    decisions = await quality_gate(FakeClient(), make_config(), OK_BASELINE, diags)
    admitted = admitted_diagnostics(diags, decisions)
    trust_by_tool = {a.tool_id: a.trust for a in admitted}
    assert trust_by_tool == {"framing": "high", "adversarial": "low"}


async def test_sanity_check_rejects_short_baseline():
    bad = BaselineResult(answer="too short", status="ok")
    assert await sanity_check_baseline(FakeClient(), make_config(), bad) is False


async def test_sanity_check_rejects_empty_status():
    bad = BaselineResult(answer="", status="empty")
    assert await sanity_check_baseline(FakeClient(), make_config(), bad) is False


async def test_sanity_check_accepts_coherent_baseline():
    client = FakeClient(handler=lambda m, msgs, j, w: "YES")
    assert await sanity_check_baseline(client, make_config(), OK_BASELINE) is True
