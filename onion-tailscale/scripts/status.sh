#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

TAILSCALE="$BASE_DIR/bin/tailscale"
TAILSCALED="$BASE_DIR/bin/tailscaled"
STATE_DIR="$BASE_DIR/state"
RUN_DIR="${TS_RUN_DIR:-/tmp/onion-tailscale}"
PID_FILE="$STATE_DIR/tailscaled.pid"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"

PID=$(cat "$PID_FILE" 2>/dev/null || true)
case "$PID" in
  ''|*[!0-9]*) PID="" ;;
esac
if [ -n "$PID" ] && [ -r "/proc/$PID/cmdline" ] &&
    tr '\000' ' ' <"/proc/$PID/cmdline" | grep -F "$TAILSCALED" >/dev/null 2>&1 &&
    kill -0 "$PID" 2>/dev/null; then
  echo "tailscaled: running, PID $PID"
else
  echo "tailscaled: not running"
fi

if [ -x "$TAILSCALE" ] && [ -S "$SOCKET_FILE" ]; then
  "$TAILSCALE" --socket="$SOCKET_FILE" status || true
  "$TAILSCALE" --socket="$SOCKET_FILE" ip || true
else
  echo "tailscale CLI or daemon socket is not available yet."
fi
