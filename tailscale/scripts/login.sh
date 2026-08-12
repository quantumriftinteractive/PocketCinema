#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

TAILSCALE="$BASE_DIR/bin/tailscale"
RUN_DIR="${TS_RUN_DIR:-/tmp/pocketstremio-tailscale}"
SOCKET_FILE="${TS_SOCKET:-$RUN_DIR/tailscaled.sock}"
HOSTNAME="${TS_HOSTNAME:-miyoo-pocketstremio}"

if [ ! -x "$TAILSCALE" ]; then
  echo "Missing executable: $TAILSCALE"
  exit 1
fi

if [ ! -S "$SOCKET_FILE" ]; then
  echo "Daemon socket not found: $SOCKET_FILE"
  echo "Run ./start.sh first."
  exit 1
fi

"$TAILSCALE" --socket="$SOCKET_FILE" up --hostname="$HOSTNAME"
