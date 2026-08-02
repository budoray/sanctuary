"""Sanctuary hosts no login of its own - one Tenshin Arts account opens every
game - so every player route must refuse a request with no session cookie.

⚠ These run in a SUBPROCESS with TENSHIN_DEV stripped, because `tenshin_gate`
latches dev mode into a module constant at import time. Importing app.py inside
the normal test run (which sets TENSHIN_DEV=1) would prove nothing at all.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_PROBE = textwrap.dedent('''
    import json
    from fastapi.testclient import TestClient
    import app as A
    c = TestClient(A.app, raise_server_exceptions=False)
    out = {}
    for m, u in [("GET","/"),("POST","/api/character"),("POST","/api/roll-abilities"),
                 ("POST","/api/delve/start"),("POST","/api/delve/act"),
                 ("GET","/api/delve/x"),("GET","/version"),("GET","/licence"),
                 ("GET","/live/embed")]:
        out[u] = c.request(m, u, json={}).status_code
    print(json.dumps(out))
''')


def _status_without_dev() -> dict:
    env = {k: v for k, v in os.environ.items() if k != "TENSHIN_DEV"}
    r = subprocess.run([sys.executable, "-c", _PROBE], env=env, cwd=str(ROOT),
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    import json
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_every_player_route_refuses_a_request_with_no_session():
    got = _status_without_dev()
    leaks = {u: s for u, s in got.items()
             if u in ("/", "/api/character", "/api/roll-abilities",
                      "/api/delve/start", "/api/delve/act", "/api/delve/x")
             and s != 401}
    assert leaks == {}, f"routes served without a session: {leaks}"


def test_the_platform_contract_routes_stay_open():
    """The unauthenticated /live/embed carries build - report - back, and the
    hub reads /version cross-origin to show a live build on the game's card."""
    got = _status_without_dev()
    for u in ("/version", "/licence", "/live/embed"):
        assert got[u] == 200, f"{u} must be reachable without a session, got {got[u]}"
