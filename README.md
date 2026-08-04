# Sanctuary

A web-based tabletop game platform: solo adventures, AI-DM'd campaigns, and human-DM'd multiplayer campaigns. Top-down 2D maps, plug-in rulesets, event-sourced persistence.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, python-socketio
- **Frontend:** Vite + TypeScript + PixiJS v8
- **Persistence:** SQLite for local dev, PostgreSQL for production
- **Real-time:** WebSockets (Redis adapter optional for scaling)
- **Rulesets:** YAML manifest + Python adapter (OSRIC ships first)

## Run locally

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

The backend runs on `http://127.0.0.1:9300` and the Vite dev server on `http://localhost:5173`.

## Production build

```bash
cd frontend
npm run build
cd ..
python app.py
```

## Tests

```bash
cd backend && python -m pytest tests -q
```

## Deployment

Follows the Tenshin Arts pattern: clone to `/opt/tenshin/sanctuary`, run as the `tenshin` user, proxy through Caddy on `sanctuary.tenshinarts.com` to `127.0.0.1:9300`. See `deploy/tenshin-sanctuary.service`.
