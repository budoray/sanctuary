#!/usr/bin/env bash
# One script to provision a fresh DigitalOcean droplet and deploy the entire
# Tenshin platform (site + games). Run once as root on a new Ubuntu droplet,
# then run again any time to pull updates and redeploy.
#
# Assumptions:
#   - Ubuntu 22.04/24.04
#   - Root access
#   - tenshinarts.com and game subdomains point to this droplet
#   - Game repos are accessible from the server
set -euo pipefail

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
TENSHIN_DOMAIN="tenshinarts.com"
PLATFORM_DIR="/opt/tenshin/site"
SECRETS_FILE="${PLATFORM_DIR}/.env"
SERVICE_USER="tenshin"

# Games to deploy: name|repo|port|subdomain
GAMES=(
  "sanctuary|https://github.com/budoray/sanctuary.git|9300|sanctuary.tenshinarts.com"
)

# Optional: main Tensin site repo. Leave empty to serve a placeholder page.
# TENSHIN_SITE_REPO="https://github.com/budoray/tenshinarts.com.git"
TENSHIN_SITE_REPO=""
TENSHIN_SITE_DIR="/opt/tenshin/site/web"
TENSHIN_SITE_PORT="9000"

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: run this script as root" >&2
    exit 1
  fi
}

gen_password() {
  tr -dc 'A-Za-z0-9_.~-' </dev/urandom | head -c 32
}

url_encode() {
  python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$1"
}

set_env() {
  local file="$1"
  local key="$2"
  local value="$3"
  local overwrite="${4:-0}"

  mkdir -p "$(dirname "$file")"
  touch "$file"

  local escaped
  escaped=$(printf '%s' "$value" | sed 's/"/\\"/g')

  if grep -q "^${key}=" "$file" 2>/dev/null; then
    if [ "$overwrite" -eq 1 ]; then
      sed -i "/^${key}=/c${key}=\"${escaped}\"" "$file"
    fi
  else
    echo "${key}=\"${escaped}\"" >> "$file"
  fi
}

get_env() {
  local file="$1"
  local key="$2"
  if [ -f "$file" ]; then
    grep -oP "^${key}=\"?\\K[^\"]+" "$file" 2>/dev/null || true
  fi
}

# ---------------------------------------------------------------------------
# SYSTEM
# ---------------------------------------------------------------------------
install_system_deps() {
  echo "==> Updating packages"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get upgrade -y -qq

  echo "==> Installing base dependencies"
  apt-get install -y -qq git curl wget gnupg software-properties-common \
    python3 python3-venv python3-pip python3-dev build-essential \
    postgresql postgresql-contrib nodejs npm

  echo "==> Installing Caddy"
  apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' 2>/dev/null | \
    gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' 2>/dev/null | \
    tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq
  apt-get install -y -qq caddy

  systemctl enable caddy
}

create_service_user() {
  if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    echo "==> Creating ${SERVICE_USER} user"
    useradd -r -m -s /usr/sbin/nologin "$SERVICE_USER"
  fi
}

# ---------------------------------------------------------------------------
# PLATFORM SECRETS
# ---------------------------------------------------------------------------
setup_platform_secrets() {
  echo "==> Setting up platform secrets"
  mkdir -p "$PLATFORM_DIR"

  local tenshin_secret
  tenshin_secret=$(get_env "$SECRETS_FILE" "TENSHIN_SECRET")
  if [ -z "$tenshin_secret" ]; then
    tenshin_secret=$(gen_password)
    set_env "$SECRETS_FILE" "TENSHIN_SECRET" "$tenshin_secret"
    echo "    Generated TENSHIN_SECRET (save this if you need it): ${tenshin_secret}"
  fi

  chmod 600 "$SECRETS_FILE"
  chown root:root "$SECRETS_FILE"
}

# ---------------------------------------------------------------------------
# POSTGRESQL
# ---------------------------------------------------------------------------
setup_postgres() {
  echo "==> Ensuring PostgreSQL is running"
  systemctl enable postgresql
  systemctl start postgresql

  for entry in "${GAMES[@]}"; do
    local name repo port domain
    IFS='|' read -r name repo port domain <<< "$entry"

    local db_name="${name}"
    local db_user="${name}"
    local db_pass
    db_pass=$(get_env "$SECRETS_FILE" "${name^^}_DB_PASSWORD")
    if [ -z "$db_pass" ]; then
      db_pass=$(gen_password)
      set_env "$SECRETS_FILE" "${name^^}_DB_PASSWORD" "$db_pass"
    fi

    local sql_pass
    sql_pass="${db_pass//\'/\'\'}"
    local url_pass
    url_pass=$(url_encode "$db_pass")

    echo "==> Ensuring PostgreSQL database/user for ${name}"
    sudo -u postgres psql -c "CREATE USER ${db_user} WITH PASSWORD '${sql_pass}';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE ${db_name} OWNER ${db_user};" 2>/dev/null || true
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_user};" 2>/dev/null || true

    set_env "$SECRETS_FILE" "${name^^}_DATABASE_URL" \
      "postgresql+asyncpg://${db_user}:${url_pass}@127.0.0.1:5432/${db_name}"
  done

  chmod 600 "$SECRETS_FILE"
}

# ---------------------------------------------------------------------------
# CADDY
# ---------------------------------------------------------------------------
setup_caddy() {
  echo "==> Writing Caddyfile"

  local caddyfile="/etc/caddy/Caddyfile"
  if [ -f "$caddyfile" ]; then
    cp "$caddyfile" "${caddyfile}.bak-$(date +%Y%m%d-%H%M%S)"
  fi

  python3 - "$caddyfile" "$TENSHIN_DOMAIN" "$TENSHIN_SITE_REPO" "$TENSHIN_SITE_DIR" "$TENSHIN_SITE_PORT" "${GAMES[@]}" <<'PY'
import os, sys
caddyfile = sys.argv[1]
domain = sys.argv[2]
site_repo = sys.argv[3]
site_dir = sys.argv[4]
site_port = sys.argv[5]
games = sys.argv[6:]

lines = [f"{domain} {{"]
if site_repo and os.path.isdir(site_dir):
    lines.append(f"    reverse_proxy 127.0.0.1:{site_port}")
else:
    lines.append('    respond "Tenshin Arts" 200')
lines.extend(["}", ""])

for entry in games:
    name, repo, port, sub = entry.split("|")
    lines.extend([f"{sub} {{", f"    reverse_proxy 127.0.0.1:{port}", "}", ""])

with open(caddyfile, "w") as f:
    f.write("\n".join(lines).rstrip() + "\n")
PY

  chown root:caddy "$caddyfile"
  chmod 644 "$caddyfile"

  systemctl reload caddy || systemctl start caddy
}

# ---------------------------------------------------------------------------
# GAME DEPLOY
# ---------------------------------------------------------------------------
deploy_game() {
  local name="$1"
  local repo="$2"
  local port="$3"
  local domain="$4"

  local install_dir="/opt/tenshin/${name}"
  local service="tenshin-${name}"
  local service_file="/etc/systemd/system/${service}.service"
  local env_file="${install_dir}/.env"

  echo "==> Deploying ${name} (${domain} -> 127.0.0.1:${port})"

  # Code
  if [ ! -d "${install_dir}/.git" ]; then
    echo "    Cloning ${repo}"
    mkdir -p "$(dirname "$install_dir")"
    git clone "$repo" "$install_dir"
  fi

  cd "$install_dir"
  git fetch origin
  git reset --hard origin/main

  # Python
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt

  # Env
  local tenshin_secret db_url
  tenshin_secret=$(get_env "$SECRETS_FILE" "TENSHIN_SECRET")
  db_url=$(get_env "$SECRETS_FILE" "${name^^}_DATABASE_URL")

  mkdir -p "$(dirname "$env_file")"
  touch "$env_file"
  set_env "$env_file" "APP_ENV" "production" 1
  set_env "$env_file" "TENSHIN_SECRET" "$tenshin_secret" 1
  set_env "$env_file" "TENSHIN_SITE_URL" "https://${TENSHIN_DOMAIN}" 1
  set_env "$env_file" "DATABASE_URL" "$db_url" 1
  set_env "$env_file" "OLLAMA_ENABLED" "true" 1
  set_env "$env_file" "OLLAMA_HOST" "http://127.0.0.1:11434" 1
  set_env "$env_file" "OLLAMA_MODEL" "llama3.2" 1
  set_env "$env_file" "OLLAMA_TIMEOUT" "5.0" 1

  chown "${SERVICE_USER}:${SERVICE_USER}" "$env_file" 2>/dev/null || true
  chmod 600 "$env_file"

  # Frontend
  if command -v npm >/dev/null 2>&1 && [ -f frontend/package.json ]; then
    echo "    Building frontend"
    (cd frontend && npm ci && npm run build)
  fi

  # Migrations
  if [ -d backend/alembic ]; then
    echo "    Running migrations"
    (cd backend && ../.venv/bin/alembic upgrade head)
  fi

  # Service
  cat > "$service_file" <<EOF
[Unit]
Description=${name}
After=network.target

[Service]
WorkingDirectory=${install_dir}
Environment=TENSHIN_SITE_URL=https://${TENSHIN_DOMAIN}
Environment=OLLAMA_HOST=http://127.0.0.1:11434
Environment=OLLAMA_MODEL=llama3.2
EnvironmentFile=-${env_file}
ExecStart=${install_dir}/.venv/bin/python app.py
Restart=always
User=${SERVICE_USER}

[Install]
WantedBy=multi-user.target
EOF

  chown root:root "$service_file"
  chmod 644 "$service_file"

  systemctl daemon-reload
  systemctl enable "$service"
  systemctl reset-failed "$service" 2>/dev/null || true
  systemctl restart "$service"

  # Health check
  echo "    Waiting for ${name}"
  for _ in {1..30}; do
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${port}/health" 2>/dev/null || echo "000")
    if [ "$code" = "200" ] || [ "$code" = "303" ] || [ "$code" = "401" ]; then
      echo "    health check localhost:${port} -> HTTP ${code}"
      break
    fi
    sleep 1
  done

  local public_code
  public_code=$(curl -s -o /dev/null -w "%{http_code}" "https://${domain}/health" 2>/dev/null || echo "000")
  echo "    health check ${domain} -> HTTP ${public_code}"
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
main() {
  require_root

  echo "============================================"
  echo " Tenshin Platform Provision + Deploy"
  echo "============================================"

  install_system_deps
  create_service_user
  setup_platform_secrets
  setup_postgres

  for entry in "${GAMES[@]}"; do
    local name repo port domain
    IFS='|' read -r name repo port domain <<< "$entry"
    deploy_game "$name" "$repo" "$port" "$domain"
  done

  setup_caddy

  echo "============================================"
  echo " Done."
  echo " Platform secrets: ${SECRETS_FILE}"
  echo " Caddyfile: /etc/caddy/Caddyfile"
  echo "============================================"
}

main "$@"
