#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
PID_FILE="$BASE_DIR/state/tailscaled.pid"

echo "== memory =="
free 2>/dev/null || cat /proc/meminfo

echo
echo "== swap =="
grep -E 'Swap(Total|Free|Cached)' /proc/meminfo 2>/dev/null || true

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  PID=$(cat "$PID_FILE")
  echo
  echo "== tailscaled process =="
  ps | grep '[t]ailscaled' || true
  echo
  echo "== /proc/$PID/status =="
  grep -E '^(Name|State|VmSize|VmRSS|VmData|VmStk|VmExe|VmSwap|Threads):' "/proc/$PID/status" 2>/dev/null || true
else
  echo
  echo "tailscaled is not running according to $PID_FILE"
fi
