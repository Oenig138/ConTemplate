"""A/B eval harness (spec §8): harness output vs the bare single call.

The bare single call IS the harness's own baseline, so every run yields both
arms for free. We record, per prompt: which tools were selected/admitted, how
far each diagnostic diverged from the baseline (a coarse lexical proxy), and —
if a judge model is configured — a blind A/B verdict. This is the instrument
that turns "the harness works" into "tool X earns its tokens on prompt kind Y".
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from contemplate.client import CompletionError, LLMClient
from contemplate.config import Config, load_config
from contemplate.models import RunRecord
from contemplate.pipeline import run_harness

from .prompts import SEED_PROMPTS, EvalPrompt

logger = logging.getLogger("contemplate.eval")

RESULTS_DIR = Path(__file__).resolve().parent / "results"
_WORD = re.compile(r"[a-z0-9]+")


class PromptResult(BaseModel):
    prompt_id: str
    kind: str
    fast_path: bool
    fallback: str | None
    selected: list[str]
    admitted: list[str]
    dropped: dict[str, str] = Field(default_factory=dict)
    divergence: dict[str, float] = Field(default_factory=dict)
    judge_winner: str | None = None  # "harness" | "single" | "tie" | None
    # Full texts so the UI can assemble an external judge prompt (no API judge).
    prompt_text: str = ""
    baseline_answer: str = ""
    harness_answer: str = ""


class EvalSummary(BaseModel):
    n_prompts: int
    harness_wins: int = 0
    single_wins: int = 0
    ties: int = 0
    tool_selected: dict[str, int] = Field(default_factory=dict)
    tool_admitted: dict[str, int] = Field(default_factory=dict)
    results: list[PromptResult] = Field(default_factory=list)


async def eval_stream(
    client: LLMClient,
    config: Config,
    prompts: list[EvalPrompt],
    *,
    dial: str = "high",
    judge: bool = True,
    seed: int = 0,
):
    """Yield ("prompt_result", PromptResult) per prompt, then ("eval_summary", EvalSummary).

    The single source of truth for the eval loop; both the CLI and the
    streaming API consume it.
    """
    rng = random.Random(seed)
    summary = EvalSummary(n_prompts=len(prompts))
    for prompt in prompts:
        record = await run_harness(client, config, prompt.text, dial=dial)
        result = _score_record(prompt, record)
        if judge and config.judge_model and not record.fast_path:
            result.judge_winner = await _judge(client, config, prompt.text, record, rng)
        _accumulate(summary, result)
        summary.results.append(result)
        yield "prompt_result", result
    yield "eval_summary", summary


async def run_eval(
    client: LLMClient,
    config: Config,
    prompts: list[EvalPrompt],
    *,
    dial: str = "high",
    judge: bool = True,
    seed: int = 0,
) -> EvalSummary:
    """Run the full eval and return the final summary (drains eval_stream)."""
    summary = EvalSummary(n_prompts=len(prompts))
    async for kind, payload in eval_stream(
        client, config, prompts, dial=dial, judge=judge, seed=seed
    ):
        if kind == "eval_summary":
            summary = payload
    return summary


def _score_record(prompt: EvalPrompt, record: RunRecord) -> PromptResult:
    selected = record.manifest.selected if record.manifest else []
    admitted = [d.tool_id for d in record.gate_decisions if d.admitted]
    dropped = {d.tool_id: d.reason for d in record.gate_decisions if not d.admitted}
    baseline = record.baseline.answer if record.baseline else ""
    divergence = {
        d.tool_id: _lexical_divergence(d.output, baseline) for d in record.diagnostics
    }
    return PromptResult(
        prompt_id=prompt.id,
        kind=prompt.kind,
        fast_path=record.fast_path,
        fallback=record.fallback,
        selected=selected,
        admitted=admitted,
        dropped=dropped,
        divergence=divergence,
        prompt_text=prompt.text,
        baseline_answer=baseline,
        harness_answer=record.answer,
    )


def _accumulate(summary: EvalSummary, result: PromptResult) -> None:
    for tool in result.selected:
        summary.tool_selected[tool] = summary.tool_selected.get(tool, 0) + 1
    for tool in result.admitted:
        summary.tool_admitted[tool] = summary.tool_admitted.get(tool, 0) + 1
    if result.judge_winner == "harness":
        summary.harness_wins += 1
    elif result.judge_winner == "single":
        summary.single_wins += 1
    elif result.judge_winner == "tie":
        summary.ties += 1


def _lexical_divergence(a: str, b: str) -> float:
    """Coarse 1 - Jaccard over word sets. A proxy, not ground truth."""
    wa, wb = set(_WORD.findall(a.lower())), set(_WORD.findall(b.lower()))
    if not wa and not wb:
        return 0.0
    return round(1 - len(wa & wb) / len(wa | wb), 3)


async def _judge(
    client: LLMClient, config: Config, prompt: str, record: RunRecord, rng: random.Random
) -> str | None:
    """Blind A/B: present harness vs single answer in random order to the judge."""
    harness_ans = record.answer
    single_ans = record.baseline.answer if record.baseline else ""
    harness_is_a = rng.random() < 0.5
    answer_a, answer_b = (
        (harness_ans, single_ans) if harness_is_a else (single_ans, harness_ans)
    )
    messages = [
        {
            "role": "user",
            "content": (
                "Two answers to the same prompt. Reply with exactly one letter — "
                "A or B — for the better answer, or TIE.\n\n"
                f"PROMPT:\n{prompt}\n\nANSWER A:\n{answer_a}\n\nANSWER B:\n{answer_b}"
            ),
        }
    ]
    try:
        result = await client.complete(config.judge_model, messages, temperature=0.0)
    except CompletionError as exc:
        logger.warning("judge call failed for %r: %s", prompt[:40], exc)
        return None
    return _interpret_verdict(result.text, harness_is_a)


def _interpret_verdict(text: str, harness_is_a: bool) -> str:
    verdict = text.strip().upper()[:4]
    if "TIE" in verdict:
        return "tie"
    if verdict.startswith("A"):
        return "harness" if harness_is_a else "single"
    if verdict.startswith("B"):
        return "single" if harness_is_a else "harness"
    return "tie"


def _persist_summary(summary: EvalSummary) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-eval.json"
    path.write_text(summary.model_dump_json(indent=2))
    return path


def _print_summary(summary: EvalSummary) -> None:
    print(f"\nEval over {summary.n_prompts} prompts")
    if summary.harness_wins or summary.single_wins or summary.ties:
        print(
            f"  judge: harness={summary.harness_wins} "
            f"single={summary.single_wins} tie={summary.ties}"
        )
    print(f"  tool selected: {summary.tool_selected}")
    print(f"  tool admitted: {summary.tool_admitted}")
    for r in summary.results:
        tag = "fast-path" if r.fast_path else f"sel={r.selected} adm={r.admitted}"
        print(f"  [{r.kind:12}] {r.prompt_id:24} {tag}")


async def _main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config = load_config()
    client = LLMClient(config)
    summary = await run_eval(client, config, SEED_PROMPTS, judge=bool(config.judge_model))
    path = _persist_summary(summary)
    _print_summary(summary)
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
