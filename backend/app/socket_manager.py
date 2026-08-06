"""Socket.IO manager for real-time game state."""
import socketio

from backend.app.config import SETTINGS

# In-memory adapter for single-process deployments. Swap to Redis adapter
# (socketio.AsyncRedisManager) when scaling horizontally.
if SETTINGS.redis_url:
    mgr = socketio.AsyncRedisManager(SETTINGS.redis_url)
else:
    mgr = None

socket_manager = socketio.AsyncServer(
    async_mode="asgi",
    # The server is behind Caddy and only reachable through the subdomain,
    # so open CORS is safe here. Restricting to localhost breaks production.
    cors_allowed_origins="*",
    client_manager=mgr,
    logger=SETTINGS.app_env == "development",
    engineio_logger=SETTINGS.app_env == "development",
)

# Serve Socket.IO at the full /ws/socket.io path so Caddy proxies it cleanly
# without depending on Starlette's mount path stripping.
socket_app = socketio.ASGIApp(socket_manager, socketio_path="ws/socket.io")


def _account_from_environ(environ):
    """Resolve the Tenshin account_id and display name from the ASGI handshake.

    Returns a tuple of (account_id, name). Either value may be ``None`` if the
    session cookie is missing or invalid.
    """
    from backend.app.tenshin_gate import name_from_cookie_header, resolve_account

    scope = environ.get("asgi.scope", {})
    headers = scope.get("headers", [])
    cookie_header = ""
    for name, value in headers:
        if name.lower() == b"cookie":
            try:
                cookie_header = value.decode("utf-8")
            except UnicodeDecodeError:
                cookie_header = value.decode("latin-1")
            break

    account_id = resolve_account(cookie_header, "")
    name = name_from_cookie_header(cookie_header)
    return account_id, name


async def _can_chat_in_session(account_id, session_id):
    """Return True if ``account_id`` owns or is a member of the campaign session."""
    from sqlalchemy import select

    from backend.app.db import AsyncSessionLocal, CampaignMemberRecord, SessionRecord

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(SessionRecord).where(SessionRecord.id == session_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False
        if record.account_id == account_id:
            return True
        if not record.campaign_id:
            return False
        result = await db.execute(
            select(CampaignMemberRecord).where(
                CampaignMemberRecord.campaign_id == record.campaign_id,
                CampaignMemberRecord.account_id == account_id,
            )
        )
        return result.scalar_one_or_none() is not None


def _format_chat_message(account_id, name, text):
    """Normalize a chat payload for broadcast.

    Trims whitespace and truncates to safe limits. ``text`` is left unescaped so
    clients can safely render it with ``textContent``; only structural validation
    and length limits are applied here.
    """
    text = (text or "").strip()
    if len(text) > 500:
        text = text[:500]

    name = (name or "Player").strip()
    if len(name) > 40:
        name = name[:40]
    if not name:
        name = "Player"

    from datetime import datetime, timezone

    return {
        "account_id": account_id,
        "name": name,
        "text": text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@socket_manager.event
async def connect(sid, environ, auth=None):
    account_id, name = _account_from_environ(environ)
    await socket_manager.save_session(sid, {"account_id": account_id, "name": name})
    await socket_manager.emit(
        "message", {"type": "system", "text": "Connected."}, to=sid
    )


@socket_manager.event
async def disconnect(sid):
    pass


@socket_manager.event
async def join_session(sid, data):
    session_id = data.get("session_id")
    if session_id:
        await socket_manager.enter_room(sid, session_id)
        await socket_manager.emit(
            "message",
            {"type": "system", "text": f"Joined session {session_id}."},
            room=session_id,
            skip_sid=sid,
        )


@socket_manager.event
async def move_token(sid, data):
    # Broadcast to everyone in the session. Persistence is handled via the REST API.
    session_id = data.get("session_id")
    await socket_manager.emit(
        "message",
        {"type": "move", "token_id": data.get("token_id"), "x": data.get("x"), "y": data.get("y")},
        room=session_id,
        skip_sid=sid,
    )


@socket_manager.event
async def chat_message(sid, data):
    """Handle a party chat message from a campaign session member."""
    data = data or {}
    session_id = data.get("session_id")
    text = data.get("text")

    if not session_id or not isinstance(text, str) or not text.strip():
        return

    sess = await socket_manager.get_session(sid)
    account_id = sess.get("account_id") if sess else None
    if not account_id:
        return

    if not await _can_chat_in_session(account_id, session_id):
        return

    # Prefer the authoritative Tenshin name from the session cookie; fall back
    # to the name supplied by the trusted, authenticated client.
    name = (sess.get("name") if sess else None) or data.get("name")
    payload = _format_chat_message(account_id, name, text)
    await socket_manager.emit("chat_broadcast", payload, room=session_id)
