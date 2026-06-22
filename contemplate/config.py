"""Configuration loading and startup validation.

Single responsibility: read `.env` + `config.yaml`, fail loud if required
environment is missing, and expose a typed, immutable `Config` object. No
other module reads the filesystem or `os.environ` for config.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# ── Structural constants (tool identities, not user-tunable) ──────────────
# Whether a tool sees the baseline is a property of the tool (spec §4.3),
# so these live in code alongside the architecture, not in config.yaml.
ALL_TOOLS: tuple[str, ...] = (
    "framing",
    "premise",
    "empirical",
    "adversarial",
    "abductive",
    "genealogical",
)
BASELINE_CONSUMERS: frozenset[str] = frozenset(
    {"framing", "premise", "empirical", "adversarial"}
)
BASELINE_SHIELDED: frozenset[str] = frozenset({"abductive", "genealogical"})
RETRIEVAL_TOOLS: frozenset[str] = frozenset({"empirical"})

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class Specs(BaseModel):
    """Worker-model specification — the orchestrator consumes this as data."""

    model_id: str
    knowledge_cutoff: str  # ISO month, e.g. "2026-01"
    benchmarks: dict[str, float]
    known_failure_modes: list[str]


class Tiers(BaseModel):
    baseline: str
    orchestrator: str
    synthesis: str
    diagnostic: str
    redundancy: str
    per_tool: dict[str, str] = Field(default_factory=dict)

    @field_validator("per_tool", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> object:
        # An empty `per_tool:` block in YAML parses to None.
        return value or {}

    def for_tool(self, tool_id: str) -> str:
        """Slug for a diagnostic, honouring per-tool overrides."""
        return self.per_tool.get(tool_id, self.diagnostic)


class WebConfig(BaseModel):
    max_results: int = 5


class Defaults(BaseModel):
    temperature: float = 0.7
    baseline_temperature: float = 0.3
    synthesis_temperature: float = 0.3
    request_timeout_s: int = 120


class Config(BaseModel):
    """Fully-resolved, immutable configuration."""

    model_config = {"frozen": True}

    api_key: str
    judge_model: str | None
    base_url: str
    tiers: Tiers
    provider_pin: str | None
    specs: Specs
    dials: dict[str, int]
    web: WebConfig
    defaults: Defaults

    def ceiling(self, dial: str) -> int:
        if dial not in self.dials:
            raise ValueError(f"unknown dial {dial!r}; expected one of {list(self.dials)}")
        return self.dials[dial]


def load_config(config_path: Path | None = None) -> Config:
    """Load and validate configuration. Fails loud on missing API key.

    This is the only place credentials or config files are read.
    """
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
            "your OpenRouter key before running ConTemplate."
        )

    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        raise RuntimeError(f"config file not found at {path}")
    raw = yaml.safe_load(path.read_text())

    tiers = Tiers(**raw["tiers"])
    _warn_on_placeholder_slugs(tiers)

    return Config(
        api_key=api_key,
        judge_model=os.environ.get("OPENROUTER_JUDGE_MODEL") or None,
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        tiers=tiers,
        provider_pin=raw.get("provider_pin"),
        specs=Specs(**raw["specs"]),
        dials=raw["dials"],
        web=WebConfig(**raw.get("web", {})),
        defaults=Defaults(**raw.get("defaults", {})),
    )


def _warn_on_placeholder_slugs(tiers: Tiers) -> None:
    """Loud, non-fatal warning if the config still holds placeholder slugs.

    Non-fatal so tests and dry runs work; the live run will get an obvious
    OpenRouter error, but this points at the real cause first.
    """
    placeholders = [
        name
        for name, slug in (
            ("baseline", tiers.baseline),
            ("orchestrator", tiers.orchestrator),
            ("synthesis", tiers.synthesis),
            ("diagnostic", tiers.diagnostic),
            ("redundancy", tiers.redundancy),
        )
        if "REPLACE_ME" in slug
    ]
    if placeholders:
        import logging

        logging.getLogger("contemplate.config").warning(
            "config.yaml still has placeholder model slugs for: %s — fill them "
            "with real OpenRouter slugs before a live run.",
            ", ".join(placeholders),
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Process-wide cached config accessor."""
    return load_config()
