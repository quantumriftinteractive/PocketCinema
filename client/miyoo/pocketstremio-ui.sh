#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketStremio
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/pocketstremio-ui.log"
CONFIG_FILE="$BASE_DIR/config/pocketstremio.conf"
HTTP_ERROR_FILE=/tmp/pocketstremio-http-error
SERVER_BASE="${POCKETSTREMIO_SERVER:-}"
PROXY="${POCKETSTREMIO_PROXY:-}"
AUTO_FIRST="${POCKETSTREMIO_AUTO_FIRST:-}"
DEFAULT_QUERY="${POCKETSTREMIO_DEFAULT_QUERY:-}"
CURL="$SYS_DIR/bin/curl"
JQ="$SYS_DIR/bin/jq"
KBINPUT="$SYS_DIR/bin/kbinput"
SHELLECT="$SYS_DIR/script/shellect.sh"
SDL_SELECTOR="$BASE_DIR/bin/pocketstremio-selector"
PAUSE_MONITOR="$BASE_DIR/bin/pocketstremio-pause-monitor"
INFOPANEL="$SYS_DIR/bin/infoPanel"
FFPLAY="$SYS_DIR/bin/ffplay"
PADSP="$MIYOO_DIR/lib/libpadsp.so"
LOADING_PID=""
PAUSE_MONITOR_PID=""
READY_ERROR=""
CONFIG_ERROR=""

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"

load_config() {
  [ -f "$CONFIG_FILE" ] || return 0
  while IFS='=' read -r config_key config_value; do
    config_value=$(printf '%s' "$config_value" | tr -d '\r')
    case "$config_key" in
      ''|'#'*) continue ;;
      SERVER_BASE) [ -n "$SERVER_BASE" ] || SERVER_BASE="$config_value" ;;
      PROXY) [ -n "$PROXY" ] || PROXY="$config_value" ;;
      DEFAULT_QUERY) [ -n "$DEFAULT_QUERY" ] || DEFAULT_QUERY="$config_value" ;;
      AUTO_FIRST) [ -n "$AUTO_FIRST" ] || AUTO_FIRST="$config_value" ;;
      *) CONFIG_ERROR="Unknown setting: $config_key" ;;
    esac
  done <"$CONFIG_FILE"
}

load_config
AUTO_FIRST="${AUTO_FIRST:-0}"
DEFAULT_QUERY="${DEFAULT_QUERY:-big buck bunny}"
case "$SERVER_BASE" in
  http://*|https://*) ;;
  '') CONFIG_ERROR="SERVER_BASE is required" ;;
  *) CONFIG_ERROR="SERVER_BASE must be an HTTP URL" ;;
esac
case "$PROXY" in
  ''|http://*) ;;
  *) CONFIG_ERROR="PROXY must be empty or an HTTP URL" ;;
esac
case "$AUTO_FIRST" in
  0|1) ;;
  *) CONFIG_ERROR="AUTO_FIRST must be 0 or 1" ;;
esac

cleanup() {
  stop_loading
  if [ -n "$PAUSE_MONITOR_PID" ] && kill -0 "$PAUSE_MONITOR_PID" 2>/dev/null; then
    kill "$PAUSE_MONITOR_PID" 2>/dev/null || true
    wait "$PAUSE_MONITOR_PID" 2>/dev/null || true
  fi
  rm -f /tmp/stay_awake /tmp/pocketstremio-subtitle.srt \
    /tmp/pocketstremio-ffplay.log /tmp/pocketstremio-paused-seconds \
    /tmp/pocketstremio-account.json /tmp/pocketstremio-account-link.json \
    /tmp/pocketstremio-addons.json /tmp/pocketstremio-live-tv.json \
    /tmp/pocketstremio-live-tv.tsv \
    "$HTTP_ERROR_FILE"
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
  if [ "${POCKETSTREMIO_HEADLESS:-0}" = "1" ]; then
    log "message title=$title body=$body"
    return 0
  fi
  "$INFOPANEL" --title "$title" --message "$body" --auto >/dev/null 2>&1 || true
}

start_loading() {
  loading_title="$1"
  loading_message="$2"
  stop_loading
  rm -f /tmp/dismiss_info_panel
  "$INFOPANEL" --title "$loading_title" --message "$loading_message" --persistent >/dev/null 2>&1 &
  LOADING_PID=$!
  log "loading start pid=$LOADING_PID message=$loading_message"
}

stop_loading() {
  [ -n "$LOADING_PID" ] || return 0
  if kill -0 "$LOADING_PID" 2>/dev/null; then
    touch /tmp/dismiss_info_panel
    wait "$LOADING_PID" 2>/dev/null || true
  fi
  log "loading stop pid=$LOADING_PID"
  LOADING_PID=""
  rm -f /tmp/dismiss_info_panel
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

api_get() {
  path="$1"
  timeout="${2:-30}"
  rm -f "$HTTP_ERROR_FILE"
  curl_request -fsS --max-time "$timeout" "$SERVER_BASE$path" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "api get failed path=$path rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
}

api_post_empty() {
  path="$1"
  timeout="${2:-30}"
  rm -f "$HTTP_ERROR_FILE"
  curl_request -fsS --max-time "$timeout" -H 'Content-Type: application/json' \
    -d '{}' "$SERVER_BASE$path" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "api post failed path=$path rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
}

api_post_play() {
  type="$1"
  id="$2"
  stream_id="$3"
  body=$("$JQ" -nc \
    --arg type "$type" \
    --arg id "$id" \
    --arg stream_id "$stream_id" \
    '{type:$type,id:$id,stream_id:$stream_id}')
  rm -f "$HTTP_ERROR_FILE"
  curl_request -sS --max-time 60 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/play" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "api post play failed rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
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
  rm -f "$HTTP_ERROR_FILE"
  curl_request -fsS --max-time 30 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/progress" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "api post progress failed rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
}

ffplay_has_subtitles() {
  (unset LD_PRELOAD; "$FFPLAY" -hide_banner -filters 2>/dev/null) | grep -q '[[:space:]]subtitles[[:space:]]'
}

run_ffplay() (
  video_filter="$1"
  url="$2"
  resume_seconds="$3"
  if [ -n "$PROXY" ]; then
    unset ALL_PROXY all_proxy
    HOME=/mnt/SDCARD \
    HTTP_PROXY="$PROXY" \
    http_proxy="$PROXY" \
    HTTPS_PROXY="$PROXY" \
    https_proxy="$PROXY" \
    LD_PRELOAD="$PADSP" \
    "$FFPLAY" -hide_banner -stats -autoexit -ss "$resume_seconds" -vf "$video_filter" -i "$url"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    HOME=/mnt/SDCARD \
    LD_PRELOAD="$PADSP" \
    "$FFPLAY" -hide_banner -stats -autoexit -ss "$resume_seconds" -vf "$video_filter" -i "$url"
  fi
)

play_url() {
  url="$1"
  resume_seconds="${2:-0}"
  subtitle_file="${3:-}"
  PLAYBACK_RC=1
  PLAYBACK_ELAPSED=0
  PLAYBACK_STARTUP=0
  PLAYBACK_PAUSED=0
  PAUSE_TRACKING_VALID=0
  PLAYBACK_VALID=0
  playback_visible_started=0
  ffplay_log=/tmp/pocketstremio-ffplay.log
  pause_result=/tmp/pocketstremio-paused-seconds
  PAUSE_MONITOR_PID=""
  rm -f "$ffplay_log" "$pause_result"
  log "ffplay launch url=$url resume_seconds=$resume_seconds subtitles=${subtitle_file:-none}"
  touch /tmp/stay_awake
  cd "$SYS_DIR" || return 1
  playback_started=$(date +%s)
  video_filter="hflip,vflip"
  [ -n "$subtitle_file" ] && video_filter="subtitles=$subtitle_file,hflip,vflip"
  run_ffplay "$video_filter" "$url" "$resume_seconds" >"$ffplay_log" 2>&1 &
  ffplay_pid=$!
  while kill -0 "$ffplay_pid" 2>/dev/null; do
    if grep -q 'SDL_SetVideoMode' "$ffplay_log"; then
      playback_visible_started=$(date +%s)
      PLAYBACK_STARTUP=$((playback_visible_started - playback_started))
      log "ffplay video ready startup_seconds=$PLAYBACK_STARTUP"
      if [ -x "$PAUSE_MONITOR" ]; then
        "$PAUSE_MONITOR" "$pause_result" >>"$LOG_FILE" 2>&1 &
        PAUSE_MONITOR_PID=$!
        log "pause monitor start pid=$PAUSE_MONITOR_PID"
      else
        log "pause monitor unavailable"
      fi
      break
    fi
    sleep 1
  done
  wait "$ffplay_pid"
  PLAYBACK_RC=$?
  if [ -n "$PAUSE_MONITOR_PID" ]; then
    if kill -0 "$PAUSE_MONITOR_PID" 2>/dev/null; then
      kill "$PAUSE_MONITOR_PID" 2>/dev/null || true
    fi
    wait "$PAUSE_MONITOR_PID" 2>/dev/null
    pause_monitor_rc=$?
    PAUSE_MONITOR_PID=""
    if [ "$pause_monitor_rc" -eq 0 ] && [ -f "$pause_result" ]; then
      PLAYBACK_PAUSED=$(cat "$pause_result")
      case "$PLAYBACK_PAUSED" in
        ''|*[!0-9]*) PLAYBACK_PAUSED=0 ;;
        *) PAUSE_TRACKING_VALID=1 ;;
      esac
    fi
  fi
  cat "$ffplay_log" >>"$LOG_FILE"
  if grep -q '^Input #0' "$ffplay_log" \
    && grep -q 'SDL_SetVideoMode' "$ffplay_log" \
    && ! grep -Eq 'HTTP error|Input/output error|partial file' "$ffplay_log"; then
    PLAYBACK_VALID=1
  fi
  rm -f "$ffplay_log"
  if [ "$PLAYBACK_VALID" -ne 1 ] && [ "$PLAYBACK_RC" -eq 0 ]; then
    PLAYBACK_RC=1
  fi
  playback_ended=$(date +%s)
  if [ "$playback_visible_started" -gt 0 ] 2>/dev/null; then
    PLAYBACK_ELAPSED=$((playback_ended - playback_visible_started))
    if [ "$PLAYBACK_PAUSED" -ge "$PLAYBACK_ELAPSED" ] 2>/dev/null; then
      PLAYBACK_ELAPSED=0
    else
      PLAYBACK_ELAPSED=$((PLAYBACK_ELAPSED - PLAYBACK_PAUSED))
    fi
  fi
  rm -f /tmp/stay_awake
  [ -n "$subtitle_file" ] && rm -f "$subtitle_file"
  rm -f "$pause_result"
  log "ffplay exit rc=$PLAYBACK_RC startup_seconds=$PLAYBACK_STARTUP paused_seconds=$PLAYBACK_PAUSED watched_seconds=$PLAYBACK_ELAPSED valid=$PLAYBACK_VALID pause_tracking=$PAUSE_TRACKING_VALID"
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

show_account_qr() {
  account_link="$1"
  log "account qr waiting for approval"
  qr_action=$(printf '%s\n' "$account_link" | \
    POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" "$SDL_SELECTOR" --qr \
    "Connect Stremio" "Scan, approve, A Refresh, B Back" 2>>"$LOG_FILE")
  qr_rc=$?
  log "account qr exit rc=$qr_rc"
  [ "$qr_rc" -eq 0 ] || return "$qr_rc"
  printf '%s' "$qr_action"
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
  ready_attempts="${POCKETSTREMIO_READY_ATTEMPTS:-6}"
  ready_timeout="${POCKETSTREMIO_READY_TIMEOUT:-5}"
  case "$ready_attempts:$ready_timeout" in
    *[!0-9:]*|0:*|*:0) ready_attempts=6; ready_timeout=5 ;;
  esac
  attempts=0
  while [ "$attempts" -lt "$ready_attempts" ]; do
    if api_get "/api/status" "$ready_timeout" >/tmp/pocketstremio-status.json; then
      server_status=$("$JQ" -r '.status // ""' /tmp/pocketstremio-status.json 2>/dev/null)
      if [ "$server_status" = "ok" ]; then
        server_version=$("$JQ" -r '.version // "unknown"' /tmp/pocketstremio-status.json)
        log "server ready after attempts=$((attempts + 1)) version=$server_version"
        return 0
      fi
      log "server readiness returned invalid status=$server_status"
    fi
    attempts=$((attempts + 1))
    log "server readiness attempt=$attempts failed"
    sleep 2
  done
  READY_ERROR="PocketStremio server unavailable"
  return 1
}

home_flow() {
  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      action="Search"
      log "auto-selected home action=Search"
    else
      printf 'Search\nLive TV\nContinue Watching\nStremio Account\nExit\n' >/tmp/pocketstremio-home.tsv
      action=$(select_from_file "PocketStremio" /tmp/pocketstremio-home.tsv)
    fi
    case "$action" in
      Search)
        search_flow
        ;;
      "Live TV")
        live_tv_flow
        ;;
      "Continue Watching")
        continue_watching_flow
        ;;
      "Stremio Account")
        account_flow
        ;;
      *)
        return 0
        ;;
    esac
    [ "$AUTO_FIRST" = "1" ] && return 0
  done
}

live_tv_flow() {
  start_loading "PocketStremio" "Loading live channels..."
  api_get "/api/live-tv" 45 >/tmp/pocketstremio-live-tv.json
  live_tv_rc=$?
  stop_loading
  if [ "$live_tv_rc" -ne 0 ]; then
    message "PocketStremio" "Live TV unavailable"
    return 1
  fi
  live_tv_count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-live-tv.json)
  if [ "$live_tv_count" = "0" ]; then
    live_tv_error=$("$JQ" -r '.failures[0].message // "No live channels available"' /tmp/pocketstremio-live-tv.json)
    message "PocketStremio" "$live_tv_error"
    return 0
  fi

  "$JQ" -r '.items[] | "\(.title) [\(.source)]\t\(.id)\t\(.title)"' /tmp/pocketstremio-live-tv.json >/tmp/pocketstremio-live-tv.tsv
  while :; do
    selected=$(select_from_file "Live TV" /tmp/pocketstremio-live-tv.tsv)
    [ -z "$selected" ] && return 0
    line=$(grep -F "$selected	" /tmp/pocketstremio-live-tv.tsv | head -n 1)
    if [ -z "$line" ]; then
      log "live TV selection did not match selected=$selected"
      message "PocketStremio" "Selection failed"
      return 1
    fi
    id=$(printf '%s' "$line" | cut -f2)
    title=$(printf '%s' "$line" | cut -f3)
    log "selected live channel id=$id title=$title"
    streams_flow "tv" "$id" "$title" "" 0
  done
}

account_flow() {
  while :; do
    start_loading "PocketStremio" "Checking Stremio account..."
    api_get "/api/addons?refresh=1" 45 >/tmp/pocketstremio-addons.json
    account_rc=$?
    stop_loading
    if [ "$account_rc" -ne 0 ]; then
      message "PocketStremio" "Stremio account unavailable"
      return 1
    fi
    account_configured=$("$JQ" -r '.configured // false' /tmp/pocketstremio-addons.json)
    if [ "$account_configured" = "true" ]; then
      account_authenticated=$("$JQ" -r '.authenticated // false' /tmp/pocketstremio-addons.json)
      addon_count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-addons.json)
      if [ "$account_authenticated" = "true" ]; then
        printf 'Connected - %s addons\nRefresh\nBack\n' "$addon_count" >/tmp/pocketstremio-account.tsv
      else
        printf 'Account unavailable\nRefresh\nBack\n' >/tmp/pocketstremio-account.tsv
      fi
      account_action=$(select_from_file "Stremio Account" /tmp/pocketstremio-account.tsv)
      case "$account_action" in
        Refresh) continue ;;
        Back|'') return 0 ;;
        *) message "Stremio Account" "$account_action" ;;
      esac
      continue
    fi

    printf 'Connect Account\nBack\n' >/tmp/pocketstremio-account.tsv
    account_action=$(select_from_file "Stremio Account" /tmp/pocketstremio-account.tsv)
    case "$account_action" in
      "Connect Account") ;;
      *) return 0 ;;
    esac

    start_loading "PocketStremio" "Creating account link..."
    api_post_empty "/api/account/link" 30 >/tmp/pocketstremio-account-link.json
    link_rc=$?
    stop_loading
    if [ "$link_rc" -ne 0 ]; then
      message "PocketStremio" "Could not create account link"
      return 1
    fi
    account_link=$("$JQ" -r '.link // ""' /tmp/pocketstremio-account-link.json)
    [ -n "$account_link" ] || {
      message "PocketStremio" "Account link unavailable"
      return 1
    }

    while :; do
      qr_action=$(show_account_qr "$account_link")
      [ "$?" -eq 0 ] || return 0
      [ "$qr_action" = "refresh" ] || return 0
      start_loading "PocketStremio" "Checking account approval..."
      api_get "/api/account?poll=1" 30 >/tmp/pocketstremio-account.json
      poll_rc=$?
      stop_loading
      if [ "$poll_rc" -ne 0 ]; then
        message "PocketStremio" "Account approval check failed"
        return 1
      fi
      link_state=$("$JQ" -r '.link.state // "idle"' /tmp/pocketstremio-account.json)
      case "$link_state" in
        connected)
          message "PocketStremio" "Stremio account connected"
          break
          ;;
        waiting)
          account_link=$("$JQ" -r '.link.link // ""' /tmp/pocketstremio-account.json)
          [ -n "$account_link" ] || return 1
          ;;
        expired)
          message "PocketStremio" "Account link expired"
          return 0
          ;;
        *)
          message "PocketStremio" "Account link unavailable"
          return 1
          ;;
      esac
    done
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

  encoded=$(printf '%s' "$query" | "$JQ" -sRr @uri)
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
    series_id=$("$JQ" -r '.items[] | select(.type == "series") | .id' /tmp/pocketstremio-search.json | head -n 1)
    if [ -n "$series_id" ]; then
      series_title=$("$JQ" -r --arg id "$series_id" '.items[] | select(.id == $id) | .title' /tmp/pocketstremio-search.json)
      series_year=$("$JQ" -r --arg id "$series_id" '.items[] | select(.id == $id) | (.year // "")' /tmp/pocketstremio-search.json)
      series_dry_run "$series_id" "$series_title" "$series_year"
    fi
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

    if [ "$type" = "series" ]; then
      series_flow "$id" "$title" "$year"
    else
      media_flow "$type" "$id" "$title" "$year" 0
    fi
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

write_season_choices() {
  "$JQ" -r '.seasons[] | "Season \(.number) (\(.episode_count) episodes)\t\(.number)"' "$1" >"$2"
}

write_episode_choices() {
  "$JQ" -r --argjson season "$2" --arg year "$4" '
    .episodes[]
    | select(.season == $season)
    | "\(.episode). \(.title)\t\(.id)\t\(.title)\t\(.year // $year)\t\(.season)\t\(.episode)"
  ' "$1" >"$3"
}

series_dry_run() {
  dry_series_id="$1"
  dry_series_title="$2"
  dry_series_year="$3"
  if ! api_get "/api/meta/series/$dry_series_id" >/tmp/pocketstremio-series-meta.json; then
    log "series dry run metadata failed id=$dry_series_id"
    return 1
  fi
  write_season_choices /tmp/pocketstremio-series-meta.json /tmp/pocketstremio-seasons.tsv
  log "series dry run id=$dry_series_id title=$dry_series_title"
  cat /tmp/pocketstremio-seasons.tsv >>"$LOG_FILE"
  dry_season=$(head -n 1 /tmp/pocketstremio-seasons.tsv | cut -f2)
  if [ -n "$dry_season" ]; then
    write_episode_choices /tmp/pocketstremio-series-meta.json "$dry_season" /tmp/pocketstremio-episodes.tsv "$dry_series_year"
    cat /tmp/pocketstremio-episodes.tsv >>"$LOG_FILE"
  fi
}

series_flow() {
  series_id="$1"
  series_title="$2"
  series_year="$3"

  if ! api_get "/api/meta/series/$series_id" >/tmp/pocketstremio-series-meta.json; then
    message "PocketStremio" "Series details unavailable"
    return 1
  fi
  write_season_choices /tmp/pocketstremio-series-meta.json /tmp/pocketstremio-seasons.tsv
  if [ ! -s /tmp/pocketstremio-seasons.tsv ]; then
    message "PocketStremio" "No seasons available"
    return 0
  fi

  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      season_line=$(head -n 1 /tmp/pocketstremio-seasons.tsv)
      season_selected=$(printf '%s' "$season_line" | cut -f1)
      log "auto-selected first season selected=$season_selected"
    else
      season_selected=$(select_from_file "$series_title" /tmp/pocketstremio-seasons.tsv)
      [ -z "$season_selected" ] && return 10
      season_line=$(grep -F "$season_selected	" /tmp/pocketstremio-seasons.tsv | head -n 1)
      if [ -z "$season_line" ]; then
        log "season selection did not match selected=$season_selected"
        message "PocketStremio" "Selection failed"
        return 1
      fi
    fi
    season_number=$(printf '%s' "$season_line" | cut -f2)
    log "selected season series_id=$series_id season=$season_number"

    episodes_flow "$series_id" "$series_title" "$series_year" "$season_number"
    flow_rc=$?
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

episodes_flow() {
  episode_series_id="$1"
  episode_series_title="$2"
  episode_series_year="$3"
  episode_season="$4"
  write_episode_choices /tmp/pocketstremio-series-meta.json "$episode_season" /tmp/pocketstremio-episodes.tsv "$episode_series_year"
  if [ ! -s /tmp/pocketstremio-episodes.tsv ]; then
    message "PocketStremio" "No episodes available"
    return 10
  fi

  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      episode_line=$(head -n 1 /tmp/pocketstremio-episodes.tsv)
      episode_selected=$(printf '%s' "$episode_line" | cut -f1)
      log "auto-selected first episode selected=$episode_selected"
    else
      episode_selected=$(select_from_file "Season $episode_season" /tmp/pocketstremio-episodes.tsv)
      [ -z "$episode_selected" ] && return 10
      episode_line=$(grep -F "$episode_selected	" /tmp/pocketstremio-episodes.tsv | head -n 1)
      if [ -z "$episode_line" ]; then
        log "episode selection did not match selected=$episode_selected"
        message "PocketStremio" "Selection failed"
        return 1
      fi
    fi

    episode_id=$(printf '%s' "$episode_line" | cut -f2)
    episode_title=$(printf '%s' "$episode_line" | cut -f3)
    episode_year=$(printf '%s' "$episode_line" | cut -f4)
    episode_number=$(printf '%s' "$episode_line" | cut -f6)
    episode_saved_title="$episode_series_title - S${episode_season}E${episode_number} $episode_title"
    episode_display_title="S${episode_season}E${episode_number} $episode_title"
    log "selected episode series_id=$episode_series_id id=$episode_id season=$episode_season episode=$episode_number"

    media_flow "series" "$episode_id" "$episode_saved_title" "$episode_year" 0 "$episode_display_title"
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
  display_title="${6:-$title}"

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
      action=$(select_from_file "$display_title ($year)" /tmp/pocketstremio-actions.tsv)
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
  start_loading "PocketStremio" "Finding streams..."
  api_get "/api/streams/$type/$id" >/tmp/pocketstremio-streams.json
  stream_lookup_rc=$?
  stop_loading
  if [ "$stream_lookup_rc" -ne 0 ]; then
    message "PocketStremio" "Stream lookup failed"
    return 1
  fi

  "$JQ" -r '.items | to_entries[] | select(.value.playable == true) | "\(if .value.compatibility.status == "confirmed" then "[OK] " else "[TEST] " end)\(.value.name)\t\(.value.id)\t\(.value.description // "")"' /tmp/pocketstremio-streams.json >/tmp/pocketstremio-streams.tsv
  if [ ! -s /tmp/pocketstremio-streams.tsv ]; then
    stream_error=$("$JQ" -r '.failures[0].message // "No playable streams"' /tmp/pocketstremio-streams.json)
    log "no playable streams message=$stream_error"
    message "PocketStremio" "$stream_error"
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

  start_loading "PocketStremio" "Checking compatibility..."
  api_post_play "$type" "$id" "$stream_id" >/tmp/pocketstremio-play.json
  play_setup_rc=$?
  stop_loading
  if [ "$play_setup_rc" -ne 0 ]; then
    message "PocketStremio" "Playback setup failed"
    return 1
  fi
  play_url_value=$("$JQ" -r '.url // ""' /tmp/pocketstremio-play.json)
  if [ -z "$play_url_value" ]; then
    play_error=$("$JQ" -r '.message // "Playback setup failed"' /tmp/pocketstremio-play.json 2>/dev/null)
    [ -n "$play_error" ] || play_error="Playback setup failed"
    log "playback setup rejected message=$play_error"
    message "PocketStremio" "$play_error"
    return 1
  fi
  duration_seconds=$("$JQ" -r '(.duration_seconds // 0) | floor' /tmp/pocketstremio-play.json)
  compatibility_status=$("$JQ" -r '.compatibility.status // "unknown"' /tmp/pocketstremio-play.json)
  compatibility_message=$("$JQ" -r '.compatibility.message // ""' /tmp/pocketstremio-play.json)
  log "media preflight status=$compatibility_status message=$compatibility_message"

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
  start_loading "PocketStremio" "Starting video..."
  sleep 1
  stop_loading
  if ! play_url "$play_url_value" "$resume_seconds" "$subtitle_file"; then
    message "PocketStremio" "Playback failed"
  fi

  if [ "$type" = "tv" ]; then
    log "live playback ended without progress update"
    return 0
  fi

  new_position=$((resume_seconds + PLAYBACK_ELAPSED))
  completed=false
  if [ "$duration_seconds" -gt 0 ] 2>/dev/null && [ $((new_position * 10)) -ge $((duration_seconds * 9)) ]; then
    completed=true
  fi
  if [ "$PLAYBACK_VALID" -eq 1 ] 2>/dev/null && [ "$PAUSE_TRACKING_VALID" -eq 1 ] 2>/dev/null && [ "$PLAYBACK_RC" -eq 0 ] 2>/dev/null && [ "$PLAYBACK_ELAPSED" -gt 0 ] 2>/dev/null; then
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
if [ -n "$PROXY" ]; then
  transport="proxy:$PROXY"
else
  transport="direct"
fi
log "PocketStremio UI start server=$SERVER_BASE transport=$transport"
if [ -n "$CONFIG_ERROR" ]; then
  log "configuration error=$CONFIG_ERROR"
  message "PocketStremio" "$CONFIG_ERROR"
  exit 1
fi
if ! ensure_ready; then
  [ -n "$READY_ERROR" ] || READY_ERROR="PocketStremio unavailable"
  log "startup unavailable message=$READY_ERROR"
  message "PocketStremio" "$READY_ERROR"
  exit 1
fi

home_flow
log "PocketStremio UI exit"
sync
