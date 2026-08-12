#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

TAILSCALED="$BASE_DIR/bin/tailscaled"
STATE_DIR="$BASE_DIR/state"
LOG_DIR="$BASE_DIR/logs"
RUN_DIR="${TS_RUN_DIR:-/tmp/pocketstremio-tailscale}"
STATE_FILE="$STATE_DIR/tailscaled.state"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"
PID_FILE="$STATE_DIR/tailscaled.pid"
LOG_FILE="$LOG_DIR/tailscaled.log"

SOCKS5_LISTEN="${TS_SOCKS5_LISTEN:-127.0.0.1:1055}"
HTTP_PROXY_LISTEN="${TS_HTTP_PROXY_LISTEN:-127.0.0.1:1055}"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$RUN_DIR"

if [ ! -x "$TAILSCALED" ]; then
  echo "Missing executable: $TAILSCALED"
  echo "Install the ARM static Tailscale binaries into $BASE_DIR/bin first."
  exit 1
fi

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "tailscaled is already running with PID $(cat "$PID_FILE")"
  exit 0
fi

rm -f "$SOCKET_FILE"

HOME="$RUN_DIR" TS_NO_LOGS_NO_SUPPORT="${TS_NO_LOGS_NO_SUPPORT:-true}" nohup "$TAILSCALED" \
  --tun=userspace-networking \
  --state="$STATE_FILE" \
  --socket="$SOCKET_FILE" \
  --socks5-server="$SOCKS5_LISTEN" \
  --outbound-http-proxy-listen="$HTTP_PROXY_LISTEN" \
  >>"$LOG_FILE" 2>&1 &

PID=$!
echo "$PID" > "$PID_FILE"
sleep 2

if kill -0 "$PID" 2>/dev/null; then
  echo "tailscaled started with PID $PID"
  echo "socket: $SOCKET_FILE"
  echo "SOCKS5 proxy: $SOCKS5_LISTEN"
  echo "HTTP proxy: $HTTP_PROXY_LISTEN"
  echo "log: $LOG_FILE"
else
  echo "tailscaled failed to stay running. Last log lines:"
  tail -n 40 "$LOG_FILE" 2>/dev/null || true
  exit 1
fi
