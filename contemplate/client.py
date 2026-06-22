"""The single OpenRouter gateway.

`LLMClient` is the only object that talks to the network. Every stage
receives it by injection (Dependency Inversion) — nothing constructs an
OpenAI client inline. It centralizes provider pinning (so DeepSeek's
automatic prefix cache lands), the web plugin for the empirical tool, JSON
mode, and usage/cost extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from .config import Config
from .models import CompletionResult, Usage

logger = logging.getLogger("contemplate.client")


class CompletionError(RuntimeError):
    """A hard failure of an LLM call (network, API, or empty response)."""


class LLMClient:
    """Async wrapper over the OpenRouter chat-completions endpoint."""

    def __init__(self, config: Config, openai_client: AsyncOpenAI | None = None) -> None:
        self._config = config
        self._client = openai_client or AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.defaults.request_timeout_s,
        )
        # Per-run tally of every call's usage — captures orchestrator, gate, and
        # repair calls the stage return values would otherwise drop.
        self.usage_log: list[Usage] = []

    def reset_usage(self) -> None:
        """Clear the usage tally at the start of a run."""
        self.usage_log = []

    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        json_mode: bool = False,
        web: bool = False,
    ) -> CompletionResult:
        """One chat completion. Raises CompletionError on failure or empty text."""
        extra_body = self._build_extra_body(web=web)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "extra_body": extra_body,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised as our typed error
            logger.warning("LLM call failed (model=%s): %s", model, exc)
            raise CompletionError(str(exc)) from exc

        choice = resp.choices[0] if resp.choices else None
        text = (choice.message.content if choice and choice.message else None) or ""
        if not text.strip():
            raise CompletionError(f"empty response from {model}")

        usage = _extract_usage(resp)
        self.usage_log.append(usage)
        return CompletionResult(
            text=text,
            usage=usage,
            citations=_extract_citations(choice),
            model=getattr(resp, "model", model),
        )

    def _build_extra_body(self, *, web: bool) -> dict[str, Any]:
        """Provider pin (for cache hits), usage accounting, and web plugin."""
        body: dict[str, Any] = {"usage": {"include": True}}
        if self._config.provider_pin:
            body["provider"] = {
                "order": [self._config.provider_pin],
                "allow_fallbacks": False,
            }
        if web:
            body["plugins"] = [
                {"id": "web", "max_results": self._config.web.max_results}
            ]
        return body


def _extract_usage(resp: Any) -> Usage:
    """Pull token + cached + cost figures defensively across SDK shapes."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return Usage()
    data = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    details = data.get("prompt_tokens_details") or {}
    cached = details.get("cached_tokens", 0) if isinstance(details, dict) else 0
    return Usage(
        prompt_tokens=data.get("prompt_tokens", 0) or 0,
        completion_tokens=data.get("completion_tokens", 0) or 0,
        cached_tokens=cached or 0,
        cost_usd=data.get("cost"),
    )


def _extract_citations(choice: Any) -> list[str]:
    """Collect URL citations the web plugin attaches to the message."""
    if choice is None or not getattr(choice, "message", None):
        return []
    annotations = getattr(choice.message, "annotations", None) or []
    urls: list[str] = []
    for ann in annotations:
        ann_dict = ann.model_dump() if hasattr(ann, "model_dump") else dict(ann)
        url = (ann_dict.get("url_citation") or {}).get("url")
        if url:
            urls.append(url)
    return urls
