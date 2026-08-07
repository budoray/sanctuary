#!/usr/bin/env bash
# Wrapper for the full platform deploy script.
# Run as root on the droplet.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/deploy/deploy.sh" "$@"
