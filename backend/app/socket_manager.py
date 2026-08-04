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
    cors_allowed_origins=SETTINGS.cors_origins,
    client_manager=mgr,
    logger=SETTINGS.app_env == "development",
    engineio_logger=SETTINGS.app_env == "development",
)

socket_app = socketio.ASGIApp(socket_manager)


@socket_manager.event
async def connect(sid, environ):
    await socket_manager.emit("message", {"type": "system", "text": "Connected."}, to=sid)


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
