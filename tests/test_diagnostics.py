"""Diagnostics: confidence-sentinel parsing, baseline routing, web-only-empirical."""

from __future__ import annotations

import pytest

from contemplate.diagnostics import _parse_confidence, diagnostic_call, run_diagnostics
from tests.conftest import FakeClient, _system_of, _user_of, make_config


def test_parse_confidence_present():
    text = "the finding here\nCONFIDENCE: low"
    cleaned, conf = _parse_confidence(text)
    assert conf == "low"
    assert "CONFIDENCE" not in cleaned
    assert cleaned == "the finding here"


def test_parse_confidence_absent_defaults_medium():
    cleaned, conf = _parse_confidence("just a finding, no sentinel")
    assert conf == "medium"
    assert cleaned == "just a finding, no sentinel"


def test_parse_confidence_takes_last_match():
    _, conf = _parse_confidence("CONFIDENCE: high in the body\nfinal\nCONFIDENCE: low")
    assert conf == "low"


async def test_empty_output_is_malformed():
    client = FakeClient(handler=lambda m, msgs, j, w: "CONFIDENCE: high")
    result = await diagnostic_call(client, make_config(), "framing", "p", "baseline")
    assert result.status == "malformed"


async def test_only_empirical_gets_web():
    client = FakeClient()
    config = make_config()
    await run_diagnostics(
        client, config, ["framing", "empirical", "abductive"], "prompt", "baseline text"
    )
    web_calls = client.calls_for(web=True)
    assert len(web_calls) == 1
    assert "empirical verification" in _system_of(web_calls[0].messages)


async def test_consumer_sees_baseline_shielded_does_not():
    client = FakeClient()
    config = make_config()
    await run_diagnostics(client, config, ["framing", "abductive"], "prompt", "BASELINE_MARKER")
    by_system = {_system_of(c.messages): _user_of(c.messages) for c in client.calls}
    framing_user = next(u for s, u in by_system.items() if "framing analysis" in s)
    abductive_user = next(u for s, u in by_system.items() if "abductive expansion" in s)
    assert "BASELINE_MARKER" in framing_user  # consumer
    assert "BASELINE_MARKER" not in abductive_user  # shielded


@pytest.mark.parametrize("tool", ["framing", "premise", "empirical", "adversarial"])
async def test_per_tool_override_routes_model(tool):
    config = make_config()
    config.tiers.per_tool[tool] = "pro-override"
    client = FakeClient()
    await diagnostic_call(client, config, tool, "p", "b")
    assert client.calls[0].model == "pro-override"
