#!/usr/bin/env bash
set -euo pipefail

cd /home/site/wwwroot

# Azure sets WEBSITES_PORT / PORT. Fallback to 8000 for local.
export PORT="${WEBSITES_PORT:-${PORT:-8000}}"

python server.py
