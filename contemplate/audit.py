"""Audit persistence (spec §3, §6): every run is an inspectable artifact.

Everything except the answer — baseline, manifest, diagnostics, gate
decisions, per-call token/cost usage — is written to a timestamped JSON file.
This is what lets the eval tune the box and what validates the §9 cost claim
(cached-token counts are in the usage records).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from .models import RunRecord

logger = logging.getLogger("contemplate.audit")

DEFAULT_RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def persist(record: RunRecord, runs_dir: Path | None = None) -> Path:
    """Write the run record to runs/<timestamp>-<slug>.json and return the path."""
    target_dir = runs_dir or DEFAULT_RUNS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    slug = _slug(record.prompt)
    path = target_dir / f"{stamp}-{slug}.json"
    path.write_text(record.model_dump_json(indent=2))
    logger.info("persisted run record to %s", path)
    return path


def _slug(prompt: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")
    return cleaned[:max_len] or "prompt"
