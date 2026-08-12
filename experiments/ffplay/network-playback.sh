#!/bin/sh
set -eu

URL="${1:-${POCKETSTREMIO_VIDEO_URL:-http://100.85.171.67:8755/media/test-video.mp4}}"
PROXY="${HTTP_PROXY:-http://127.0.0.1:1055/}"
FFPLAY="${FFPLAY:-/mnt/SDCARD/.tmp_update/bin/ffplay}"
LOG_DIR="${POCKETSTREMIO_LOG_DIR:-/mnt/SDCARD/App/PocketStremio/experiments/logs}"
LOG_FILE="$LOG_DIR/ffplay-network.log"

mkdir -p "$LOG_DIR"

if [ ! -x "$FFPLAY" ]; then
  echo "ffplay not found at $FFPLAY"
  exit 1
fi

echo "url=$URL" | tee "$LOG_FILE"
echo "proxy=$PROXY" | tee -a "$LOG_FILE"
echo "ffplay=$FFPLAY" | tee -a "$LOG_FILE"

HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$FFPLAY" \
  -hide_banner \
  -autoexit \
  -t 10 \
  "$URL" >>"$LOG_FILE" 2>&1
