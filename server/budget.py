"""Live OpenRouter credit balance for the session budget meter.

Tries OpenRouter's credit endpoints; falls back to summing locally-recorded
run costs so the meter degrades gracefully offline.
"""

from __future__ import annotations

import logging

import httpx

from contemplate.config import Config

from .runs_store import total_spent

logger = logging.getLogger("contemplate.server.budget")


async def get_budget(config: Config) -> dict[str, object]:
    """Return {limit, usage, remaining, source}. Never raises."""
    headers = {"Authorization": f"Bearer {config.api_key}"}
    async with httpx.AsyncClient(timeout=10) as http:
        remote = await _try_credits(http, config.base_url, headers)
        if remote is None:
            remote = await _try_key(http, config.base_url, headers)
    if remote is not None:
        return remote

    spent = total_spent()
    logger.info("budget falling back to local run-cost sum (%.4f)", spent)
    return {"limit": None, "usage": spent, "remaining": None, "source": "local"}


async def _try_credits(http: httpx.AsyncClient, base_url: str, headers: dict) -> dict | None:
    try:
        resp = await http.get(f"{base_url}/credits", headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
        limit = data["total_credits"]
        usage = data["total_usage"]
        return {"limit": limit, "usage": usage, "remaining": round(limit - usage, 6), "source": "credits"}
    except (httpx.HTTPError, KeyError) as exc:
        logger.debug("credits endpoint unavailable: %s", exc)
        return None


async def _try_key(http: httpx.AsyncClient, base_url: str, headers: dict) -> dict | None:
    try:
        resp = await http.get(f"{base_url}/auth/key", headers=headers)
        resp.raise_for_status()
        data = resp.json()["data"]
        limit = data.get("limit")
        usage = data.get("usage", 0.0)
        remaining = data.get("limit_remaining")
        if remaining is None and limit is not None:
            remaining = round(limit - usage, 6)
        return {"limit": limit, "usage": usage, "remaining": remaining, "source": "auth/key"}
    except (httpx.HTTPError, KeyError) as exc:
        logger.debug("auth/key endpoint unavailable: %s", exc)
        return None
