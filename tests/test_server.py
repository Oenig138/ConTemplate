"""Backend API: endpoints respond and the run stream emits SSE events offline."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from tests.conftest import FakeClient, make_config
from tests.test_pipeline import orchestrator_handler


@pytest.fixture
def client():
    app = create_app(
        config=make_config(),
        client=FakeClient(handler=orchestrator_handler(["adversarial", "framing"])),
    )
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_meta_lists_six_tools(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tools"]) == 6
    assert set(body["dials"]) == {"off", "medium", "high"}
    assert body["models"]["baseline"] == "pro"


def test_security_headers_present(client):
    resp = client.get("/api/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_unknown_dial_rejected(client):
    resp = client.get("/api/run/stream", params={"prompt": "hi", "dial": "ludicrous"})
    assert resp.status_code == 422


def test_run_stream_emits_events(client):
    resp = client.get("/api/run/stream", params={"prompt": "a real prompt", "dial": "high"})
    assert resp.status_code == 200
    body = resp.text
    assert "event: run_started" in body
    assert "event: diagnostic_done" in body
    assert "event: run_complete" in body
    # the terminal event carries the full record
    record = _find_record(body)
    assert record["answer"] == "FINAL synthesized answer."
    assert record["diagnostics"][0]["tool_id"] == "adversarial"


def _find_record(sse_text: str) -> dict:
    """Scan every SSE data line for the payload carrying the run record."""
    for line in sse_text.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line[len("data:"):].strip())
        except json.JSONDecodeError:
            continue
        inner = payload.get("payload", {}) if isinstance(payload, dict) else {}
        if "record" in inner:
            return inner["record"]
    raise AssertionError("no run_complete record found in stream")
