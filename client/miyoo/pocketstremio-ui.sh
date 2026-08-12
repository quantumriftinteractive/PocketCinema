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

cleanup() {
  rm -f /tmp/stay_awake /tmp/pocketstremio-subtitle.srt
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

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
  timeout="${2:-30}"
  (unset LD_PRELOAD; HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time "$timeout" "$SERVER_BASE$path")
}

api_post_play() {
  type="$1"
  id="$2"
  stream_id="$3"
  body="{\"type\":\"$type\",\"id\":\"$id\",\"stream_id\":\"$stream_id\"}"
  (unset LD_PRELOAD; HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time 30 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/play")
}

api_post_progress() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  position="$5"
  duration="$6"
  completed="$7"
  body=$("$JQ" -n \
    --arg type "$type" \
    --arg id "$id" \
    --arg title "$title" \
    --arg year "$year" \
    --argjson position "$position" \
    --argjson duration "$duration" \
    --argjson completed "$completed" \
    '{type:$type,id:$id,title:$title,year:$year,position_seconds:$position,duration_seconds:$duration,completed:$completed}')
  (unset LD_PRELOAD; HTTP_PROXY="$PROXY" http_proxy="$PROXY" "$CURL" -fsS --max-time 30 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/progress")
}

ffplay_has_subtitles() {
  (unset LD_PRELOAD; "$FFPLAY" -hide_banner -filters 2>/dev/null) | grep -q '[[:space:]]subtitles[[:space:]]'
}

play_url() {
  url="$1"
  resume_seconds="${2:-0}"
  subtitle_file="${3:-}"
  PLAYBACK_RC=1
  PLAYBACK_ELAPSED=0
  log "ffplay launch url=$url resume_seconds=$resume_seconds subtitles=${subtitle_file:-none}"
  touch /tmp/stay_awake
  cd "$SYS_DIR" || return 1
  playback_started=$(date +%s)
  if [ -n "$subtitle_file" ]; then
    HOME=/mnt/SDCARD \
    HTTP_PROXY="$PROXY" \
    http_proxy="$PROXY" \
    LD_PRELOAD="$PADSP" \
    "$FFPLAY" -hide_banner -autoexit -ss "$resume_seconds" -vf "subtitles=$subtitle_file,hflip,vflip" -i "$url" >> "$LOG_FILE" 2>&1
  else
    HOME=/mnt/SDCARD \
    HTTP_PROXY="$PROXY" \
    http_proxy="$PROXY" \
    LD_PRELOAD="$PADSP" \
    "$FFPLAY" -hide_banner -autoexit -ss "$resume_seconds" -vf "hflip,vflip" -i "$url" >> "$LOG_FILE" 2>&1
  fi
  PLAYBACK_RC=$?
  playback_ended=$(date +%s)
  PLAYBACK_ELAPSED=$((playback_ended - playback_started))
  rm -f /tmp/stay_awake
  [ -n "$subtitle_file" ] && rm -f "$subtitle_file"
  log "ffplay exit rc=$PLAYBACK_RC elapsed_seconds=$PLAYBACK_ELAPSED"
  return "$PLAYBACK_RC"
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
  started=0
  if [ ! -S /tmp/pocketstremio-tailscale/tailscaled.sock ]; then
    log "tailscaled socket missing; starting"
    (unset LD_PRELOAD; "$BASE_DIR/tailscale/scripts/start.sh") >> "$LOG_FILE" 2>&1 || return 1
    started=1
  fi
  [ "$started" = "1" ] && sleep 6

  attempts=0
  while [ "$attempts" -lt 6 ]; do
    if api_get "/api/status" 5 >/tmp/pocketstremio-status.json; then
      log "server ready after attempts=$((attempts + 1))"
      return 0
    fi
    attempts=$((attempts + 1))
    log "server readiness attempt=$attempts failed"
    sleep 2
  done
  return 1
}

home_flow() {
  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      action="Search"
      log "auto-selected home action=Search"
    else
      printf 'Search\nContinue Watching\nExit\n' >/tmp/pocketstremio-home.tsv
      action=$(select_from_file "PocketStremio" /tmp/pocketstremio-home.tsv)
    fi
    case "$action" in
      Search)
        search_flow
        ;;
      "Continue Watching")
        continue_watching_flow
        ;;
      *)
        return 0
        ;;
    esac
    [ "$AUTO_FIRST" = "1" ] && return 0
  done
}

continue_watching_flow() {
  if ! api_get "/api/continue-watching" >/tmp/pocketstremio-continue.json; then
    message "PocketStremio" "Continue Watching unavailable"
    return 1
  fi
  count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-continue.json)
  if [ "$count" = "0" ]; then
    message "PocketStremio" "Nothing to continue"
    return 0
  fi

  "$JQ" -r '.items[] | "\(.title) (\(.year // "????")) - \((.position_seconds / 60) | floor)m \((.position_seconds % 60) | floor)s\t\(.type)\t\(.id)\t\(.title)\t\(.year // "")\t\(.position_seconds // 0)"' /tmp/pocketstremio-continue.json >/tmp/pocketstremio-continue.tsv
  selected=$(select_from_file "Continue Watching" /tmp/pocketstremio-continue.tsv)
  [ -z "$selected" ] && return 0
  line=$(grep -F "$selected	" /tmp/pocketstremio-continue.tsv | head -n 1)
  if [ -z "$line" ]; then
    log "continue selection did not match selected=$selected"
    message "PocketStremio" "Selection failed"
    return 1
  fi
  type=$(printf '%s' "$line" | cut -f2)
  id=$(printf '%s' "$line" | cut -f3)
  title=$(printf '%s' "$line" | cut -f4)
  year=$(printf '%s' "$line" | cut -f5)
  resume_seconds=$(printf '%s' "$line" | cut -f6)
  log "continue selected type=$type id=$id position_seconds=$resume_seconds"
  media_flow "$type" "$id" "$title" "$year" "$resume_seconds"
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

    media_flow "$type" "$id" "$title" "$year" 0
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

media_flow() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  saved_position="${5:-0}"

  api_get "/api/meta/$type/$id" >/tmp/pocketstremio-meta.json || {
    message "PocketStremio" "Details unavailable"
    return 1
  }

  description=$("$JQ" -r '.description // ""' /tmp/pocketstremio-meta.json | cut -c 1-120)
  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      action="start"
      log "auto-selected action=start"
    else
      if [ "$saved_position" -gt 0 ] 2>/dev/null; then
        resume_minutes=$((saved_position / 60))
        resume_remainder=$((saved_position % 60))
        printf 'Resume at %sm %ss\tresume\nPlay from Start\tstart\nBack\tback\n' "$resume_minutes" "$resume_remainder" >/tmp/pocketstremio-actions.tsv
      else
        printf 'Play\tstart\nBack\tback\n' >/tmp/pocketstremio-actions.tsv
      fi
      action=$(select_from_file "$title ($year)" /tmp/pocketstremio-actions.tsv)
      [ -z "$action" ] && return 10
      action_line=$(grep -F "$action	" /tmp/pocketstremio-actions.tsv | head -n 1)
      action=$(printf '%s' "$action_line" | cut -f2)
      [ "$action" = "back" ] && return 10
    fi

    if [ "$action" = "resume" ]; then
      play_position="$saved_position"
    else
      play_position=0
    fi
    streams_flow "$type" "$id" "$title" "$year" "$play_position"
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

streams_flow() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  resume_seconds="${5:-0}"
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

  while :; do
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

    subtitle_id=$(select_subtitle "$type" "$id" "$stream_id")
    [ "$subtitle_id" = "back" ] && continue
    break
  done

  if ! api_post_play "$type" "$id" "$stream_id" >/tmp/pocketstremio-play.json; then
    message "PocketStremio" "Playback setup failed"
    return 1
  fi
  play_url_value=$("$JQ" -r '.url // ""' /tmp/pocketstremio-play.json)
  if [ -z "$play_url_value" ]; then
    message "PocketStremio" "Playback URL missing"
    return 1
  fi
  duration_seconds=$("$JQ" -r '(.duration_seconds // 0) | floor' /tmp/pocketstremio-play.json)

  subtitle_file=""
  if [ -n "$subtitle_id" ] && [ "$subtitle_id" != "none" ]; then
    subtitle_file=/tmp/pocketstremio-subtitle.srt
    rm -f "$subtitle_file"
    if ! api_get "/subtitle/$subtitle_id" >"$subtitle_file"; then
      rm -f "$subtitle_file"
      message "PocketStremio" "Subtitle download failed"
      return 1
    fi
    log "subtitle downloaded id=$subtitle_id"
  fi

  log "playback url received"
  if ! play_url "$play_url_value" "$resume_seconds" "$subtitle_file"; then
    message "PocketStremio" "Playback failed"
  fi

  new_position=$((resume_seconds + PLAYBACK_ELAPSED))
  completed=false
  if [ "$duration_seconds" -gt 0 ] 2>/dev/null && [ $((new_position * 10)) -ge $((duration_seconds * 9)) ]; then
    completed=true
  fi
  if [ "$PLAYBACK_RC" -eq 0 ] 2>/dev/null && [ "$PLAYBACK_ELAPSED" -gt 0 ] 2>/dev/null; then
    if api_post_progress "$type" "$id" "$title" "$year" "$new_position" "$duration_seconds" "$completed" >/tmp/pocketstremio-progress.json; then
      log "progress saved position_seconds=$new_position duration_seconds=$duration_seconds completed=$completed"
    else
      log "progress save failed"
    fi
  fi
}

select_subtitle() {
  type="$1"
  id="$2"
  stream_id="$3"

  if ! ffplay_has_subtitles; then
    log "ffplay subtitles filter unavailable"
    printf '%s' "none"
    return 0
  fi
  if ! api_get "/api/subtitles/$type/$id?stream_id=$stream_id" >/tmp/pocketstremio-subtitles.json; then
    log "subtitle lookup failed"
    printf '%s' "none"
    return 0
  fi
  count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-subtitles.json)
  if [ "$count" = "0" ] || [ "$AUTO_FIRST" = "1" ]; then
    [ "$AUTO_FIRST" = "1" ] && log "auto-selected subtitles=none"
    printf '%s' "none"
    return 0
  fi

  printf 'No subtitles\tnone\n' >/tmp/pocketstremio-subtitles.tsv
  "$JQ" -r '.items[] | "\(.name) [\(.lang)]\t\(.id)"' /tmp/pocketstremio-subtitles.json >>/tmp/pocketstremio-subtitles.tsv
  selected=$(select_from_file "Select Subtitles" /tmp/pocketstremio-subtitles.tsv)
  if [ -z "$selected" ]; then
    printf '%s' "back"
    return 0
  fi
  line=$(grep -F "$selected	" /tmp/pocketstremio-subtitles.tsv | head -n 1)
  subtitle_id=$(printf '%s' "$line" | cut -f2)
  log "selected subtitle_id=$subtitle_id name=$selected"
  printf '%s' "$subtitle_id"
}

cd "$SYS_DIR" || exit 1
log "PocketStremio UI start server=$SERVER_BASE proxy=$PROXY"
if ! ensure_ready; then
  log "server unavailable"
  message "PocketStremio" "Server unavailable"
  exit 1
fi

home_flow
log "PocketStremio UI exit"
sync
