#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
TAILSCALED="$BASE_DIR/bin/tailscaled"
PID_FILE="$BASE_DIR/state/tailscaled.pid"

echo "== memory =="
free 2>/dev/null || cat /proc/meminfo

echo
echo "== swap =="
grep -E 'Swap(Total|Free|Cached)' /proc/meminfo 2>/dev/null || true

PID=$(cat "$PID_FILE" 2>/dev/null || true)
case "$PID" in
  ''|*[!0-9]*) PID="" ;;
esac
if [ -n "$PID" ] && [ -r "/proc/$PID/cmdline" ] &&
    tr '\000' ' ' <"/proc/$PID/cmdline" | grep -F "$TAILSCALED" >/dev/null 2>&1 &&
    kill -0 "$PID" 2>/dev/null; then
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
