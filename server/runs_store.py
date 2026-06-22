"""Read access to the persisted audit records under runs/.

The harness already writes one JSON per run; the history screen is just a
reader over that directory. No new storage layer.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from contemplate.audit import DEFAULT_RUNS_DIR
from contemplate.models import RunRecord

logger = logging.getLogger("contemplate.server.runs")


def list_runs(runs_dir: Path | None = None, limit: int = 200) -> list[dict[str, object]]:
    """Lightweight summaries of recent runs, newest first."""
    target = runs_dir or DEFAULT_RUNS_DIR
    summaries: list[dict[str, object]] = []
    for path in sorted(target.glob("*.json"), reverse=True)[:limit]:
        record = _load(path)
        if record is None:
            continue
        summaries.append(
            {
                "id": record.id,
                "created_at": record.created_at,
                "prompt": record.prompt,
                "dial": record.dial,
                "fast_path": record.fast_path,
                "fallback": record.fallback,
                "selected": record.manifest.selected if record.manifest else [],
                "cost_usd": record.total_usage.cost_usd,
            }
        )
    return summaries


def get_run(run_id: str, runs_dir: Path | None = None) -> RunRecord | None:
    """Full record by id (scans the directory; fine at this scale)."""
    target = runs_dir or DEFAULT_RUNS_DIR
    for path in target.glob(f"*{run_id}.json"):
        record = _load(path)
        if record and record.id == run_id:
            return record
    return None


def total_spent(runs_dir: Path | None = None) -> float:
    """Sum of recorded costs across all runs — the local budget fallback."""
    target = runs_dir or DEFAULT_RUNS_DIR
    total = 0.0
    for path in target.glob("*.json"):
        record = _load(path)
        if record and record.total_usage.cost_usd:
            total += record.total_usage.cost_usd
    return round(total, 6)


def _load(path: Path) -> RunRecord | None:
    try:
        return RunRecord(**json.loads(path.read_text()))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.warning("skipping unreadable run file %s: %s", path, exc)
        return None
