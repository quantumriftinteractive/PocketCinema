#!/bin/sh
set -u

BASE_DIR=/mnt/SDCARD/App/Tailscale
SYS_DIR=/mnt/SDCARD/.tmp_update
LOG_FILE="$BASE_DIR/logs/app.log"
INFOPANEL="$SYS_DIR/bin/infoPanel"

mkdir -p "$BASE_DIR/logs"

show_message() {
  title="$1"
  body="$2"
  if [ -x "$INFOPANEL" ]; then
    "$INFOPANEL" --title "$title" --message "$body" --auto >/dev/null 2>&1 || true
  else
    printf '%s: %s\n' "$title" "$body"
  fi
}

{
  date
  echo "Tailscale app launch"
  if "$BASE_DIR/scripts/start.sh"; then
    "$BASE_DIR/scripts/status.sh" || true
    show_message "Tailscale" "Connection service is running"
  else
    rc=$?
    echo "start failed rc=$rc"
    show_message "Tailscale" "Connection service failed. Check app logs."
    exit "$rc"
  fi
} >>"$LOG_FILE" 2>&1
