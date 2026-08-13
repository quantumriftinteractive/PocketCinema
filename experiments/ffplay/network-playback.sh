#!/bin/sh
set -eu

URL="${1:-${POCKETSTREMIO_VIDEO_URL:-}}"
PROXY="${HTTP_PROXY:-}"
FFPLAY="${FFPLAY:-/mnt/SDCARD/.tmp_update/bin/ffplay}"
LOG_DIR="${POCKETSTREMIO_LOG_DIR:-/mnt/SDCARD/App/PocketStremio/experiments/logs}"
LOG_FILE="$LOG_DIR/ffplay-network.log"

mkdir -p "$LOG_DIR"

if [ -z "$URL" ]; then
  echo "Usage: $0 http://SERVER/media/test-video.mp4"
  exit 2
fi

if [ ! -x "$FFPLAY" ]; then
  echo "ffplay not found at $FFPLAY"
  exit 1
fi

echo "url=$URL" | tee "$LOG_FILE"
echo "proxy=${PROXY:-none}" | tee -a "$LOG_FILE"
echo "ffplay=$FFPLAY" | tee -a "$LOG_FILE"

if [ -n "$PROXY" ]; then
  unset ALL_PROXY all_proxy
  HTTP_PROXY="$PROXY" http_proxy="$PROXY" \
  HTTPS_PROXY="$PROXY" https_proxy="$PROXY" "$FFPLAY" \
    -hide_banner -autoexit -t 10 "$URL" >>"$LOG_FILE" 2>&1
else
  unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
  "$FFPLAY" -hide_banner -autoexit -t 10 "$URL" >>"$LOG_FILE" 2>&1
fi
