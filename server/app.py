"""FastAPI application factory.

Wires the harness (one injected LLMClient + Config, built at startup) to the
routes, with the security posture the standards require: explicit CORS
origins, security headers on every response, and a rate limiter on the
money-spending endpoints.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from contemplate.client import LLMClient
from contemplate.config import load_config

from .limiter import limiter
from .routes import router

logger = logging.getLogger("contemplate.server")

# Vite dev server origins. Production would serve the built SPA same-origin.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tests inject config/client up front; otherwise load and fail loud here.
    if not getattr(app.state, "config", None):
        config = load_config()  # fails loud if OPENROUTER_API_KEY is missing
        app.state.config = config
        app.state.client = LLMClient(config)
    logger.info("ConTemplate API ready (model=%s)", app.state.config.tiers.baseline)
    yield


def create_app(config=None, client=None) -> FastAPI:
    app = FastAPI(title="ConTemplate", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.client = client

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    app.include_router(router)
    return app


app = create_app()
