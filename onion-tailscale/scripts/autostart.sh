#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
BASE_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
SOURCE="$BASE_DIR/boot/onion-tailscale.sh"
STARTUP_DIR="${ONION_STARTUP_DIR:-/mnt/SDCARD/.tmp_update/startup}"
TARGET="$STARTUP_DIR/onion-tailscale.sh"
ACTION="${1:-status}"

hook_state() {
  if [ ! -e "$TARGET" ]; then
    echo "disabled"
  elif cmp -s "$SOURCE" "$TARGET"; then
    echo "enabled"
  else
    echo "conflict"
  fi
}

case "$ACTION" in
  status)
    hook_state
    ;;
  enable)
    state=$(hook_state)
    if [ "$state" = "conflict" ]; then
      echo "Refusing to overwrite unexpected startup hook: $TARGET"
      exit 2
    fi
    mkdir -p "$STARTUP_DIR"
    cp "$SOURCE" "$TARGET"
    chmod +x "$TARGET"
    echo "Automatic enable on boot is on"
    ;;
  disable)
    state=$(hook_state)
    if [ "$state" = "conflict" ]; then
      echo "Refusing to remove unexpected startup hook: $TARGET"
      exit 2
    fi
    rm -f "$TARGET"
    echo "Automatic enable on boot is off"
    ;;
  *)
    echo "Usage: $0 [status|enable|disable]"
    exit 1
    ;;
esac
