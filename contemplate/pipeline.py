"""The harness control flow (spec §A.3): the one place stages are wired.

    (baseline ∥ orchestrator + guards) → tool selection → parallel diagnostic
    fan-out → quality gate → synthesis → return

Everything else is a stage with a single responsibility; this module owns
ordering, the fast-path, the baseline-failure fallback, and assembling the
audit record.
"""

from __future__ import annotations

import asyncio
import logging

from .audit import persist
from .baseline import baseline_call
from .client import CompletionError, LLMClient
from .config import BASELINE_CONSUMERS, Config
from .gate import admitted_diagnostics, quality_gate, sanity_check_baseline
from .guards import GuardResult, run_deterministic_guards
from .models import BaselineResult, RunRecord, Usage
from .orchestrator import orchestrator_call
from .diagnostics import run_diagnostics
from .synthesis import synthesis_call

logger = logging.getLogger("contemplate.pipeline")


async def run_harness(
    client: LLMClient,
    config: Config,
    prompt: str,
    *,
    dial: str = "high",
    force_empirical: bool | None = None,
    persist_record: bool = True,
) -> RunRecord:
    """Run the full harness for one prompt and return its audit record."""
    client.reset_usage()
    ceiling = config.ceiling(dial)
    guards = run_deterministic_guards(prompt, config.specs, force_empirical=force_empirical)

    baseline, manifest = await asyncio.gather(
        baseline_call(client, config, prompt),
        orchestrator_call(client, config, prompt, ceiling),
    )

    record = RunRecord(
        prompt=prompt,
        dial=dial,
        answer="",
        baseline=baseline,
        manifest=manifest,
        guards=guards.forced,
    )

    # Fast-path: orchestrator wants none and no guard forces one (spec §A.3 §3).
    if manifest.fast_path and not guards:
        return _finalize(client, record, baseline.answer, fast_path=True, persist_record=persist_record)

    selected = _merge_selection(manifest.selected, guards, ceiling)
    if not selected:
        return _finalize(client, record, baseline.answer, fast_path=True, persist_record=persist_record)

    baseline = await _ensure_baseline(client, config, baseline, prompt, selected)
    if baseline.status != "ok":
        logger.error("baseline unusable after regeneration; aborting to single-call fallback")
        record.baseline = baseline
        return _finalize(
            client, record, baseline.answer, fallback="bad_baseline", persist_record=persist_record
        )
    record.baseline = baseline

    diagnostics = await run_diagnostics(client, config, selected, prompt, baseline.answer)
    decisions = await quality_gate(client, config, baseline, diagnostics)
    admitted = admitted_diagnostics(diagnostics, decisions)
    record.diagnostics = diagnostics
    record.gate_decisions = decisions

    answer, fallback = await _synthesize(client, config, prompt, baseline.answer, manifest.rationale, admitted)
    return _finalize(client, record, answer, fallback=fallback, persist_record=persist_record)


def _merge_selection(selected: list[str], guards: GuardResult, ceiling: int) -> list[str]:
    """Forced guards first (so they survive the cap), then orchestrator picks."""
    ordered = list(guards.forced) + [t for t in selected if t not in guards.forced]
    blocked = set(guards.blocked)
    deduped: list[str] = []
    for tool_id in ordered:
        if tool_id not in blocked and tool_id not in deduped:
            deduped.append(tool_id)
    return deduped[:ceiling]


async def _ensure_baseline(
    client: LLMClient,
    config: Config,
    baseline: BaselineResult,
    prompt: str,
    selected: list[str],
) -> BaselineResult:
    """Sanity-check the baseline before consumers use it; regenerate once if bad."""
    if not any(tool_id in BASELINE_CONSUMERS for tool_id in selected):
        return baseline  # only shielded tools selected; baseline not consumed
    if await sanity_check_baseline(client, config, baseline):
        return baseline
    logger.warning("baseline failed sanity check; regenerating once")
    regenerated = await baseline_call(client, config, prompt)
    if await sanity_check_baseline(client, config, regenerated):
        return regenerated
    return BaselineResult(answer=regenerated.answer, status="malformed", usage=regenerated.usage)


async def _synthesize(client, config, prompt, baseline, rationale, admitted):
    """Run synthesis, falling back to the baseline answer on failure."""
    try:
        result = await synthesis_call(client, config, prompt, baseline, rationale, admitted)
        return result.text, None
    except CompletionError as exc:
        logger.error("synthesis failed; returning baseline: %s", exc)
        return baseline, "synthesis_failed"


def _finalize(
    client: LLMClient,
    record: RunRecord,
    answer: str,
    *,
    fast_path: bool = False,
    fallback: str | None = None,
    persist_record: bool = True,
) -> RunRecord:
    """Stamp the answer, total usage, and write the audit artifact."""
    record.answer = answer
    record.fast_path = fast_path
    record.fallback = fallback
    record.total_usage = Usage.sum(client.usage_log)
    if persist_record:
        persist(record)
    return record
