"""Guards: overrides win; recency heuristic forces empirical and logs."""

from __future__ import annotations

import logging

from contemplate.guards import run_deterministic_guards
from tests.conftest import make_config

SPECS = make_config().specs  # knowledge_cutoff = 2026-01


def test_force_off_blocks_empirical():
    result = run_deterministic_guards("anything", SPECS, force_empirical=False)
    assert result.blocked == ["empirical"]
    assert result.forced == []


def test_force_on_forces_empirical():
    result = run_deterministic_guards("anything", SPECS, force_empirical=True)
    assert result.forced == ["empirical"]


def test_override_beats_recency_heuristic():
    # Prompt would trip the heuristic, but force-off must still win.
    result = run_deterministic_guards("the latest news in 2027", SPECS, force_empirical=False)
    assert result.blocked == ["empirical"]
    assert result.forced == []


def test_recency_term_fires_empirical(caplog):
    with caplog.at_level(logging.INFO):
        result = run_deterministic_guards("what is the current state of X", SPECS)
    assert result.forced == ["empirical"]
    assert any("recency heuristic fired" in r.message for r in caplog.records)


def test_future_year_fires_empirical():
    result = run_deterministic_guards("what happened in 2030", SPECS)
    assert result.forced == ["empirical"]


def test_neutral_prompt_no_guard():
    result = run_deterministic_guards("explain why the sky is blue", SPECS)
    assert not result  # falsy GuardResult
    assert result.forced == [] and result.blocked == []
