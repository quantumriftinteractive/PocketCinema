#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
RUN_DIR="${TS_RUN_DIR:-/tmp/pocketstremio-tailscale}"
PID_FILE="$BASE_DIR/state/tailscaled.pid"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found. tailscaled may already be stopped."
  rm -f "$SOCKET_FILE"
  exit 0
fi

PID=$(cat "$PID_FILE")
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  sleep 1
  if kill -0 "$PID" 2>/dev/null; then
    echo "tailscaled did not exit after SIGTERM; sending SIGKILL"
    kill -9 "$PID" 2>/dev/null || true
  fi
  echo "tailscaled stopped"
else
  echo "PID $PID is not running"
fi

rm -f "$PID_FILE" "$SOCKET_FILE"
