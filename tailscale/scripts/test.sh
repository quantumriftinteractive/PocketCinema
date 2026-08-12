#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
RUN_DIR="${TS_RUN_DIR:-/tmp/pocketstremio-tailscale}"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"
URL="${1:-${POCKETSTREMIO_TEST_URL:-}}"
PROXY="${TS_HTTP_PROXY_URL:-http://127.0.0.1:1055/}"

if [ -z "$URL" ]; then
  echo "Usage: $0 http://TAILSCALE_DEVICE_OR_IP:PORT/path"
  echo "Example: $0 http://gaming-pc:8754/api/status"
  exit 2
fi

if [ ! -S "$SOCKET_FILE" ]; then
  echo "Daemon socket not found. Run ./start.sh and ./login.sh first."
  exit 1
fi

if command -v curl >/dev/null 2>&1; then
  HTTP_PROXY="$PROXY" http_proxy="$PROXY" curl -v --max-time 20 "$URL"
elif command -v wget >/dev/null 2>&1; then
  HTTP_PROXY="$PROXY" http_proxy="$PROXY" wget -S -O - "$URL"
else
  echo "Neither curl nor wget was found."
  echo "Install or copy a small HTTP client, or run a PocketStremio test client that supports HTTP_PROXY."
  exit 1
fi
