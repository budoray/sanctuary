#!/usr/bin/env bash
# Deploy Sanctuary on the DigitalOcean droplet.
# Run this as a user with sudo privileges on tenshin-web.
set -euo pipefail

REPO_DIR="/opt/tenshin/sanctuary"
SERVICE="tenshin-sanctuary"

echo "==> Pulling latest Sanctuary code"
cd "$REPO_DIR"
git pull origin main

echo "==> Updating Python dependencies"
source "$REPO_DIR/.venv/bin/activate"
pip install -q -r "$REPO_DIR/requirements.txt"

echo "==> Restarting $SERVICE"
sudo systemctl restart "$SERVICE"
sudo systemctl is-active "$SERVICE" || {
  echo "!!! Service failed to start"
  sudo journalctl -u "$SERVICE" --no-pager | tail -30
  exit 1
}

echo "==> Sanctuary deployed"
