#!/usr/bin/env bash
# One script to deploy or update Sanctuary on the DigitalOcean droplet.
# Run as root. After the first run, every future deploy is just:
#   bash /opt/tenshin/sanctuary/deploy/deploy.sh
set -euo pipefail

NAME="sanctuary"
DOMAIN="sanctuary.tenshinarts.com"
PORT="9300"
REPO="https://github.com/budoray/sanctuary.git"
INSTALL_DIR="/opt/tenshin/${NAME}"
SERVICE="tenshin-${NAME}"
ENV_FILE="${INSTALL_DIR}/.env"
SERVICE_FILE="/etc/systemd/system/${SERVICE}.service"
CADDYFILE="/etc/caddy/Caddyfile"

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run this script as root" >&2
    exit 1
  fi
}

# Write KEY="value" to .env, preserving any existing value unless overwrite=1.
set_env() {
  local key="$1"
  local value="$2"
  local overwrite="${3:-0}"

  if [ ! -f "$ENV_FILE" ]; then
    mkdir -p "$(dirname "$ENV_FILE")"
    touch "$ENV_FILE"
  fi

  # Escape double quotes in value for the .env line.
  local escaped
  escaped=$(printf '%s' "$value" | sed 's/"/\\"/g')

  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    if [ "$overwrite" -eq 1 ]; then
      sed -i "/^${key}=/c${key}=\"${escaped}\"" "$ENV_FILE"
    fi
  else
    echo "${key}=\"${escaped}\"" >> "$ENV_FILE"
  fi
}

get_existing_secret() {
  local secret=""
  if [ -f "$SERVICE_FILE" ]; then
    secret=$(grep -oP '^Environment=TENSHIN_SECRET=\K[^ ]+' "$SERVICE_FILE" 2>/dev/null || true)
  fi
  if [ -z "$secret" ] && [ -f "$ENV_FILE" ]; then
    secret=$(grep -oP '^TENSHIN_SECRET=\"?\K[^\"]+' "$ENV_FILE" 2>/dev/null || true)
  fi
  printf '%s' "$secret"
}

get_existing_database_url() {
  local url=""
  if [ -f "$ENV_FILE" ]; then
    url=$(grep -oP '^DATABASE_URL=\"?\K[^\"]+' "$ENV_FILE" 2>/dev/null || true)
  fi
  printf '%s' "$url"
}

main() {
  require_root

  echo "==> Deploying ${NAME} (${DOMAIN})"

  # 1. Code
  if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "==> Cloning ${REPO} into ${INSTALL_DIR}"
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO" "$INSTALL_DIR"
  fi

  cd "$INSTALL_DIR"
  echo "==> Pulling latest main"
  git fetch origin
  git reset --hard origin/main

  # 2. Python environment
  if [ ! -d ".venv" ]; then
    echo "==> Creating Python virtual environment"
    python3 -m venv .venv
  fi
  echo "==> Installing / updating Python dependencies"
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt

  # 3. Environment file
  echo "==> Checking environment file"
  mkdir -p "$(dirname "$ENV_FILE")"
  touch "$ENV_FILE"

  local tenshin_secret
  tenshin_secret=$(get_existing_secret)
  if [ -z "$tenshin_secret" ] || [ "$tenshin_secret" = "SAME_SECRET_AS_THE_WEBSITE" ]; then
    echo "ERROR: TENSHIN_SECRET is not set." >&2
    echo "Add the shared Tenshin secret to ${ENV_FILE}:" >&2
    echo '  TENSHIN_SECRET="your-secret-here"' >&2
    exit 1
  fi
  set_env "TENSHIN_SECRET" "$tenshin_secret"

  local database_url
  database_url=$(get_existing_database_url)
  if [ -z "$database_url" ]; then
    echo "WARNING: DATABASE_URL not set. Using SQLite for now." >&2
    set_env "DATABASE_URL" "sqlite+aiosqlite://${INSTALL_DIR}/sanctuary.db"
  else
    set_env "DATABASE_URL" "$database_url"
  fi

  set_env "APP_ENV" "production" 1
  set_env "TENSHIN_SITE_URL" "https://tenshinarts.com" 1
  set_env "OLLAMA_ENABLED" "true" 1
  set_env "OLLAMA_HOST" "http://127.0.0.1:11434" 1
  set_env "OLLAMA_MODEL" "llama3.2" 1
  set_env "OLLAMA_TIMEOUT" "5.0" 1

  chown tenshin:tenshin "$ENV_FILE" 2>/dev/null || true
  chmod 600 "$ENV_FILE"

  # 4. Frontend build (if Node is installed; otherwise rely on committed dist)
  if command -v npm >/dev/null 2>&1 && [ -f frontend/package.json ]; then
    echo "==> Building frontend"
    (cd frontend && npm ci && npm run build)
  else
    echo "==> Node not found; using committed frontend/dist"
  fi

  # 5. Database migrations
  echo "==> Running database migrations"
  (cd backend && ../.venv/bin/alembic upgrade head)

  # 6. Service user and service file
  if ! id -u tenshin >/dev/null 2>&1; then
    echo "==> Creating tenshin service user"
    useradd -r -s /usr/sbin/nologin tenshin
  fi

  echo "==> Installing systemd service"
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Sanctuary
After=network.target

[Service]
WorkingDirectory=${INSTALL_DIR}
Environment=TENSHIN_SITE_URL=https://tenshinarts.com
Environment=OLLAMA_HOST=http://127.0.0.1:11434
Environment=OLLAMA_MODEL=llama3.2
EnvironmentFile=-${ENV_FILE}
ExecStart=${INSTALL_DIR}/.venv/bin/python app.py
Restart=always
User=tenshin

[Install]
WantedBy=multi-user.target
EOF

  chown root:root "$SERVICE_FILE"
  chmod 644 "$SERVICE_FILE"
  systemctl daemon-reload
  systemctl enable "$SERVICE"

  # 7. Start / restart
  echo "==> Restarting ${SERVICE}"
  systemctl reset-failed "$SERVICE" 2>/dev/null || true
  systemctl restart "$SERVICE"

  # 8. Health checks
  echo "==> Waiting for service"
  for i in {1..30}; do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  echo "==> Local health check"
  curl -fsS "http://127.0.0.1:${PORT}/health" || {
    echo "!!! Local health check failed" >&2
    journalctl -u "$SERVICE" --no-pager | tail -40
    exit 1
  }

  echo "==> Public health check"
  curl -fsS "https://${DOMAIN}/health" || {
    echo "!!! Public health check failed (Caddy may still be loading)" >&2
    exit 1
  }

  # 9. Caddy
  if [ -f "$CADDYFILE" ]; then
    if ! grep -q "^${DOMAIN} {" "$CADDYFILE"; then
      echo "==> Adding ${DOMAIN} to ${CADDYFILE}"
      cp "$CADDYFILE" "${CADDYFILE}.bak-$(date +%Y%m%d-%H%M%S)"
      cat >> "$CADDYFILE" <<EOF

${DOMAIN} {
    reverse_proxy 127.0.0.1:${PORT}
}
EOF
      systemctl reload caddy
    else
      echo "==> ${DOMAIN} already present in Caddyfile"
    fi
  else
    echo "WARNING: ${CADDYFILE} not found; skipped Caddy update" >&2
  fi

  echo "==> ${NAME} deployed successfully"
}

main "$@"
