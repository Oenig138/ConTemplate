"""The orchestrator (spec §3, §A.4): routes which diagnostics to deploy.

Shielded from the baseline — it routes on prompt + specs alone. Critically it
does not know it is orchestrating copies of its own model; it reasons about
"a system with these capabilities". Output is strict JSON, validated and
repaired. On unrecoverable failure it returns a safe fast-path manifest so
the pipeline falls back to the baseline (single-call) answer.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from .charters import build_orchestrator_messages
from .client import CompletionError, LLMClient
from .config import ALL_TOOLS, Config
from .models import RoutingManifest

logger = logging.getLogger("contemplate.orchestrator")

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
_SAFE_FALLBACK = RoutingManifest(fast_path=True, selected=[], rationale={})


async def orchestrator_call(
    client: LLMClient, config: Config, prompt: str, ceiling: int
) -> RoutingManifest:
    """Decide the diagnostic subset. Never raises; degrades to fast-path."""
    messages = build_orchestrator_messages(prompt, config.specs, ceiling)
    try:
        result = await client.complete(
            config.tiers.orchestrator,
            messages,
            temperature=0.2,
            json_mode=True,
        )
    except CompletionError as exc:
        logger.error("orchestrator call failed; falling back to baseline: %s", exc)
        return _SAFE_FALLBACK

    manifest = _parse_manifest(result.text)
    if manifest is None:
        manifest = await _repair(client, config, result.text)
    if manifest is None:
        logger.error("orchestrator JSON unrecoverable; falling back to baseline")
        return _SAFE_FALLBACK
    return _sanitize(manifest)


def _parse_manifest(text: str) -> RoutingManifest | None:
    """Parse JSON, tolerating markdown fences and surrounding prose."""
    candidates = [text]
    match = _JSON_BLOCK.search(text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            return RoutingManifest(**json.loads(candidate))
        except (json.JSONDecodeError, ValidationError, TypeError):
            continue
    return None


async def _repair(client: LLMClient, config: Config, broken: str) -> RoutingManifest | None:
    """One repair pass: ask the model to re-emit valid manifest JSON."""
    messages = [
        {
            "role": "user",
            "content": (
                "The following was supposed to be a JSON routing manifest of the "
                'form {"fast_path": bool, "selected": [tool_ids], "rationale": '
                "{tool_id: reason}} but is malformed. Re-emit it as valid JSON "
                f"only, no prose:\n\n{broken}"
            ),
        }
    ]
    try:
        result = await client.complete(
            config.tiers.orchestrator, messages, temperature=0.0, json_mode=True
        )
    except CompletionError as exc:
        logger.warning("orchestrator repair call failed: %s", exc)
        return None
    return _parse_manifest(result.text)


def _sanitize(manifest: RoutingManifest) -> RoutingManifest:
    """Drop unknown tool ids and de-duplicate, preserving order."""
    seen: set[str] = set()
    cleaned: list[str] = []
    for tool_id in manifest.selected:
        if tool_id in ALL_TOOLS and tool_id not in seen:
            seen.add(tool_id)
            cleaned.append(tool_id)
        elif tool_id not in ALL_TOOLS:
            logger.warning("orchestrator selected unknown tool %r; dropping", tool_id)
    rationale = {k: v for k, v in manifest.rationale.items() if k in seen}
    return RoutingManifest(
        fast_path=manifest.fast_path, selected=cleaned, rationale=rationale
    )
