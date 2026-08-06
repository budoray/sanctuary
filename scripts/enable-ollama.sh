#!/usr/bin/env bash
# One-time helper: enable Ollama narration for Sanctuary and restart the service.
# Run as root on the droplet, then delete this script.

set -euo pipefail

ENV_FILE="/opt/tenshin/sanctuary/.env"
SERVICE="tenshin-sanctuary"

echo "Enabling Ollama in ${ENV_FILE}..."

# Append only if not already present.
if grep -q '^OLLAMA_ENABLED=' "${ENV_FILE}" 2>/dev/null; then
  echo "OLLAMA_ENABLED already set; leaving existing values in place."
else
  cat >> "${ENV_FILE}" <<'EOF'
OLLAMA_ENABLED=true
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
OLLAMA_TIMEOUT=5.0
EOF
  echo "Ollama flags appended."
fi

echo "Restarting ${SERVICE}..."
systemctl restart "${SERVICE}"

echo "Done. Verifying env and health:"
grep '^OLLAMA_' "${ENV_FILE}" || true
sleep 1
curl -s https://sanctuary.tenshinarts.com/version || true
echo
