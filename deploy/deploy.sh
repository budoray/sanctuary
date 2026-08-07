#!/usr/bin/env bash
# Deprecated wrapper for the Sanctuary deploy script.
# The canonical deploy script is deploy-all.sh at the repository root.
# This file is kept so old curl/ssh one-liners continue to work.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/../deploy-all.sh" "$@"
