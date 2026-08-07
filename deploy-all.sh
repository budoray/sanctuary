#!/usr/bin/env bash
# Tenshin deploy script.
# Run as root on the droplet to pull the latest code for every Tenshin repo
# under /opt/tenshin/, install Python deps into Sanctuary's venv, run
# migrations, and restart the service. No Node/npm frontend build is required.
set -euo pipefail

TENSHIN_ROOT="/opt/tenshin"
SANCTUARY_DIR="${TENSHIN_ROOT}/sanctuary"
VENV_DIR="${SANCTUARY_DIR}/.venv"
SERVICE_USER="tenshin"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this script as root" >&2
  exit 1
fi

if [ ! -d "${TENSHIN_ROOT}" ]; then
  echo "ERROR: ${TENSHIN_ROOT} does not exist" >&2
  exit 1
fi

pull_repo() {
  local repo_dir="$1"
  local repo_name
  repo_name="$(basename "${repo_dir}")"

  echo "==> [${repo_name}] Pulling latest code"
  cd "${repo_dir}"

  # Try a fast-forward pull first; fall back to a hard reset if the tree
  # has diverged or the branch was force-pushed.
  if ! git pull --ff-only origin main 2>/dev/null; then
    echo "    [${repo_name}] Fast-forward pull failed; resetting to origin/main"
    git fetch origin
    git reset --hard origin/main
  fi
}

# Pull every git repository under /opt/tenshin/.
for repo in "${TENSHIN_ROOT}"/*; do
  if [ -d "${repo}/.git" ]; then
    pull_repo "${repo}"
  else
    echo "==> [$(basename "${repo}")] Skipping (not a git repo)"
  fi
done

# Sanctuary-specific deployment steps.
echo "==> [sanctuary] Ensuring Python venv exists at ${VENV_DIR}"
if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi
# Ensure the service user can read/execute the venv.
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${VENV_DIR}"
chmod -R u+rX "${VENV_DIR}"

echo "==> [sanctuary] Installing Python requirements"
cd "${SANCTUARY_DIR}"
"${VENV_DIR}/bin/pip" install -r requirements.txt

echo "==> [sanctuary] Running database migrations"
cd "${SANCTUARY_DIR}/backend"
"${VENV_DIR}/bin/python" -m alembic upgrade head

echo "==> [sanctuary] Reloading systemd unit"
systemctl daemon-reload

echo "==> [sanctuary] Restarting tenshin-sanctuary"
systemctl restart tenshin-sanctuary

echo "==> Deploy complete"
