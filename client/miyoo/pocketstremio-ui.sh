#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketStremio
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/pocketstremio-ui.log"
SERVER_BASE="${POCKETSTREMIO_SERVER:-http://100.85.171.67:8755}"
PROXY="${POCKETSTREMIO_PROXY:-http://127.0.0.1:1055/}"
AUTO_FIRST="${POCKETSTREMIO_AUTO_FIRST:-0}"
DEFAULT_QUERY="${POCKETSTREMIO_DEFAULT_QUERY:-big buck bunny}"
CURL="$SYS_DIR/bin/curl"
JQ="$SYS_DIR/bin/jq"
KBINPUT="$SYS_DIR/bin/kbinput"
SHELLECT="$SYS_DIR/script/shellect.sh"
SDL_SELECTOR="$BASE_DIR/bin/pocketstremio-selector"
INFOPANEL="$SYS_DIR/bin/infoPanel"
FFPLAY="$SYS_DIR/bin/ffplay"
PADSP="$MIYOO_DIR/lib/libpadsp.so"

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

message() {
  title="$1"
  body="$2"
  "$INFOPANEL" --title "$title" --message "$body" --auto >/dev/null 2>&1 || true
}

api_get() {
  path="$1"
  (unset LD_PRELOAD; HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time 30 "$SERVER_BASE$path")
}

api_post_play() {
  type="$1"
  id="$2"
  stream_id="$3"
  body="{\"type\":\"$type\",\"id\":\"$id\",\"stream_id\":\"$stream_id\"}"
  (unset LD_PRELOAD; HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time 30 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/play")
}

play_url() {
  url="$1"
  log "ffplay launch url=$url"
  touch /tmp/stay_awake
  cd "$SYS_DIR" || return 1
  HOME=/mnt/SDCARD \
  HTTP_PROXY="$PROXY" \
  http_proxy="$PROXY" \
  LD_PRELOAD="$PADSP" \
  "$FFPLAY" -hide_banner -autoexit -vf "hflip,vflip" -i "$url" >> "$LOG_FILE" 2>&1
  rc=$?
  rm -f /tmp/stay_awake
  log "ffplay exit rc=$rc"
  return "$rc"
}

select_from_file() {
  title="$1"
  file="$2"
  log "select title=$title waiting for input debounce"
  sleep 1
  if [ -x "$SDL_SELECTOR" ]; then
    selected=$(POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" cut -f1 "$file" | POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" "$SDL_SELECTOR" "$title" "Up/Down move  A select  B back")
    rc=$?
    log "sdl selector rc=$rc"
  else
    selected=$(cut -f1 "$file" | "$SHELLECT" -t "$title" -b "A select, B/back exits")
    rc=$?
    log "shellect selector rc=$rc"
  fi
  log "select title=$title selected=$selected"
  printf '%s' "$selected"
}

read_keyboard() {
  initial="$1"
  title="$2"
  raw="$("$KBINPUT" -i "$initial" -t "$title")"
  printf '%s\n' "$raw" | awk '
    /^RESULT:/ {
      value = substr($0, index($0, ":") + 1)
      sub(/^[[:space:]]*/, "", value)
      if (value != "") {
        print value
        exit
      }
      found = 1
      next
    }
    found {
      if ($0 != "") {
        print
        exit
      }
    }
  '
}

ensure_ready() {
  if [ ! -S /tmp/pocketstremio-tailscale/tailscaled.sock ]; then
    log "tailscaled socket missing; starting"
    (unset LD_PRELOAD; "$BASE_DIR/tailscale/scripts/start.sh") >> "$LOG_FILE" 2>&1 || return 1
  fi
  api_get "/api/status" >/tmp/pocketstremio-status.json || return 1
  return 0
}

search_flow() {
  if [ "${POCKETSTREMIO_DRY_RUN:-0}" = "1" ]; then
    query="$DEFAULT_QUERY"
  else
    query="$(read_keyboard "$DEFAULT_QUERY" "PocketStremio Search")"
  fi
  [ -z "$query" ] && return 0
  log "search q=$query"

  encoded=$(printf '%s' "$query" | sed 's/ /%20/g')
  if ! api_get "/api/search?q=$encoded" >/tmp/pocketstremio-search.json; then
    log "search failed"
    message "PocketStremio" "Server unavailable"
    return 1
  fi

  count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-search.json)
  if [ "$count" = "0" ]; then
    message "PocketStremio" "No results"
    return 0
  fi

  "$JQ" -r '.items | to_entries[] | "\(.key + 1). \(.value.title) (\(.value.year // "????"))\t\(.value.type)\t\(.value.id)\t\(.value.title)\t\(.value.year // "")"' /tmp/pocketstremio-search.json >/tmp/pocketstremio-results.tsv
  if [ "${POCKETSTREMIO_DRY_RUN:-0}" = "1" ]; then
    head -n 5 /tmp/pocketstremio-results.tsv >> "$LOG_FILE"
    log "dry run stopping before interactive selection"
    return 0
  fi
  while :; do
    selected=$(select_from_file "Search: $query" /tmp/pocketstremio-results.tsv)
    if [ -z "$selected" ]; then
      log "result selection empty"
      if [ "$AUTO_FIRST" = "1" ]; then
        line=$(head -n 1 /tmp/pocketstremio-results.tsv)
        log "auto-selected first result"
      else
        return 10
      fi
    else
      line=$(grep -F "$selected	" /tmp/pocketstremio-results.tsv | head -n 1)
      if [ -z "$line" ]; then
        log "result selection did not match selected=$selected"
        message "PocketStremio" "Selection failed"
        return 1
      fi
    fi

    type=$(printf '%s' "$line" | cut -f2)
    id=$(printf '%s' "$line" | cut -f3)
    title=$(printf '%s' "$line" | cut -f4)
    year=$(printf '%s' "$line" | cut -f5)
    log "selected media type=$type id=$id title=$title year=$year"

    media_flow "$type" "$id" "$title" "$year"
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

media_flow() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"

  api_get "/api/meta/$type/$id" >/tmp/pocketstremio-meta.json || {
    message "PocketStremio" "Details unavailable"
    return 1
  }

  description=$("$JQ" -r '.description // ""' /tmp/pocketstremio-meta.json | cut -c 1-120)
  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      action="Play"
      log "auto-selected action=Play"
    else
      printf 'Play\nBack\n' >/tmp/pocketstremio-actions.tsv
      action=$(select_from_file "$title ($year)" /tmp/pocketstremio-actions.tsv)
      [ -z "$action" ] && return 10
      [ "$action" = "Back" ] && return 10
    fi

    streams_flow "$type" "$id"
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

streams_flow() {
  type="$1"
  id="$2"
  log "resolve streams type=$type id=$id"
  if ! api_get "/api/streams/$type/$id" >/tmp/pocketstremio-streams.json; then
    message "PocketStremio" "Stream lookup failed"
    return 1
  fi

  "$JQ" -r '.items | to_entries[] | select(.value.playable == true) | "\(.value.name)\t\(.value.id)\t\(.value.description // "")"' /tmp/pocketstremio-streams.json >/tmp/pocketstremio-streams.tsv
  if [ ! -s /tmp/pocketstremio-streams.tsv ]; then
    log "no playable streams"
    message "PocketStremio" "No playable streams"
    return 0
  fi

  if [ "$AUTO_FIRST" = "1" ]; then
    line=$(head -n 1 /tmp/pocketstremio-streams.tsv)
    selected=$(printf '%s' "$line" | cut -f1)
    log "auto-selected first stream selected=$selected"
  else
    selected=$(select_from_file "Select Stream" /tmp/pocketstremio-streams.tsv)
    [ -z "$selected" ] && return 10
    line=$(grep -F "$selected	" /tmp/pocketstremio-streams.tsv | head -n 1)
    if [ -z "$line" ]; then
      log "stream selection did not match selected=$selected"
      message "PocketStremio" "Selection failed"
      return 1
    fi
  fi
  stream_id=$(printf '%s' "$line" | cut -f2)
  log "selected stream_id=$stream_id name=$selected"

  if ! api_post_play "$type" "$id" "$stream_id" >/tmp/pocketstremio-play.json; then
    message "PocketStremio" "Playback setup failed"
    return 1
  fi
  play_url_value=$("$JQ" -r '.url // ""' /tmp/pocketstremio-play.json)
  if [ -z "$play_url_value" ]; then
    message "PocketStremio" "Playback URL missing"
    return 1
  fi
  log "playback url received"
  play_url "$play_url_value" || message "PocketStremio" "Playback failed"
}

cd "$SYS_DIR" || exit 1
log "PocketStremio UI start server=$SERVER_BASE proxy=$PROXY"
if ! ensure_ready; then
  log "server unavailable"
  message "PocketStremio" "Server unavailable"
  exit 1
fi

while :; do
  search_flow
  flow_rc=$?
  [ "$flow_rc" -eq 10 ] || break
done
log "PocketStremio UI exit"
sync
