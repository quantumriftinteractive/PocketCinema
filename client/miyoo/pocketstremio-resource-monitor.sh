#!/bin/sh

# App-local, bounded playback metrics. Receives the FFplay PID from the UI and
# never inspects unrelated processes.
BASE_DIR=/mnt/SDCARD/App/PocketStremio
LOG_FILE="${1:-$BASE_DIR/logs/playback-resources.log}"
PLAYER_PID="${2:-}"
PLAYER_KIND="${3:-unknown}"
MAX_SECONDS="${POCKETSTREMIO_MONITOR_SECONDS:-10800}"
INTERVAL_SECONDS="${POCKETSTREMIO_MONITOR_INTERVAL:-5}"
MAX_BYTES=262144

case "$PLAYER_PID" in ''|*[!0-9]*) exit 2 ;; esac
case "$MAX_SECONDS" in ''|*[!0-9]*) MAX_SECONDS=10800 ;; esac
case "$INTERVAL_SECONDS" in ''|*[!0-9]*) INTERVAL_SECONDS=5 ;; esac
[ "$INTERVAL_SECONDS" -gt 0 ] 2>/dev/null || INTERVAL_SECONDS=5

mkdir -p "$BASE_DIR/logs"
: >"$LOG_FILE"
end_time=$(( $(date +%s) + MAX_SECONDS ))
finished=0

finish() {
  [ "$finished" = "1" ] && exit 0
  finished=1
  printf 'monitor_end time=%s pid=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$PLAYER_PID" >>"$LOG_FILE"
  exit 0
}

trap finish INT TERM

printf 'monitor_start time=%s pid=%s player=%s interval_seconds=%s\n' \
  "$(date '+%Y-%m-%dT%H:%M:%S')" "$PLAYER_PID" "$PLAYER_KIND" "$INTERVAL_SECONDS" >>"$LOG_FILE"

while kill -0 "$PLAYER_PID" 2>/dev/null && [ "$(date +%s)" -lt "$end_time" ]; do
  if [ -r "/proc/$PLAYER_PID/status" ]; then
    printf 'sample time=%s pid=%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$PLAYER_PID" >>"$LOG_FILE"
    grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo >>"$LOG_FILE"
    grep -E '^(VmRSS|VmSwap|Threads):' "/proc/$PLAYER_PID/status" >>"$LOG_FILE"
  fi
  log_bytes=$(wc -c <"$LOG_FILE" 2>/dev/null | tr -d ' ')
  if [ "${log_bytes:-0}" -gt "$MAX_BYTES" ] 2>/dev/null; then
    tail -c 196608 "$LOG_FILE" >"$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
  fi
  sleep "$INTERVAL_SECONDS"
done

finish
