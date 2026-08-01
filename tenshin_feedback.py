"""Drop-in bug/feature reporter for Tenshin Arts games. Copy this ONE file into a game repo.

The game calls submit(...) server-side when a player files a report; it POSTs to the shared hub
(tenshinarts.com/feedback), authenticating with the same TENSHIN_SECRET the game already runs with.
One shared queue for every game — view + auto-fix at tenshinarts.com/admin/feedback.

    import tenshin_feedback
    ok, info = tenshin_feedback.submit(game="freight", kind="bug",
                                       title="Ship stuck at Mars", body="...", username="42",
                                       image=shot_data_url)   # optional

Config (env): TENSHIN_HUB_URL (default https://tenshinarts.com), TENSHIN_SECRET (shared with the hub).
"""
import json
import os
import urllib.parse
import urllib.request

HUB = os.environ.get("TENSHIN_HUB_URL", "https://tenshinarts.com").rstrip("/")
SECRET = os.environ.get("TENSHIN_SECRET") or "dev-insecure-secret-change-me"


def submit(game, kind, title, body="", username="", meta=None, image="", timeout=6):
    """Send a report to the shared hub. Returns (ok: bool, info: dict). NEVER raises —
    a down hub must not break the game."""
    fields = {
        "game": game, "kind": kind, "title": title, "body": body,
        "username": str(username or ""), "meta": json.dumps(meta) if meta else "",
        # ⚠ A DATA URL (`data:image/jpeg;base64,...`), not a file. Downscale client-side
        # first — Fading Wilds caps at 1600px JPEG q85, which is what keeps a screen-sized
        # PNG out of the request entirely. A malformed one is dropped by the hub and the
        # report still files: the words are the report, the picture is evidence.
        "image": image or "",
        "secret": SECRET,
    }
    data = urllib.parse.urlencode(fields).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(HUB + "/feedback", data=data), timeout=timeout)
        return True, json.loads(r.read() or "{}")
    except Exception as e:
        # ⚠ NEVER LOSE THE REPORT OVER THE PICTURE. An oversized screenshot makes the POST
        # itself fail — too large, or too slow for the timeout — and the player's words go
        # with it. Measured: a >8 MB image failed the whole submission before the hub could
        # even apply its own limits. So if there WAS an image, try once more without it.
        if image:
            try:
                d2 = urllib.parse.urlencode({**fields, "image": ""}).encode()
                r = urllib.request.urlopen(
                    urllib.request.Request(HUB + "/feedback", data=d2), timeout=timeout)
                return True, {**json.loads(r.read() or "{}"), "image_dropped": str(e)[:120]}
            except Exception as e2:
                return False, {"error": str(e2)}
        return False, {"error": str(e)}
