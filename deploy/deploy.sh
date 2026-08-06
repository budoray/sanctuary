#!/usr/bin/env bash
# Deploy Sanctuary on the DigitalOcean droplet.
# Run this as root on tenshin-web.
set -euo pipefail

CANONICAL="/opt/tenshin/site/deploy/deploy-game.sh"
NAME="sanctuary"
REPO="https://github.com/budoray/sanctuary.git"
PORT="9300"

if [ -x "$CANONICAL" ]; then
    echo "==> Using canonical Tenshin deploy: $CANONICAL"
    bash "$CANONICAL" "$NAME" "$REPO" "$PORT"
    exit 0
fi

# Fallback standalone deploy (only used when the platform deploy script is unavailable).
REPO_DIR="/opt/tenshin/$NAME"
SERVICE="tenshin-$NAME"

echo "==> Pulling latest Sanctuary code"
cd "$REPO_DIR"
git fetch origin
git reset --hard "origin/$(git rev-parse --abbrev-ref HEAD)"

echo "==> Updating Python dependencies"
"$REPO_DIR/.venv/bin/pip" install -q -r "$REPO_DIR/requirements.txt"

echo "==> Running database migrations"
cd "$REPO_DIR/backend"
"$REPO_DIR/.venv/bin/alembic" upgrade head

echo "==> Restarting $SERVICE"
systemctl daemon-reload
systemctl reset-failed "$SERVICE" 2>/dev/null || true
systemctl restart "$SERVICE"
systemctl is-active "$SERVICE" || {
  echo "!!! Service failed to start"
  journalctl -u "$SERVICE" --no-pager | tail -30
  exit 1
}

echo "==> Sanctuary deployed"
