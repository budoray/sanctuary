# Sanctuary Deployment

This folder contains the scripts used to deploy Sanctuary to an Ubuntu server.
Sanctuary is now a plain Python/FastAPI application with a static frontend; no
Node.js, npm, or frontend build step is required.

## One-command deploy

From your local machine, SSH into the target server as root and run the
canonical deploy script at the repository root:

```bash
ssh root@<your-droplet-ip> 'bash /opt/tenshin/sanctuary/deploy-all.sh'
```

Or, if you already have the repo cloned locally and want to pipe the bundled
script:

```bash
cat deploy-all.sh | ssh root@<your-droplet-ip> bash
```

The script is idempotent: run it again any time to pull the latest code, install
Python updates, run database migrations, and restart the service.

## What the deploy script does

`deploy-all.sh` performs the following steps on the server:

1. Iterates over every directory under `/opt/tenshin/` that is a git repository.
2. For each repo, runs `git pull --ff-only origin main` (or falls back to
   `git fetch && git reset --hard origin/main` if the branch diverged).
3. For Sanctuary specifically:
   - `pip install -r requirements.txt`
   - `alembic upgrade head`
   - `systemctl restart tenshin-sanctuary`

No frontend build is needed because `frontend/static/` is served directly.

## Environment variable checklist

Sanctuary reads these variables from `/opt/tenshin/sanctuary/.env`:

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `TENSHIN_SECRET` | Yes | Shared secret used for Tenshin Arts session verification. Generated automatically if missing. |
| `DATABASE_URL` | Yes | PostgreSQL connection string, e.g. `postgresql+asyncpg://sanctuary:<pass>@127.0.0.1:5432/sanctuary`. Generated automatically. |
| `OLLAMA_ENABLED` | No | Set to `false` to disable Ollama integration. Defaults to `true`. |
| `OLLAMA_HOST` | No | Base URL for Ollama, e.g. `http://127.0.0.1:11434`. Defaults to `http://127.0.0.1:11434`. |
| `OLLAMA_MODEL` | No | Model name used for narration. Defaults to `llama3.2`. |
| `OLLAMA_TIMEOUT` | No | Request timeout in seconds. Defaults to `5.0`. |
| `SANCTUARY_ADMIN_IDS` | No | Comma-separated Tenshin account IDs with admin access, e.g. `1,42`. |
| `PIXELLAB_HOST` | No | Base URL for a PixelLab-compatible image API. When unset, static class portraits are served. |
| `PIXELLAB_KEY` | No | API key sent as `Authorization: Bearer <key>` to the PixelLab host. |
| `PIXELLAB_MODEL` | No | Model name passed to PixelLab. Defaults to `flux`. |
| `PIXELLAB_TIMEOUT` | No | Portrait generation timeout in seconds. Defaults to `30.0`. |

Edit the env file directly on the server:

```bash
nano /opt/tenshin/sanctuary/.env
systemctl restart tenshin-sanctuary
```

## Useful operational commands

```bash
# View service logs
journalctl -u tenshin-sanctuary -f

# Restart the game service
systemctl restart tenshin-sanctuary

# Reload Caddy after manual Caddyfile changes
systemctl reload caddy

# Run migrations by hand
cd /opt/tenshin/sanctuary/backend
python3 -m alembic upgrade head
```

## Log rotation

The service logs to the systemd journal. To limit disk use, enable persistent
journal limits or create a logrotate rule for `/var/log/journal`. For example:

```bash
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/99-tenshin.conf <<EOF
[Journal]
SystemMaxUse=500M
SystemMaxFileSize=50M
EOF
systemctl restart systemd-journald
```

## Database reset

To drop and recreate the Sanctuary database:

```bash
bash deploy/setup-postgres.sh
```

This stops the service if it is running, recreates the database, and restarts
the service.
