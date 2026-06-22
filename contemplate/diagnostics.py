"""The diagnostic toolbox dispatch (spec §4): runs the selected tools.

One entry point per tool would duplicate plumbing six ways; instead a single
dispatch routes by tool id, applying the per-tool rules that actually differ:
which tier, whether the baseline is consumed or shielded, and whether the web
plugin is attached (only the empirical tool gets it). Confidence is parsed
back out of the trailing sentinel.
"""

from __future__ import annotations

import asyncio
import logging
import re

from .charters import build_diagnostic_messages
from .client import CompletionError, LLMClient
from .config import BASELINE_CONSUMERS, RETRIEVAL_TOOLS, Config
from .models import Confidence, DiagnosticResult

logger = logging.getLogger("contemplate.diagnostics")

_CONFIDENCE = re.compile(r"CONFIDENCE:\s*(high|medium|low)", re.IGNORECASE)


async def diagnostic_call(
    client: LLMClient,
    config: Config,
    tool_id: str,
    prompt: str,
    baseline: str | None,
) -> DiagnosticResult:
    """Run one diagnostic. Never raises; failures surface as status."""
    baseline_for_tool = baseline if tool_id in BASELINE_CONSUMERS else None
    messages = build_diagnostic_messages(tool_id, prompt, baseline_for_tool)
    use_web = tool_id in RETRIEVAL_TOOLS

    try:
        result = await client.complete(
            config.tiers.for_tool(tool_id),
            messages,
            temperature=config.defaults.temperature,
            web=use_web,
        )
    except CompletionError as exc:
        logger.warning("diagnostic %s failed: %s", tool_id, exc)
        return DiagnosticResult(tool_id=tool_id, output="", status="empty")

    output, confidence = _parse_confidence(result.text)
    status = "ok" if output.strip() else "malformed"
    return DiagnosticResult(
        tool_id=tool_id,
        output=output,
        self_confidence=confidence,
        status=status,
        citations=result.citations,
        usage=result.usage,
    )


async def run_diagnostics(
    client: LLMClient,
    config: Config,
    tool_ids: list[str],
    prompt: str,
    baseline: str | None,
) -> list[DiagnosticResult]:
    """Parallel fan-out over the selected tools (spec §A.3 step 5)."""
    if not tool_ids:
        return []
    tasks = [
        diagnostic_call(client, config, tool_id, prompt, baseline)
        for tool_id in tool_ids
    ]
    return list(await asyncio.gather(*tasks))


def _parse_confidence(text: str) -> tuple[str, Confidence]:
    """Strip the trailing CONFIDENCE sentinel; default medium if absent."""
    matches = list(_CONFIDENCE.finditer(text))
    if not matches:
        return text.strip(), "medium"
    last = matches[-1]
    confidence = last.group(1).lower()
    cleaned = (text[: last.start()] + text[last.end():]).strip()
    return cleaned, confidence  # type: ignore[return-value]
