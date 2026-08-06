"""Tests for Socket.IO chat helpers."""
import pytest

from backend.app.socket_manager import _format_chat_message


def test_format_chat_message_trims_and_truncates():
    long_text = "hello " + "x" * 600
    msg = _format_chat_message(42, "  Alice  ", "  " + long_text + "  ")

    assert msg["account_id"] == 42
    assert msg["name"] == "Alice"
    assert msg["text"].startswith("hello")
    assert len(msg["text"]) == 500
    assert "timestamp" in msg


def test_format_chat_message_falls_back_to_player():
    msg = _format_chat_message(1, "", "")
    assert msg["name"] == "Player"
    assert msg["text"] == ""


def test_format_chat_message_caps_name_length():
    msg = _format_chat_message(1, "A" * 100, "hi")
    assert msg["name"] == "A" * 40


@pytest.mark.asyncio
async def test_chat_handler_is_registered():
    """The chat_message event handler is registered on the Socket.IO server."""
    from backend.app.socket_manager import socket_manager

    namespace_handlers = socket_manager.handlers.get("/", {})
    assert "chat_message" in namespace_handlers
    assert "chat_broadcast" not in namespace_handlers
