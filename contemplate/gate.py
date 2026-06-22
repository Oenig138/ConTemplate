"""The quality gate (spec §7, §A.7): the reliability layer before synthesis.

A multi-call harness multiplies the failure surface; confident garbage is
worse than an absent diagnostic because it anchors the final answer. The gate
drops empties/malformed, flags low-confidence as low-trust, runs the
redundancy check the shielded generative tools skipped at runtime, and
sanity-checks the baseline (the one failure that poisons all four consumers).
"""

from __future__ import annotations

import logging

from .client import CompletionError, LLMClient
from .config import BASELINE_SHIELDED, Config
from .models import (
    AdmittedDiagnostic,
    BaselineResult,
    DiagnosticResult,
    GateDecision,
)

logger = logging.getLogger("contemplate.gate")

_MIN_BASELINE_CHARS = 20


async def quality_gate(
    client: LLMClient,
    config: Config,
    baseline: BaselineResult,
    diagnostics: list[DiagnosticResult],
) -> list[GateDecision]:
    """Decide, per diagnostic, whether synthesis sees it (and at what trust)."""
    decisions: list[GateDecision] = []
    for diag in diagnostics:
        decisions.append(await _decide(client, config, baseline, diag))
    return decisions


async def _decide(
    client: LLMClient,
    config: Config,
    baseline: BaselineResult,
    diag: DiagnosticResult,
) -> GateDecision:
    if diag.status != "ok":
        return GateDecision(
            tool_id=diag.tool_id, admitted=False, reason=f"status={diag.status}"
        )

    trust = "low" if diag.self_confidence == "low" else "high"

    if diag.tool_id in BASELINE_SHIELDED:
        if await _redundant_with(client, config, diag.output, baseline.answer):
            return GateDecision(
                tool_id=diag.tool_id, admitted=False, reason="redundant with baseline"
            )

    return GateDecision(
        tool_id=diag.tool_id,
        admitted=True,
        trust=trust,
        reason="ok" if trust == "high" else "low self-confidence",
    )


def admitted_diagnostics(
    diagnostics: list[DiagnosticResult], decisions: list[GateDecision]
) -> list[AdmittedDiagnostic]:
    """Project the diagnostics synthesis is allowed to see."""
    trust_by_tool = {d.tool_id: d.trust for d in decisions if d.admitted}
    output_by_tool = {d.tool_id: d.output for d in diagnostics}
    return [
        AdmittedDiagnostic(
            tool_id=tool_id, output=output_by_tool[tool_id], trust=trust
        )
        for tool_id, trust in trust_by_tool.items()
    ]


async def _redundant_with(
    client: LLMClient, config: Config, output: str, baseline: str
) -> bool:
    """Cheap novelty check (spec §A.7). Fails open: on error, treat as novel."""
    messages = [
        {
            "role": "user",
            "content": (
                "Below are a BASELINE answer and a separate ANALYSIS. Does the "
                "ANALYSIS contain any substantive insight, angle, or correction "
                "NOT already present in the BASELINE? Reply with exactly one "
                "word: NOVEL or REDUNDANT.\n\n"
                f"BASELINE:\n{baseline}\n\nANALYSIS:\n{output}"
            ),
        }
    ]
    try:
        result = await client.complete(
            config.tiers.redundancy, messages, temperature=0.0
        )
    except CompletionError as exc:
        logger.warning("redundancy check failed; admitting as novel: %s", exc)
        return False
    return "REDUNDANT" in result.text.upper()


async def sanity_check_baseline(
    client: LLMClient, config: Config, baseline: BaselineResult
) -> bool:
    """Structural + cheap coherence check before diagnostics consume it."""
    if baseline.status != "ok" or len(baseline.answer.strip()) < _MIN_BASELINE_CHARS:
        logger.warning("baseline failed structural sanity check (status=%s)", baseline.status)
        return False

    messages = [
        {
            "role": "user",
            "content": (
                "Is the following a coherent, on-topic attempt at an answer "
                "(not an error message, refusal, or gibberish)? Reply with "
                f"exactly one word: YES or NO.\n\n{baseline.answer}"
            ),
        }
    ]
    try:
        result = await client.complete(
            config.tiers.redundancy, messages, temperature=0.0
        )
    except CompletionError as exc:
        logger.warning("baseline coherence check failed; assuming ok: %s", exc)
        return True  # fail open: don't discard a baseline over a flaky check
    return "YES" in result.text.upper()
