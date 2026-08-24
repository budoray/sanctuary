"""In-memory turn + movement state for the 0.1.x test ground.

The test ground is a single shared square-grid map where every created
character gets a token. Multiple players may be logged in; the DM decision
timer resolves early once every expected participant has submitted a move.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from engine.grid import apply_direction


@dataclass
class PendingMove:
    character_id: int
    direction: int


@dataclass
class TestGroundSession:
    decision_timeout_seconds: int = 60
    on_tick: Callable | None = None
    participant_count_fn: Callable[[], int] | None = None

    _lock: threading.RLock = field(default_factory=threading.RLock)
    _pending: dict[int, PendingMove] = field(default_factory=dict)
    _timer_end: float = 0.0
    _timer_thread: threading.Thread | None = None
    _round: int = 1
    _shutdown: bool = False

    def start_round(self):
        with self._lock:
            if self._shutdown:
                return
            self._pending.clear()
            self._timer_end = time.time() + self.decision_timeout_seconds
            if self._timer_thread is None or not self._timer_thread.is_alive():
                self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
                self._timer_thread.start()

    def shutdown(self):
        """Stop the turn loop and do not start new rounds."""
        with self._lock:
            self._shutdown = True
            self._pending.clear()

    def _expected_participants(self) -> int:
        fn = self.participant_count_fn
        try:
            return max(0, int(fn())) if fn else 0
        except Exception:
            return 0

    def _timer_loop(self):
        while True:
            with self._lock:
                if self._shutdown or time.time() >= self._timer_end:
                    break
                if self._all_submitted():
                    break
            time.sleep(0.25)
        self._resolve_round()

    def _all_submitted(self) -> bool:
        expected = self._expected_participants()
        return expected > 0 and len(self._pending) >= expected

    def _resolve_round(self):
        with self._lock:
            moves = list(self._pending.values())
            self._pending.clear()
            self._round += 1
            self._timer_thread = None
        if self.on_tick:
            self.on_tick(moves)
        if not self._shutdown:
            self.start_round()

    def submit_move(self, character_id: int, direction: int) -> bool:
        with self._lock:
            if self._shutdown or character_id in self._pending:
                return False
            self._pending[character_id] = PendingMove(character_id, direction)
            return True

    def get_state(self) -> dict:
        with self._lock:
            return {
                "round": self._round,
                "timer_end": self._timer_end,
                "pending_count": len(self._pending),
                "expected_count": self._expected_participants(),
            }


# Global test ground for 0.1.x; replaced by per-campaign sessions later.
_test_ground: TestGroundSession | None = None


def get_test_ground(timeout_seconds: int = 60) -> TestGroundSession:
    global _test_ground
    if _test_ground is None:
        _test_ground = TestGroundSession(decision_timeout_seconds=timeout_seconds)
        _test_ground.start_round()
    return _test_ground


def shutdown_test_ground():
    """Public cleanup helper, mainly for tests."""
    global _test_ground
    if _test_ground is not None:
        _test_ground.shutdown()
        _test_ground = None


def apply_move(x: int, y: int, direction: int) -> tuple[int, int]:
    return apply_direction(x, y, direction)
