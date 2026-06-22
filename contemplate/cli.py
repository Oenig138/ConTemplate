"""Command-line entrypoint: run one prompt through the harness.

    python -m contemplate --dial high "your prompt here"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .client import LLMClient
from .config import load_config
from .models import RunRecord
from .pipeline import run_harness


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contemplate", description=__doc__)
    parser.add_argument("prompt", help="the user prompt to answer")
    parser.add_argument(
        "--dial", choices=["off", "medium", "high"], default="high",
        help="diagnostic ceiling (default: high)",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--force-empirical", dest="force_empirical", action="store_true",
        default=None, help="force the web-retrieval tool on",
    )
    group.add_argument(
        "--no-empirical", dest="force_empirical", action="store_false",
        help="force the web-retrieval tool off (privacy/offline)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    return parser


def _print_summary(record: RunRecord) -> None:
    selected = record.manifest.selected if record.manifest else []
    admitted = [d.tool_id for d in record.gate_decisions if d.admitted]
    u = record.total_usage
    print("\n" + "─" * 60, file=sys.stderr)
    print(f"dial={record.dial}  fast_path={record.fast_path}  fallback={record.fallback}", file=sys.stderr)
    print(f"selected: {selected or '—'}", file=sys.stderr)
    print(f"admitted: {admitted or '—'}", file=sys.stderr)
    print(
        f"tokens: prompt={u.prompt_tokens} (cached={u.cached_tokens}) "
        f"completion={u.completion_tokens}  cost_usd={u.cost_usd}",
        file=sys.stderr,
    )


async def _run(args: argparse.Namespace) -> int:
    config = load_config()
    client = LLMClient(config)
    record = await run_harness(
        client, config, args.prompt, dial=args.dial, force_empirical=args.force_empirical
    )
    print(record.answer)
    _print_summary(record)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(_run(args))
    except RuntimeError as exc:  # config / startup failures, fail loud
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
