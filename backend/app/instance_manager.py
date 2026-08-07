"""Persistent instance AI-DM loop.

Active instances with no human players connected are advanced by an AI DM on a
fixed interval so the world keeps moving across server restarts and empty rooms.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.sessions import _load_session_module, _persist_instance_state
from backend.app.db import AsyncSessionLocal, SessionRecord
from backend.app.engine import session as session_engine
from backend.app.socket_manager import socket_manager

_LOOP_INTERVAL_SECONDS = 30

_ai_dm_task: asyncio.Task[Any] | None = None
_stop_event: asyncio.Event | None = None


async def advance_idle_instances() -> int:
    """Advance one AI DM turn for every active instance with no players present.

    Returns the number of instances that were advanced.
    """
    advanced = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionRecord).where(
                SessionRecord.status == "active",
                SessionRecord.ai_dm_enabled.is_(True),
            )
        )
        records = result.scalars().all()

        for record in records:
            state: dict[str, Any] = json.loads(record.state)
            if not state.get("players"):
                continue

            phase = state.get("phase")
            active_index = state.get("active_player_index", 0)
            players = state.get("players", [])
            active_player = players[active_index] if active_index < len(players) else None

            should_advance = False
            if phase == "dm":
                should_advance = True
            elif phase == "player" and active_player and active_player.get("ai_controlled"):
                # The active player is absent; let the AI DM play their turn.
                should_advance = True

            if not should_advance:
                continue

            try:
                mod = await _load_session_module(record, db)
                if phase == "dm":
                    state = await session_engine.act(state, mod, "dm_turn")
                else:
                    state = await session_engine.run_ai_players(state, mod)
            except Exception:
                # Module missing or the engine rejected the turn; skip this
                # instance rather than killing the whole loop.
                continue

            try:
                _persist_instance_state(record, state)
                await db.commit()
                advanced += 1
            except StaleDataError:
                # Another request updated the instance concurrently; it will be
                # picked up on the next loop iteration.
                await db.rollback()
                continue

            session_view = session_engine.view(state)
            try:
                await socket_manager.emit(
                    "session_update",
                    {"session": session_view},
                    room=record.id,
                )
            except Exception:
                pass

    return advanced


async def _ai_dm_loop() -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            await advance_idle_instances()
        except Exception:
            # The loop must stay alive across transient DB or engine errors.
            pass
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=_LOOP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


def start() -> None:
    """Start the background AI-DM loop unless tests explicitly disabled it."""
    global _ai_dm_task, _stop_event
    if _ai_dm_task is not None and not _ai_dm_task.done():
        return
    if os.environ.get("SANCTUARY_DISABLE_INSTANCE_LOOP") or os.environ.get("PYTEST_CURRENT_TEST"):
        return

    _stop_event = asyncio.Event()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    _ai_dm_task = loop.create_task(_ai_dm_loop())


async def stop() -> None:
    """Stop the background AI-DM loop."""
    global _ai_dm_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _ai_dm_task is not None and not _ai_dm_task.done():
        _ai_dm_task.cancel()
        try:
            await _ai_dm_task
        except asyncio.CancelledError:
            pass
    _ai_dm_task = None
    _stop_event = None
