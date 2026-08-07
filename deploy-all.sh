#!/usr/bin/env bash
# Sanctuary deploy script.
# Run as root on the droplet to pull the latest code, install Python deps,
# and restart the service. No Node/npm frontend build is required.
set -euo pipefail

DEPLOY_DIR="/opt/tenshin/sanctuary"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root" >&2
  exit 1
fi

if [ ! -d "${DEPLOY_DIR}/.git" ]; then
  echo "ERROR: ${DEPLOY_DIR} is not a Sanctuary git clone" >&2
  exit 1
fi

cd "${DEPLOY_DIR}"

echo "==> Fetching latest code"
git fetch
git reset --hard origin/main

echo "==> Installing Python requirements"
pip install -r requirements.txt

echo "==> Restarting tenshin-sanctuary"
systemctl restart tenshin-sanctuary

echo "==> Deploy complete"
