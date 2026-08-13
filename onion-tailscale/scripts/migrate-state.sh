#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/common.sh"

SOURCE="${1:-}"
if [ -z "$SOURCE" ]; then
  echo "Usage: $0 /path/to/existing/tailscaled.state"
  exit 1
fi
if [ ! -f "$SOURCE" ]; then
  echo "Source state does not exist: $SOURCE"
  exit 1
fi
if [ -e "$STATE_FILE" ]; then
  echo "Destination state already exists; refusing to overwrite it: $STATE_FILE"
  exit 2
fi
if [ -n "$(managed_pid || true)" ] || [ -n "$(other_tailscaled_pid || true)" ]; then
  echo "Stop every tailscaled process before copying node state."
  exit 3
fi

mkdir -p "$STATE_DIR"
TEMP_STATE="$STATE_FILE.migrating"
rm -f "$TEMP_STATE"
cp "$SOURCE" "$TEMP_STATE"
chmod 600 "$TEMP_STATE"
mv "$TEMP_STATE" "$STATE_FILE"

echo "Copied node state to $STATE_FILE"
echo "Source state retained unchanged at $SOURCE"
