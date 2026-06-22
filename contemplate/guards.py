"""Deterministic guards for the empirical (web-touching) tool (spec §6).

Routing the empirical tool is three layers in priority order: deterministic
guards (here), user override (here), then orchestrator discretion (elsewhere).
The principle: take the specifiable decisions off the cheap model's plate.

The post-cutoff recency heuristic is deliberately coarse and **logs every
time it fires**, because a silent guard that force-runs a web call is exactly
the kind of invisible behaviour the standards forbid.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from .config import Specs

logger = logging.getLogger("contemplate.guards")

# Phrases that imply a dependence on information newer than any fixed cutoff.
_RECENCY_TERMS = (
    "latest",
    "current",
    "currently",
    "today",
    "right now",
    "as of",
    "this year",
    "recent",
    "recently",
    "newest",
    "up to date",
    "up-to-date",
    "nowadays",
)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


class GuardResult(BaseModel):
    """Tool ids the guards force on, and tool ids they block."""

    forced: list[str] = Field(default_factory=list)
    blocked: list[str] = Field(default_factory=list)

    def __bool__(self) -> bool:  # truthiness drives the fast-path check in A.3
        return bool(self.forced or self.blocked)


def run_deterministic_guards(
    prompt: str,
    specs: Specs,
    *,
    force_empirical: bool | None = None,
) -> GuardResult:
    """Return forced/blocked tool ids before orchestrator discretion applies.

    `force_empirical`: True = user force-on (research session), False =
    user force-off (privacy/offline; empirical may never run), None = defer
    to the recency heuristic.
    """
    if force_empirical is False:
        logger.info("user force-off: empirical tool blocked for this run")
        return GuardResult(blocked=["empirical"])
    if force_empirical is True:
        logger.info("user force-on: empirical tool forced for this run")
        return GuardResult(forced=["empirical"])

    if _depends_on_post_cutoff(prompt, specs):
        return GuardResult(forced=["empirical"])
    return GuardResult()


def _depends_on_post_cutoff(prompt: str, specs: Specs) -> bool:
    """Coarse heuristic: does the prompt likely need post-cutoff information?"""
    lowered = prompt.lower()
    matched_terms = [term for term in _RECENCY_TERMS if term in lowered]

    cutoff_year = _cutoff_year(specs.knowledge_cutoff)
    future_years = [
        m.group(0)
        for m in _YEAR.finditer(prompt)
        if cutoff_year and int(m.group(0)) > cutoff_year
    ]

    if matched_terms or future_years:
        logger.info(
            "recency heuristic fired empirical guard (terms=%s, future_years=%s) — "
            "coarse check, may false-positive",
            matched_terms,
            future_years,
        )
        return True
    return False


def _cutoff_year(cutoff: str) -> int | None:
    try:
        return int(cutoff.split("-")[0])
    except (ValueError, IndexError):
        logger.warning("could not parse knowledge_cutoff %r", cutoff)
        return None
