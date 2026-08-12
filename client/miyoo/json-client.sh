#!/bin/sh
set -eu

SERVER_BASE="${POCKETSTREMIO_SERVER:-http://100.85.171.67:8755}"
PROXY="${HTTP_PROXY:-http://127.0.0.1:1055/}"
CURL="${CURL:-/mnt/SDCARD/.tmp_update/bin/curl}"
LOG_DIR="${POCKETSTREMIO_LOG_DIR:-/mnt/SDCARD/App/PocketStremio/client/logs}"
LOG_FILE="$LOG_DIR/json-client.log"

mkdir -p "$LOG_DIR"

if [ ! -x "$CURL" ]; then
  echo "curl not found at $CURL"
  exit 1
fi

log() {
  printf '%s\n' "$*" | tee -a "$LOG_FILE"
}

json_string() {
  key="$1"
  sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1
}

json_number() {
  key="$1"
  sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' | head -n 1
}

fetch() {
  path="$1"
  HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time 20 "$SERVER_BASE$path"
}

log "PocketStremio Miyoo JSON client"
log "server=$SERVER_BASE"
log "proxy=$PROXY"

STATUS_JSON="$(fetch /api/status)"
STATUS="$(printf '%s\n' "$STATUS_JSON" | json_string status)"
SERVICE="$(printf '%s\n' "$STATUS_JSON" | json_string service)"
MESSAGE="$(printf '%s\n' "$STATUS_JSON" | json_string message)"

log "status.status=$STATUS"
log "status.service=$SERVICE"
log "status.message=$MESSAGE"

SEARCH_JSON="$(fetch '/api/search?q=alien')"
QUERY="$(printf '%s\n' "$SEARCH_JSON" | json_string query)"
COUNT="$(printf '%s\n' "$SEARCH_JSON" | json_number count)"

log "search.query=$QUERY"
log "search.count=$COUNT"
log "search.results:"
printf '%s\n' "$SEARCH_JSON" |
  sed -n 's/.*"title"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/  title=\1/p' |
  tee -a "$LOG_FILE"

log "json-client=ok"

if [ "${POCKETSTREMIO_HOLD_SECONDS:-0}" != "0" ]; then
  log "hold_seconds=$POCKETSTREMIO_HOLD_SECONDS"
  sleep "$POCKETSTREMIO_HOLD_SECONDS"
fi
