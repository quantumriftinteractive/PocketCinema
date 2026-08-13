#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

MODE="${1:-full}"
PID=$(managed_pid || true)
IP=""
if [ -n "$PID" ] && [ -x "$TAILSCALE" ] && [ -S "$SOCKET_FILE" ]; then
  IP=$("$TAILSCALE" --socket="$SOCKET_FILE" ip -4 2>/dev/null | sed -n '1p' || true)
fi

if [ "$MODE" = "--brief" ]; then
  if [ -n "$PID" ]; then
    printf 'enabled\t%s\n' "$IP"
  else
    printf 'disabled\t\n'
  fi
  exit 0
fi

if [ -n "$PID" ]; then
  echo "tailscaled: enabled, PID $PID"
  if [ -n "$IP" ]; then
    echo "Tailscale IPv4: $IP"
  else
    echo "Tailscale IPv4: unavailable"
  fi
else
  echo "tailscaled: disabled"
fi

if [ -x "$TAILSCALE" ] && [ -S "$SOCKET_FILE" ]; then
  "$TAILSCALE" --socket="$SOCKET_FILE" status || true
else
  echo "tailscale CLI or daemon socket is not available yet."
fi
