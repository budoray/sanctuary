#!/usr/bin/env bash
# Reset and create a fresh PostgreSQL database for Sanctuary.
# Run as root (or any user that can sudo to postgres) ON THE SERVER.
#
# Usage:
#   bash deploy/setup-postgres.sh [password]
#
# If no password is supplied, a strong URL-safe password is generated and printed.
# The script drops any existing sanctuary database/user and recreates them clean.
set -euo pipefail

DB_NAME="sanctuary"
DB_USER="sanctuary"
DB_PASSWORD="${1:-}"
ENV_FILE="/opt/tenshin/sanctuary/.env"

# Generate a URL-safe password if none provided.
# Uses /dev/urandom and avoids shell-sensitive characters (: / ? # [ ] @ ! $ & ' ( ) * + , ; =)
generate_password() {
  tr -dc 'A-Za-z0-9_.~-' </dev/urandom | head -c 32
}

if [ -z "$DB_PASSWORD" ]; then
  DB_PASSWORD=$(generate_password)
  echo ">> Generated password: $DB_PASSWORD"
  echo ">> Save this somewhere safe; it will not be shown again."
fi

# Pick how to run psql as the postgres superuser.
PSQL_CMD=("psql")
if [ "$(id -u)" -ne 0 ]; then
  if sudo -n -u postgres psql -c "SELECT 1" >/dev/null 2>&1; then
    PSQL_CMD=("sudo" "-u" "postgres" "psql")
  else
    echo "ERROR: must run as root or as a user that can sudo to postgres"
    exit 1
  fi
else
  # Running as root: prefer sudo -u postgres, fall back to running as postgres directly.
  if sudo -n -u postgres psql -c "SELECT 1" >/dev/null 2>&1; then
    PSQL_CMD=("sudo" "-u" "postgres" "psql")
  fi
fi

echo ">> Dropping existing ${DB_NAME} database and user (if any)..."
"${PSQL_CMD[@]}" -c "DROP DATABASE IF EXISTS ${DB_NAME};" >/dev/null
"${PSQL_CMD[@]}" -c "DROP USER IF EXISTS ${DB_USER};" >/dev/null

# Escape single quotes for the SQL literal by doubling them.
SQL_PASSWORD="${DB_PASSWORD//'/'''}"

echo ">> Creating ${DB_USER} user..."
"${PSQL_CMD[@]}" -c "CREATE USER ${DB_USER} WITH PASSWORD '${SQL_PASSWORD}';" >/dev/null

echo ">> Creating ${DB_NAME} database..."
"${PSQL_CMD[@]}" -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" >/dev/null

echo ">> Granting privileges..."
"${PSQL_CMD[@]}" -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" >/dev/null

echo ">> Testing connection..."
if PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
  echo ">> Connection OK"
else
  echo "ERROR: created user/database but connection test failed"
  exit 1
fi

# URL-encode the password so special characters (#, %, @, etc.) survive SQLAlchemy/asyncpg parsing.
URL_PASSWORD=$(python3 -c "import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))" "$DB_PASSWORD")

# Write or update the sanctuary .env file so the app can connect.
# We write the URL quoted to protect shell special characters.
if [ -d "$(dirname "$ENV_FILE")" ]; then
  echo ">> Writing DATABASE_URL to ${ENV_FILE}"
  if [ -f "$ENV_FILE" ]; then
    # Remove any existing DATABASE_URL line (with optional leading quote).
    sed -i '/^DATABASE_URL=/d' "$ENV_FILE"
  fi
  echo "DATABASE_URL=\"postgresql+asyncpg://${DB_USER}:${URL_PASSWORD}@127.0.0.1:5432/${DB_NAME}\"" >> "$ENV_FILE"
  # Ensure the file is readable only by the service user.
  chown tenshin:tenshin "$ENV_FILE" 2>/dev/null || true
  chmod 600 "$ENV_FILE" 2>/dev/null || true
else
  echo ">> WARN: ${ENV_FILE} directory does not exist; not writing .env"
  echo "    Add this line manually:"
  echo "    DATABASE_URL=\"postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@127.0.0.1:5432/${DB_NAME}\""
fi

echo ">> Done. Sanctuary PostgreSQL database is fresh and ready."
