"""Static UI metadata: the tools' falsifiers and the harness's dials/specs.

The frontend reads this once to render tool tooltips, dial options, and the
model identities — so those facts live in one place, not duplicated in TS.
"""

from __future__ import annotations

from contemplate.config import ALL_TOOLS, BASELINE_SHIELDED, RETRIEVAL_TOOLS, Config

# One-line falsifier per tool (spec §4.4): the error each exists to catch.
TOOL_CATCHES: dict[str, str] = {
    "framing": "flawless reasoning inside the wrong frame",
    "premise": "a false load-bearing premise imported silently",
    "empirical": "a claim that is valid and well-framed but untrue or outdated",
    "adversarial": "a defeasible inference that never met its strongest objection",
    "abductive": "the answer that is true, defensible, and boring — a local optimum",
    "genealogical": "a frame that is coherent but an artifact of interest, occluding what its provenance requires",
}


def tool_metadata() -> list[dict[str, object]]:
    """Per-tool descriptors for the routing display."""
    return [
        {
            "tool_id": tool_id,
            "catches": TOOL_CATCHES[tool_id],
            "shielded": tool_id in BASELINE_SHIELDED,
            "retrieval": tool_id in RETRIEVAL_TOOLS,
        }
        for tool_id in ALL_TOOLS
    ]


def harness_meta(config: Config) -> dict[str, object]:
    """Everything the UI needs to render controls and labels."""
    return {
        "tools": tool_metadata(),
        "dials": config.dials,
        "models": {
            "baseline": config.tiers.baseline,
            "orchestrator": config.tiers.orchestrator,
            "synthesis": config.tiers.synthesis,
            "diagnostic": config.tiers.diagnostic,
        },
        "knowledge_cutoff": config.specs.knowledge_cutoff,
        "model_id": config.specs.model_id,
    }
