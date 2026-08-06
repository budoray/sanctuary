"""Shared FastAPI dependencies."""
from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import Depends, HTTPException, Request

from backend.app.auth import require_account


class _SlidingWindowRateLimiter:
    """Simple in-memory sliding-window rate limiter keyed by account ID.

    The limit is ``max_calls`` per ``window_seconds``. Requests that exceed
    the limit receive HTTP 429. This is process-local and intentionally
    simple; a production deployment with multiple workers would need a
    shared store such as Redis.
    """

    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self._windows: dict[Any, deque[float]] = {}

    def is_allowed(self, key: Any) -> bool:
        now = time.monotonic()
        window = self._windows.setdefault(key, deque())
        while window and window[0] < now - self.window_seconds:
            window.popleft()
        if len(window) >= self.max_calls:
            return False
        window.append(now)
        return True


# 30 actions per minute per account.
_action_limiter = _SlidingWindowRateLimiter(max_calls=30, window_seconds=60)


def limit_actions(request: Request, account_id: int = Depends(require_account)) -> None:
    """Rate-limit session actions to 30 per account per minute."""
    if not _action_limiter.is_allowed(account_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded: 30 actions per minute")
