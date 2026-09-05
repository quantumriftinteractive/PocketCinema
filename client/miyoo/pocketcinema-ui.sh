#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketCinema
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/pocketcinema-ui.log"
PREVIOUS_LOG_FILE="$LOG_DIR/pocketcinema-ui.previous.log"
CONFIG_FILE="$BASE_DIR/config/pocketcinema.conf"
LAST_PLAY_FILE="$BASE_DIR/config/last-play.json"
HTTP_ERROR_FILE=/tmp/pocketcinema-http-error
SERVER_BASE="${POCKETCINEMA_SERVER:-}"
SERVER_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_SERVER:-}" ] && SERVER_ENV_OVERRIDE=1
PROXY="${POCKETCINEMA_PROXY:-}"
PROXY_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_PROXY:-}" ] && PROXY_ENV_OVERRIDE=1
AUTO_FIRST="${POCKETCINEMA_AUTO_FIRST:-}"
DEFAULT_QUERY="${POCKETCINEMA_DEFAULT_QUERY:-}"
AUDIO_GAIN="${POCKETCINEMA_AUDIO_GAIN:-}"
AUDIO_GAIN_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_AUDIO_GAIN:-}" ] && AUDIO_GAIN_ENV_OVERRIDE=1
AUDIO_LANGUAGES="${POCKETCINEMA_AUDIO_LANGUAGES:-}"
AUDIO_FALLBACK="${POCKETCINEMA_AUDIO_FALLBACK:-}"
AUDIO_LANGUAGE_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_AUDIO_LANGUAGES:-}" ] && AUDIO_LANGUAGE_ENV_OVERRIDE=1
[ -n "${POCKETCINEMA_AUDIO_FALLBACK:-}" ] && AUDIO_LANGUAGE_ENV_OVERRIDE=1
SUBTITLE_LANGUAGES="${POCKETCINEMA_SUBTITLE_LANGUAGES:-}"
SUBTITLE_FALLBACK="${POCKETCINEMA_SUBTITLE_FALLBACK:-}"
SUBTITLE_FONT_SCALE="${POCKETCINEMA_SUBTITLE_FONT_SCALE:-}"
SUBTITLE_FONT_SCALE_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_SUBTITLE_FONT_SCALE:-}" ] && SUBTITLE_FONT_SCALE_ENV_OVERRIDE=1
MAX_SUBTITLES_PER_LANGUAGE="${POCKETCINEMA_MAX_SUBTITLES_PER_LANGUAGE:-}"
MAX_SUBTITLES_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_MAX_SUBTITLES_PER_LANGUAGE:-}" ] && MAX_SUBTITLES_ENV_OVERRIDE=1
SUBTITLE_LANGUAGE_ENV_OVERRIDE=0
[ -n "${POCKETCINEMA_SUBTITLE_LANGUAGES:-}" ] && SUBTITLE_LANGUAGE_ENV_OVERRIDE=1
[ -n "${POCKETCINEMA_SUBTITLE_FALLBACK:-}" ] && SUBTITLE_LANGUAGE_ENV_OVERRIDE=1
CURL="$SYS_DIR/bin/curl"
JQ="$SYS_DIR/bin/jq"
KBINPUT="$SYS_DIR/bin/kbinput"
SHELLECT="$SYS_DIR/script/shellect.sh"
SDL_SELECTOR="$BASE_DIR/bin/pocketcinema-selector"
PAUSE_MONITOR="$BASE_DIR/bin/pocketcinema-pause-monitor"
PLAYBACK_CONTROL="$BASE_DIR/bin/pocketcinema-playback-control"
RESOURCE_MONITOR="$BASE_DIR/client/pocketcinema-resource-monitor.sh"
DISCOVERY_CLIENT="$BASE_DIR/bin/pocketcinema-discovery"
PROXY_HELPER="$BASE_DIR/client/pocketcinema-proxy.sh"
CONNECTION_HELPER="$BASE_DIR/client/pocketcinema-connection.sh"
INFOPANEL="$SYS_DIR/bin/infoPanel"
FFPLAY="$SYS_DIR/bin/ffplay"
APP_LOCAL_PLAYER="${POCKETCINEMA_APP_LOCAL_PLAYER:-1}"
FIELD_TEST="${POCKETCINEMA_SUBTITLE_FIELD_TEST:-0}"
MATROSKA_SUBTITLES="${POCKETCINEMA_MATROSKA_SUBTITLES:-}"
if [ -f "$BASE_DIR/config/ffplay-field-test.mode" ]; then
  FIELD_TEST=1
  rm -f "$BASE_DIR/config/ffplay-field-test.mode"
fi
if [ -f "$BASE_DIR/config/matroska-subtitles.mode" ]; then
  MATROSKA_SUBTITLES=1
  rm -f "$BASE_DIR/config/matroska-subtitles.mode"
fi
DISPLAY_SURFACE_TEST="${POCKETCINEMA_DISPLAY_SURFACE_TEST:-0}"
if [ -f "$BASE_DIR/config/ffplay-display-surface-test.mode" ]; then
  DISPLAY_SURFACE_TEST=1
  rm -f "$BASE_DIR/config/ffplay-display-surface-test.mode"
fi
CANDIDATE_PLAYER=0
FIELD_TEST_DIR="$BASE_DIR/experiments/ffplay"
FIELD_TEST_LIB_DIR="$FIELD_TEST_DIR/lib"
FIELD_TEST_SUBTITLE_FILE=""
PADSP="$MIYOO_DIR/lib/libpadsp.so"
LOADING_PID=""
PAUSE_MONITOR_PID=""
PLAYBACK_CONTROL_PID=""
RESOURCE_MONITOR_PID=""
PLAYBACK_CONTROL_FILE=/tmp/pocketcinema-playback-control
CONFIG_ERROR=""
SERVER_CONFIG_MESSAGE=""
SERVER_URL_VALID=1
SERVER_REACHABLE=2
SERVER_STATUS_TEXT=""
SERVER_MONITOR_PID=""
SERVER_STATUS_FILE=/tmp/pocketcinema-server-status
SERVER_STATUS_JSON=/tmp/pocketcinema-server-status.json
SERVER_ROUTE_FILE=/tmp/pocketcinema-server-route
LOCAL_PCSERVER=""
REMOTE_PCSERVER=""
CONNECTION_MODE=""
CONNECTION_PROFILE=0
LEGACY_SERVER_BASE=""
LEGACY_PROXY=""
REQUEST_PROXY=""
ACTIVE_ROUTE=""
ROUTE_FAILURE=""
PLAYBACK_ERROR="Playback failed"
FAILED_STREAM_IDS=""
STREAM_RETRY_SUBTITLE_ID=""

mkdir -p "$LOG_DIR"
[ -r "$PROXY_HELPER" ] || {
  printf 'Missing PocketCinema HTTP proxy helper\n' >&2
  exit 1
}
. "$PROXY_HELPER"
[ -r "$CONNECTION_HELPER" ] || {
  printf 'Missing PocketCinema connection helper\n' >&2
  exit 1
}
. "$CONNECTION_HELPER"
rm -f "$PREVIOUS_LOG_FILE.tmp"
if [ -s "$LOG_FILE" ]; then
  tail -c 262144 "$LOG_FILE" >"$PREVIOUS_LOG_FILE.tmp" 2>/dev/null \
    && mv "$PREVIOUS_LOG_FILE.tmp" "$PREVIOUS_LOG_FILE"
fi
: > "$LOG_FILE"

load_config() {
  [ -f "$CONFIG_FILE" ] || return 0
  while IFS='=' read -r config_key config_value; do
    config_value=$(printf '%s' "$config_value" | tr -d '\r')
    case "$config_key" in
      ''|'#'*) continue ;;
      SERVER_BASE) [ -n "$SERVER_BASE" ] || SERVER_BASE="$config_value" ;;
      PROXY) [ -n "$PROXY" ] || PROXY="$config_value" ;;
      LOCAL_PCSERVER) LOCAL_PCSERVER="$config_value" ;;
      REMOTE_PCSERVER) REMOTE_PCSERVER="$config_value" ;;
      CONNECTION_MODE) CONNECTION_MODE="$config_value" ;;
      DEFAULT_QUERY) [ -n "$DEFAULT_QUERY" ] || DEFAULT_QUERY="$config_value" ;;
      AUTO_FIRST) [ -n "$AUTO_FIRST" ] || AUTO_FIRST="$config_value" ;;
      AUDIO_GAIN) [ -n "$AUDIO_GAIN" ] || AUDIO_GAIN="$config_value" ;;
      AUDIO_LANGUAGES) [ -n "$AUDIO_LANGUAGES" ] || AUDIO_LANGUAGES="$config_value" ;;
      AUDIO_FALLBACK) [ -n "$AUDIO_FALLBACK" ] || AUDIO_FALLBACK="$config_value" ;;
      SUBTITLE_LANGUAGES)
        [ -n "$SUBTITLE_LANGUAGES" ] || SUBTITLE_LANGUAGES="$config_value"
        ;;
      SUBTITLE_FALLBACK)
        [ -n "$SUBTITLE_FALLBACK" ] || SUBTITLE_FALLBACK="$config_value"
        ;;
      SUBTITLE_FONT_SCALE)
        [ -n "$SUBTITLE_FONT_SCALE" ] || SUBTITLE_FONT_SCALE="$config_value"
        ;;
      MAX_SUBTITLES_PER_LANGUAGE)
        [ -n "$MAX_SUBTITLES_PER_LANGUAGE" ] || MAX_SUBTITLES_PER_LANGUAGE="$config_value"
        ;;
      POCKETCINEMA_MATROSKA_SUBTITLES)
        [ -n "$MATROSKA_SUBTITLES" ] || MATROSKA_SUBTITLES="$config_value"
        ;;
      *) CONFIG_ERROR="Unknown setting: $config_key" ;;
    esac
  done <"$CONFIG_FILE"
}

valid_language_order() {
  language_order="$1"
  [ -z "$language_order" ] && return 0
  printf '%s\n' "$language_order" | awk -F, '
    NF < 1 || NF > 5 { exit 1 }
    {
      for (i = 1; i <= NF; i++) {
        if (length($i) < 2 || length($i) > 3 || $i !~ /^[a-z]+$/ || seen[$i]++) {
          exit 1
        }
      }
    }
  '
}

load_config
AUTO_FIRST="${AUTO_FIRST:-0}"
DEFAULT_QUERY="${DEFAULT_QUERY:-big buck bunny}"
AUDIO_GAIN="${AUDIO_GAIN:-2.0}"
AUDIO_FALLBACK="${AUDIO_FALLBACK:-ask}"
SUBTITLE_FALLBACK="${SUBTITLE_FALLBACK:-ask}"
SUBTITLE_FONT_SCALE="${SUBTITLE_FONT_SCALE:-1.5}"
MAX_SUBTITLES_PER_LANGUAGE="${MAX_SUBTITLES_PER_LANGUAGE:-3}"
# Selectable Matroska subtitles are the accepted normal production path.  An
# explicit environment or persisted configuration value of 0 remains the opt-out.
MATROSKA_SUBTITLES="${MATROSKA_SUBTITLES:-1}"
case "$PROXY" in
  '') ;;
  *)
    normalized_proxy=$(pocketcinema_normalize_http_proxy "$PROXY") ||
      CONFIG_ERROR="PROXY must be an HTTP host:port URL without credentials"
    [ -n "${normalized_proxy:-}" ] && PROXY="$normalized_proxy"
    ;;
esac
if [ -n "$LOCAL_PCSERVER$REMOTE_PCSERVER$CONNECTION_MODE" ] && [ "$SERVER_ENV_OVERRIDE" -eq 0 ]; then
  CONNECTION_PROFILE=1
  if [ -n "$LOCAL_PCSERVER" ]; then
    LOCAL_PCSERVER=$(pocketcinema_normalize_pcserver_url "$LOCAL_PCSERVER") || \
      CONFIG_ERROR="LOCAL_PCSERVER must be an HTTP URL"
  fi
  if [ -n "$REMOTE_PCSERVER" ]; then
    REMOTE_PCSERVER=$(pocketcinema_normalize_pcserver_url "$REMOTE_PCSERVER") || \
      CONFIG_ERROR="REMOTE_PCSERVER must be an HTTP URL"
  fi
  CONNECTION_MODE=$(pocketcinema_normalize_connection_mode "$CONNECTION_MODE") || \
    CONFIG_ERROR="CONNECTION_MODE must be automatic, local, or remote"
  if [ -z "$CONFIG_ERROR" ] && ! pocketcinema_validate_connection_profile \
    "$LOCAL_PCSERVER" "$REMOTE_PCSERVER" "$CONNECTION_MODE" "$PROXY"; then
    CONFIG_ERROR="Connection profile is incomplete"
  fi
  [ -n "$CONFIG_ERROR" ] || SERVER_URL_VALID=1
else
  LEGACY_SERVER_BASE="$SERVER_BASE"
  LEGACY_PROXY="$PROXY"
  REQUEST_PROXY="$PROXY"
  case "$SERVER_BASE" in
    http://*|https://*) ;;
    '') SERVER_URL_VALID=0; SERVER_CONFIG_MESSAGE="No PCServer connection configured" ;;
    *) SERVER_URL_VALID=0; SERVER_CONFIG_MESSAGE="SERVER_BASE must be an HTTP URL" ;;
  esac
fi
case "$AUTO_FIRST" in
  0|1) ;;
  *) CONFIG_ERROR="AUTO_FIRST must be 0 or 1" ;;
esac
case "$AUDIO_GAIN" in
  1|1.0|1.25|1.5|1.75|2|2.0) ;;
  *) CONFIG_ERROR="AUDIO_GAIN must be 1, 1.25, 1.5, 1.75, or 2" ;;
esac
if ! valid_language_order "$AUDIO_LANGUAGES"; then
  CONFIG_ERROR="AUDIO_LANGUAGES must contain up to five unique 2-3 letter codes"
fi
case "$AUDIO_FALLBACK" in
  ask|first|stop) ;;
  *) CONFIG_ERROR="AUDIO_FALLBACK must be ask, first, or stop" ;;
esac
if ! valid_language_order "$SUBTITLE_LANGUAGES"; then
  CONFIG_ERROR="SUBTITLE_LANGUAGES must contain up to five unique 2-3 letter codes"
fi
case "$SUBTITLE_FALLBACK" in
  ask|none) ;;
  *) CONFIG_ERROR="SUBTITLE_FALLBACK must be ask or none" ;;
esac
case "$SUBTITLE_FONT_SCALE" in
  1.0|1.25|1.5|2.0|2.5|3.0) ;;
  *) CONFIG_ERROR="SUBTITLE_FONT_SCALE must be 1.0, 1.25, 1.5, 2.0, 2.5, or 3.0" ;;
esac
case "$MAX_SUBTITLES_PER_LANGUAGE" in
  1|2|3) ;;
  *) CONFIG_ERROR="MAX_SUBTITLES_PER_LANGUAGE must be 1, 2, or 3" ;;
esac
case "$APP_LOCAL_PLAYER" in
  0|1) ;;
  *) CONFIG_ERROR="POCKETCINEMA_APP_LOCAL_PLAYER must be 0 or 1" ;;
esac
case "$MATROSKA_SUBTITLES" in
  0|1) ;;
  *) CONFIG_ERROR="POCKETCINEMA_MATROSKA_SUBTITLES must be 0 or 1" ;;
esac

# The app-local player owns a fixed 640x480 SDL surface.  This prevents the
# normal Onion FFplay path from stretching correctly encoded letterboxed video.
# Selectable Matroska subtitles always require this track-aware candidate.
if [ "$APP_LOCAL_PLAYER" = "1" ] || [ "$FIELD_TEST" = "1" ] \
  || [ "$DISPLAY_SURFACE_TEST" = "1" ] || [ "$MATROSKA_SUBTITLES" = "1" ]; then
  CANDIDATE_PLAYER=1
  FFPLAY="$BASE_DIR/experiments/ffplay/bin/ffplay"
fi

cleanup() {
  stop_loading
  stop_server_monitor
  if [ -n "$PAUSE_MONITOR_PID" ] && kill -0 "$PAUSE_MONITOR_PID" 2>/dev/null; then
    kill "$PAUSE_MONITOR_PID" 2>/dev/null || true
    wait "$PAUSE_MONITOR_PID" 2>/dev/null || true
  fi
  if [ -n "$RESOURCE_MONITOR_PID" ]; then
    kill "$RESOURCE_MONITOR_PID" 2>/dev/null || true
    wait "$RESOURCE_MONITOR_PID" 2>/dev/null || true
    RESOURCE_MONITOR_PID=""
  fi
  rm -f /tmp/stay_awake /tmp/pocketcinema-subtitle.srt \
    "$FIELD_TEST_SUBTITLE_FILE" \
    /tmp/pocketcinema-ffplay.log /tmp/pocketcinema-paused-seconds \
    /tmp/pocketcinema-play-error.json \
    "$PLAYBACK_CONTROL_FILE" \
    /tmp/pocketcinema-aspect-request \
    /tmp/pocketcinema-account.json /tmp/pocketcinema-account-link.json \
    /tmp/pocketcinema-addons.json /tmp/pocketcinema-live-tv.json \
    /tmp/pocketcinema-live-tv.tsv \
    /tmp/pocketcinema-discovery.raw /tmp/pocketcinema-discovery.tsv \
    /tmp/pocketcinema-discovery-status.json \
    /tmp/pocketcinema-settings.tsv /tmp/pocketcinema-proxy.tsv \
    /tmp/pocketcinema-connection.tsv /tmp/pocketcinema-route-status-$$.json \
    /tmp/pocketcinema-continue-action \
    /tmp/pocketcinema-remove-confirm.tsv \
    /tmp/pocketcinema-language-action.tsv \
    /tmp/pocketcinema-language-catalog.tsv \
    /tmp/pocketcinema-language-choices.tsv \
    /tmp/pocketcinema-language-order.tsv \
    /tmp/pocketcinema-language-fallback.tsv \
    /tmp/pocketcinema-max-subtitles.tsv \
    /tmp/pocketcinema-matroska-subtitle-fallback.tsv \
    /tmp/pocketcinema-english-subtitles.json \
    "$SERVER_STATUS_FILE" "$SERVER_STATUS_JSON" "$SERVER_ROUTE_FILE" \
    /tmp/pocketcinema-stream-details.tsv \
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
  message_mode="${3:-auto}"
  message_max_lines=4
  if [ "${POCKETCINEMA_HEADLESS:-0}" = "1" ]; then
    log "message mode=$message_mode title=$title body=$body"
    return 0
  fi
  display_body=$(printf '%s\n' "$body" | tr '\r' ' ' | fold -s -w 32 | \
    awk -v max_lines="$message_max_lines" '
    NR <= max_lines { lines[NR] = $0 }
    NR == max_lines + 1 { truncated = 1 }
    END {
      for (i = 1; i <= max_lines && i in lines; i++) {
        if (i == max_lines && truncated) print substr(lines[i], 1, 29) "..."
        else print lines[i]
      }
    }
  ')
  if [ "$message_mode" = timed ]; then
    rm -f /tmp/dismiss_info_panel
    "$INFOPANEL" --title "$title" --message "$display_body" --persistent >/dev/null 2>&1 &
    timed_message_pid=$!
    sleep 3
    if kill -0 "$timed_message_pid" 2>/dev/null; then
      touch /tmp/dismiss_info_panel
      wait "$timed_message_pid" 2>/dev/null || true
    fi
    rm -f /tmp/dismiss_info_panel
  elif [ "$message_mode" = acknowledge ]; then
    "$INFOPANEL" --title "$title" --message "$display_body" >/dev/null 2>&1 || true
  else
    "$INFOPANEL" --title "$title" --message "$display_body" --auto >/dev/null 2>&1 || true
  fi
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

curl_request_with_proxy() (
  request_proxy="$1"
  shift
  unset LD_PRELOAD
  if [ -n "$request_proxy" ]; then
    unset ALL_PROXY all_proxy
    HTTP_PROXY="$request_proxy" http_proxy="$request_proxy" \
    HTTPS_PROXY="$request_proxy" https_proxy="$request_proxy" "$CURL" "$@"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    "$CURL" "$@"
  fi
)

curl_request() (
  curl_request_with_proxy "$REQUEST_PROXY" "$@"
)

api_get() {
  path="$1"
  timeout="${2:-30}"
  ensure_active_route || return 1
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
  ensure_active_route || return 1
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
  subtitle_id="${4:-none}"
  resume_seconds="${5:-0}"
  audio_stream_index="${6:-0}"
  ensure_active_route || return 1
  body=$("$JQ" -nc \
    --arg type "$type" \
    --arg id "$id" \
    --arg stream_id "$stream_id" \
    --arg subtitle_id "$subtitle_id" \
    --argjson audio_stream_index "$audio_stream_index" \
    --argjson field_test "$([ "$FIELD_TEST" = "1" ] && printf 1 || printf 0)" \
    --argjson matroska_subtitles "$([ "$MATROSKA_SUBTITLES" = "1" ] && printf 1 || printf 0)" \
    --arg subtitle_languages "$SUBTITLE_LANGUAGES" \
    --argjson max_subtitles_per_language "$MAX_SUBTITLES_PER_LANGUAGE" \
    --argjson resume_seconds "$resume_seconds" \
    '{type:$type,id:$id,stream_id:$stream_id,subtitle_id:$subtitle_id,audio_stream_index:$audio_stream_index,field_test:($field_test == 1),matroska_subtitles:($matroska_subtitles == 1),subtitle_languages:(if $subtitle_languages == "" then [] else ($subtitle_languages | split(",")) end),max_subtitles_per_language:$max_subtitles_per_language,resume_seconds:$resume_seconds}')
  rm -f "$HTTP_ERROR_FILE"
  curl_request -sS --max-time 60 -H 'Content-Type: application/json' -d "$body" "$SERVER_BASE/api/play" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "api post play failed rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
}

save_last_play() {
  last_type="$1"
  last_id="$2"
  last_title="$3"
  last_year="$4"
  last_resume_seconds="$5"
  last_stream_id="$6"
  last_subtitle_id="$7"
  last_audio_stream_index="${8:-0}"
  last_tmp="$LAST_PLAY_FILE.tmp"
  "$JQ" -nc \
    --arg server "$SERVER_BASE" \
    --arg type "$last_type" \
    --arg id "$last_id" \
    --arg title "$last_title" \
    --arg year "$last_year" \
    --arg stream_id "$last_stream_id" \
    --arg subtitle_id "$last_subtitle_id" \
    --argjson audio_stream_index "$last_audio_stream_index" \
    --argjson resume_seconds "$last_resume_seconds" \
    '{server:$server,type:$type,id:$id,title:$title,year:$year,stream_id:$stream_id,subtitle_id:$subtitle_id,audio_stream_index:$audio_stream_index,resume_seconds:$resume_seconds}' \
    >"$last_tmp" 2>/dev/null \
    && mv "$last_tmp" "$LAST_PLAY_FILE"
  rm -f "$last_tmp"
}

api_post_progress() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  position="$5"
  duration="$6"
  completed="$7"
  ensure_active_route || return 1
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

api_post_continue_remove() {
  type="$1"
  id="$2"
  ensure_active_route || return 1
  body=$("$JQ" -nc --arg type "$type" --arg id "$id" '{type:$type,id:$id}')
  rm -f "$HTTP_ERROR_FILE"
  curl_request -fsS --max-time 30 -H 'Content-Type: application/json' -d "$body" \
    "$SERVER_BASE/api/continue-watching/remove" 2>"$HTTP_ERROR_FILE"
  http_rc=$?
  if [ "$http_rc" -ne 0 ]; then
    http_detail=$(tail -c 240 "$HTTP_ERROR_FILE" 2>/dev/null | tr '\r\n' '  ')
    log "continue watching remove failed type=$type id=$id rc=$http_rc detail=$http_detail"
  fi
  return "$http_rc"
}

ffplay_has_subtitles() {
  (unset LD_PRELOAD; "$FFPLAY" -hide_banner -filters 2>/dev/null) | grep -q '[[:space:]]subtitles[[:space:]]'
}

playback_setup_error() {
  if [ -n "$REQUEST_PROXY" ]; then
    case "$1" in
      5) printf '%s\n' "Configured HTTP proxy could not be resolved"; return 0 ;;
      7) printf '%s\n' "Configured HTTP proxy could not be reached"; return 0 ;;
      28) printf '%s\n' "Configured HTTP proxy timed out"; return 0 ;;
    esac
  fi
  case "$1" in
    5|6) printf '%s\n' "PCServer address could not be resolved" ;;
    7) printf '%s\n' "PCServer is offline or refused the connection" ;;
    28) printf '%s\n' "PCServer did not respond in time" ;;
    35|60) printf '%s\n' "Secure connection to PCServer failed" ;;
    *) printf '%s\n' "Could not contact PCServer for playback" ;;
  esac
}

classify_playback_error() {
  failure_log="$1"
  failure_rc="$2"
  if grep -Eqi 'HTTP error (401|403)|Server returned (401|403)' "$failure_log"; then
    printf '%s\n' "Stream access was denied or expired"
  elif grep -Eqi 'HTTP error (404|410)|Server returned (404|410)' "$failure_log"; then
    printf '%s\n' "Stream is no longer available"
  elif grep -Eqi 'HTTP error 429|Server returned 429' "$failure_log"; then
    printf '%s\n' "Stream provider is rate-limiting requests"
  elif grep -Eqi 'HTTP error 502 Subtitle download failed' "$failure_log"; then
    printf '%s\n' "Selected subtitle could not be downloaded"
  elif grep -Eqi 'HTTP error 502 Conversion (could not start|produced no media)' "$failure_log"; then
    printf '%s\n' "PCServer conversion could not start"
  elif grep -Eqi 'HTTP error 5[0-9][0-9]|Server returned 5[0-9][0-9]' "$failure_log"; then
    printf '%s\n' "Stream provider or PCServer failed; choose another stream"
  elif grep -Eqi 'Connection refused|Connection timed out|Network is unreachable|No route to host|Could not resolve|Temporary failure in name resolution' "$failure_log"; then
    printf '%s\n' "Could not reach the media stream"
  elif grep -Eqi 'Input/output error|partial file|Connection reset|End of file' "$failure_log"; then
    printf '%s\n' "Media stream ended or was interrupted"
  elif grep -Eqi 'Invalid data found when processing input|could not find codec parameters|moov atom not found|Invalid argument' "$failure_log"; then
    printf '%s\n' "Stream format is unsupported or invalid"
  elif grep -Eqi 'Decoder.*not found|Unknown decoder|codec.*not supported|Could not open codec' "$failure_log"; then
    printf '%s\n' "Video or audio codec is unsupported"
  elif grep -Eqi '/dev/dsp.*(fail|error|No such)|SDL_OpenAudio.*(fail|error)|audio device.*(fail|error)' "$failure_log"; then
    printf '%s\n' "Audio could not initialize"
  elif grep -q 'Input #0' "$failure_log" && grep -q 'SDL_SetVideoMode' "$failure_log"; then
    printf '%s\n' "Playback stopped unexpectedly after video started"
  elif grep -q 'Input #0' "$failure_log"; then
    printf '%s\n' "Video could not start on this device"
  elif [ "$failure_rc" -eq 126 ] 2>/dev/null || [ "$failure_rc" -eq 127 ] 2>/dev/null; then
    printf '%s\n' "FFplay could not be started"
  elif [ ! -s "$failure_log" ]; then
    printf '%s\n' "FFplay exited without diagnostic output"
  else
    printf '%s\n' "Media stream could not be opened"
  fi
}

# FFplay reports a short HTTP status line only, so retrieve the bounded,
# session-scoped PCServer failure code after a playback setup failure.  Older PCServer
# versions simply return 404 and retain the existing local classification.
playback_server_error() {
  playback_error_url="$1"
  playback_error_session_id=${playback_error_url##*/}
  playback_error_session_id=${playback_error_session_id%%\?*}
  case "$playback_error_session_id" in
    ''|*[!0-9a-f]*) return 1 ;;
  esac
  playback_error_file=/tmp/pocketcinema-play-error.json
  rm -f "$playback_error_file"
  if ! curl_request -fsS --max-time 5 -o "$playback_error_file" \
    "$SERVER_BASE/api/play-error/$playback_error_session_id" \
    2>>"$HTTP_ERROR_FILE"; then
    rm -f "$playback_error_file"
    return 1
  fi
  playback_error_code=$("$JQ" -r '.error // empty' "$playback_error_file" 2>/dev/null)
  rm -f "$playback_error_file"
  case "$playback_error_code" in
    subtitle_download_failed) printf '%s\n' "Selected subtitle could not be downloaded" ;;
    transcode_start_failed|transcode_failed) printf '%s\n' "PCServer conversion could not start" ;;
    *) return 1 ;;
  esac
}

run_ffplay() (
  video_filter="$1"
  url="$2"
  resume_seconds="$3"
  aspect_mode="${4:-0}"
  playback_preload="$PADSP"
  screen_args=""
  audio_args="-af volume=$AUDIO_GAIN"
  if [ "$CANDIDATE_PLAYER" = "1" ]; then
    screen_args="-x 640 -y 480"
    # The deployed app-local candidate does not yet include FFmpeg's volume
    # filter.  Keep this empty until its rebuilt binary is deployed.
    audio_args=""
    export LD_LIBRARY_PATH="$FIELD_TEST_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    playback_preload="$PADSP:$MIYOO_DIR/lib/libSDL-1.2.so.0"
    export FONTCONFIG_PATH="$FIELD_TEST_DIR"
    export FONTCONFIG_FILE="$FIELD_TEST_DIR/fonts.conf"
    export POCKETCINEMA_FONTCONFIG_FILE="$FIELD_TEST_DIR/fonts.conf"
    export POCKETCINEMA_DEFAULT_FONT="$FIELD_TEST_DIR/fonts/PocketCinema.ttf"
    export POCKETCINEMA_SUBTITLE_FONT_SCALE="$SUBTITLE_FONT_SCALE"
    export POCKETCINEMA_ASPECT_MODE="$aspect_mode"
    # The normal deployment migration can retain the physically accepted
    # pre-rename FFplay binary. It is compiled to read the legacy identifiers,
    # so provide the same app-local production assets under both identities
    # until a rebuilt binary replaces it. These are internal runtime bindings,
    # not user-facing test activation.
    export POCKETSTREMIO_FONTCONFIG_FILE="$FIELD_TEST_DIR/fonts.conf"
    export POCKETSTREMIO_DEFAULT_FONT="$FIELD_TEST_DIR/fonts/PocketCinema.ttf"
    export POCKETSTREMIO_SUBTITLE_FONT_SCALE="$SUBTITLE_FONT_SCALE"
    export POCKETSTREMIO_ASPECT_MODE="$aspect_mode"
    if [ -n "$FIELD_TEST_SUBTITLE_FILE" ]; then
      export POCKETCINEMA_SUBTITLE_FILE="$FIELD_TEST_SUBTITLE_FILE"
      export POCKETSTREMIO_SUBTITLE_FILE="$FIELD_TEST_SUBTITLE_FILE"
    else
      unset POCKETCINEMA_SUBTITLE_FILE
      unset POCKETSTREMIO_SUBTITLE_FILE
    fi
  fi
  if [ -n "$REQUEST_PROXY" ]; then
    unset ALL_PROXY all_proxy
    HOME=/mnt/SDCARD \
    HTTP_PROXY="$REQUEST_PROXY" \
    http_proxy="$REQUEST_PROXY" \
    HTTPS_PROXY="$REQUEST_PROXY" \
    https_proxy="$REQUEST_PROXY" \
    LD_PRELOAD="$playback_preload" \
    "$FFPLAY" $screen_args $audio_args -hide_banner -stats -autoexit -ss "$resume_seconds" -vf "$video_filter" -i "$url"
  else
    unset HTTP_PROXY http_proxy HTTPS_PROXY https_proxy ALL_PROXY all_proxy
    HOME=/mnt/SDCARD \
    LD_PRELOAD="$playback_preload" \
    "$FFPLAY" $screen_args $audio_args -hide_banner -stats -autoexit -ss "$resume_seconds" -vf "$video_filter" -i "$url"
  fi
)

play_url() {
  url="$1"
  player_seek_seconds="${2:-0}"
  subtitle_file="${3:-}"
  restart_seek_enabled="${4:-0}"
  subtitle_id="${5:-}"
  absolute_start_seconds="${6:-$player_seek_seconds}"
  PLAYBACK_RC=1
  PLAYBACK_ELAPSED=0
  PLAYBACK_STARTUP=0
  PLAYBACK_PAUSED=0
  PAUSE_TRACKING_VALID=0
  PLAYBACK_VALID=0
  PLAYBACK_ERROR="Playback failed"
  playback_visible_started=0
  ffplay_log=/tmp/pocketcinema-ffplay.log
  pause_result=/tmp/pocketcinema-paused-seconds
  PAUSE_MONITOR_PID=""
  PLAYBACK_CONTROL_PID=""
  RESOURCE_MONITOR_PID=""
  rm -f "$ffplay_log" "$pause_result" "$PLAYBACK_CONTROL_FILE"
  log "ffplay launch url=$url resume_seconds=$player_seek_seconds subtitles=${subtitle_file:-none}"
  touch /tmp/stay_awake
  cd "$SYS_DIR" || return 1
  playback_started=$(date +%s)
  video_filter="hflip,vflip"
  # The app-local candidate inserts the selected Matroska track through
  # POCKETCINEMA_SUBTITLE_FILE so R1 can rebuild it with a new `si`.  Adding
  # the same filter here would render every cue twice.  Onion FFplay has no
  # such candidate hook, so the normal burn-in path remains unchanged.
  if [ -n "$subtitle_file" ] && [ "$CANDIDATE_PLAYER" != "1" ]; then
    video_filter="subtitles=$subtitle_file,hflip,vflip"
  fi
  seek_target="$absolute_start_seconds"
  current_url="$url"
  first_ready=1
  while :; do
    rm -f "$PLAYBACK_CONTROL_FILE"
    run_ffplay "$video_filter" "$current_url" 0 "$aspect_mode" >"$ffplay_log" 2>&1 &
    ffplay_pid=$!
    if [ "$first_ready" = "1" ] && [ -x "$RESOURCE_MONITOR" ]; then
      if [ "$CANDIDATE_PLAYER" = "1" ]; then
        resource_player="app-local"
      else
        resource_player="onion"
      fi
      "$RESOURCE_MONITOR" "$BASE_DIR/logs/playback-resources.log" \
        "$ffplay_pid" "$resource_player" >>"$LOG_FILE" 2>&1 &
      RESOURCE_MONITOR_PID=$!
      log "resource monitor start pid=$RESOURCE_MONITOR_PID player_pid=$ffplay_pid"
    fi
    while kill -0 "$ffplay_pid" 2>/dev/null; do
      if grep -q 'SDL_SetVideoMode' "$ffplay_log"; then
        if [ "$first_ready" = "1" ]; then
          playback_visible_started=$(date +%s)
          PLAYBACK_STARTUP=$((playback_visible_started - playback_started))
          stop_loading
          log "ffplay video ready startup_seconds=$PLAYBACK_STARTUP"
          if [ -x "$PAUSE_MONITOR" ]; then
            "$PAUSE_MONITOR" "$pause_result" >>"$LOG_FILE" 2>&1 &
            PAUSE_MONITOR_PID=$!
            log "pause monitor start pid=$PAUSE_MONITOR_PID"
          else
            log "pause monitor unavailable"
          fi
          if [ "$restart_seek_enabled" = "1" ] \
            || [ "$restart_seek_enabled" = "true" ] \
            && [ -x "$PLAYBACK_CONTROL" ]; then
            "$PLAYBACK_CONTROL" "$PLAYBACK_CONTROL_FILE" "$BASE_DIR/logs/playback-input.log" >>"$LOG_FILE" 2>&1 &
            PLAYBACK_CONTROL_PID=$!
            log "playback control start pid=$PLAYBACK_CONTROL_PID"
          fi
          first_ready=0
        fi
        break
      fi
      sleep 1
    done
    restart_requested=0
    while kill -0 "$ffplay_pid" 2>/dev/null; do
      if [ "$restart_seek_enabled" = "1" ] || [ "$restart_seek_enabled" = "true" ]; then
        seek_delta=$(cat "$PLAYBACK_CONTROL_FILE" 2>/dev/null)
        rm -f "$PLAYBACK_CONTROL_FILE"
        case "$seek_delta" in
          aspect)
            touch /tmp/pocketcinema-aspect-request
            log "aspect request sent to candidate"
            ;;
          -600|-60|-10|10|60|600)
            seek_target=$((seek_target + seek_delta))
            [ "$seek_target" -lt 0 ] && seek_target=0
            current_url="$url?start_seconds=$seek_target"
            if [ "$FIELD_TEST" = "1" ] && [ -n "$subtitle_id" ]; then
              curl_request -fsS --max-time 60 -o "$subtitle_file" \
                "$SERVER_BASE/subtitle/$subtitle_id?format=matroska&offset_seconds=$seek_target" \
                2>>"$HTTP_ERROR_FILE" || true
            fi
            log "converted seek restart delta=$seek_delta target=$seek_target"
            restart_requested=1
            kill "$ffplay_pid" 2>/dev/null || true
            break
            ;;
        esac
      fi
      sleep 1
    done
    wait "$ffplay_pid"
    PLAYBACK_RC=$?
    if [ "$restart_requested" = "1" ]; then
      # The server tears down the previous bounded FFmpeg job asynchronously.
      # Give its single-job lock time to release before reopening the session.
      sleep 3
      continue
    fi
    break
  done
  stop_loading
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
  if [ -n "$PLAYBACK_CONTROL_PID" ]; then
    kill "$PLAYBACK_CONTROL_PID" 2>/dev/null || true
    wait "$PLAYBACK_CONTROL_PID" 2>/dev/null || true
    PLAYBACK_CONTROL_PID=""
  fi
  if [ -n "$RESOURCE_MONITOR_PID" ]; then
    kill "$RESOURCE_MONITOR_PID" 2>/dev/null || true
    wait "$RESOURCE_MONITOR_PID" 2>/dev/null || true
    RESOURCE_MONITOR_PID=""
  fi
  cat "$ffplay_log" >>"$LOG_FILE"
  if grep -q 'Input #0' "$ffplay_log" \
    && grep -q 'SDL_SetVideoMode' "$ffplay_log" \
    && ! grep -Eq 'HTTP error|Input/output error|partial file' "$ffplay_log"; then
    PLAYBACK_VALID=1
  fi
  if [ "$FIELD_TEST" = "1" ] \
    && grep -q 'Input #0' "$ffplay_log" \
    && grep -q 'SDL_SetVideoMode' "$ffplay_log" \
    && [ "$PLAYBACK_RC" -ne 0 ] 2>/dev/null; then
    log "field-test accepted intentional disconnect after video readiness"
    PLAYBACK_VALID=1
    PLAYBACK_RC=0
  fi
  if [ "$PLAYBACK_VALID" -ne 1 ] || [ "$PLAYBACK_RC" -ne 0 ] 2>/dev/null; then
    PLAYBACK_ERROR=$(classify_playback_error "$ffplay_log" "$PLAYBACK_RC")
    server_playback_error=$(playback_server_error "$url" || true)
    [ -n "$server_playback_error" ] && PLAYBACK_ERROR="$server_playback_error"
    log "playback failure rc=$PLAYBACK_RC reason=$PLAYBACK_ERROR"
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
  bottom="${3:-Up/Down move  A select  B back}"
  x_action_file="${4:-}"
  if [ -n "$x_action_file" ]; then
    rm -f "$x_action_file"
  fi
  log "select title=$title waiting for input debounce"
  sleep 1
  if [ -x "$SDL_SELECTOR" ]; then
    if [ "$file" = "/tmp/pocketcinema-home.tsv" ]; then
      selected=$(POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" cut -f1 "$file" | \
        POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" \
        POCKETSTREMIO_DYNAMIC_FIRST_ITEM_FILE="$SERVER_STATUS_FILE" \
        POCKETSTREMIO_SELECTOR_X_ACTION_FILE="$x_action_file" \
        "$SDL_SELECTOR" "$title" "$bottom")
    else
      selected=$(POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" cut -f1 "$file" | \
        POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" \
        POCKETSTREMIO_SELECTOR_X_ACTION_FILE="$x_action_file" \
        "$SDL_SELECTOR" "$title" "$bottom")
    fi
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

stop_server_monitor() {
  if [ -n "$SERVER_MONITOR_PID" ] \
    && kill -0 "$SERVER_MONITOR_PID" 2>/dev/null; then
    kill "$SERVER_MONITOR_PID" 2>/dev/null || true
    wait "$SERVER_MONITOR_PID" 2>/dev/null || true
  fi
  SERVER_MONITOR_PID=""
}

write_server_status() {
  status_value="$1"
  status_temp="$SERVER_STATUS_FILE.tmp"
  printf '%s\n' "$status_value" >"$status_temp" && mv "$status_temp" "$SERVER_STATUS_FILE"
}

write_server_route() {
  route_name="$1"
  route_server="$2"
  route_proxy="$3"
  route_temp="$SERVER_ROUTE_FILE.tmp"
  printf '%s\t%s\t%s\n' "$route_name" "$route_server" "$route_proxy" \
    >"$route_temp" && mv "$route_temp" "$SERVER_ROUTE_FILE"
}

clear_server_route() {
  rm -f "$SERVER_ROUTE_FILE"
  ACTIVE_ROUTE=""
}

sync_server_status() {
  [ -f "$SERVER_STATUS_FILE" ] || return 0
  IFS= read -r server_status_value <"$SERVER_STATUS_FILE" || return 0
  SERVER_STATUS_TEXT="$server_status_value"
  case "$server_status_value" in
    "Server: Connected"* ) SERVER_REACHABLE=1 ;;
    "Server: Connecting...") SERVER_REACHABLE=2 ;;
    *) SERVER_REACHABLE=0 ;;
  esac
  if [ "$SERVER_REACHABLE" -eq 1 ] && [ -f "$SERVER_ROUTE_FILE" ]; then
    tab=$(printf '\t')
    IFS="$tab" read -r active_route active_server active_proxy <"$SERVER_ROUTE_FILE" || true
    case "$active_route" in
      local) ACTIVE_ROUTE="Local" ;;
      remote) ACTIVE_ROUTE="Remote" ;;
      legacy) ACTIVE_ROUTE="" ;;
      *) return 0 ;;
    esac
    [ -n "$active_server" ] && SERVER_BASE="$active_server"
    REQUEST_PROXY="$active_proxy"
  elif [ "$SERVER_REACHABLE" -eq 0 ]; then
    ACTIVE_ROUTE=""
  fi
}

validate_pcserver_url_with_proxy() {
  candidate_url="$1"
  candidate_proxy="$2"
  ROUTE_VALIDATION_CURL_RC=0
  route_status_file="/tmp/pocketcinema-route-status-$$.json"
  rm -f "$route_status_file"
  curl_request_with_proxy "$candidate_proxy" -fsS --connect-timeout 4 --max-time 7 \
    "$candidate_url/api/status" >"$route_status_file" 2>/dev/null
  route_curl_rc=$?
  if [ "$route_curl_rc" -ne 0 ]; then
    ROUTE_VALIDATION_CURL_RC=$route_curl_rc
    rm -f "$route_status_file"
    return 1
  fi
  "$JQ" -e '.status == "ok" and .service == "pocketcinema-server"' \
    "$route_status_file" >/dev/null 2>&1
  route_validation_rc=$?
  rm -f "$route_status_file"
  return "$route_validation_rc"
}

pocketcinema_probe_route() {
  probe_route="$1"
  probe_server="$2"
  probe_proxy="$3"
  POCKETCINEMA_ROUTE_PROBE_FAILURE="pcserver"
  validate_pcserver_url_with_proxy "$probe_server" "$probe_proxy" || {
    if [ "$probe_route" = remote ]; then
      case "$ROUTE_VALIDATION_CURL_RC" in
        5|7|28) POCKETCINEMA_ROUTE_PROBE_FAILURE="proxy" ;;
      esac
    fi
    return 1
  }
}

resolve_active_route() {
  if [ "$CONNECTION_PROFILE" -eq 1 ]; then
    resolve_mode="$CONNECTION_MODE"
  else
    resolve_mode=legacy
  fi
  pocketcinema_resolve_connection_route "$resolve_mode" "$LOCAL_PCSERVER" \
    "$REMOTE_PCSERVER" "$PROXY" "$LEGACY_SERVER_BASE" "$LEGACY_PROXY"
  resolve_rc=$?
  ROUTE_RESULT="$POCKETCINEMA_RESOLVED_ROUTE"
  ROUTE_SERVER="$POCKETCINEMA_RESOLVED_SERVER"
  ROUTE_PROXY="$POCKETCINEMA_RESOLVED_PROXY"
  ROUTE_FAILURE="$POCKETCINEMA_ROUTE_FAILURE"
  return "$resolve_rc"
}

route_offline_status() {
  case "$1" in
    remote_proxy_unavailable) printf '%s\n' "Server: Remote proxy unavailable" ;;
    remote_pcserver_unreachable) printf '%s\n' "Server: Remote PCServer unreachable" ;;
    local_pcserver_unreachable) printf '%s\n' "Server: Local PCServer unreachable" ;;
    *) printf '%s\n' "Server: Offline" ;;
  esac
}

ensure_active_route() {
  sync_server_status
  [ "$SERVER_REACHABLE" -eq 1 ] && [ -n "$SERVER_BASE" ] && return 0
  resolve_active_route || {
    SERVER_REACHABLE=0
    ACTIVE_ROUTE=""
    SERVER_STATUS_TEXT=$(route_offline_status "$ROUTE_FAILURE")
    clear_server_route
    write_server_status "$SERVER_STATUS_TEXT"
    return 1
  }
  SERVER_BASE="$ROUTE_SERVER"
  REQUEST_PROXY="$ROUTE_PROXY"
  case "$ROUTE_RESULT" in
    local) ACTIVE_ROUTE="Local"; SERVER_STATUS_TEXT="Server: Connected (Local)" ;;
    remote) ACTIVE_ROUTE="Remote"; SERVER_STATUS_TEXT="Server: Connected (Remote)" ;;
    *) ACTIVE_ROUTE=""; SERVER_STATUS_TEXT="Server: Connected" ;;
  esac
  SERVER_REACHABLE=1
  write_server_route "$ROUTE_RESULT" "$SERVER_BASE" "$REQUEST_PROXY"
  write_server_status "$SERVER_STATUS_TEXT"
}

start_server_monitor() {
  stop_server_monitor
  if [ "$SERVER_URL_VALID" -ne 1 ]; then
    SERVER_REACHABLE=0
    write_server_status "No PCServer connection configured"
    clear_server_route
    return 0
  fi

  monitor_interval="${POCKETCINEMA_STATUS_INTERVAL:-10}"
  case "$monitor_interval" in
    ''|*[!0-9]*|0) monitor_interval=10 ;;
  esac
  SERVER_REACHABLE=2
  clear_server_route
  write_server_status "Server: Connecting..."
  (
    monitor_child_pid=""
    stop_monitor_child() {
      trap - TERM INT HUP
      if [ -n "$monitor_child_pid" ] \
        && kill -0 "$monitor_child_pid" 2>/dev/null; then
        kill "$monitor_child_pid" 2>/dev/null || true
        wait "$monitor_child_pid" 2>/dev/null || true
      fi
      exit 0
    }
    trap stop_monitor_child TERM INT HUP
    while :; do
      if resolve_active_route; then
        write_server_route "$ROUTE_RESULT" "$ROUTE_SERVER" "$ROUTE_PROXY"
        case "$ROUTE_RESULT" in
          local) write_server_status "Server: Connected (Local)" ;;
          remote) write_server_status "Server: Connected (Remote)" ;;
          *) write_server_status "Server: Connected" ;;
        esac
      else
        clear_server_route
        write_server_status "$(route_offline_status "$ROUTE_FAILURE")"
      fi
      sleep "$monitor_interval" &
      monitor_child_pid=$!
      wait "$monitor_child_pid" 2>/dev/null || true
      monitor_child_pid=""
    done
  ) &
  SERVER_MONITOR_PID=$!
  log "server status monitor start pid=$SERVER_MONITOR_PID server=$SERVER_BASE"
}

validate_pcserver_url() {
  candidate_url="$1"
  validate_pcserver_url_with_proxy "$candidate_url" "$REQUEST_PROXY"
}

save_server_base() {
  new_server_base="$1"
  config_temp="$CONFIG_FILE.tmp"
  mkdir -p "$BASE_DIR/config"
  if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" || return 1
  fi
  awk -v server_base="$new_server_base" '
    BEGIN { replaced = 0 }
    /^SERVER_BASE=/ {
      if (!replaced) {
        print "SERVER_BASE=" server_base
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) print "SERVER_BASE=" server_base
    }
  ' "$CONFIG_FILE" 2>/dev/null >"$config_temp" || {
    printf 'SERVER_BASE=%s\n' "$new_server_base" >"$config_temp" || return 1
  }
  mv "$config_temp" "$CONFIG_FILE" || return 1
  chmod 644 "$CONFIG_FILE"
}

proxy_display_value() {
  if [ -n "$PROXY" ]; then
    printf '%s' "${PROXY#http://}"
  else
    printf '%s' "Disabled"
  fi
}

save_http_proxy() {
  pocketcinema_save_http_proxy "$CONFIG_FILE" "$1"
}

activate_http_proxy() {
  new_proxy="$1"
  if ! save_http_proxy "$new_proxy"; then
    message "HTTP Proxy" "Could not save proxy setting"
    return 1
  fi
  if [ "$PROXY_ENV_OVERRIDE" -eq 1 ]; then
    message "HTTP Proxy" "Saved. Environment override remains active."
    return 0
  fi
  PROXY="$new_proxy"
  LEGACY_PROXY="$new_proxy"
  [ "$CONNECTION_PROFILE" -eq 1 ] || REQUEST_PROXY="$new_proxy"
  # Reuse the normal monitor so its next /api/status request uses this
  # transport, rather than leaving a result cached under the previous proxy.
  start_server_monitor
  if [ -n "$PROXY" ]; then
    log "saved HTTP proxy enabled"
    message "HTTP Proxy" "Proxy saved. Checking PCServer..."
  else
    log "saved HTTP proxy disabled"
    message "HTTP Proxy" "Proxy disabled. Direct connections only. Checking PCServer..."
  fi
}

http_proxy_flow() {
  while :; do
    current_proxy=$(proxy_display_value)
    default_proxy_display=${POCKETCINEMA_DEFAULT_HTTP_PROXY#http://}
    if [ -n "$PROXY" ]; then
      printf 'Edit HTTP proxy\nRestore default (%s)\nDisable proxy\nBack\n' \
        "$default_proxy_display" >/tmp/pocketcinema-proxy.tsv
    else
      printf 'Enable default (%s)\nEdit HTTP proxy\nBack\n' \
        "$default_proxy_display" >/tmp/pocketcinema-proxy.tsv
    fi
    proxy_action=$(select_from_file "HTTP proxy: $current_proxy" \
      /tmp/pocketcinema-proxy.tsv)
    case "$proxy_action" in
      "Edit HTTP proxy")
        proxy_initial="$PROXY"
        [ -n "$proxy_initial" ] || proxy_initial="$POCKETCINEMA_DEFAULT_HTTP_PROXY"
        raw_proxy=$(read_keyboard "$proxy_initial" "HTTP proxy host:port")
        raw_proxy=$(printf '%s' "$raw_proxy" | tr -d '\r\n')
        [ -n "$raw_proxy" ] || continue
        normalized_proxy=$(pocketcinema_normalize_http_proxy "$raw_proxy") || {
          message "HTTP Proxy" "Use HTTP host:port without credentials"
          continue
        }
        activate_http_proxy "$normalized_proxy"
        ;;
      "Enable default "*|"Restore default "*)
        activate_http_proxy "$POCKETCINEMA_DEFAULT_HTTP_PROXY"
        ;;
      "Disable proxy")
        printf 'Disable proxy\tclear\nCancel\tcancel\n' >/tmp/pocketcinema-proxy.tsv
        clear_action=$(select_from_file "Disable HTTP proxy?" /tmp/pocketcinema-proxy.tsv)
        [ "$clear_action" = "Disable proxy" ] && activate_http_proxy ""
        ;;
      *) return 0 ;;
    esac
  done
}

save_audio_gain() {
  new_audio_gain="$1"
  config_temp="$CONFIG_FILE.tmp"
  mkdir -p "$BASE_DIR/config"
  if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" || return 1
  fi
  awk -v audio_gain="$new_audio_gain" '
    BEGIN { replaced = 0 }
    /^AUDIO_GAIN=/ {
      if (!replaced) {
        print "AUDIO_GAIN=" audio_gain
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) print "AUDIO_GAIN=" audio_gain
    }
  ' "$CONFIG_FILE" 2>/dev/null >"$config_temp" || {
    printf 'AUDIO_GAIN=%s\n' "$new_audio_gain" >"$config_temp" || return 1
  }
  mv "$config_temp" "$CONFIG_FILE" || return 1
  chmod 644 "$CONFIG_FILE"
}

save_max_subtitles_per_language() {
  new_max_subtitles="$1"
  config_temp="$CONFIG_FILE.tmp"
  mkdir -p "$BASE_DIR/config"
  if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" || return 1
  fi
  awk -v max_subtitles="$new_max_subtitles" '
    BEGIN { replaced = 0 }
    /^MAX_SUBTITLES_PER_LANGUAGE=/ {
      if (!replaced) {
        print "MAX_SUBTITLES_PER_LANGUAGE=" max_subtitles
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) print "MAX_SUBTITLES_PER_LANGUAGE=" max_subtitles
    }
  ' "$CONFIG_FILE" 2>/dev/null >"$config_temp" || {
    printf 'MAX_SUBTITLES_PER_LANGUAGE=%s\n' "$new_max_subtitles" >"$config_temp" || return 1
  }
  mv "$config_temp" "$CONFIG_FILE" || return 1
  chmod 644 "$CONFIG_FILE"
}

save_subtitle_font_scale() {
  new_subtitle_font_scale="$1"
  config_temp="$CONFIG_FILE.tmp"
  mkdir -p "$BASE_DIR/config"
  if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" || return 1
  fi
  awk -v subtitle_font_scale="$new_subtitle_font_scale" '
    BEGIN { replaced = 0 }
    /^SUBTITLE_FONT_SCALE=/ {
      if (!replaced) {
        print "SUBTITLE_FONT_SCALE=" subtitle_font_scale
        replaced = 1
      }
      next
    }
    { print }
    END {
      if (!replaced) print "SUBTITLE_FONT_SCALE=" subtitle_font_scale
    }
  ' "$CONFIG_FILE" 2>/dev/null >"$config_temp" || {
    printf 'SUBTITLE_FONT_SCALE=%s\n' "$new_subtitle_font_scale" >"$config_temp" || return 1
  }
  mv "$config_temp" "$CONFIG_FILE" || return 1
  chmod 644 "$CONFIG_FILE"
}

subtitle_font_scale_flow() {
  printf '1.0x\t1.0\n1.25x\t1.25\n1.5x (default)\t1.5\n2.0x\t2.0\n2.5x\t2.5\n3.0x\t3.0\nBack\tback\n' \
    >/tmp/pocketcinema-subtitle-font-scale.tsv
  selected_scale=$(select_from_file "Subtitle size (current ${SUBTITLE_FONT_SCALE}x)" \
    /tmp/pocketcinema-subtitle-font-scale.tsv)
  [ -n "$selected_scale" ] || return 0
  tab=$(printf '\t')
  scale_line=$(grep -F "$selected_scale$tab" /tmp/pocketcinema-subtitle-font-scale.tsv | head -n 1)
  new_subtitle_font_scale=$(printf '%s' "$scale_line" | cut -f2)
  [ "$new_subtitle_font_scale" = "back" ] && return 0
  case "$new_subtitle_font_scale" in
    1.0|1.25|1.5|2.0|2.5|3.0) ;;
    *) return 1 ;;
  esac
  if ! save_subtitle_font_scale "$new_subtitle_font_scale"; then
    message "PocketCinema Settings" "Could not save subtitle size"
    return 1
  fi
  if [ "$SUBTITLE_FONT_SCALE_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketCinema Settings" "Saved. Environment override remains active."
    return 0
  fi
  SUBTITLE_FONT_SCALE="$new_subtitle_font_scale"
  log "saved subtitle font scale=$SUBTITLE_FONT_SCALE"
  message "PocketCinema Settings" "Subtitle size set to ${SUBTITLE_FONT_SCALE}x"
}

max_subtitles_per_language_flow() {
  printf '1 track per language\t1\n2 tracks per language\t2\n3 tracks per language\t3\nBack\tback\n' \
    >/tmp/pocketcinema-max-subtitles.tsv
  selected_max=$(select_from_file "Matroska subtitle tracks (current $MAX_SUBTITLES_PER_LANGUAGE)" \
    /tmp/pocketcinema-max-subtitles.tsv)
  [ -n "$selected_max" ] || return 0
  tab=$(printf '\t')
  max_line=$(grep -F "$selected_max$tab" /tmp/pocketcinema-max-subtitles.tsv | head -n 1)
  new_max_subtitles=$(printf '%s' "$max_line" | cut -f2)
  [ "$new_max_subtitles" = "back" ] && return 0
  if ! save_max_subtitles_per_language "$new_max_subtitles"; then
    message "PocketCinema Settings" "Could not save subtitle track limit"
    return 1
  fi
  if [ "$MAX_SUBTITLES_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketCinema Settings" "Saved. Environment override remains active."
    return 0
  fi
  MAX_SUBTITLES_PER_LANGUAGE="$new_max_subtitles"
  log "saved Matroska subtitle track limit=$MAX_SUBTITLES_PER_LANGUAGE"
  message "PocketCinema Settings" "Matroska subtitles set to $MAX_SUBTITLES_PER_LANGUAGE per language"
}

audio_gain_flow() {
  printf '100%% (normal)\t1\n125%%\t1.25\n150%%\t1.5\n175%%\t1.75\n200%% (louder)\t2\nBack\tback\n' \
    >/tmp/pocketcinema-audio-gain.tsv
  selected_gain=$(select_from_file "Audio gain (current ${AUDIO_GAIN}x)" /tmp/pocketcinema-audio-gain.tsv)
  [ -n "$selected_gain" ] || return 0
  tab=$(printf '\t')
  gain_line=$(grep -F "$selected_gain$tab" /tmp/pocketcinema-audio-gain.tsv | head -n 1)
  new_audio_gain=$(printf '%s' "$gain_line" | cut -f2)
  [ "$new_audio_gain" = "back" ] && return 0
  if ! save_audio_gain "$new_audio_gain"; then
    message "PocketCinema Settings" "Could not save audio gain"
    return 1
  fi
  if [ "$AUDIO_GAIN_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketCinema Settings" "Saved. Environment override remains active."
    return 0
  fi
  AUDIO_GAIN="$new_audio_gain"
  log "saved audio gain=$AUDIO_GAIN"
  message "PocketCinema Settings" "Audio gain set to ${AUDIO_GAIN}x for the next video"
}

save_language_preferences() {
  language_kind="$1"
  new_languages="$2"
  new_fallback="$3"
  case "$language_kind" in
    audio)
      languages_key=AUDIO_LANGUAGES
      fallback_key=AUDIO_FALLBACK
      ;;
    subtitle)
      languages_key=SUBTITLE_LANGUAGES
      fallback_key=SUBTITLE_FALLBACK
      ;;
    *) return 1 ;;
  esac
  config_temp="$CONFIG_FILE.tmp"
  mkdir -p "$BASE_DIR/config"
  if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak" || return 1
  fi
  awk -v languages_key="$languages_key" -v languages="$new_languages" \
      -v fallback_key="$fallback_key" -v fallback="$new_fallback" '
    BEGIN { replaced_languages = 0; replaced_fallback = 0 }
    index($0, languages_key "=") == 1 {
      if (!replaced_languages) {
        print languages_key "=" languages
        replaced_languages = 1
      }
      next
    }
    index($0, fallback_key "=") == 1 {
      if (!replaced_fallback) {
        print fallback_key "=" fallback
        replaced_fallback = 1
      }
      next
    }
    { print }
    END {
      if (!replaced_languages) print languages_key "=" languages
      if (!replaced_fallback) print fallback_key "=" fallback
    }
  ' "$CONFIG_FILE" 2>/dev/null >"$config_temp" || {
    printf '%s=%s\n%s=%s\n' "$languages_key" "$new_languages" \
      "$fallback_key" "$new_fallback" >"$config_temp" || return 1
  }
  mv "$config_temp" "$CONFIG_FILE" || return 1
  chmod 644 "$CONFIG_FILE"
}

normalize_language_order() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | \
    sed 's/[[:space:];][[:space:];]*/,/g; s/,,*/,/g; s/^,//; s/,$//'
}

write_language_catalog() {
  cat > /tmp/pocketcinema-language-catalog.tsv <<'EOF'
Afrikaans	afr
Albanian	sqi
Arabic	ara
Armenian	hye
Azerbaijani	aze
Basque	eus
Belarusian	bel
Bengali	ben
Bosnian	bos
Bulgarian	bul
Catalan	cat
Chinese	zho
Croatian	hrv
Czech	ces
Danish	dan
Dutch	nld
English	eng
Estonian	est
Filipino	fil
Finnish	fin
French	fra
Georgian	kat
German	deu
Greek	ell
Hebrew	heb
Hindi	hin
Hungarian	hun
Icelandic	isl
Indonesian	ind
Italian	ita
Japanese	jpn
Korean	kor
Latvian	lav
Lithuanian	lit
Macedonian	mkd
Malay	msa
Malayalam	mal
Marathi	mar
Norwegian	nor
Persian	fas
Polish	pol
Portuguese	por
Romanian	ron
Russian	rus
Serbian	srp
Slovak	slk
Slovenian	slv
Spanish	spa
Swahili	swa
Swedish	swe
Tamil	tam
Telugu	tel
Thai	tha
Turkish	tur
Ukrainian	ukr
Urdu	urd
Vietnamese	vie
Welsh	cym
EOF
}

language_order_names() {
  order="$1"
  write_language_catalog
  awk -F '\t' -v order="$order" '
    { names[$2] = $1 }
    END {
      count = split(order, codes, ",")
      for (i = 1; i <= count; i++) {
        if (i > 1) printf " > "
        if (codes[i] == "und") printf "Unverified"
        else printf "%s", (codes[i] in names ? names[codes[i]] : codes[i])
      }
      print ""
    }
  ' /tmp/pocketcinema-language-catalog.tsv
}

language_fallback_label() {
  case "$1:$2" in
    audio:ask) printf 'Ask when unavailable' ;;
    audio:first) printf 'Use first verified track' ;;
    audio:stop) printf 'Stop and report' ;;
    subtitle:ask) printf 'Ask when unavailable' ;;
    subtitle:none) printf 'Use no subtitles' ;;
    *) printf '%s' "$2" ;;
  esac
}

reorder_language_order() {
  reorder_order="$1"
  reorder_selected="$2"
  reorder_target="$3"
  printf '%s\n' "$reorder_order" | awk -F, \
    -v selected="$reorder_selected" -v target="$reorder_target" '
    {
      count = split($0, codes, ",")
      output = ""
      position = 0
      for (i = 1; i <= count; i++) {
        if (codes[i] == selected) continue
        position++
        if (position == target) {
          if (output != "") output = output ","
          output = output selected
        }
        if (output != "") output = output ","
        output = output codes[i]
      }
      if (position < target) {
        if (output != "") output = output ","
        output = output selected
      }
      print output
    }
  '
}

change_language_priority_flow() {
  priority_kind="$1"
  priority_order="$2"
  priority_name="$3"
  while :; do
    write_language_catalog
    awk -F '\t' -v order="$priority_order" '
      BEGIN { count = split(order, codes, ",") }
      { names[$2] = $1 }
      END {
        for (i = 1; i <= count; i++) {
          name = (codes[i] in names ? names[codes[i]] : codes[i])
          printf "%s\t%s\n", i ". " name, codes[i]
        }
        print "Done\tdone"
      }
    ' /tmp/pocketcinema-language-catalog.tsv \
      >/tmp/pocketcinema-language-choices.tsv
    selected_language=$(select_from_file "Change $priority_name order" \
      /tmp/pocketcinema-language-choices.tsv)
    [ -n "$selected_language" ] || return 0
    [ "$selected_language" = "Done" ] && return 0
    tab=$(printf '\t')
    selected_line=$(grep -F "$selected_language$tab" \
      /tmp/pocketcinema-language-choices.tsv | head -n 1)
    selected_code=$(printf '%s' "$selected_line" | cut -f2)
    [ -n "$selected_code" ] || continue
    current_position=$(printf '%s\n' "$priority_order" | awk -F, \
      -v selected="$selected_code" '{ for (i = 1; i <= NF; i++) if ($i == selected) print i }')
    printf '%s\n' "$priority_order" | awk -F, \
      -v current="$current_position" '
      {
        count = NF
        for (i = 1; i <= count; i++) {
          if (i == current) printf "* Priority %d (current)\t%d\n", i, i
          else printf "Priority %d\t%d\n", i, i
        }
      }
    ' >/tmp/pocketcinema-language-order.tsv
    selected_target=$(select_from_file "Place $selected_language" \
      /tmp/pocketcinema-language-order.tsv)
    [ -n "$selected_target" ] || continue
    target_line=$(grep -F "$selected_target$tab" \
      /tmp/pocketcinema-language-order.tsv | head -n 1)
    target_position=$(printf '%s' "$target_line" | cut -f2)
    case "$target_position" in
      1|2|3|4|5) ;;
      *) continue ;;
    esac
    new_priority_order=$(reorder_language_order "$priority_order" \
      "$selected_code" "$target_position")
    save_active_language_preferences "$priority_kind" "$new_priority_order" \
      "$current_fallback" || return 1
    priority_order="$new_priority_order"
  done
}

save_active_language_preferences() {
  active_kind="$1"
  active_languages="$2"
  active_fallback="$3"
  if ! save_language_preferences "$active_kind" "$active_languages" "$active_fallback"; then
    message "PocketCinema Settings" "Could not save language preference"
    return 1
  fi
  if [ "$active_kind" = "audio" ]; then
    if [ "$AUDIO_LANGUAGE_ENV_OVERRIDE" -eq 1 ]; then
      message "PocketCinema Settings" "Saved. Environment override remains active."
      return 0
    fi
    AUDIO_LANGUAGES="$active_languages"
    AUDIO_FALLBACK="$active_fallback"
    log "saved audio languages=${AUDIO_LANGUAGES:-manual} fallback=$AUDIO_FALLBACK"
  else
    if [ "$SUBTITLE_LANGUAGE_ENV_OVERRIDE" -eq 1 ]; then
      message "PocketCinema Settings" "Saved. Environment override remains active."
      return 0
    fi
    SUBTITLE_LANGUAGES="$active_languages"
    SUBTITLE_FALLBACK="$active_fallback"
    log "saved subtitle languages=${SUBTITLE_LANGUAGES:-manual} fallback=$SUBTITLE_FALLBACK"
  fi
}

language_preference_flow() {
  language_kind="$1"
  while :; do
    case "$language_kind" in
      audio)
        current_languages="$AUDIO_LANGUAGES"
        current_fallback="$AUDIO_FALLBACK"
        preference_name=Audio
        keyboard_title="Advanced audio codes"
        ;;
      subtitle)
        current_languages="$SUBTITLE_LANGUAGES"
        current_fallback="$SUBTITLE_FALLBACK"
        preference_name=Subtitles
        keyboard_title="Advanced subtitle codes"
        ;;
      *) return 1 ;;
    esac
    if [ -n "$current_languages" ]; then
      language_count=$(printf '%s\n' "$current_languages" | awk -F, '{print NF}')
      preference_title="$preference_name: $language_count selected"
    else
      language_count=0
      preference_title="$preference_name: manual"
    fi
    fallback_label=$(language_fallback_label "$language_kind" "$current_fallback")
    printf 'Change priority order\tchange\nAdd language\tadd\n' \
      >/tmp/pocketcinema-language-action.tsv
    if [ "$language_count" -gt 0 ]; then
      printf 'Remove language\tremove\n' >>/tmp/pocketcinema-language-action.tsv
    fi
    printf 'Fallback: %s\tfallback\nManual each playback\tmanual\nAdvanced: enter codes\tadvanced\nBack\tback\n' \
      "$fallback_label" >>/tmp/pocketcinema-language-action.tsv
    preference_action=$(select_from_file "$preference_title" \
      /tmp/pocketcinema-language-action.tsv)
    case "$preference_action" in
      "Change priority order")
        if [ -z "$current_languages" ]; then
          message "$preference_name languages" "Add languages before changing priority"
        else
          change_language_priority_flow "$language_kind" "$current_languages" \
            "$preference_name"
        fi
        ;;
      "Add language")
        if [ "$language_count" -ge 5 ]; then
          message "$preference_name languages" "Five languages are already selected"
          continue
        fi
        write_language_catalog
        awk -F '\t' -v order="$current_languages" '
          BEGIN {
            count = split(order, codes, ",")
            for (i = 1; i <= count; i++) selected[codes[i]] = 1
          }
          !($2 in selected) { print }
        ' /tmp/pocketcinema-language-catalog.tsv \
          >/tmp/pocketcinema-language-choices.tsv
        selected_language=$(select_from_file "Add $preference_name language" \
          /tmp/pocketcinema-language-choices.tsv)
        [ -n "$selected_language" ] || continue
        tab=$(printf '\t')
        selected_line=$(grep -F "$selected_language$tab" \
          /tmp/pocketcinema-language-choices.tsv | head -n 1)
        selected_code=$(printf '%s' "$selected_line" | cut -f2)
        [ -n "$selected_code" ] || continue
        if [ -n "$current_languages" ]; then
          new_languages="$current_languages,$selected_code"
        else
          new_languages="$selected_code"
        fi
        save_active_language_preferences "$language_kind" "$new_languages" \
          "$current_fallback" || return 1
        ;;
      "Remove language")
        write_language_catalog
        awk -F '\t' -v order="$current_languages" '
          { names[$2] = $1 }
          END {
            count = split(order, codes, ",")
            for (i = 1; i <= count; i++) {
              name = (codes[i] in names ? names[codes[i]] : codes[i])
              print i ". " name "\t" codes[i]
            }
          }
        ' /tmp/pocketcinema-language-catalog.tsv \
          >/tmp/pocketcinema-language-choices.tsv
        selected_language=$(select_from_file "Remove $preference_name language" \
          /tmp/pocketcinema-language-choices.tsv)
        [ -n "$selected_language" ] || continue
        tab=$(printf '\t')
        selected_line=$(grep -F "$selected_language$tab" \
          /tmp/pocketcinema-language-choices.tsv | head -n 1)
        selected_code=$(printf '%s' "$selected_line" | cut -f2)
        [ -n "$selected_code" ] || continue
        new_languages=$(printf '%s\n' "$current_languages" | \
          awk -F, -v removed="$selected_code" '
            {
              separator = ""
              for (i = 1; i <= NF; i++) {
                if ($i != removed) {
                  printf "%s%s", separator, $i
                  separator = ","
                }
              }
              print ""
            }
          ')
        save_active_language_preferences "$language_kind" "$new_languages" \
          "$current_fallback" || return 1
        ;;
      "Fallback:"*)
        if [ "$language_kind" = "audio" ]; then
          printf 'Ask when unavailable\task\nUse first verified track\tfirst\nStop and report\tstop\nBack\tback\n' \
            >/tmp/pocketcinema-language-fallback.tsv
        else
          printf 'Ask when unavailable\task\nUse no subtitles\tnone\nBack\tback\n' \
            >/tmp/pocketcinema-language-fallback.tsv
        fi
        selected_fallback=$(select_from_file "$preference_name fallback" \
          /tmp/pocketcinema-language-fallback.tsv)
        [ -n "$selected_fallback" ] || continue
        tab=$(printf '\t')
        fallback_line=$(grep -F "$selected_fallback$tab" \
          /tmp/pocketcinema-language-fallback.tsv | head -n 1)
        new_fallback=$(printf '%s' "$fallback_line" | cut -f2)
        [ "$new_fallback" = "back" ] && continue
        case "$language_kind:$new_fallback" in
          audio:ask|audio:first|audio:stop|subtitle:ask|subtitle:none) ;;
          *) continue ;;
        esac
        save_active_language_preferences "$language_kind" "$current_languages" \
          "$new_fallback" || return 1
        ;;
      "Manual each playback")
        save_active_language_preferences "$language_kind" "" ask || return 1
        message "$preference_name languages" "Manual selection restored"
        ;;
      "Advanced: enter codes")
        raw_languages=$(read_keyboard "$current_languages" "$keyboard_title")
        [ -n "$raw_languages" ] || continue
        new_languages=$(normalize_language_order "$raw_languages")
        if ! valid_language_order "$new_languages"; then
          message "PocketCinema Settings" \
            "Use up to five unique 2-3 letter codes, separated by commas"
          continue
        fi
        save_active_language_preferences "$language_kind" "$new_languages" \
          "$current_fallback" || return 1
        ;;
      *) return 0 ;;
    esac
  done
}

audio_language_flow() {
  language_preference_flow audio
}

subtitle_language_flow() {
  language_preference_flow subtitle
}

activate_server_base() {
  new_server_base="$1"
  server_description="$2"
  if ! save_server_base "$new_server_base"; then
    message "PocketCinema Settings" "Could not save server setting"
    return 1
  fi
  if [ "$SERVER_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketCinema Settings" "Saved. Environment override remains active."
    return 0
  fi
  SERVER_BASE="$new_server_base"
  SERVER_URL_VALID=1
  SERVER_CONFIG_MESSAGE=""
  SERVER_REACHABLE=1
  start_server_monitor
  log "saved PCServer server=$SERVER_BASE"
  message "PocketCinema Settings" "Connected to $server_description"
}

server_status_flow() {
  sync_server_status
  if [ "$SERVER_URL_VALID" -ne 1 ]; then
    connection_setup_flow
  elif [ "$SERVER_REACHABLE" -eq 1 ]; then
    message "PocketCinema Server" "${SERVER_STATUS_TEXT#Server: }: $SERVER_BASE"
  elif [ "$SERVER_REACHABLE" -eq 2 ]; then
    message "PocketCinema Server" "Connecting to $SERVER_BASE"
  else
    settings_flow
  fi
}

discover_local_pcserver() {
  SETUP_PCSERVER_URL=""
  if [ ! -x "$DISCOVERY_CLIENT" ]; then
    message "PocketCinema Settings" "Discovery helper is unavailable"
    return 1
  fi

  start_loading "PocketCinema Settings" "Scanning for PCServer..."
  rm -f /tmp/pocketcinema-discovery.raw /tmp/pocketcinema-discovery.tsv
  "$DISCOVERY_CLIENT" >/tmp/pocketcinema-discovery.raw 2>>"$LOG_FILE"
  discovery_rc=$?
  : >/tmp/pocketcinema-discovery.tsv
  if [ "$discovery_rc" -eq 0 ]; then
    tab=$(printf '\t')
    while IFS="$tab" read -r discovered_name discovered_url discovered_network; do
      [ -n "$discovered_name" ] && [ -n "$discovered_url" ] \
        && [ -n "$discovered_network" ] || continue
      discovered_address=$(printf '%s' "$discovered_url" | sed 's|^[A-Za-z]*://||')
      short_name=$(printf '%s' "$discovered_name" | cut -c1-12)
      short_network=$(printf '%s' "$discovered_network" | cut -c1-10)
      printf 'Found: %s - %s - %s\t%s\n' "$short_name" "$discovered_address" \
        "$short_network" "$discovered_url" >>/tmp/pocketcinema-discovery.tsv
    done </tmp/pocketcinema-discovery.raw
  fi
  stop_loading

  if [ ! -s /tmp/pocketcinema-discovery.tsv ]; then
    message "PocketCinema Settings" "No PCServer found on the local network"
    return 1
  fi

  discovered_choice=$(select_from_file "Found local PCServer" /tmp/pocketcinema-discovery.tsv)
  [ -n "$discovered_choice" ] || return 0
  discovered_line=$(grep -F "$discovered_choice	" \
    /tmp/pocketcinema-discovery.tsv | head -n 1)
  discovered_url=$(printf '%s' "$discovered_line" | cut -f2)
  [ -n "$discovered_url" ] || {
    message "PocketCinema Settings" "Server selection failed"
    return 1
  }
  start_loading "Local connection" "Checking found PCServer..."
  if ! validate_pcserver_url_with_proxy "$discovered_url" ""; then
    stop_loading
    message "Local connection" "Found but local PCServer unreachable"
    return 1
  fi
  stop_loading
  SETUP_PCSERVER_URL="$discovered_url"
  log "local discovery found and validated"
}

read_setup_pcserver_url() {
  setup_initial="$1"
  setup_title="$2"
  SETUP_PCSERVER_URL=""
  [ -n "$setup_initial" ] || setup_initial="http://"
  manual_url=$(read_keyboard "$setup_initial" "$setup_title")
  manual_url=$(printf '%s' "$manual_url" | tr -d '\r\n')
  [ -n "$manual_url" ] || return 0
  manual_url=$(pocketcinema_normalize_pcserver_url "$manual_url") || {
    message "PocketCinema Settings" "Invalid PCServer URL"
    return 1
  }
  SETUP_PCSERVER_URL="$manual_url"
}

validate_setup_pcserver_url() {
  setup_kind="$1"
  setup_url="$2"
  setup_proxy="$3"
  start_loading "$setup_kind connection" "Checking PCServer..."
  validate_pcserver_url_with_proxy "$setup_url" "$setup_proxy"
  manual_rc=$?
  stop_loading
  if [ "$manual_rc" -ne 0 ]; then
    case "$setup_kind" in
      Remote)
        case "$ROUTE_VALIDATION_CURL_RC" in
          5|7|28) message "Remote connection" "Remote proxy unavailable" ;;
          *) message "Remote connection" "Remote PCServer unreachable" ;;
        esac
        ;;
      *) message "Local connection" "Local PCServer unreachable" ;;
    esac
    return 1
  fi
  return 0
}

choose_local_endpoint() {
  SETUP_PCSERVER_URL=""
  while :; do
    printf 'Scan local PCServer\nEnter local address\nBack\n' >/tmp/pocketcinema-connection.tsv
    local_action=$(select_from_file "Local connection" /tmp/pocketcinema-connection.tsv)
    case "$local_action" in
      "Scan local PCServer")
        discover_local_pcserver && return 0
        ;;
      "Enter local address")
        read_setup_pcserver_url "$LOCAL_PCSERVER" "Local PCServer URL" || continue
        [ -n "$SETUP_PCSERVER_URL" ] || continue
        validate_setup_pcserver_url Local "$SETUP_PCSERVER_URL" "" && return 0
        ;;
      *) return 1 ;;
    esac
  done
}

choose_remote_proxy() {
  SETUP_PROXY=""
  default_proxy_display=${POCKETCINEMA_DEFAULT_HTTP_PROXY#http://}
  current_proxy_display=$(proxy_display_value)
  while :; do
    printf 'Use current proxy (%s)\nUse default proxy (%s)\nEdit remote proxy\nBack\n' \
      "$current_proxy_display" "$default_proxy_display" >/tmp/pocketcinema-connection.tsv
    proxy_action=$(select_from_file "Remote connection" /tmp/pocketcinema-connection.tsv)
    case "$proxy_action" in
      "Use current proxy "*)
        [ -n "$PROXY" ] || {
          message "Remote connection" "Remote proxy unavailable"
          continue
        }
        SETUP_PROXY="$PROXY"
        return 0
        ;;
      "Use default proxy "*)
        SETUP_PROXY="$POCKETCINEMA_DEFAULT_HTTP_PROXY"
        return 0
        ;;
      "Edit remote proxy")
        raw_proxy=$(read_keyboard "${PROXY:-$POCKETCINEMA_DEFAULT_HTTP_PROXY}" "Remote proxy host:port")
        SETUP_PROXY=$(pocketcinema_normalize_http_proxy "$raw_proxy") || {
          message "Remote connection" "Use HTTP host:port without credentials"
          continue
        }
        return 0
        ;;
      *) return 1 ;;
    esac
  done
}

choose_remote_endpoint() {
  SETUP_PCSERVER_URL=""
  choose_remote_proxy || return 1
  read_setup_pcserver_url "$REMOTE_PCSERVER" "Remote PCServer URL" || return 1
  [ -n "$SETUP_PCSERVER_URL" ] || return 1
  validate_setup_pcserver_url Remote "$SETUP_PCSERVER_URL" "$SETUP_PROXY"
}

apply_connection_profile() {
  profile_local="$1"
  profile_remote="$2"
  profile_mode="$3"
  profile_proxy="$4"
  if ! pocketcinema_save_connection_profile "$CONFIG_FILE" "$profile_local" \
    "$profile_remote" "$profile_mode" "$profile_proxy"; then
    message "Connection settings" "Could not save connection profile"
    return 1
  fi
  if [ "$SERVER_ENV_OVERRIDE" -eq 1 ]; then
    message "Connection settings" "Saved. Server environment override remains active."
    return 0
  fi
  LOCAL_PCSERVER="$profile_local"
  REMOTE_PCSERVER="$profile_remote"
  CONNECTION_MODE="$profile_mode"
  PROXY="$profile_proxy"
  CONNECTION_PROFILE=1
  SERVER_BASE=""
  REQUEST_PROXY=""
  ACTIVE_ROUTE=""
  SERVER_URL_VALID=1
  SERVER_CONFIG_MESSAGE=""
  start_server_monitor
  message "Connection settings" "Profile saved. Checking PCServer..."
}

connection_setup_flow() {
  while :; do
    printf 'Local / same network\nRemote / away from home\nBoth / automatic\nBack\n' \
      >/tmp/pocketcinema-connection.tsv
    setup_action=$(select_from_file "PocketCinema setup" /tmp/pocketcinema-connection.tsv)
    case "$setup_action" in
      "Local / same network")
        choose_local_endpoint || continue
        apply_connection_profile "$SETUP_PCSERVER_URL" "" local "$PROXY"
        return $?
        ;;
      "Remote / away from home")
        message "Remote connection" "Use a separately configured network helper."
        choose_remote_endpoint || continue
        apply_connection_profile "" "$SETUP_PCSERVER_URL" remote "$SETUP_PROXY"
        return $?
        ;;
      "Both / automatic")
        message "Automatic connection" \
          "Both addresses will be saved.
Automatic prefers Local first.
If it is unavailable, Remote
uses the configured proxy." timed
        choose_local_endpoint || continue
        both_local="$SETUP_PCSERVER_URL"
        message "Remote connection" "Use a separately configured network helper."
        choose_remote_endpoint || continue
        apply_connection_profile "$both_local" "$SETUP_PCSERVER_URL" automatic "$SETUP_PROXY"
        return $?
        ;;
      *) return 0 ;;
    esac
  done
}

connection_mode_flow() {
  printf 'Automatic\tautomatic\nLocal only\tlocal\nRemote only\tremote\nBack\tback\n' \
    >/tmp/pocketcinema-connection.tsv
  selected_mode=$(select_from_file "Connection mode" /tmp/pocketcinema-connection.tsv)
  case "$selected_mode" in
    Automatic) new_mode=automatic ;;
    "Local only") new_mode=local ;;
    "Remote only") new_mode=remote ;;
    *) return 0 ;;
  esac
  apply_connection_profile "$LOCAL_PCSERVER" "$REMOTE_PCSERVER" "$new_mode" "$PROXY"
}

connection_profile_flow() {
  if [ "$CONNECTION_PROFILE" -eq 0 ]; then
    connection_setup_flow
    return
  fi
  while :; do
    local_display=${LOCAL_PCSERVER#http://}
    remote_display=${REMOTE_PCSERVER#http://}
    [ -n "$local_display" ] || local_display="Not set"
    [ -n "$remote_display" ] || remote_display="Not set"
    case "$CONNECTION_MODE" in
      automatic) mode_display="Automatic" ;;
      local) mode_display="Local only" ;;
      remote) mode_display="Remote only" ;;
    esac
    printf 'Edit local PCServer (%s)\nEdit remote PCServer (%s)\nMode: %s\nHTTP proxy\nBack\n' \
      "$local_display" "$remote_display" "$mode_display" >/tmp/pocketcinema-connection.tsv
    profile_action=$(select_from_file "Connection profile" /tmp/pocketcinema-connection.tsv)
    case "$profile_action" in
      "Edit local PCServer "*)
        choose_local_endpoint || continue
        new_mode="$CONNECTION_MODE"
        [ "$new_mode" = remote ] && new_mode=automatic
        apply_connection_profile "$SETUP_PCSERVER_URL" "$REMOTE_PCSERVER" "$new_mode" "$PROXY"
        ;;
      "Edit remote PCServer "*)
        choose_remote_endpoint || continue
        new_mode="$CONNECTION_MODE"
        [ "$new_mode" = local ] && new_mode=automatic
        apply_connection_profile "$LOCAL_PCSERVER" "$SETUP_PCSERVER_URL" "$new_mode" "$SETUP_PROXY"
        ;;
      "Mode: "*) connection_mode_flow ;;
      "HTTP proxy") http_proxy_flow ;;
      *) return 0 ;;
    esac
  done
}

settings_flow() {
  while :; do
    printf 'Connection setup\nConnection profile\nHTTP proxy\nAudio gain\nAudio languages\nSubtitle languages\nSubtitle size (%sx)\nMatroska subtitle limit\nBack\n' "$SUBTITLE_FONT_SCALE" \
      >/tmp/pocketcinema-settings.tsv
    settings_action=$(select_from_file "Settings" /tmp/pocketcinema-settings.tsv)
    case "$settings_action" in
      "Connection setup") connection_setup_flow ;;
      "Connection profile") connection_profile_flow ;;
      "HTTP proxy") http_proxy_flow ;;
      "Audio gain") audio_gain_flow ;;
      "Audio languages") audio_language_flow ;;
      "Subtitle languages") subtitle_language_flow ;;
      "Subtitle size ("*) subtitle_font_scale_flow ;;
      "Matroska subtitle limit") max_subtitles_per_language_flow ;;
      *) return 0 ;;
    esac
  done
}

home_flow() {
  while :; do
    sync_server_status
    if [ "$AUTO_FIRST" = "1" ]; then
      action="Search"
      log "auto-selected home action=Search"
    else
      if [ "$SERVER_REACHABLE" -eq 1 ]; then
        if [ -n "$ACTIVE_ROUTE" ]; then
          server_action="Server: Connected ($ACTIVE_ROUTE)"
        else
          server_action="Server: Connected"
        fi
      elif [ "$SERVER_REACHABLE" -eq 2 ]; then
        server_action="Server: Connecting..."
      elif [ "$SERVER_URL_VALID" -eq 1 ]; then
        server_action="${SERVER_STATUS_TEXT:-Server: Offline}"
      else
        server_action="No PCServer connection configured"
      fi
      printf '%s\nSearch\nLive TV\nQuick Resume\nContinue Watching\nStremio Account\nSettings\nExit\n' \
        "$server_action" >/tmp/pocketcinema-home.tsv
      action=$(select_from_file "PocketCinema" /tmp/pocketcinema-home.tsv)
    fi
    # The selector's first row can update while it is open. Synchronize again
    # before a chosen request so it uses the route that produced that status.
    sync_server_status
    case "$action" in
      Search)
        search_flow
        ;;
      "Live TV")
        live_tv_flow
        ;;
      "Quick Resume")
        quick_resume_flow
        ;;
      "Continue Watching")
        continue_watching_flow
        ;;
      "Stremio Account")
        account_flow
        ;;
      "Server: "*|"No PCServer connection configured")
        server_status_flow
        ;;
      Settings)
        settings_flow
        ;;
      *)
        return 0
        ;;
    esac
    [ "$AUTO_FIRST" = "1" ] && return 0
  done
}

live_tv_flow() {
  start_loading "PocketCinema" "Loading live channels..."
  api_get "/api/live-tv" 45 >/tmp/pocketcinema-live-tv.json
  live_tv_rc=$?
  stop_loading
  if [ "$live_tv_rc" -ne 0 ]; then
    message "PocketCinema" "Live TV unavailable"
    return 1
  fi
  live_tv_count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-live-tv.json)
  if [ "$live_tv_count" = "0" ]; then
    live_tv_error=$("$JQ" -r '.failures[0].message // "No live channels available"' /tmp/pocketcinema-live-tv.json)
    message "PocketCinema" "$live_tv_error"
    return 0
  fi

  "$JQ" -r '.items[] | "\(.title) [\(.source)]\t\(.id)\t\(.title)"' /tmp/pocketcinema-live-tv.json >/tmp/pocketcinema-live-tv.tsv
  while :; do
    selected=$(select_from_file "Live TV" /tmp/pocketcinema-live-tv.tsv)
    [ -z "$selected" ] && return 0
    line=$(grep -F "$selected	" /tmp/pocketcinema-live-tv.tsv | head -n 1)
    if [ -z "$line" ]; then
      log "live TV selection did not match selected=$selected"
      message "PocketCinema" "Selection failed"
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
    start_loading "PocketCinema" "Checking Stremio account..."
    api_get "/api/addons?refresh=1" 45 >/tmp/pocketcinema-addons.json
    account_rc=$?
    stop_loading
    if [ "$account_rc" -ne 0 ]; then
      message "PocketCinema" "Stremio account unavailable"
      return 1
    fi
    account_configured=$("$JQ" -r '.configured // false' /tmp/pocketcinema-addons.json)
    if [ "$account_configured" = "true" ]; then
      account_authenticated=$("$JQ" -r '.authenticated // false' /tmp/pocketcinema-addons.json)
      addon_count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-addons.json)
      if [ "$account_authenticated" = "true" ]; then
        printf 'Connected - %s addons\nRefresh\nBack\n' "$addon_count" >/tmp/pocketcinema-account.tsv
      else
        printf 'Account unavailable\nRefresh\nBack\n' >/tmp/pocketcinema-account.tsv
      fi
      account_action=$(select_from_file "Stremio Account" /tmp/pocketcinema-account.tsv)
      case "$account_action" in
        Refresh) continue ;;
        Back|'') return 0 ;;
        *) message "Stremio Account" "$account_action" ;;
      esac
      continue
    fi

    printf 'Connect Account\nBack\n' >/tmp/pocketcinema-account.tsv
    account_action=$(select_from_file "Stremio Account" /tmp/pocketcinema-account.tsv)
    case "$account_action" in
      "Connect Account") ;;
      *) return 0 ;;
    esac

    start_loading "PocketCinema" "Creating account link..."
    api_post_empty "/api/account/link" 30 >/tmp/pocketcinema-account-link.json
    link_rc=$?
    stop_loading
    if [ "$link_rc" -ne 0 ]; then
      message "PocketCinema" "Could not create account link"
      return 1
    fi
    account_link=$("$JQ" -r '.link // ""' /tmp/pocketcinema-account-link.json)
    [ -n "$account_link" ] || {
      message "PocketCinema" "Account link unavailable"
      return 1
    }

    while :; do
      qr_action=$(show_account_qr "$account_link")
      [ "$?" -eq 0 ] || return 0
      [ "$qr_action" = "refresh" ] || return 0
      start_loading "PocketCinema" "Checking account approval..."
      api_get "/api/account?poll=1" 30 >/tmp/pocketcinema-account.json
      poll_rc=$?
      stop_loading
      if [ "$poll_rc" -ne 0 ]; then
        message "PocketCinema" "Account approval check failed"
        return 1
      fi
      link_state=$("$JQ" -r '.link.state // "idle"' /tmp/pocketcinema-account.json)
      case "$link_state" in
        connected)
          message "PocketCinema" "Stremio account connected"
          break
          ;;
        waiting)
          account_link=$("$JQ" -r '.link.link // ""' /tmp/pocketcinema-account.json)
          [ -n "$account_link" ] || return 1
          ;;
        expired)
          message "PocketCinema" "Account link expired"
          return 0
          ;;
        *)
          message "PocketCinema" "Account link unavailable"
          return 1
          ;;
      esac
    done
  done
}

continue_watching_flow() {
  continue_action_file=/tmp/pocketcinema-continue-action
  while :; do
    if ! api_get "/api/continue-watching" >/tmp/pocketcinema-continue.json; then
      message "PocketCinema" "Continue Watching unavailable"
      return 1
    fi
    count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-continue.json)
    if [ "$count" = "0" ]; then
      message "PocketCinema" "Nothing to continue"
      return 0
    fi

    "$JQ" -r '.items[] | "\(.title) (\(.year // "????")) - \((.position_seconds / 60) | floor)m \((.position_seconds % 60) | floor)s\t\(.type)\t\(.id)\t\(.title)\t\(.year // "")\t\(.position_seconds // 0)"' /tmp/pocketcinema-continue.json >/tmp/pocketcinema-continue.tsv
    selected=$(select_from_file "Continue Watching" /tmp/pocketcinema-continue.tsv \
      "Up/Down move  A open  X remove  B back" "$continue_action_file")
    [ -z "$selected" ] && return 0
    line=$(grep -F "$selected	" /tmp/pocketcinema-continue.tsv | head -n 1)
    if [ -z "$line" ]; then
      log "continue selection did not match selected=$selected"
      message "PocketCinema" "Selection failed"
      return 1
    fi
    type=$(printf '%s' "$line" | cut -f2)
    id=$(printf '%s' "$line" | cut -f3)
    title=$(printf '%s' "$line" | cut -f4)
    year=$(printf '%s' "$line" | cut -f5)
    resume_seconds=$(printf '%s' "$line" | cut -f6)

    continue_action=$(head -n 1 "$continue_action_file" 2>/dev/null | tr -d '\r\n')
    rm -f "$continue_action_file"
    if [ "$continue_action" = "x" ]; then
      printf 'Remove\tremove\nCancel\tcancel\n' >/tmp/pocketcinema-remove-confirm.tsv
      remove_choice=$(select_from_file "Remove $title?" /tmp/pocketcinema-remove-confirm.tsv \
        "A confirm  B cancel")
      if [ "$remove_choice" != "Remove" ]; then
        log "continue watching remove canceled type=$type id=$id"
        continue
      fi
      if api_post_continue_remove "$type" "$id" >/dev/null; then
        log "continue watching removed type=$type id=$id"
        message "Continue Watching" "Removed"
        continue
      fi
      message "Continue Watching" "Could not remove item"
      return 1
    fi

    log "continue selected type=$type id=$id position_seconds=$resume_seconds"
    media_flow "$type" "$id" "$title" "$year" "$resume_seconds"
    return $?
  done
}

quick_resume_flow() {
  if [ ! -s "$LAST_PLAY_FILE" ]; then
    message "PocketCinema" "No recent stream to resume"
    return 0
  fi
  quick_server=$("$JQ" -r '.server // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_type=$("$JQ" -r '.type // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_id=$("$JQ" -r '.id // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_title=$("$JQ" -r '.title // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_year=$("$JQ" -r '.year // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_position=$("$JQ" -r '(.resume_seconds // 0) | floor' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_stream_id=$("$JQ" -r '.stream_id // ""' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_subtitle_id=$("$JQ" -r '.subtitle_id // "none"' "$LAST_PLAY_FILE" 2>/dev/null)
  quick_audio_stream_index=$("$JQ" -r '.audio_stream_index // 0' "$LAST_PLAY_FILE" 2>/dev/null)
  if [ "$quick_server" != "$SERVER_BASE" ] \
    || [ -z "$quick_type" ] || [ -z "$quick_id" ] || [ -z "$quick_stream_id" ]; then
    message "PocketCinema" "Quick Resume is unavailable for this server"
    return 0
  fi
  case "$quick_position" in
    ''|*[!0-9]*) quick_position=0 ;;
  esac
  log "quick resume type=$quick_type id=$quick_id position_seconds=$quick_position"
  play_selected_stream "$quick_type" "$quick_id" "$quick_title" "$quick_year" \
    "$quick_position" "$quick_stream_id" "$quick_subtitle_id" "$quick_audio_stream_index"
  quick_rc=$?
  if [ "$quick_rc" -ne 0 ]; then
    quick_error=$("$JQ" -r '.error // ""' /tmp/pocketcinema-play.json 2>/dev/null)
    if [ "$quick_error" = "stream_not_found" ] || [ "$quick_error" = "subtitle_not_found" ]; then
      rm -f "$LAST_PLAY_FILE"
      message "PocketCinema" "Saved stream expired; choose it again"
      media_flow "$quick_type" "$quick_id" "$quick_title" "$quick_year" "$quick_position"
      return $?
    fi
  fi
  return "$quick_rc"
}

search_flow() {
  if [ "${POCKETCINEMA_DRY_RUN:-0}" = "1" ]; then
    query="$DEFAULT_QUERY"
  else
    query="$(read_keyboard "$DEFAULT_QUERY" "PocketCinema Search")"
  fi
  [ -z "$query" ] && return 0
  log "search q=$query"

  encoded=$(printf '%s' "$query" | "$JQ" -sRr @uri)
  if ! api_get "/api/search?q=$encoded" >/tmp/pocketcinema-search.json; then
    log "search failed"
    message "PocketCinema" "Server unavailable"
    return 1
  fi

  count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-search.json)
  if [ "$count" = "0" ]; then
    message "PocketCinema" "No results"
    return 0
  fi

  "$JQ" -r '
    .items | to_entries[] |
    .value as $item |
    ($item.title // "") as $title |
    (if $item.type == "series" then "SERIES" else "MOVIE" end) as $type_label |
    (if ($title | length) > 25 then (($title[0:22]) + "...") else $title end) as $short |
    "\(.key + 1). \($short) (\($item.year // "????")) [\($type_label)]\t\($item.type)\t\($item.id)\t\($item.title)\t\($item.year // "")"
  ' /tmp/pocketcinema-search.json >/tmp/pocketcinema-results.tsv
  if [ "${POCKETCINEMA_DRY_RUN:-0}" = "1" ]; then
    head -n 5 /tmp/pocketcinema-results.tsv >> "$LOG_FILE"
    series_id=$("$JQ" -r '.items[] | select(.type == "series") | .id' /tmp/pocketcinema-search.json | head -n 1)
    if [ -n "$series_id" ]; then
      series_title=$("$JQ" -r --arg id "$series_id" '.items[] | select(.id == $id) | .title' /tmp/pocketcinema-search.json)
      series_year=$("$JQ" -r --arg id "$series_id" '.items[] | select(.id == $id) | (.year // "")' /tmp/pocketcinema-search.json)
      series_dry_run "$series_id" "$series_title" "$series_year"
    fi
    log "dry run stopping before interactive selection"
    return 0
  fi
  while :; do
    selected=$(select_from_file "Search: $query" /tmp/pocketcinema-results.tsv)
    if [ -z "$selected" ]; then
      log "result selection empty"
      if [ "$AUTO_FIRST" = "1" ]; then
        line=$(head -n 1 /tmp/pocketcinema-results.tsv)
        log "auto-selected first result"
      else
        return 10
      fi
    else
      line=$(grep -F "$selected	" /tmp/pocketcinema-results.tsv | head -n 1)
      if [ -z "$line" ]; then
        log "result selection did not match selected=$selected"
        message "PocketCinema" "Selection failed"
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
  if ! api_get "/api/meta/series/$dry_series_id" >/tmp/pocketcinema-series-meta.json; then
    log "series dry run metadata failed id=$dry_series_id"
    return 1
  fi
  write_season_choices /tmp/pocketcinema-series-meta.json /tmp/pocketcinema-seasons.tsv
  log "series dry run id=$dry_series_id title=$dry_series_title"
  cat /tmp/pocketcinema-seasons.tsv >>"$LOG_FILE"
  dry_season=$(head -n 1 /tmp/pocketcinema-seasons.tsv | cut -f2)
  if [ -n "$dry_season" ]; then
    write_episode_choices /tmp/pocketcinema-series-meta.json "$dry_season" /tmp/pocketcinema-episodes.tsv "$dry_series_year"
    cat /tmp/pocketcinema-episodes.tsv >>"$LOG_FILE"
  fi
}

series_flow() {
  series_id="$1"
  series_title="$2"
  series_year="$3"

  if ! api_get "/api/meta/series/$series_id" >/tmp/pocketcinema-series-meta.json; then
    message "PocketCinema" "Series details unavailable"
    return 1
  fi
  write_season_choices /tmp/pocketcinema-series-meta.json /tmp/pocketcinema-seasons.tsv
  if [ ! -s /tmp/pocketcinema-seasons.tsv ]; then
    message "PocketCinema" "No seasons available"
    return 0
  fi

  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      season_line=$(head -n 1 /tmp/pocketcinema-seasons.tsv)
      season_selected=$(printf '%s' "$season_line" | cut -f1)
      log "auto-selected first season selected=$season_selected"
    else
      season_selected=$(select_from_file "$series_title" /tmp/pocketcinema-seasons.tsv)
      [ -z "$season_selected" ] && return 10
      season_line=$(grep -F "$season_selected	" /tmp/pocketcinema-seasons.tsv | head -n 1)
      if [ -z "$season_line" ]; then
        log "season selection did not match selected=$season_selected"
        message "PocketCinema" "Selection failed"
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
  write_episode_choices /tmp/pocketcinema-series-meta.json "$episode_season" /tmp/pocketcinema-episodes.tsv "$episode_series_year"
  if [ ! -s /tmp/pocketcinema-episodes.tsv ]; then
    message "PocketCinema" "No episodes available"
    return 10
  fi

  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      episode_line=$(head -n 1 /tmp/pocketcinema-episodes.tsv)
      episode_selected=$(printf '%s' "$episode_line" | cut -f1)
      log "auto-selected first episode selected=$episode_selected"
    else
      episode_selected=$(select_from_file "Season $episode_season" /tmp/pocketcinema-episodes.tsv)
      [ -z "$episode_selected" ] && return 10
      episode_line=$(grep -F "$episode_selected	" /tmp/pocketcinema-episodes.tsv | head -n 1)
      if [ -z "$episode_line" ]; then
        log "episode selection did not match selected=$episode_selected"
        message "PocketCinema" "Selection failed"
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
  # Keep a failed provider/session out of this title's current picker.  The
  # server also caches deterministic incompatibilities; this handles transient
  # provider failures without forcing the user back through Continue Watching.
  FAILED_STREAM_IDS=""
  STREAM_RETRY_SUBTITLE_ID=""

  api_get "/api/meta/$type/$id" >/tmp/pocketcinema-meta.json || {
    message "PocketCinema" "Details unavailable"
    return 1
  }

  description=$("$JQ" -r '.description // ""' /tmp/pocketcinema-meta.json | cut -c 1-120)
  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      action="start"
      log "auto-selected action=start"
    else
      if [ "$saved_position" -gt 0 ] 2>/dev/null; then
        resume_minutes=$((saved_position / 60))
        resume_remainder=$((saved_position % 60))
        printf 'Resume at %sm %ss\tresume\nPlay from Start\tstart\nBack\tback\n' "$resume_minutes" "$resume_remainder" >/tmp/pocketcinema-actions.tsv
      else
        printf 'Play\tstart\nBack\tback\n' >/tmp/pocketcinema-actions.tsv
      fi
      action=$(select_from_file "$display_title ($year)" /tmp/pocketcinema-actions.tsv)
      [ -z "$action" ] && return 10
      action_line=$(grep -F "$action	" /tmp/pocketcinema-actions.tsv | head -n 1)
      action=$(printf '%s' "$action_line" | cut -f2)
      [ "$action" = "back" ] && return 10
    fi

    if [ "$action" = "resume" ]; then
      play_position="$saved_position"
    else
      play_position=0
    fi
    retry_subtitle_id=""
    while :; do
      streams_flow "$type" "$id" "$title" "$year" "$play_position" "$retry_subtitle_id"
      flow_rc=$?
      [ "$flow_rc" -eq 11 ] || break
      retry_subtitle_id="$STREAM_RETRY_SUBTITLE_ID"
      log "retrying stream picker after playback failure subtitle_id=${retry_subtitle_id:-none}"
    done
    [ "$flow_rc" -eq 10 ] || return "$flow_rc"
  done
}

select_audio_track() {
  stream_id="$1"
  track_count=$("$JQ" -r --arg id "$stream_id" '
    [.items[] | select(.id == $id) | (.compatibility.audio_tracks // [])[]] | length
  ' /tmp/pocketcinema-streams.json)
  if [ -n "$AUDIO_LANGUAGES" ]; then
    preferred_index=$("$JQ" -r --arg id "$stream_id" \
      --arg preferences "$AUDIO_LANGUAGES" '
      ($preferences | split(",") | map(ascii_downcase)) as $preferred |
      [.items[] | select(.id == $id) | (.compatibility.audio_tracks // [])[]] as $tracks |
      [range(0; $preferred | length) as $rank |
        $tracks[] | select((.language // "" | ascii_downcase) == $preferred[$rank]) |
        {rank:$rank, ordinal:.ordinal}] |
      sort_by(.rank, .ordinal) | (.[0].ordinal // "")
    ' /tmp/pocketcinema-streams.json)
    if [ -n "$preferred_index" ]; then
      log "preferred audio selected stream_id=$stream_id index=$preferred_index languages=$AUDIO_LANGUAGES"
      printf '%s' "$preferred_index"
      return 0
    fi
    case "$AUDIO_FALLBACK" in
      first)
        log "preferred audio unavailable; using first verified track stream_id=$stream_id"
        printf '0'
        return 0
        ;;
      stop)
        log "preferred audio unavailable stream_id=$stream_id languages=$AUDIO_LANGUAGES"
        printf 'unavailable'
        return 0
        ;;
    esac
  fi
  case "$track_count" in
    ''|0|1) printf '0'; return 0 ;;
  esac
  : > /tmp/pocketcinema-audio-tracks.tsv
  "$JQ" -r --arg id "$stream_id" '
    .items[] | select(.id == $id) | (.compatibility.audio_tracks // [])[] |
    ("Track " + ((.ordinal + 1)|tostring) + ": " +
      (if .language == "" then "language unknown" else .language end) +
      (if .title == "" then "" else " - " + .title end)) + "\t" + (.ordinal|tostring)
  ' /tmp/pocketcinema-streams.json >/tmp/pocketcinema-audio-tracks.tsv
  selected_audio=$(select_from_file "Select audio track" /tmp/pocketcinema-audio-tracks.tsv)
  [ -n "$selected_audio" ] || { printf 'back'; return 0; }
  grep -F "$selected_audio	" /tmp/pocketcinema-audio-tracks.tsv | head -n 1 | cut -f2
}

streams_flow() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  resume_seconds="${5:-0}"
  preferred_subtitle_id="${6:-}"
  log "resolve streams type=$type id=$id preflight=1"
  start_loading "PocketCinema" "Checking available streams..."
  api_get "/api/streams/$type/$id?preflight=1" 120 >/tmp/pocketcinema-streams.json
  stream_lookup_rc=$?
  stop_loading
  if [ "$stream_lookup_rc" -ne 0 ]; then
    message "PocketCinema" "Stream lookup failed"
    return 1
  fi

  source_filter=""
  audio_filter=""
  if [ "${POCKETCINEMA_DRY_RUN:-0}" != "1" ]; then
    if [ -n "$AUDIO_LANGUAGES" ]; then
      audio_filter=$("$JQ" -r --arg preferences "$AUDIO_LANGUAGES" \
        --arg failed_ids "$FAILED_STREAM_IDS" '
        ($preferences | split(",") | map(ascii_downcase)) as $preferred |
        [.items[] | select(.playable == true) | . as $stream
          | select(($failed_ids | contains("|" + $stream.id + "|")) | not)
          | (.compatibility.audio_languages // [])[] | ascii_downcase] as $available |
        [$preferred[] as $language
          | select($available | index($language)) | $language] |
        (.[0] // "")
      ' /tmp/pocketcinema-streams.json)
      if [ -n "$audio_filter" ]; then
        audio_filter_name=$(language_order_names "$audio_filter")
        log "using saved audio language=$audio_filter_name code=$audio_filter order=$AUDIO_LANGUAGES"
      else
        case "$AUDIO_FALLBACK" in
          stop)
            preferred_names=$(language_order_names "$AUDIO_LANGUAGES")
            log "no stream matches saved audio order=$AUDIO_LANGUAGES"
            message "PocketCinema" "No playable stream has verified $preferred_names audio"
            return 0
            ;;
          first)
            log "no stream matches saved audio order; allowing first verified track"
            ;;
          ask)
            log "no stream matches saved audio order; asking for available language"
            ;;
        esac
      fi
    fi

    printf 'All sources\tall\n' > /tmp/pocketcinema-source-filters.tsv
    "$JQ" -r --arg failed_ids "$FAILED_STREAM_IDS" --arg audio_filter "$audio_filter" '
      .items[] | select(.playable == true) | . as $stream
      | select(($failed_ids | contains("|" + $stream.id + "|")) | not)
      | select(($audio_filter == "") or (($stream.compatibility.audio_languages // []) | map(ascii_downcase) | any(. == ($audio_filter | ascii_downcase))))
      | (.source_label // .name) + "\t" + (.source_label // .name)
    ' \
      /tmp/pocketcinema-streams.json | sort -u >> /tmp/pocketcinema-source-filters.tsv
    selected_source=$(select_from_file "Stream source" /tmp/pocketcinema-source-filters.tsv)
    if [ -z "$selected_source" ]; then
      log "stream source selection canceled"
      return 10
    fi
    if [ -n "$selected_source" ] && [ "$selected_source" != "All sources" ]; then
      source_filter="$selected_source"
    fi

    if [ -z "$AUDIO_LANGUAGES" ] || { [ -z "$audio_filter" ] && [ "$AUDIO_FALLBACK" = "ask" ]; }; then
      printf 'All audio languages\t\n' > /tmp/pocketcinema-audio-filters.tsv
      "$JQ" -r '.items[] | select(.playable == true) | (.compatibility.audio_languages // [])[] | select(ascii_downcase != "und")' \
        /tmp/pocketcinema-streams.json | sort -u | while IFS= read -r language; do
          [ -n "$language" ] && printf '%s (verified)\t%s\n' "$language" "$language"
        done >> /tmp/pocketcinema-audio-filters.tsv
      verified_audio_count=$(wc -l </tmp/pocketcinema-audio-filters.tsv | tr -d ' ')
      if [ "$verified_audio_count" -gt 1 ]; then
        selected_audio=$(select_from_file "Audio language (verified tags)" /tmp/pocketcinema-audio-filters.tsv)
        if [ -n "$selected_audio" ]; then
          audio_filter=$(grep -F "$selected_audio	" /tmp/pocketcinema-audio-filters.tsv | head -n 1 | cut -f2)
        fi
      else
        log "no verified audio tags available; leaving streams unfiltered"
        message "Audio language" "No verified tags.
Choose stream."
      fi
    fi
  fi

  "$JQ" -r --arg failed_ids "$FAILED_STREAM_IDS" --arg source_filter "$source_filter" --arg audio_filter "$audio_filter" '
    .items[] | select(.playable == true) | . as $stream
    | select(($failed_ids | contains("|" + $stream.id + "|")) | not)
    | select(($source_filter == "") or (($stream.source_label // $stream.name) == $source_filter))
    | select(($audio_filter == "") or (($stream.compatibility.audio_languages // []) | map(ascii_downcase) | any(. == ($audio_filter | ascii_downcase))))
    | "\(if .playback_mode == "direct" then "[DIRECT] " elif .playback_mode == "convert" then "[CONVERT]" else "[CHECK]" end) \(.source_label // .name)\\n\(.release_label // "release metadata unavailable")\\n\((.compatibility.width // "?")|tostring)x\((.compatibility.height // "?")|tostring) \(.compatibility.video_codec // "?")/\(.compatibility.audio_codec // "?")\t\(.id)\t\(.description // "")"' /tmp/pocketcinema-streams.json >/tmp/pocketcinema-streams.tsv
  if [ ! -s /tmp/pocketcinema-streams.tsv ]; then
    stream_error=$("$JQ" -r '.failures[0].message // "No playable streams"' /tmp/pocketcinema-streams.json)
    log "no playable streams message=$stream_error"
    message "PocketCinema" "$stream_error"
    return 0
  fi

  while :; do
    if [ "$AUTO_FIRST" = "1" ]; then
      line=$(head -n 1 /tmp/pocketcinema-streams.tsv)
      selected=$(printf '%s' "$line" | cut -f1)
      log "auto-selected first stream selected=$selected"
    else
      selected=$(select_from_file "Select Stream" /tmp/pocketcinema-streams.tsv)
      [ -z "$selected" ] && return 10
      line=$(grep -F "$selected	" /tmp/pocketcinema-streams.tsv | head -n 1)
      if [ -z "$line" ]; then
        log "stream selection did not match selected=$selected"
        message "PocketCinema" "Selection failed"
        return 1
      fi
    fi
    stream_id=$(printf '%s' "$line" | cut -f2)
    log "selected stream_id=$stream_id name=$selected"

    stream_audio_codes=$("$JQ" -r --arg id "$stream_id" '
      [.items[] | select(.id == $id) | (.compatibility.audio_languages // [])[]]
      | join(",")
    ' /tmp/pocketcinema-streams.json)
    if [ -n "$stream_audio_codes" ]; then
      stream_audio_names=$(language_order_names "$stream_audio_codes" | cut -c 1-52)
    else
      stream_audio_names="Unverified"
    fi
    "$JQ" -r --arg id "$stream_id" '.items[] | select(.id == $id) |
      ("Source: " + (.source_label // .name)),
      ("Release: " + ((.release_label // "not provided") | .[0:42])),
      ("Media: " + ((.compatibility.width // "?")|tostring) + "x" + ((.compatibility.height // "?")|tostring) + " " + (.compatibility.video_codec // "?") + "/" + (.compatibility.audio_codec // "?")),
      ("Mode: " + ((.playback_mode // "check") | ascii_upcase))' /tmp/pocketcinema-streams.json |
      while IFS= read -r detail; do printf '%s\t%s\n' "$detail" "$detail"; done >/tmp/pocketcinema-stream-details.tsv
    printf 'Audio: %s\tAudio: %s\nUse this stream\tUse this stream\n' \
      "$stream_audio_names" "$stream_audio_names" \
      >>/tmp/pocketcinema-stream-details.tsv
    while :; do
      detail_choice=$(select_from_file "Stream Details" /tmp/pocketcinema-stream-details.tsv)
      [ "$detail_choice" = "Use this stream" ] && break
      [ -z "$detail_choice" ] && break
    done
    [ "$detail_choice" = "Use this stream" ] || continue
    audio_stream_index=$(select_audio_track "$stream_id")
    [ "$audio_stream_index" = "back" ] && continue
    if [ "$audio_stream_index" = "unavailable" ]; then
      message "PocketCinema" "Preferred audio language is unavailable"
      continue
    fi
    log "selected audio_stream_index=$audio_stream_index"

    if [ "$FIELD_TEST" = "1" ]; then
      subtitle_id=none
      log "field-test bypassed subtitle selection"
    elif [ "$MATROSKA_SUBTITLES" = "1" ]; then
      subtitle_id=none
      log "matroska mode bypassed subtitle selection"
    elif [ -n "$preferred_subtitle_id" ]; then
      subtitle_id="$preferred_subtitle_id"
      log "reused subtitle selection after playback failure subtitle_id=$subtitle_id"
    else
      subtitle_id=$(select_subtitle "$type" "$id" "$stream_id")
      [ "$subtitle_id" = "back" ] && continue
    fi
    play_selected_stream "$type" "$id" "$title" "$year" "$resume_seconds" \
      "$stream_id" "$subtitle_id" "$audio_stream_index"
    play_selected_rc=$?
    if [ "$play_selected_rc" -eq 10 ]; then
      return 10
    fi
    if [ "$play_selected_rc" -eq 12 ]; then
      continue
    fi
    if [ "$play_selected_rc" -ne 0 ]; then
      FAILED_STREAM_IDS="${FAILED_STREAM_IDS}|${stream_id}|"
      STREAM_RETRY_SUBTITLE_ID="$subtitle_id"
      log "stream failed; returning to filtered picker stream_id=$stream_id"
      return 11
    fi
    return 0
  done
}

fallback_matroska_playback() {
  fallback_reason="$1"
  fallback_type="$2"
  fallback_id="$3"
  fallback_title="$4"
  fallback_year="$5"
  fallback_resume_seconds="$6"
  fallback_stream_id="$7"
  fallback_audio_stream_index="${8:-0}"

  stop_loading
  rm -f "$FIELD_TEST_SUBTITLE_FILE"
  FIELD_TEST_SUBTITLE_FILE=""
  log "matroska setup fallback reason=$fallback_reason stream_id=$fallback_stream_id"
  case "$fallback_reason" in
    no-preferred-subtitles|server-subtitles_unavailable)
      fallback_choice=$(select_matroska_subtitle_fallback "$fallback_type" \
        "$fallback_id" "$fallback_stream_id")
      case "$fallback_choice" in
        none)
          fallback_previous_mode="$MATROSKA_SUBTITLES"
          MATROSKA_SUBTITLES=0
          log "matroska preferred subtitles unavailable; user selected none"
          play_selected_stream "$fallback_type" "$fallback_id" "$fallback_title" \
            "$fallback_year" "$fallback_resume_seconds" "$fallback_stream_id" \
            "none" "$fallback_audio_stream_index"
          fallback_rc=$?
          MATROSKA_SUBTITLES="$fallback_previous_mode"
          return "$fallback_rc"
          ;;
        english)
          fallback_previous_languages="$SUBTITLE_LANGUAGES"
          SUBTITLE_LANGUAGES=eng
          log "matroska preferred subtitles unavailable; user selected English"
          play_selected_stream "$fallback_type" "$fallback_id" "$fallback_title" \
            "$fallback_year" "$fallback_resume_seconds" "$fallback_stream_id" \
            "none" "$fallback_audio_stream_index"
          fallback_rc=$?
          SUBTITLE_LANGUAGES="$fallback_previous_languages"
          return "$fallback_rc"
          ;;
        back)
          log "matroska preferred subtitle fallback canceled"
          return 12
          ;;
        *)
          log "matroska preferred subtitle fallback failed"
          return 1
          ;;
      esac
      ;;
  esac
  fallback_subtitle_id=$(select_subtitle "$fallback_type" "$fallback_id" \
    "$fallback_stream_id")
  if [ "$fallback_subtitle_id" = "back" ]; then
    log "matroska setup fallback canceled"
    return 10
  fi

  log "matroska setup fallback selected normal subtitle_id=$fallback_subtitle_id"
  fallback_previous_mode="$MATROSKA_SUBTITLES"
  fallback_previous_field_test="$FIELD_TEST"
  MATROSKA_SUBTITLES=0
  FIELD_TEST=0
  play_selected_stream "$fallback_type" "$fallback_id" "$fallback_title" \
    "$fallback_year" "$fallback_resume_seconds" "$fallback_stream_id" \
    "$fallback_subtitle_id" "$fallback_audio_stream_index"
  fallback_rc=$?
  MATROSKA_SUBTITLES="$fallback_previous_mode"
  FIELD_TEST="$fallback_previous_field_test"
  return "$fallback_rc"
}

play_selected_stream() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  resume_seconds="$5"
  stream_id="$6"
  subtitle_id="$7"
  audio_stream_index="${8:-0}"
  if [ "$MATROSKA_SUBTITLES" = "1" ] \
    && { [ "$CANDIDATE_PLAYER" != "1" ] || [ ! -x "$FFPLAY" ]; }; then
    log "matroska candidate unavailable"
    message "PocketCinema" "Selectable subtitle player is unavailable"
    return 1
  fi
  if [ "$MATROSKA_SUBTITLES" = "1" ]; then
    start_loading "PocketCinema" "Preparing video and selectable subtitles..."
    subtitle_query="/api/subtitles/$type/$id?stream_id=$stream_id&all=1&matroska_subtitles=1&max_per_language=$MAX_SUBTITLES_PER_LANGUAGE"
    [ -n "$SUBTITLE_LANGUAGES" ] && subtitle_query="$subtitle_query&languages=$SUBTITLE_LANGUAGES"
    api_get "$subtitle_query" \
      >/tmp/pocketcinema-subtitles.json
    subtitle_lookup_rc=$?
    if [ "$subtitle_lookup_rc" -ne 0 ]; then
      log "matroska subtitle discovery failed"
      fallback_matroska_playback "subtitle-discovery" "$type" "$id" "$title" \
        "$year" "$resume_seconds" "$stream_id" "$audio_stream_index"
      return $?
    fi
    subtitle_count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-subtitles.json)
    if [ "$subtitle_count" -le 0 ] 2>/dev/null; then
      stop_loading
      subtitle_error=$("$JQ" -r '.unavailable_reason // "No preferred-language subtitles are available"' \
        /tmp/pocketcinema-subtitles.json 2>/dev/null)
      log "matroska subtitle discovery returned no supported tracks message=$subtitle_error"
      fallback_matroska_playback "no-preferred-subtitles" "$type" "$id" "$title" \
        "$year" "$resume_seconds" "$stream_id" "$audio_stream_index"
      return $?
    fi
    log "matroska subtitle discovery cached tracks=$subtitle_count"
  else
    start_loading "PocketCinema" "Checking compatibility..."
  fi
  api_post_play "$type" "$id" "$stream_id" "$subtitle_id" "$resume_seconds" "$audio_stream_index" >/tmp/pocketcinema-play.json
  play_setup_rc=$?
  if [ "$play_setup_rc" -ne 0 ]; then
    stop_loading
    play_error=$(playback_setup_error "$play_setup_rc")
    log "playback setup transport failure rc=$play_setup_rc reason=$play_error"
    message "PocketCinema" "$play_error"
    return 1
  fi
  play_url_value=$("$JQ" -r '.url // ""' /tmp/pocketcinema-play.json)
  if [ -z "$play_url_value" ]; then
    play_error_code=$("$JQ" -r '.error // ""' /tmp/pocketcinema-play.json 2>/dev/null)
    if [ "$MATROSKA_SUBTITLES" = "1" ]; then
      case "$play_error_code" in
        invalid_subtitle_mode|subtitle_not_found|subtitles_unavailable)
          log "matroska playback setup rejected error=$play_error_code"
          fallback_matroska_playback "server-$play_error_code" "$type" "$id" \
            "$title" "$year" "$resume_seconds" "$stream_id" \
            "$audio_stream_index"
          return $?
          ;;
      esac
    fi
    stop_loading
    play_error=$("$JQ" -r '.message // "Playback setup failed"' /tmp/pocketcinema-play.json 2>/dev/null)
    [ -n "$play_error" ] || play_error="PCServer returned an invalid playback response"
    log "playback setup rejected message=$play_error"
    message "PocketCinema" "$play_error"
    return 1
  fi
  save_last_play "$type" "$id" "$title" "$year" "$resume_seconds" "$stream_id" "$subtitle_id" "$audio_stream_index"
  server_field_test=$("$JQ" -r '.field_test // false' /tmp/pocketcinema-play.json)
  if [ "$FIELD_TEST" = "1" ] && [ "$server_field_test" != "true" ]; then
    stop_loading
    log "field-test rejected because server mode is disabled"
    message "PocketCinema" "Subtitle field test is disabled on the server"
    return 1
  fi
  server_matroska_subtitles=$("$JQ" -r '.matroska_subtitles // false' /tmp/pocketcinema-play.json)
  if [ "$MATROSKA_SUBTITLES" = "1" ] && [ "$server_matroska_subtitles" != "true" ]; then
    log "matroska subtitles rejected because server mode is disabled"
    fallback_matroska_playback "server-mode-disabled" "$type" "$id" "$title" \
      "$year" "$resume_seconds" "$stream_id" "$audio_stream_index"
    return $?
  fi
  duration_seconds=$("$JQ" -r '(.duration_seconds // 0) | floor' /tmp/pocketcinema-play.json)
  compatibility_status=$("$JQ" -r '.compatibility.status // "unknown"' /tmp/pocketcinema-play.json)
  compatibility_message=$("$JQ" -r '.compatibility.message // ""' /tmp/pocketcinema-play.json)
  log "media preflight status=$compatibility_status message=$compatibility_message"

  transcoded=$("$JQ" -r '.transcoded // false' /tmp/pocketcinema-play.json)
  server_seek_applied=$("$JQ" -r '.server_seek_applied // false' /tmp/pocketcinema-play.json)
  ffplay_resume_seconds="$resume_seconds"
  [ "$server_seek_applied" = "true" ] && ffplay_resume_seconds=0
  log "playback conversion=$transcoded subtitle_id=${subtitle_id:-none} server_seek=$server_seek_applied"

  FIELD_TEST_SUBTITLE_FILE=""
  if { [ "$FIELD_TEST" = "1" ] && [ -n "$subtitle_id" ] && [ "$subtitle_id" != "none" ]; } \
    || [ "$MATROSKA_SUBTITLES" = "1" ]; then
    FIELD_TEST_SUBTITLE_FILE="$BASE_DIR/experiments/ffplay/.field-test-subtitle-$$.mkv"
    subtitle_pack_url="$SERVER_BASE/subtitle/$subtitle_id?format=matroska&offset_seconds=$resume_seconds"
    if [ "$MATROSKA_SUBTITLES" = "1" ]; then
      subtitle_pack_url=$("$JQ" -r '.subtitle_pack_url // ""' /tmp/pocketcinema-play.json)
      track_count=$("$JQ" -r '(.subtitle_tracks // []) | length' /tmp/pocketcinema-play.json)
      log "matroska subtitle tracks=$track_count (use R1 to cycle)"
    fi
    if [ -z "$subtitle_pack_url" ] || ! curl_request -fsS --max-time 60 -o "$FIELD_TEST_SUBTITLE_FILE" \
      "$subtitle_pack_url" 2>>"$HTTP_ERROR_FILE"; then
      log "field-test subtitle download failed"
      rm -f "$FIELD_TEST_SUBTITLE_FILE"
      FIELD_TEST_SUBTITLE_FILE=""
      if [ "$MATROSKA_SUBTITLES" = "1" ]; then
        fallback_matroska_playback "subtitle-package-download" "$type" "$id" \
          "$title" "$year" "$resume_seconds" "$stream_id" \
          "$audio_stream_index"
        return $?
      fi
    elif [ ! -r "$FIELD_TEST_SUBTITLE_FILE" ] || [ ! -s "$FIELD_TEST_SUBTITLE_FILE" ]; then
      log "field-test subtitle handoff invalid path=$FIELD_TEST_SUBTITLE_FILE"
      rm -f "$FIELD_TEST_SUBTITLE_FILE"
      FIELD_TEST_SUBTITLE_FILE=""
      if [ "$MATROSKA_SUBTITLES" = "1" ]; then
        fallback_matroska_playback "subtitle-package-empty" "$type" "$id" \
          "$title" "$year" "$resume_seconds" "$stream_id" \
          "$audio_stream_index"
        return $?
      fi
    else
      field_test_subtitle_bytes=$(wc -c <"$FIELD_TEST_SUBTITLE_FILE" 2>/dev/null | tr -d ' ')
      log "field-test subtitle handoff ready bytes=$field_test_subtitle_bytes"
    fi
  fi

  log "playback url received"
  if [ "$MATROSKA_SUBTITLES" != "1" ]; then
    stop_loading
    if [ -n "$subtitle_id" ] && [ "$subtitle_id" != "none" ]; then
      start_loading "PocketCinema" \
        "Starting video... Subtitles are fixed; R1 switching is unavailable."
    else
      start_loading "PocketCinema" "Starting video..."
    fi
  fi
  playback_result=0
  nonseekable_mode=0
  [ "$FIELD_TEST" = "1" ] && nonseekable_mode=1
  [ "$MATROSKA_SUBTITLES" = "1" ] && nonseekable_mode=1
  if ! play_url "$play_url_value" "$ffplay_resume_seconds" "$FIELD_TEST_SUBTITLE_FILE" \
    "$nonseekable_mode" "$subtitle_id" "$resume_seconds"; then
    message "PocketCinema" "$PLAYBACK_ERROR"
    playback_result=1
  fi

  if [ "$type" = "tv" ]; then
    log "live playback ended without progress update"
    return "$playback_result"
  fi

  new_position=$((resume_seconds + PLAYBACK_ELAPSED))
  completed=false
  if [ "$duration_seconds" -gt 0 ] 2>/dev/null && [ $((new_position * 10)) -ge $((duration_seconds * 9)) ]; then
    completed=true
  fi
  if [ "$PLAYBACK_VALID" -eq 1 ] 2>/dev/null && [ "$PAUSE_TRACKING_VALID" -eq 1 ] 2>/dev/null && [ "$PLAYBACK_RC" -eq 0 ] 2>/dev/null && [ "$PLAYBACK_ELAPSED" -gt 0 ] 2>/dev/null; then
    if api_post_progress "$type" "$id" "$title" "$year" "$new_position" "$duration_seconds" "$completed" >/tmp/pocketcinema-progress.json; then
      log "progress saved position_seconds=$new_position duration_seconds=$duration_seconds completed=$completed"
      save_last_play "$type" "$id" "$title" "$year" "$new_position" "$stream_id" "$subtitle_id" "$audio_stream_index"
    else
      log "progress save failed"
    fi
  fi
  return "$playback_result"
}

select_matroska_subtitle_fallback() {
  fallback_type="$1"
  fallback_id="$2"
  fallback_stream_id="$3"
  fallback_preferred_names=$(language_order_names "$SUBTITLE_LANGUAGES")
  fallback_preferred_names=$(printf '%s' "$fallback_preferred_names" | cut -c 1-34)
  english_available=0
  case ",$SUBTITLE_LANGUAGES," in
    *,eng,*) ;;
    *)
      english_query="/api/subtitles/$fallback_type/$fallback_id?stream_id=$fallback_stream_id&all=1&matroska_subtitles=1&max_per_language=$MAX_SUBTITLES_PER_LANGUAGE&languages=eng"
      start_loading "PocketCinema" "Checking English subtitles..."
      if api_get "$english_query" >/tmp/pocketcinema-english-subtitles.json; then
        english_count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-english-subtitles.json)
        [ "$english_count" -gt 0 ] 2>/dev/null && english_available=1
      else
        log "English subtitle lookup failed"
      fi
      stop_loading
      ;;
  esac
  printf 'Continue with no subtitles\tnone\n' \
    >/tmp/pocketcinema-matroska-subtitle-fallback.tsv
  [ "$english_available" = "1" ] \
    && printf 'Use English subtitles\tenglish\n' \
      >>/tmp/pocketcinema-matroska-subtitle-fallback.tsv
  printf 'Back to streams\tback\n' \
    >>/tmp/pocketcinema-matroska-subtitle-fallback.tsv
  fallback_action=$(select_from_file "No $fallback_preferred_names subtitles found" \
    /tmp/pocketcinema-matroska-subtitle-fallback.tsv)
  case "$fallback_action" in
    "Continue with no subtitles") printf '%s' "none" ;;
    "Use English subtitles") printf '%s' "english" ;;
    *) printf '%s' "back" ;;
  esac
}

select_subtitle() {
  type="$1"
  id="$2"
  stream_id="$3"

  subtitle_all=0
  while :; do
    subtitle_query="/api/subtitles/$type/$id?stream_id=$stream_id"
    if [ -n "$SUBTITLE_LANGUAGES" ]; then
      subtitle_query="$subtitle_query&languages=$SUBTITLE_LANGUAGES"
    fi
    [ "$subtitle_all" = "1" ] && subtitle_query="$subtitle_query&all=1"
    start_loading "PocketCinema" "Loading subtitles..."
    api_get "$subtitle_query" >/tmp/pocketcinema-subtitles.json
    subtitle_lookup_rc=$?
    stop_loading
    if [ "$subtitle_lookup_rc" -ne 0 ]; then
      log "subtitle lookup failed"
      printf '%s' "none"
      return 0
    fi
    count=$("$JQ" -r '.count // 0' /tmp/pocketcinema-subtitles.json)
    other_count=$("$JQ" -r '.other_count // 0' /tmp/pocketcinema-subtitles.json)
    if [ "$AUTO_FIRST" = "1" ]; then
      log "auto-selected subtitles=none"
      printf '%s' "none"
      return 0
    fi
    if [ -n "$SUBTITLE_LANGUAGES" ] && [ "$subtitle_all" = "0" ]; then
      if [ "$count" -gt 0 ] 2>/dev/null; then
        subtitle_id=$("$JQ" -r '.items[0].id // "none"' \
          /tmp/pocketcinema-subtitles.json)
        subtitle_lang=$("$JQ" -r '.items[0].lang // ""' \
          /tmp/pocketcinema-subtitles.json)
        log "preferred subtitle selected id=$subtitle_id language=$subtitle_lang order=$SUBTITLE_LANGUAGES"
        printf '%s' "$subtitle_id"
        return 0
      fi
      if [ "$SUBTITLE_FALLBACK" = "none" ]; then
        log "preferred subtitle unavailable; using none order=$SUBTITLE_LANGUAGES"
        printf '%s' "none"
        return 0
      fi
    fi
    if [ "$count" = "0" ] && [ "$other_count" = "0" ]; then
      printf '%s' "none"
      return 0
    fi

    printf 'No subtitles\tnone\n' >/tmp/pocketcinema-subtitles.tsv
    "$JQ" -r '.items[] | "\(.name) [\(.lang)]\t\(.id)"' /tmp/pocketcinema-subtitles.json >>/tmp/pocketcinema-subtitles.tsv
    if [ "$subtitle_all" != "1" ] && [ "$other_count" -gt 0 ]; then
      if [ -n "$SUBTITLE_LANGUAGES" ]; then
        printf 'Show other preferred subtitles\tmore\n' >>/tmp/pocketcinema-subtitles.tsv
      else
        printf 'Show other English subtitles\tmore\n' >>/tmp/pocketcinema-subtitles.tsv
      fi
    fi
    selected=$(select_from_file "Select Subtitles" /tmp/pocketcinema-subtitles.tsv)
    if [ -z "$selected" ]; then
      printf '%s' "back"
      return 0
    fi
    line=$(grep -F "$selected	" /tmp/pocketcinema-subtitles.tsv | head -n 1)
    subtitle_id=$(printf '%s' "$line" | cut -f2)
    if [ "$subtitle_id" = "more" ]; then
      subtitle_all=1
      continue
    fi
    log "selected subtitle_id=$subtitle_id name=$selected scope=$subtitle_all"
    printf '%s' "$subtitle_id"
    return 0
  done
}

cd "$SYS_DIR" || exit 1
if [ -n "$REQUEST_PROXY" ]; then
  transport="proxy"
else
  transport="direct"
fi
log "PocketCinema UI start server=$SERVER_BASE transport=$transport"
log "preferences audio=${AUDIO_LANGUAGES:-manual}/$AUDIO_FALLBACK subtitles=${SUBTITLE_LANGUAGES:-manual}/$SUBTITLE_FALLBACK matroska_max=$MAX_SUBTITLES_PER_LANGUAGE"
if [ -n "$CONFIG_ERROR" ]; then
  log "configuration error=$CONFIG_ERROR"
  message "PocketCinema" "$CONFIG_ERROR"
  exit 1
fi
if [ "$SERVER_URL_VALID" -ne 1 ]; then
  connection_setup_flow
fi
start_server_monitor
home_flow
log "PocketCinema UI exit"
sync
