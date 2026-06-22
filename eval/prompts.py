"""A small held set of representative prompts for the A/B eval (spec §8).

Spread across question types so per-tool instrumentation can show *which*
tool earns its tokens on *which* kind of prompt — the readout that permits
tuning rather than a single pass/fail verdict on the whole box.
"""

from __future__ import annotations

from pydantic import BaseModel


class EvalPrompt(BaseModel):
    id: str
    kind: str  # the dominant failure mode this prompt is meant to probe
    text: str


SEED_PROMPTS: list[EvalPrompt] = [
    EvalPrompt(
        id="frame-suicide-nets",
        kind="framing",
        text="A factory installs nets to catch workers who jump from the roof. "
        "Is this a good safety measure?",
    ),
    EvalPrompt(
        id="premise-free-will",
        kind="premise",
        text="Given that humans have free will, how should we design a justice "
        "system that holds people responsible for their choices?",
    ),
    EvalPrompt(
        id="empirical-tallest",
        kind="empirical",
        text="What is the tallest building in the world, and how tall is it?",
    ),
    EvalPrompt(
        id="adversarial-rent-control",
        kind="adversarial",
        text="Argue that rent control is an effective way to make housing more "
        "affordable for low-income tenants.",
    ),
    EvalPrompt(
        id="abductive-traffic",
        kind="abductive",
        text="A small town's main intersection keeps having accidents despite a "
        "new traffic light. How would you fix it?",
    ),
    EvalPrompt(
        id="genealogy-productivity",
        kind="genealogical",
        text="How can employees become more productive so the company can grow?",
    ),
    EvalPrompt(
        id="trivial-capital",
        kind="trivial",  # should hit the fast-path
        text="What is the capital of France?",
    ),
    EvalPrompt(
        id="reasoning-bridge",
        kind="reasoning",
        text="Should a mid-sized city replace its aging car bridge with a wider "
        "one, or invest in transit instead?",
    ),
]
