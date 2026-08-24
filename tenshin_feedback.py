"""Drop-in bug/feature reporter for Tenshin Arts games.

Posts to the centralized Feedback app (port 9000), not the hub.

    import tenshin_feedback
    ok, info = tenshin_feedback.submit(
        game="freightmogul", kind="bug", title="...", body="...", username="42",
        version="v1.0.9", image=shot_data_url)

Config (env): TENSHIN_FEEDBACK_URL (default https://feedback.tenshinarts.com), TENSHIN_SECRET.
"""
import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("TENSHIN_FEEDBACK_URL", "https://feedback.tenshinarts.com").rstrip("/")
SECRET = os.environ.get("TENSHIN_SECRET") or "dev-insecure-secret-change-me"

# Legacy name — some game code still reads tenshin_feedback.HUB
HUB = BASE


def submit(
    game,
    kind,
    title,
    body="",
    username="",
    meta=None,
    image="",
    version="",
    timeout=6,
):
    """Send a report to the Feedback app. Returns (ok: bool, info: dict). NEVER raises."""
    ver = version or (meta or {}).get("version") or ""
    fields = {
        "game": game,
        "version": ver,
        "kind": kind,
        "title": title,
        "body": body,
        "username": str(username or ""),
        "meta": json.dumps(meta) if meta else "",
        "image": image or "",
        "secret": SECRET,
    }
    data = urllib.parse.urlencode(fields).encode()
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(BASE + "/api/submit", data=data), timeout=timeout)
        return True, json.loads(r.read() or "{}")
    except Exception as e:
        if image:
            try:
                d2 = urllib.parse.urlencode({**fields, "image": ""}).encode()
                r = urllib.request.urlopen(
                    urllib.request.Request(BASE + "/api/submit", data=d2), timeout=timeout)
                return True, {**json.loads(r.read() or "{}"), "image_dropped": str(e)[:120]}
            except Exception as e2:
                return False, {"error": str(e2)}
        return False, {"error": str(e)}
