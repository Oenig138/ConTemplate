"""The synthesis stage (spec §5, §A.6): integrate diagnostics into the baseline.

Genuine integration, not selection or averaging: directed revision of the
baseline under the orthogonal constraints the admitted diagnostics impose,
with a decisiveness guard against the hedged everything-answer. On failure it
raises, and the pipeline falls back to the baseline answer.
"""

from __future__ import annotations

import logging

from .charters import build_synthesis_messages
from .client import LLMClient
from .config import Config
from .models import AdmittedDiagnostic, CompletionResult

logger = logging.getLogger("contemplate.synthesis")


async def synthesis_call(
    client: LLMClient,
    config: Config,
    prompt: str,
    baseline: str,
    routing_rationale: dict[str, str],
    admitted: list[AdmittedDiagnostic],
) -> CompletionResult:
    """Produce the final answer on the Pro tier. Raises CompletionError on failure."""
    diagnostics = [
        {"tool_id": d.tool_id, "output": d.output, "trust": d.trust} for d in admitted
    ]
    messages = build_synthesis_messages(
        prompt, baseline, routing_rationale, diagnostics
    )
    result = await client.complete(
        config.tiers.synthesis,
        messages,
        temperature=config.defaults.synthesis_temperature,
    )
    logger.info("synthesis integrated %d admitted diagnostic(s)", len(admitted))
    return result
