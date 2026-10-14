#!/bin/sh
set -e
export SUBSCRIBE_BIND="${SUBSCRIBE_BIND:-127.0.0.1}"
export SUBSCRIBE_PORT="${SUBSCRIBE_PORT:-8000}"
python3 /app/api/server.py &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
