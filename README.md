# Sanctuary

A web-based tabletop game platform: solo adventures, AI-DM'd campaigns, and human-DM'd multiplayer campaigns. Top-down 2D maps, plug-in rulesets, event-sourced persistence.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, python-socketio
- **Frontend:** Plain HTML + CSS + JavaScript (static files in `frontend/static`)
- **Persistence:** SQLite for local dev, PostgreSQL for production
- **Real-time:** WebSockets (Redis adapter optional for scaling)
- **Rulesets:** YAML manifest + Python adapter (OSRIC ships first)

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:9300`. The static frontend is served from `frontend/static`.

To change the UI, edit the files in `frontend/static` directly and reload the browser.

## Tests

```bash
cd backend && python -m pytest tests -q
```

## Deployment

Follows the Tenshin Arts pattern: clone to `/opt/tenshin/sanctuary`, run as the `tenshin` user, proxy through Caddy on `sanctuary.tenshinarts.com` to `127.0.0.1:9300`. See `deploy/tenshin-sanctuary.service`.
