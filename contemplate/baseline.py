"""The baseline call (spec §3): a plain default answer from the worker model.

It is the draft the harness refines and the comparator the eval uses. Four
diagnostics consume it, so a garbage baseline poisons them — which is why the
gate sanity-checks it before propagation.
"""

from __future__ import annotations

import logging

from .charters import build_baseline_messages
from .client import CompletionError, LLMClient
from .config import Config
from .models import BaselineResult

logger = logging.getLogger("contemplate.baseline")


async def baseline_call(client: LLMClient, config: Config, prompt: str) -> BaselineResult:
    """Produce the default answer on the Pro tier. Never raises."""
    try:
        result = await client.complete(
            config.tiers.baseline,
            build_baseline_messages(prompt),
            temperature=config.defaults.baseline_temperature,
        )
    except CompletionError as exc:
        logger.warning("baseline call failed: %s", exc)
        return BaselineResult(answer="", status="empty")

    return BaselineResult(answer=result.text, status="ok", usage=result.usage)
