"""Bridge the harness's synchronous emitter to an async SSE stream.

The pipeline calls `emit(event)` synchronously as it runs; we push those onto
a queue that an async generator drains into Server-Sent Events. A terminal
`None` sentinel closes the stream.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from contemplate.events import Emitter, StageEvent

logger = logging.getLogger("contemplate.server.stream")


async def harness_sse(run: Callable[[Emitter], Awaitable[object]]) -> AsyncIterator[dict]:
    """Run `run(emit)` in a task, yielding each emitted event as an SSE dict."""
    queue: asyncio.Queue[StageEvent | None] = asyncio.Queue()

    def emit(event: StageEvent) -> None:
        queue.put_nowait(event)

    async def runner() -> None:
        try:
            await run(emit)
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as an event
            logger.exception("harness run failed mid-stream")
            queue.put_nowait(StageEvent(type="run_complete", payload={"error": str(exc)}))
        finally:
            queue.put_nowait(None)

    task = asyncio.create_task(runner())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {"event": event.type, "data": event.model_dump_json()}
    finally:
        if not task.done():
            task.cancel()


async def items_sse(generator: AsyncIterator[tuple[str, object]]) -> AsyncIterator[dict]:
    """Adapt an (event_name, pydantic_model) async generator to SSE dicts."""
    async for event_name, payload in generator:
        data = payload.model_dump_json() if hasattr(payload, "model_dump_json") else str(payload)
        yield {"event": event_name, "data": data}
