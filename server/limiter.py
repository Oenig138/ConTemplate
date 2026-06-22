"""Shared rate limiter (slowapi). AI-backed endpoints spend money, so the
run/eval routes are limited first (coding standard)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
