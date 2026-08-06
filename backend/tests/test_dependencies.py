import time

import pytest

from backend.app.dependencies import _SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_allows_within_limit():
    limiter = _SlidingWindowRateLimiter(max_calls=3, window_seconds=60)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is False


def test_sliding_window_rate_limiter_resets_after_window():
    limiter = _SlidingWindowRateLimiter(max_calls=1, window_seconds=0.05)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("a") is False
    time.sleep(0.06)
    assert limiter.is_allowed("a") is True


def test_sliding_window_rate_limiter_is_per_key():
    limiter = _SlidingWindowRateLimiter(max_calls=1, window_seconds=60)
    assert limiter.is_allowed("a") is True
    assert limiter.is_allowed("b") is True
