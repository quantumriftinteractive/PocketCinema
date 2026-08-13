#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketStremio
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/app-playback.log"
RESOURCE_LOG="$LOG_DIR/app-resource.log"

SERVER_BASE="${POCKETSTREMIO_SERVER:-}"
VIDEO_URL="${POCKETSTREMIO_VIDEO_URL:-}"
[ -n "$VIDEO_URL" ] || [ -z "$SERVER_BASE" ] || VIDEO_URL="$SERVER_BASE/media/test-video.mp4"
PROXY="${POCKETSTREMIO_PROXY:-}"
FFPLAY="${POCKETSTREMIO_FFPLAY:-$SYS_DIR/bin/ffplay}"
PADSP="$MIYOO_DIR/lib/libpadsp.so"
CURL="$SYS_DIR/bin/curl"

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"
: > "$RESOURCE_LOG"

if [ -z "$VIDEO_URL" ]; then
  echo "Set POCKETSTREMIO_SERVER or POCKETSTREMIO_VIDEO_URL" >>"$LOG_FILE"
  exit 2
fi

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

curl_request() (
  unset LD_PRELOAD
  if [ -n "$PROXY" ]; then
    unset ALL_PROXY all_proxy
    HTTP_PROXY="$PROXY" http_proxy="$PROXY" \
    HTTPS_PROXY="$PROXY" https_proxy="$PROXY" "$CURL" "$@"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    "$CURL" "$@"
  fi
)

run_ffplay() (
  if [ -n "$PROXY" ]; then
    unset ALL_PROXY all_proxy
    HOME=/mnt/SDCARD HTTP_PROXY="$PROXY" http_proxy="$PROXY" \
    HTTPS_PROXY="$PROXY" https_proxy="$PROXY" LD_PRELOAD="$PADSP" \
      "$FFPLAY" -hide_banner -autoexit -vf "hflip,vflip" -i "$VIDEO_URL"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    HOME=/mnt/SDCARD LD_PRELOAD="$PADSP" \
      "$FFPLAY" -hide_banner -autoexit -vf "hflip,vflip" -i "$VIDEO_URL"
  fi
)

measure_once() {
  label="$1"
  {
    echo "== $label $(date '+%Y-%m-%d %H:%M:%S') =="
    free 2>/dev/null || cat /proc/meminfo
    grep -E 'Swap(Total|Free|Cached)' /proc/meminfo 2>/dev/null || true
    for p in $(ps | awk '/[t]ailscaled/ {print $1} /\/mnt\/SDCARD\/\.tmp_update\/bin\/ffplay/ {print $1}'); do
      echo "-- /proc/$p/status --"
      grep -E '^(Name|State|VmSize|VmRSS|VmData|VmStk|VmExe|VmSwap|Threads):' "/proc/$p/status" 2>/dev/null || true
    done
  } >> "$RESOURCE_LOG"
}

monitor_resources() {
  seen_ffplay=0
  misses=0
  while true; do
    measure_once "during-playback"
    if ps | grep '/mnt/SDCARD/.tmp_update/bin/ffplay' | grep -v grep >/dev/null 2>&1; then
      seen_ffplay=1
      misses=0
    elif [ "$seen_ffplay" = "1" ]; then
      break
    else
      misses=$((misses + 1))
      [ "$misses" -ge 5 ] && break
    fi
    sleep 2
  done
}

log "PocketStremio OnionOS playback launcher"
log "server=$SERVER_BASE"
log "video=$VIDEO_URL"
log "proxy=${PROXY:-none}"
log "ffplay=$FFPLAY"

measure_once "before"

if [ ! -x "$FFPLAY" ]; then
  log "ERROR ffplay not executable: $FFPLAY"
  exit 1
fi

if [ ! -x "$CURL" ]; then
  log "ERROR curl not executable: $CURL"
  exit 1
fi

if ! curl_request -fsS -o /tmp/pocketstremio-video-check.mp4 -r 0-4095 --max-time 20 "$VIDEO_URL" >> "$LOG_FILE" 2>&1; then
  log "ERROR video check failed"
  exit 1
fi

log "video check ok"

if [ "${POCKETSTREMIO_SKIP_PLAYBACK:-0}" = "1" ]; then
  log "skip playback requested"
  measure_once "after-skip"
  exit 0
fi

touch /tmp/stay_awake

monitor_resources &
MONITOR_PID=$!

cd "$SYS_DIR" || exit 1
run_ffplay >> "$LOG_FILE" 2>&1
RETVAL=$?

kill "$MONITOR_PID" 2>/dev/null || true
rm -f /tmp/stay_awake
measure_once "after"
log "ffplay exited rc=$RETVAL"
sync

exit "$RETVAL"
