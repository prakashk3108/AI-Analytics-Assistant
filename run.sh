#!/usr/bin/env bash
set -euo pipefail

PORT=${PORT:-8025}
WATCH_FILES=(server.py deals.xlsx .env)
export VERTEX_ENDPOINT=${VERTEX_ENDPOINT:-projects/232714184900/locations/us-central1/endpoints/656275400875311104}
unset VERTEX_MODEL

mtime() {
  local file="$1"
  if [ -f "$file" ]; then
    stat -c %Y "$file"
  else
    echo 0
  fi
}

last_sig=""
server_pid=""

start_server() {
  echo "Starting server on port $PORT..."
  python3 server.py &
  server_pid=$!
}

stop_server() {
  if [ -n "$server_pid" ] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" || true
    wait "$server_pid" 2>/dev/null || true
  fi
}

trap stop_server EXIT

start_server

while true; do
  sig=""
  for file in "${WATCH_FILES[@]}"; do
    sig+="$(mtime "$file")-"
  done
  if [ "$sig" != "$last_sig" ]; then
    if [ -n "$last_sig" ]; then
      stop_server
      start_server
    fi
    last_sig="$sig"
  fi
  sleep 1
  if ! kill -0 "$server_pid" 2>/dev/null; then
    start_server
  fi
 done
