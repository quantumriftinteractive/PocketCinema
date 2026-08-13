#!/bin/sh

APP_DIR=/mnt/SDCARD/App/Tailscale
LOG_FILE="$APP_DIR/logs/boot.log"

mkdir -p "$APP_DIR/logs"
printf '%s automatic enable requested\n' "$(date '+%Y-%m-%d %H:%M:%S')" >>"$LOG_FILE"
if [ -x "$APP_DIR/scripts/start.sh" ]; then
  "$APP_DIR/scripts/start.sh" >>"$LOG_FILE" 2>&1 ||
    echo "automatic enable failed rc=$?" >>"$LOG_FILE"
else
  echo "automatic enable skipped: start.sh is unavailable" >>"$LOG_FILE"
fi

exit 0
