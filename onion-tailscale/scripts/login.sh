#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

HOSTNAME="${TS_HOSTNAME:-miyoo-onion}"
LOGIN_LOG="$RUN_DIR/login.log"
LOGIN_PID_FILE="$RUN_DIR/login.pid"
ACTION="${1:-start}"

login_pid() {
  candidate=$(cat "$LOGIN_PID_FILE" 2>/dev/null || true)
  case "$candidate" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ -r "/proc/$candidate/cmdline" ] || return 1
  [ "$(tr '\000' '\n' <"/proc/$candidate/cmdline" | sed -n '1p')" = "$TAILSCALE" ] || return 1
  kill -0 "$candidate" 2>/dev/null || return 1
  printf '%s\n' "$candidate"
}

login_url() {
  [ -f "$LOGIN_LOG" ] || return 1
  awk '
    {
      for (i = 1; i <= NF; i++) {
        if ($i ~ /^https:\/\//) {
          print $i
          exit
        }
      }
    }
  ' "$LOGIN_LOG"
}

current_ip() {
  [ -x "$TAILSCALE" ] && [ -S "$SOCKET_FILE" ] || return 1
  "$TAILSCALE" --socket="$SOCKET_FILE" ip -4 2>/dev/null | sed -n '1p'
}

if [ ! -x "$TAILSCALE" ]; then
  echo "Missing executable: $TAILSCALE" >&2
  exit 1
fi
if [ ! -S "$SOCKET_FILE" ]; then
  echo "Daemon socket is unavailable. Enable Tailscale first." >&2
  exit 1
fi

case "$ACTION" in
  start)
    if [ -n "$(current_ip || true)" ]; then
      rm -f "$LOGIN_PID_FILE" "$LOGIN_LOG"
      echo "connected"
      exit 0
    fi

    PID=$(login_pid || true)
    if [ -z "$PID" ]; then
      mkdir -p "$LOG_DIR" "$RUN_DIR"
      : >"$LOGIN_LOG"
      HOME="$RUN_DIR" nohup "$TAILSCALE" --socket="$SOCKET_FILE" up --hostname="$HOSTNAME" \
        >"$LOGIN_LOG" 2>&1 &
      PID=$!
      echo "$PID" >"$LOGIN_PID_FILE"
    fi

    attempt=0
    while [ "$attempt" -lt 15 ]; do
      IP=$(current_ip || true)
      if [ -n "$IP" ]; then
        rm -f "$LOGIN_PID_FILE" "$LOGIN_LOG"
        echo "connected"
        exit 0
      fi
      URL=$(login_url || true)
      if [ -n "$URL" ]; then
        printf '%s\n' "$URL"
        exit 0
      fi
      kill -0 "$PID" 2>/dev/null || break
      attempt=$((attempt + 1))
      sleep 1
    done
    echo "Tailscale did not provide a verification URL. Check login.log." >&2
    exit 2
    ;;
  status)
    if [ -n "$(current_ip || true)" ]; then
      rm -f "$LOGIN_PID_FILE" "$LOGIN_LOG"
      echo "connected"
    else
      URL=$(login_url || true)
      if [ -n "$URL" ]; then
        printf '%s\n' "$URL"
      else
        echo "waiting"
      fi
    fi
    ;;
  *)
    echo "Usage: $0 [start|status]" >&2
    exit 1
    ;;
esac
