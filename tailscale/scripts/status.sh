#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

TAILSCALE="$BASE_DIR/bin/tailscale"
STATE_DIR="$BASE_DIR/state"
RUN_DIR="${TS_RUN_DIR:-/tmp/pocketstremio-tailscale}"
PID_FILE="$STATE_DIR/tailscaled.pid"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "tailscaled: running, PID $(cat "$PID_FILE")"
else
  echo "tailscaled: not running"
fi

if [ -x "$TAILSCALE" ] && [ -S "$SOCKET_FILE" ]; then
  "$TAILSCALE" --socket="$SOCKET_FILE" status || true
  "$TAILSCALE" --socket="$SOCKET_FILE" ip || true
else
  echo "tailscale CLI or daemon socket is not available yet."
fi
