#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

LOGIN_PID_FILE="$RUN_DIR/login.pid"
LOGIN_LOG="$RUN_DIR/login.log"

stop_login() {
  login_process=$(cat "$LOGIN_PID_FILE" 2>/dev/null || true)
  case "$login_process" in
    ''|*[!0-9]*) ;;
    *) kill "$login_process" 2>/dev/null || true ;;
  esac
  rm -f "$LOGIN_PID_FILE" "$LOGIN_LOG"
}

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found. tailscaled may already be stopped."
  stop_login
  rm -f "$SOCKET_FILE"
  exit 0
fi

PID=$(managed_pid || true)
if [ -n "$PID" ]; then
  kill "$PID"
  attempt=0
  while [ "$attempt" -lt 5 ] && kill -0 "$PID" 2>/dev/null; do
    attempt=$((attempt + 1))
    sleep 1
  done
  if kill -0 "$PID" 2>/dev/null; then
    echo "tailscaled did not exit after SIGTERM; sending SIGKILL"
    kill -9 "$PID" 2>/dev/null || true
  fi
  echo "tailscaled stopped"
else
  echo "PID file does not identify a running daemon owned by this app"
fi

rm -f "$PID_FILE" "$SOCKET_FILE"
stop_login
