"""Orchestrator: parse, repair, sanitize, and safe fallback."""

from __future__ import annotations

from contemplate.orchestrator import _parse_manifest, _sanitize, orchestrator_call
from contemplate.models import RoutingManifest
from tests.conftest import FakeClient, make_config


def test_parse_clean_json():
    m = _parse_manifest('{"fast_path": false, "selected": ["framing"], "rationale": {}}')
    assert m is not None and m.selected == ["framing"]


def test_parse_fenced_json():
    text = 'here you go:\n```json\n{"fast_path": true, "selected": [], "rationale": {}}\n```'
    m = _parse_manifest(text)
    assert m is not None and m.fast_path is True


def test_parse_garbage_returns_none():
    assert _parse_manifest("not json at all") is None


def test_sanitize_drops_unknown_tools():
    raw = RoutingManifest(
        fast_path=False,
        selected=["framing", "telepathy", "framing"],  # unknown + duplicate
        rationale={"framing": "ok", "telepathy": "bogus"},
    )
    cleaned = _sanitize(raw)
    assert cleaned.selected == ["framing"]
    assert "telepathy" not in cleaned.rationale


async def test_orchestrator_repairs_then_succeeds():
    state = {"n": 0}

    def handler(model, messages, json_mode, web):
        state["n"] += 1
        if state["n"] == 1:
            return "oops not json"  # first call malformed
        return '{"fast_path": false, "selected": ["premise"], "rationale": {"premise": "x"}}'

    client = FakeClient(handler=handler)
    manifest = await orchestrator_call(client, make_config(), "prompt", ceiling=3)
    assert manifest.selected == ["premise"]
    assert state["n"] == 2  # original + one repair


async def test_orchestrator_unrecoverable_falls_back_to_fastpath():
    client = FakeClient(handler=lambda m, msgs, j, w: "never valid json")
    manifest = await orchestrator_call(client, make_config(), "prompt", ceiling=3)
    assert manifest.fast_path is True
    assert manifest.selected == []
