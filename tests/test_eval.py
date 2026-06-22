"""Eval harness wiring runs end-to-end offline through the fake client."""

from __future__ import annotations

import json

from eval.harness import _lexical_divergence, run_eval
from eval.prompts import SEED_PROMPTS
from tests.conftest import FakeClient, make_config


def _eval_handler(model, messages, json_mode, web):
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    if json_mode:
        return json.dumps(
            {"fast_path": False, "selected": ["framing", "adversarial"], "rationale": {}}
        )
    if "coherent, on-topic attempt" in user:
        return "YES"
    if "NOVEL or REDUNDANT" in user:
        return "NOVEL"
    if "A or B — for the better answer" in user:  # judge
        return "A"
    if "synthesis" in system:
        return "FINAL synthesized answer."
    if "analysis" in system or "test" in system or "expansion" in system:
        return "diagnostic finding\nCONFIDENCE: high"
    return "A coherent baseline answer long enough to pass the sanity check."


def test_lexical_divergence_bounds():
    assert _lexical_divergence("a b c", "a b c") == 0.0
    assert _lexical_divergence("a b", "x y") == 1.0


async def test_eval_runs_offline_and_aggregates():
    config = make_config(judge_model="judge-model")
    client = FakeClient(handler=_eval_handler)
    summary = await run_eval(client, config, SEED_PROMPTS[:3], judge=True, seed=1)

    assert summary.n_prompts == 3
    # framing + adversarial selected on every non-fast-path prompt
    assert summary.tool_selected.get("framing", 0) >= 1
    # judge always picked answer A; randomized mapping yields a valid bucket
    assert summary.harness_wins + summary.single_wins + summary.ties == 3
    assert all(r.divergence for r in summary.results)
