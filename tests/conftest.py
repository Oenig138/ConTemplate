"""Shared fixtures: a fully in-memory config and a scriptable fake LLM client.

No test touches the network or reads config.yaml/.env. The fake client
implements the exact surface the stages use (`complete`, `usage_log`,
`reset_usage`) and records every call so tests can assert on routing.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from contemplate.config import Config, Defaults, Specs, Tiers, WebConfig
from contemplate.models import CompletionResult, Usage


def make_config(**overrides) -> Config:
    """A valid Config built directly, bypassing file/env loading."""
    base = dict(
        api_key="test-key",
        judge_model=None,
        base_url="https://example.invalid/api/v1",
        tiers=Tiers(
            baseline="pro",
            orchestrator="pro",
            synthesis="pro",
            diagnostic="flash",
            redundancy="flash",
            per_tool={},
        ),
        provider_pin=None,
        specs=Specs(
            model_id="test-model",
            knowledge_cutoff="2026-01",
            benchmarks={"x": 1.0},
            known_failure_modes=["anchors on its first frame"],
        ),
        dials={"off": 0, "medium": 3, "high": 5},
        web=WebConfig(max_results=5),
        defaults=Defaults(),
    )
    base.update(overrides)
    return Config(**base)


class Call(dict):
    """A recorded call (model, messages, json_mode, web) with attribute access."""

    __getattr__ = dict.get


Handler = Callable[[str, list[dict], bool, bool], str]


class FakeClient:
    """Scriptable stand-in for LLMClient."""

    def __init__(self, handler: Handler | None = None) -> None:
        self.handler: Handler = handler or _default_handler
        self.calls: list[Call] = []
        self.usage_log: list[Usage] = []

    def reset_usage(self) -> None:
        self.usage_log = []

    async def complete(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float,
        json_mode: bool = False,
        web: bool = False,
    ) -> CompletionResult:
        self.calls.append(
            Call(model=model, messages=messages, json_mode=json_mode, web=web)
        )
        text = self.handler(model, messages, json_mode, web)
        usage = Usage(prompt_tokens=100, completion_tokens=50, cached_tokens=80, cost_usd=0.001)
        self.usage_log.append(usage)
        return CompletionResult(text=text, usage=usage)

    def calls_for(self, *, web: bool | None = None) -> list[Call]:
        return [c for c in self.calls if web is None or c.web == web]


def _system_of(messages: list[dict]) -> str:
    return next((m["content"] for m in messages if m["role"] == "system"), "")


def _user_of(messages: list[dict]) -> str:
    return next((m["content"] for m in messages if m["role"] == "user"), "")


def _default_handler(model: str, messages: list[dict], json_mode: bool, web: bool) -> str:
    """Reasonable canned responses keyed by what the call looks like."""
    system = _system_of(messages)
    user = _user_of(messages)
    if json_mode:  # orchestrator
        return '{"fast_path": false, "selected": ["adversarial"], "rationale": {"adversarial": "test"}}'
    if "coherent, on-topic attempt" in user:  # baseline coherence check
        return "YES"
    if "NOVEL or REDUNDANT" in user:  # redundancy check
        return "NOVEL"
    if "synthesis" in system:  # synthesis stage
        return "FINAL synthesized answer."
    if "analysis" in system or "test" in system or "expansion" in system:  # a diagnostic
        return "A substantive diagnostic finding.\nCONFIDENCE: high"
    return "A plain baseline answer that is clearly long enough to be coherent."


@pytest.fixture
def config() -> Config:
    return make_config()


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()
