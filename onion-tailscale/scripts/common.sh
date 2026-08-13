#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

TAILSCALE="$BASE_DIR/bin/tailscale"
TAILSCALED="$BASE_DIR/bin/tailscaled"
STATE_DIR="$BASE_DIR/state"
LOG_DIR="$BASE_DIR/logs"
RUN_DIR="${TS_RUN_DIR:-/tmp/onion-tailscale}"
STATE_FILE="$STATE_DIR/tailscaled.state"
PID_FILE="$STATE_DIR/tailscaled.pid"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"

is_managed_pid() {
  candidate="$1"
  [ -n "$candidate" ] && [ -r "/proc/$candidate/cmdline" ] &&
    [ "$(tr '\000' '\n' <"/proc/$candidate/cmdline" | sed -n '1p')" = "$TAILSCALED" ] &&
    kill -0 "$candidate" 2>/dev/null
}

managed_pid() {
  candidate=$(cat "$PID_FILE" 2>/dev/null || true)
  case "$candidate" in
    ''|*[!0-9]*) return 1 ;;
  esac
  is_managed_pid "$candidate" || return 1
  printf '%s\n' "$candidate"
}

other_tailscaled_pid() {
  for process_dir in /proc/[0-9]*; do
    [ -r "$process_dir/cmdline" ] || continue
    executable=$(tr '\000' '\n' <"$process_dir/cmdline" | sed -n '1p')
    [ -n "$executable" ] || continue
    [ "$executable" = "$TAILSCALED" ] && continue
    [ "$(basename "$executable")" = "tailscaled" ] || continue
    basename "$process_dir"
    return 0
  done
  return 1
}
