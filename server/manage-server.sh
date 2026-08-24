#!/bin/sh

set -eu

usage() {
  printf '%s\n' \
    "Usage: $0 {start|stop|restart|status} [options]" \
    "  --host ADDRESS" \
    "  --port PORT" \
    "  --public-host ADDRESS" \
    "  --server-name NAME" \
    "  --network-name NAME" \
    "  --discovery-port PORT" \
    "  --disable-discovery" \
    "  --stremio-service-url URL" \
    "  --open-media-addon-port PORT" \
    "  --ffprobe PATH" \
    "  --ffmpeg PATH" \
    "  --local-media-root PATH" \
    "  --enable-field-test" \
    "  --enable-matroska-subtitles"
}

ACTION="${1:-status}"
case "$ACTION" in
  start|stop|restart|status) shift ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DATA_DIR="$SCRIPT_DIR/data"
PID_FILE="$DATA_DIR/server.pid"
STDOUT_LOG="$DATA_DIR/server.stdout.log"
STDERR_LOG="$DATA_DIR/server.stderr.log"
SERVER_SCRIPT="$SCRIPT_DIR/pocketstremio_server.py"

HOST_ADDRESS="${POCKETSTREMIO_HOST:-127.0.0.1}"
PORT="${POCKETSTREMIO_PORT:-8755}"
PUBLIC_HOST="${POCKETSTREMIO_PUBLIC_HOST:-}"
SERVER_NAME="${POCKETSTREMIO_SERVER_NAME:-$(hostname)}"
NETWORK_NAME="${POCKETSTREMIO_NETWORK_NAME:-Network}"
DISCOVERY_PORT="${POCKETSTREMIO_DISCOVERY_PORT:-8754}"
DISABLE_DISCOVERY="${POCKETSTREMIO_DISABLE_DISCOVERY:-0}"
STREMIO_SERVICE_URL="${POCKETSTREMIO_STREMIO_SERVICE_URL:-http://127.0.0.1:11470}"
OPEN_MEDIA_ADDON_PORT="${POCKETSTREMIO_OPEN_MEDIA_ADDON_PORT:-8756}"
FFPROBE_PATH="${POCKETSTREMIO_FFPROBE:-}"
FFMPEG_PATH="${POCKETSTREMIO_FFMPEG:-}"
LOCAL_MEDIA_ROOT="${POCKETSTREMIO_LOCAL_MEDIA_ROOT:-}"
ENABLE_FIELD_TEST="${POCKETSTREMIO_ENABLE_FIELD_TEST:-0}"
ENABLE_MATROSKA_SUBTITLES="${POCKETSTREMIO_ENABLE_MATROSKA_SUBTITLES:-0}"
PYTHON="${POCKETSTREMIO_PYTHON:-}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host) HOST_ADDRESS="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --public-host) PUBLIC_HOST="$2"; shift 2 ;;
    --server-name) SERVER_NAME="$2"; shift 2 ;;
    --network-name) NETWORK_NAME="$2"; shift 2 ;;
    --discovery-port) DISCOVERY_PORT="$2"; shift 2 ;;
    --disable-discovery) DISABLE_DISCOVERY=1; shift ;;
    --stremio-service-url) STREMIO_SERVICE_URL="$2"; shift 2 ;;
    --open-media-addon-port) OPEN_MEDIA_ADDON_PORT="$2"; shift 2 ;;
    --ffprobe) FFPROBE_PATH="$2"; shift 2 ;;
    --ffmpeg) FFMPEG_PATH="$2"; shift 2 ;;
    --local-media-root) LOCAL_MEDIA_ROOT="$2"; shift 2 ;;
    --enable-field-test) ENABLE_FIELD_TEST=1; shift ;;
    --enable-matroska-subtitles) ENABLE_MATROSKA_SUBTITLES=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$PORT:$OPEN_MEDIA_ADDON_PORT:$DISCOVERY_PORT" in
  *[!0-9:]*|:*) printf '%s\n' "Ports must be positive integers" >&2; exit 2 ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ] \
  || [ "$OPEN_MEDIA_ADDON_PORT" -lt 1 ] || [ "$OPEN_MEDIA_ADDON_PORT" -gt 65535 ]; then
  printf '%s\n' "Ports must be between 1 and 65535" >&2
  exit 2
fi
if [ "$DISCOVERY_PORT" -lt 1 ] || [ "$DISCOVERY_PORT" -gt 65535 ]; then
  printf '%s\n' "Discovery port must be between 1 and 65535" >&2
  exit 2
fi
case "$ENABLE_FIELD_TEST" in
  0|1) ;;
  *) printf '%s\n' "POCKETSTREMIO_ENABLE_FIELD_TEST must be 0 or 1" >&2; exit 2 ;;
esac
case "$ENABLE_MATROSKA_SUBTITLES" in
  0|1) ;;
  *) printf '%s\n' "POCKETSTREMIO_ENABLE_MATROSKA_SUBTITLES must be 0 or 1" >&2; exit 2 ;;
esac
case "$DISABLE_DISCOVERY" in
  0|1) ;;
  *) printf '%s\n' "POCKETSTREMIO_DISABLE_DISCOVERY must be 0 or 1" >&2; exit 2 ;;
esac

[ -n "$PUBLIC_HOST" ] || PUBLIC_HOST="$HOST_ADDRESS"
[ -n "$PYTHON" ] || PYTHON=$(command -v python3 || true)
[ -n "$FFPROBE_PATH" ] || FFPROBE_PATH=$(command -v ffprobe || true)
[ -n "$FFMPEG_PATH" ] || FFMPEG_PATH=$(command -v ffmpeg || true)
[ -n "$PYTHON" ] || { printf '%s\n' "python3 is required" >&2; exit 1; }
[ -n "$FFPROBE_PATH" ] || { printf '%s\n' "ffprobe is required" >&2; exit 1; }
[ -n "$FFMPEG_PATH" ] || { printf '%s\n' "ffmpeg is required" >&2; exit 1; }

health_url="http://$HOST_ADDRESS:$PORT/api/status"

managed_pid() {
  [ -f "$PID_FILE" ] || return 1
  IFS= read -r saved_pid <"$PID_FILE" || return 1
  case "$saved_pid" in
    ''|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$saved_pid" 2>/dev/null || return 1
  ps -p "$saved_pid" -o command= 2>/dev/null | grep -F 'pocketstremio_server.py' >/dev/null \
    || return 1
  printf '%s\n' "$saved_pid"
}

clear_stale_pid() {
  if [ -f "$PID_FILE" ] && ! managed_pid >/dev/null 2>&1; then
    rm -f "$PID_FILE"
  fi
}

wait_for_health() {
  health_attempt=0
  while [ "$health_attempt" -lt 40 ]; do
    if curl -fsS --max-time 2 "$health_url" >/dev/null 2>&1; then
      return 0
    fi
    health_attempt=$((health_attempt + 1))
    sleep 0.25
  done
  return 1
}

start_server() {
  clear_stale_pid
  if managed_pid >/dev/null 2>&1; then
    printf '%s\n' "PSS is already running" >&2
    return 1
  fi
  if curl -fsS --max-time 2 "$health_url" >/dev/null 2>&1; then
    printf '%s\n' "An unmanaged PSS already answers at $health_url" >&2
    return 1
  fi

  mkdir -p "$DATA_DIR"
  umask 077
  set -- -u "$SERVER_SCRIPT" \
    --host "$HOST_ADDRESS" \
    --port "$PORT" \
    --public-host "$PUBLIC_HOST" \
    --server-name "$SERVER_NAME" \
    --network-name "$NETWORK_NAME" \
    --discovery-port "$DISCOVERY_PORT" \
    --stremio-service-url "$STREMIO_SERVICE_URL" \
    --open-media-addon-port "$OPEN_MEDIA_ADDON_PORT" \
    --ffprobe "$FFPROBE_PATH" \
    --ffmpeg "$FFMPEG_PATH"
  if [ -n "$LOCAL_MEDIA_ROOT" ]; then
    set -- "$@" --stremio-local-media-root "$LOCAL_MEDIA_ROOT"
  fi
  if [ "$ENABLE_FIELD_TEST" = "1" ]; then
    set -- "$@" --enable-field-test
  fi
  if [ "$ENABLE_MATROSKA_SUBTITLES" = "1" ]; then
    set -- "$@" --enable-matroska-subtitles
  fi
  if [ "$DISABLE_DISCOVERY" = "1" ]; then
    set -- "$@" --disable-discovery
  fi

  nohup "$PYTHON" "$@" >"$STDOUT_LOG" 2>"$STDERR_LOG" </dev/null &
  server_pid=$!
  printf '%s\n' "$server_pid" >"$PID_FILE"
  if ! wait_for_health; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    printf '%s\n' "PSS did not become healthy at $health_url" >&2
    return 1
  fi
  printf 'PSS started: PID %s at %s\n' "$server_pid" "$health_url"
}

stop_server() {
  clear_stale_pid
  server_pid=$(managed_pid 2>/dev/null || true)
  if [ -z "$server_pid" ]; then
    printf '%s\n' "PSS is not running"
    return 0
  fi
  kill "$server_pid"
  stop_attempt=0
  while kill -0 "$server_pid" 2>/dev/null && [ "$stop_attempt" -lt 10 ]; do
    stop_attempt=$((stop_attempt + 1))
    sleep 1
  done
  if kill -0 "$server_pid" 2>/dev/null; then
    kill -KILL "$server_pid"
  fi
  rm -f "$PID_FILE"
  printf 'PSS stopped: PID %s\n' "$server_pid"
}

status_server() {
  clear_stale_pid
  server_pid=$(managed_pid 2>/dev/null || true)
  if [ -z "$server_pid" ]; then
    printf '%s\n' "PSS is not running"
    return 1
  fi
  if ! wait_for_health; then
    printf 'PSS process %s is running but health failed at %s\n' "$server_pid" "$health_url" >&2
    return 1
  fi
  printf 'PSS running: PID %s at %s\n' "$server_pid" "$health_url"
}

cd "$ROOT_DIR"
case "$ACTION" in
  start) start_server ;;
  stop) stop_server ;;
  restart) stop_server; start_server ;;
  status) status_server ;;
esac
