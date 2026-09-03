#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketCinema
LOG_FILE="${1:-$BASE_DIR/logs/compatibility-resources.log}"
MAX_SECONDS="${POCKETCINEMA_MONITOR_SECONDS:-1200}"
PID_FILE=/tmp/pocketcinema-compat-monitor.pid
LOCK_DIR=/tmp/pocketcinema-compat-monitor.lock

cleanup() {
  rm -f "$PID_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

stop() {
  cleanup
  exit 0
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "compatibility resource monitor is already running" >&2
  exit 1
fi
trap cleanup EXIT
trap stop INT TERM
echo $$ >"$PID_FILE"
: >"$LOG_FILE"
end_time=$(($(date +%s) + MAX_SECONDS))
printf 'monitor_start %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" >>"$LOG_FILE"

while [ "$(date +%s)" -lt "$end_time" ]; do
  ffplay_process=$(ps | awk '
    /\/mnt\/SDCARD\/\.tmp_update\/bin\/ffplay/ && !/awk/ {
      print $1 " system"
      exit
    }
    /\/mnt\/SDCARD\/App\/PocketCinema\/experiments\/ffplay\/bin\/ffplay/ && !/awk/ {
      print $1 " candidate"
      exit
    }
  ')
  ffplay_pid=${ffplay_process%% *}
  ffplay_kind=${ffplay_process#* }
  if [ -n "$ffplay_pid" ] && [ -r "/proc/$ffplay_pid/status" ]; then
    printf 'sample %s pid=%s player=%s\n' \
      "$(date '+%Y-%m-%dT%H:%M:%S')" "$ffplay_pid" "$ffplay_kind" >>"$LOG_FILE"
    grep -E '^(MemTotal|MemFree|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo >>"$LOG_FILE"
    grep -E '^(VmRSS|VmSwap|Threads):' "/proc/$ffplay_pid/status" >>"$LOG_FILE"
  fi
  sleep 1
done

printf 'monitor_end %s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" >>"$LOG_FILE"
