#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketCinema
SYS_DIR=/mnt/SDCARD/.tmp_update
LOG_FILE="$BASE_DIR/logs/button-diagnostic.log"
DIAGNOSTIC="$BASE_DIR/bin/pocketcinema-button-diagnostic"
INFOPANEL="$SYS_DIR/bin/infoPanel"

rm -f "$BASE_DIR/config/button-diagnostic.mode"

mkdir -p "$BASE_DIR/logs"
rm -f /tmp/stay_awake
touch /tmp/stay_awake
cleanup() {
  if [ -n "$panel_pid" ] && kill -0 "$panel_pid" 2>/dev/null; then
    touch /tmp/dismiss_info_panel
    wait "$panel_pid" 2>/dev/null || true
  fi
  rm -f /tmp/dismiss_info_panel
  rm -f /tmp/stay_awake
}
trap cleanup EXIT INT TERM

if [ ! -x "$DIAGNOSTIC" ]; then
  printf 'Button diagnostic binary is missing.\n'
  exit 1
fi

panel_pid=""
rm -f /tmp/dismiss_info_panel
if [ -x "$INFOPANEL" ]; then
  "$INFOPANEL" --title "PocketCinema Controls" \
    --message "Press each control once. Press Menu last to finish." \
    --persistent >/dev/null 2>&1 &
  panel_pid=$!
fi
"$DIAGNOSTIC" "$LOG_FILE" 90
status=$?
exit "$status"
