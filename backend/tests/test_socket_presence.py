"""Tests for session presence tracking."""
import pytest

from backend.app.socket_manager import presence_tracker, socket_manager


def test_presence_tracker_tracks_joins_and_leaves():
    present = presence_tracker.add("sid-1", "sess-a", 1, "Alice")
    assert len(present) == 1
    assert present[0]["account_id"] == 1
    assert present[0]["name"] == "Alice"

    present = presence_tracker.add("sid-2", "sess-a", 2, "Bob")
    assert len(present) == 2

    session_id, remaining = presence_tracker.remove("sid-1")
    assert session_id == "sess-a"
    assert len(remaining) == 1
    assert remaining[0]["account_id"] == 2

    session_id, remaining = presence_tracker.remove("sid-2")
    assert session_id == "sess-a"
    assert remaining == []
    assert presence_tracker.get("sess-a") == []


def test_presence_tracker_heartbeat_updates_existing_sid():
    presence_tracker.add("sid-3", "sess-b", 3, "Carol")
    present = presence_tracker.heartbeat("sid-3", "sess-b", 3, "Carol Updated")
    assert present[0]["name"] == "Carol Updated"


@pytest.mark.asyncio
async def test_presence_handlers_are_registered():
    namespace_handlers = socket_manager.handlers.get("/", {})
    assert "join_session" in namespace_handlers
    assert "heartbeat" in namespace_handlers
