"""HTTP + SSE routes. Thin adapters over the harness and the runs store.

No business logic lives here — routes parse inputs, call into the core, and
shape responses. The harness Pydantic models are returned directly.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from contemplate.pipeline import run_harness
from eval.harness import eval_stream
from eval.prompts import SEED_PROMPTS

from .budget import get_budget
from .limiter import limiter
from .meta import harness_meta
from .runs_store import get_run, list_runs
from .streaming import harness_sse, items_sse

logger = logging.getLogger("contemplate.server.routes")
router = APIRouter(prefix="/api")

_WEB_TO_FORCE = {"auto": None, "on": True, "off": False}


def _client_config(request: Request):
    return request.app.state.client, request.app.state.config


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta")
async def meta(request: Request) -> dict[str, object]:
    _, config = _client_config(request)
    return harness_meta(config)


@router.get("/budget")
async def budget(request: Request) -> dict[str, object]:
    _, config = _client_config(request)
    return await get_budget(config)


@router.get("/runs")
async def runs() -> list[dict[str, object]]:
    return list_runs()


@router.get("/runs/{run_id}")
async def run_detail(run_id: str):
    record = get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return record


@router.get("/run/stream")
@limiter.limit("30/minute")
async def run_stream(
    request: Request, prompt: str, dial: str = "high", web: str = "auto"
):
    """Stream a single harness run as Server-Sent Events."""
    client, config = _client_config(request)
    if dial not in config.dials:
        raise HTTPException(status_code=422, detail=f"unknown dial {dial!r}")
    force_empirical = _WEB_TO_FORCE.get(web, None)

    async def run(emit):
        return await run_harness(
            client, config, prompt, dial=dial, force_empirical=force_empirical, emit=emit
        )

    return EventSourceResponse(harness_sse(run))


@router.get("/eval/stream")
@limiter.limit("4/minute")
async def eval_stream_route(
    request: Request, dial: str = "high", judge: bool = True, seed: int = 0
):
    """Stream the seed-set A/B eval, one event per prompt then a summary."""
    client, config = _client_config(request)
    generator = eval_stream(
        client, config, SEED_PROMPTS, dial=dial, judge=judge, seed=seed
    )
    return EventSourceResponse(items_sse(generator))
