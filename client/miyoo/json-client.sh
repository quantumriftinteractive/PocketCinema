#!/bin/sh
set -eu

SERVER_BASE="${POCKETSTREMIO_SERVER:-}"
PROXY="${HTTP_PROXY:-}"
CURL="${CURL:-/mnt/SDCARD/.tmp_update/bin/curl}"
LOG_DIR="${POCKETSTREMIO_LOG_DIR:-/mnt/SDCARD/App/PocketStremio/client/logs}"
LOG_FILE="$LOG_DIR/json-client.log"

mkdir -p "$LOG_DIR"

if [ -z "$SERVER_BASE" ]; then
  echo "Set POCKETSTREMIO_SERVER to the PocketStremio server URL"
  exit 2
fi

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
  if [ -n "$PROXY" ]; then
    unset ALL_PROXY all_proxy
    HTTP_PROXY="$PROXY" http_proxy="$PROXY" \
    HTTPS_PROXY="$PROXY" https_proxy="$PROXY" \
      "$CURL" -fsS --max-time 20 "$SERVER_BASE$path"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    "$CURL" -fsS --max-time 20 "$SERVER_BASE$path"
  fi
}

log "PocketStremio Miyoo JSON client"
log "server=$SERVER_BASE"
log "proxy=${PROXY:-none}"

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
