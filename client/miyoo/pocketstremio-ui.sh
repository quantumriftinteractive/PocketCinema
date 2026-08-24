#!/bin/sh

BASE_DIR=/mnt/SDCARD/App/PocketStremio
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
LOG_DIR="$BASE_DIR/logs"
LOG_FILE="$LOG_DIR/pocketstremio-ui.log"
PREVIOUS_LOG_FILE="$LOG_DIR/pocketstremio-ui.previous.log"
CONFIG_FILE="$BASE_DIR/config/pocketstremio.conf"
LAST_PLAY_FILE="$BASE_DIR/config/last-play.json"
HTTP_ERROR_FILE=/tmp/pocketstremio-http-error
SERVER_BASE="${POCKETSTREMIO_SERVER:-}"
SERVER_ENV_OVERRIDE=0
[ -n "${POCKETSTREMIO_SERVER:-}" ] && SERVER_ENV_OVERRIDE=1
PROXY="${POCKETSTREMIO_PROXY:-}"
AUTO_FIRST="${POCKETSTREMIO_AUTO_FIRST:-}"
DEFAULT_QUERY="${POCKETSTREMIO_DEFAULT_QUERY:-}"
AUDIO_GAIN="${POCKETSTREMIO_AUDIO_GAIN:-}"
AUDIO_GAIN_ENV_OVERRIDE=0
[ -n "${POCKETSTREMIO_AUDIO_GAIN:-}" ] && AUDIO_GAIN_ENV_OVERRIDE=1
CURL="$SYS_DIR/bin/curl"
JQ="$SYS_DIR/bin/jq"
KBINPUT="$SYS_DIR/bin/kbinput"
SHELLECT="$SYS_DIR/script/shellect.sh"
SDL_SELECTOR="$BASE_DIR/bin/pocketstremio-selector"
PAUSE_MONITOR="$BASE_DIR/bin/pocketstremio-pause-monitor"
PLAYBACK_CONTROL="$BASE_DIR/bin/pocketstremio-playback-control"
RESOURCE_MONITOR="$BASE_DIR/client/pocketstremio-resource-monitor.sh"
DISCOVERY_CLIENT="$BASE_DIR/bin/pocketstremio-discovery"
INFOPANEL="$SYS_DIR/bin/infoPanel"
FFPLAY="$SYS_DIR/bin/ffplay"
APP_LOCAL_PLAYER="${POCKETSTREMIO_APP_LOCAL_PLAYER:-1}"
FIELD_TEST="${POCKETSTREMIO_SUBTITLE_FIELD_TEST:-0}"
MATROSKA_SUBTITLES="${POCKETSTREMIO_MATROSKA_SUBTITLES:-}"
if [ -f "$BASE_DIR/config/ffplay-field-test.mode" ]; then
  FIELD_TEST=1
  rm -f "$BASE_DIR/config/ffplay-field-test.mode"
fi
if [ -f "$BASE_DIR/config/matroska-subtitles.mode" ]; then
  MATROSKA_SUBTITLES=1
  rm -f "$BASE_DIR/config/matroska-subtitles.mode"
fi
DISPLAY_SURFACE_TEST="${POCKETSTREMIO_DISPLAY_SURFACE_TEST:-0}"
if [ -f "$BASE_DIR/config/ffplay-display-surface-test.mode" ]; then
  DISPLAY_SURFACE_TEST=1
  rm -f "$BASE_DIR/config/ffplay-display-surface-test.mode"
fi
CANDIDATE_PLAYER=0
FIELD_TEST_LIB_DIR="$BASE_DIR/experiments/ffplay/lib"
FIELD_TEST_SUBTITLE_FILE=""
PADSP="$MIYOO_DIR/lib/libpadsp.so"
LOADING_PID=""
PAUSE_MONITOR_PID=""
PLAYBACK_CONTROL_PID=""
RESOURCE_MONITOR_PID=""
PLAYBACK_CONTROL_FILE=/tmp/pocketstremio-playback-control
CONFIG_ERROR=""
SERVER_CONFIG_MESSAGE=""
SERVER_URL_VALID=1
SERVER_REACHABLE=2
SERVER_MONITOR_PID=""
SERVER_STATUS_FILE=/tmp/pocketstremio-server-status
SERVER_STATUS_JSON=/tmp/pocketstremio-server-status.json
PLAYBACK_ERROR="Playback failed"
FAILED_STREAM_IDS=""
STREAM_RETRY_SUBTITLE_ID=""

mkdir -p "$LOG_DIR"
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
      DEFAULT_QUERY) [ -n "$DEFAULT_QUERY" ] || DEFAULT_QUERY="$config_value" ;;
      AUTO_FIRST) [ -n "$AUTO_FIRST" ] || AUTO_FIRST="$config_value" ;;
      AUDIO_GAIN) [ -n "$AUDIO_GAIN" ] || AUDIO_GAIN="$config_value" ;;
      POCKETSTREMIO_MATROSKA_SUBTITLES)
        [ -n "$MATROSKA_SUBTITLES" ] || MATROSKA_SUBTITLES="$config_value"
        ;;
      *) CONFIG_ERROR="Unknown setting: $config_key" ;;
    esac
  done <"$CONFIG_FILE"
}

load_config
AUTO_FIRST="${AUTO_FIRST:-0}"
DEFAULT_QUERY="${DEFAULT_QUERY:-big buck bunny}"
AUDIO_GAIN="${AUDIO_GAIN:-2.0}"
MATROSKA_SUBTITLES="${MATROSKA_SUBTITLES:-0}"
case "$SERVER_BASE" in
  http://*|https://*) ;;
  '') SERVER_URL_VALID=0; SERVER_CONFIG_MESSAGE="No PocketStremio server configured" ;;
  *) SERVER_URL_VALID=0; SERVER_CONFIG_MESSAGE="SERVER_BASE must be an HTTP URL" ;;
esac
case "$PROXY" in
  ''|http://*) ;;
  *) CONFIG_ERROR="PROXY must be empty or an HTTP URL" ;;
esac
case "$AUTO_FIRST" in
  0|1) ;;
  *) CONFIG_ERROR="AUTO_FIRST must be 0 or 1" ;;
esac
case "$AUDIO_GAIN" in
  1|1.0|1.25|1.5|1.75|2|2.0) ;;
  *) CONFIG_ERROR="AUDIO_GAIN must be 1, 1.25, 1.5, 1.75, or 2" ;;
esac
case "$APP_LOCAL_PLAYER" in
  0|1) ;;
  *) CONFIG_ERROR="POCKETSTREMIO_APP_LOCAL_PLAYER must be 0 or 1" ;;
esac
case "$MATROSKA_SUBTITLES" in
  0|1) ;;
  *) CONFIG_ERROR="POCKETSTREMIO_MATROSKA_SUBTITLES must be 0 or 1" ;;
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
  rm -f /tmp/stay_awake /tmp/pocketstremio-subtitle.srt \
    "$FIELD_TEST_SUBTITLE_FILE" \
    /tmp/pocketstremio-ffplay.log /tmp/pocketstremio-paused-seconds \
    "$PLAYBACK_CONTROL_FILE" \
    /tmp/pocketstremio-aspect-request \
    /tmp/pocketstremio-account.json /tmp/pocketstremio-account-link.json \
    /tmp/pocketstremio-addons.json /tmp/pocketstremio-live-tv.json \
    /tmp/pocketstremio-live-tv.tsv \
    /tmp/pocketstremio-discovery.raw /tmp/pocketstremio-discovery.tsv \
    /tmp/pocketstremio-discovery-status.json \
    /tmp/pocketstremio-settings.tsv \
    "$SERVER_STATUS_FILE" "$SERVER_STATUS_JSON" \
    /tmp/pocketstremio-stream-details.tsv \
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
  subtitle_id="${4:-none}"
  resume_seconds="${5:-0}"
  audio_stream_index="${6:-0}"
  body=$("$JQ" -nc \
    --arg type "$type" \
    --arg id "$id" \
    --arg stream_id "$stream_id" \
    --arg subtitle_id "$subtitle_id" \
    --argjson audio_stream_index "$audio_stream_index" \
    --argjson field_test "$([ "$FIELD_TEST" = "1" ] && printf 1 || printf 0)" \
    --argjson matroska_subtitles "$([ "$MATROSKA_SUBTITLES" = "1" ] && printf 1 || printf 0)" \
    --argjson resume_seconds "$resume_seconds" \
    '{type:$type,id:$id,stream_id:$stream_id,subtitle_id:$subtitle_id,audio_stream_index:$audio_stream_index,field_test:($field_test == 1),matroska_subtitles:($matroska_subtitles == 1),resume_seconds:$resume_seconds}')
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

playback_setup_error() {
  case "$1" in
    5|6) printf '%s\n' "PSS address could not be resolved" ;;
    7) printf '%s\n' "PSS is offline or refused the connection" ;;
    28) printf '%s\n' "PSS did not respond in time" ;;
    35|60) printf '%s\n' "Secure connection to PSS failed" ;;
    *) printf '%s\n' "Could not contact PSS for playback" ;;
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
    printf '%s\n' "PSS conversion could not start"
  elif grep -Eqi 'HTTP error 5[0-9][0-9]|Server returned 5[0-9][0-9]' "$failure_log"; then
    printf '%s\n' "Stream provider or PSS failed; choose another stream"
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
    export FONTCONFIG_PATH="$FIELD_TEST_LIB_DIR"
    export FONTCONFIG_FILE="$FIELD_TEST_LIB_DIR/fonts.conf"
    export POCKETSTREMIO_FONTCONFIG_FILE="$FIELD_TEST_LIB_DIR/fonts.conf"
    export POCKETSTREMIO_DEFAULT_FONT="$FIELD_TEST_LIB_DIR/fonts/DejaVuSans.ttf"
    export POCKETSTREMIO_ASPECT_MODE="$aspect_mode"
    if [ -n "$FIELD_TEST_SUBTITLE_FILE" ]; then
      export POCKETSTREMIO_SUBTITLE_FILE="$FIELD_TEST_SUBTITLE_FILE"
    else
      unset POCKETSTREMIO_SUBTITLE_FILE
    fi
  fi
  if [ -n "$PROXY" ]; then
    unset ALL_PROXY all_proxy
    HOME=/mnt/SDCARD \
    HTTP_PROXY="$PROXY" \
    http_proxy="$PROXY" \
    HTTPS_PROXY="$PROXY" \
    https_proxy="$PROXY" \
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
  ffplay_log=/tmp/pocketstremio-ffplay.log
  pause_result=/tmp/pocketstremio-paused-seconds
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
  # POCKETSTREMIO_SUBTITLE_FILE so R1 can rebuild it with a new `si`.  Adding
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
            touch /tmp/pocketstremio-aspect-request
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
  log "select title=$title waiting for input debounce"
  sleep 1
  if [ -x "$SDL_SELECTOR" ]; then
    if [ "$file" = "/tmp/pocketstremio-home.tsv" ]; then
      selected=$(POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" cut -f1 "$file" | \
        POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" \
        POCKETSTREMIO_DYNAMIC_FIRST_ITEM_FILE="$SERVER_STATUS_FILE" \
        "$SDL_SELECTOR" "$title" "Up/Down move  A select  B back")
    else
      selected=$(POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" cut -f1 "$file" | \
        POCKETSTREMIO_SELECTOR_LOG="$LOG_FILE" \
        "$SDL_SELECTOR" "$title" "Up/Down move  A select  B back")
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

sync_server_status() {
  [ -f "$SERVER_STATUS_FILE" ] || return 0
  IFS= read -r server_status_value <"$SERVER_STATUS_FILE" || return 0
  case "$server_status_value" in
    "Server: Connected") SERVER_REACHABLE=1 ;;
    "Server: Connecting...") SERVER_REACHABLE=2 ;;
    *) SERVER_REACHABLE=0 ;;
  esac
}

start_server_monitor() {
  stop_server_monitor
  if [ "$SERVER_URL_VALID" -ne 1 ]; then
    SERVER_REACHABLE=0
    write_server_status "Connect to Server"
    return 0
  fi

  monitor_interval="${POCKETSTREMIO_STATUS_INTERVAL:-10}"
  case "$monitor_interval" in
    ''|*[!0-9]*|0) monitor_interval=10 ;;
  esac
  SERVER_REACHABLE=2
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
      rm -f "$SERVER_STATUS_JSON"
      if curl_request -fsS --connect-timeout 3 --max-time 5 \
        "$SERVER_BASE/api/status" >"$SERVER_STATUS_JSON" 2>/dev/null \
        && "$JQ" -e '.status == "ok" and .service == "pocketstremio-server"' \
          "$SERVER_STATUS_JSON" >/dev/null 2>&1; then
        write_server_status "Server: Connected"
      else
        write_server_status "Server: Offline"
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

validate_pss_url() {
  candidate_url="$1"
  rm -f /tmp/pocketstremio-discovery-status.json
  if ! curl_request -fsS --connect-timeout 4 --max-time 7 \
    "$candidate_url/api/status" >/tmp/pocketstremio-discovery-status.json \
    2>>"$HTTP_ERROR_FILE"; then
    return 1
  fi
  "$JQ" -e '.status == "ok" and .service == "pocketstremio-server"' \
    /tmp/pocketstremio-discovery-status.json >/dev/null 2>&1
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

audio_gain_flow() {
  printf '100%% (normal)\t1\n125%%\t1.25\n150%%\t1.5\n175%%\t1.75\n200%% (louder)\t2\nBack\tback\n' \
    >/tmp/pocketstremio-audio-gain.tsv
  selected_gain=$(select_from_file "Audio gain (current ${AUDIO_GAIN}x)" /tmp/pocketstremio-audio-gain.tsv)
  [ -n "$selected_gain" ] || return 0
  tab=$(printf '\t')
  gain_line=$(grep -F "$selected_gain$tab" /tmp/pocketstremio-audio-gain.tsv | head -n 1)
  new_audio_gain=$(printf '%s' "$gain_line" | cut -f2)
  [ "$new_audio_gain" = "back" ] && return 0
  if ! save_audio_gain "$new_audio_gain"; then
    message "PocketStremio Settings" "Could not save audio gain"
    return 1
  fi
  if [ "$AUDIO_GAIN_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketStremio Settings" "Saved. Environment override remains active."
    return 0
  fi
  AUDIO_GAIN="$new_audio_gain"
  log "saved audio gain=$AUDIO_GAIN"
  message "PocketStremio Settings" "Audio gain set to ${AUDIO_GAIN}x for the next video"
}

activate_server_base() {
  new_server_base="$1"
  server_description="$2"
  if ! save_server_base "$new_server_base"; then
    message "PocketStremio Settings" "Could not save server setting"
    return 1
  fi
  if [ "$SERVER_ENV_OVERRIDE" -eq 1 ]; then
    message "PocketStremio Settings" "Saved. Environment override remains active."
    return 0
  fi
  SERVER_BASE="$new_server_base"
  SERVER_URL_VALID=1
  SERVER_CONFIG_MESSAGE=""
  SERVER_REACHABLE=1
  start_server_monitor
  log "saved PSS server=$SERVER_BASE"
  message "PocketStremio Settings" "Connected to $server_description"
}

server_status_flow() {
  sync_server_status
  if [ "$SERVER_URL_VALID" -ne 1 ]; then
    settings_flow
  elif [ "$SERVER_REACHABLE" -eq 1 ]; then
    message "PocketStremio Server" "Connected: $SERVER_BASE"
  elif [ "$SERVER_REACHABLE" -eq 2 ]; then
    message "PocketStremio Server" "Connecting to $SERVER_BASE"
  else
    settings_flow
  fi
}

scan_for_pss() {
  if [ ! -x "$DISCOVERY_CLIENT" ]; then
    message "PocketStremio Settings" "Discovery helper is unavailable"
    return 1
  fi

  start_loading "PocketStremio Settings" "Scanning for PSS..."
  rm -f /tmp/pocketstremio-discovery.raw /tmp/pocketstremio-discovery.tsv
  "$DISCOVERY_CLIENT" >/tmp/pocketstremio-discovery.raw 2>>"$LOG_FILE"
  discovery_rc=$?
  : >/tmp/pocketstremio-discovery.tsv
  if [ "$discovery_rc" -eq 0 ]; then
    tab=$(printf '\t')
    while IFS="$tab" read -r discovered_name discovered_url discovered_network; do
      [ -n "$discovered_name" ] && [ -n "$discovered_url" ] \
        && [ -n "$discovered_network" ] || continue
      if validate_pss_url "$discovered_url"; then
        discovered_address=$(printf '%s' "$discovered_url" | sed 's|^[A-Za-z]*://||')
        short_name=$(printf '%s' "$discovered_name" | cut -c1-12)
        short_network=$(printf '%s' "$discovered_network" | cut -c1-10)
        printf '%s - %s - %s\t%s\n' "$short_name" "$discovered_address" \
          "$short_network" "$discovered_url" >>/tmp/pocketstremio-discovery.tsv
      else
        log "ignored discovery response that failed PSS status validation url=$discovered_url"
      fi
    done </tmp/pocketstremio-discovery.raw
  fi
  stop_loading

  if [ ! -s /tmp/pocketstremio-discovery.tsv ]; then
    message "PocketStremio Settings" "No PSS found on the local network"
    return 1
  fi

  discovered_choice=$(select_from_file "Select PSS" /tmp/pocketstremio-discovery.tsv)
  [ -n "$discovered_choice" ] || return 0
  discovered_line=$(grep -F "$discovered_choice	" \
    /tmp/pocketstremio-discovery.tsv | head -n 1)
  discovered_url=$(printf '%s' "$discovered_line" | cut -f2)
  [ -n "$discovered_url" ] || {
    message "PocketStremio Settings" "Server selection failed"
    return 1
  }
  activate_server_base "$discovered_url" "$discovered_choice"
}

enter_server_manually() {
  message "PocketStremio Settings" \
    "PSS has no public login. Prefer a VPN or trusted network."
  manual_initial="$SERVER_BASE"
  [ -n "$manual_initial" ] || manual_initial="http://"
  manual_url=$(read_keyboard "$manual_initial" "PSS URL or host:port")
  manual_url=$(printf '%s' "$manual_url" | tr -d '\r\n')
  [ -n "$manual_url" ] || return 0
  case "$manual_url" in
    http://*|https://*) ;;
    *://*)
      message "PocketStremio Settings" "Only HTTP and HTTPS URLs are supported"
      return 1
      ;;
    *) manual_url="http://$manual_url" ;;
  esac
  case "$manual_url" in
    *[[:space:]]*|http://*@*|https://*@*)
      message "PocketStremio Settings" "Invalid PSS URL"
      return 1
      ;;
  esac

  start_loading "PocketStremio Settings" "Checking PSS..."
  validate_pss_url "$manual_url"
  manual_rc=$?
  stop_loading
  if [ "$manual_rc" -ne 0 ]; then
    message "PocketStremio Settings" "No valid PSS found at that address"
    return 1
  fi
  activate_server_base "$manual_url" "$manual_url"
}

settings_flow() {
  while :; do
    printf 'Scan for PSS\nEnter Manually\nAudio gain\nBack\n' >/tmp/pocketstremio-settings.tsv
    settings_action=$(select_from_file "Settings" /tmp/pocketstremio-settings.tsv)
    case "$settings_action" in
      "Scan for PSS") scan_for_pss ;;
      "Enter Manually") enter_server_manually ;;
      "Audio gain") audio_gain_flow ;;
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
        server_action="Server: Connected"
      elif [ "$SERVER_REACHABLE" -eq 2 ]; then
        server_action="Server: Connecting..."
      elif [ "$SERVER_URL_VALID" -eq 1 ]; then
        server_action="Server: Offline"
      else
        server_action="Connect to Server"
      fi
      printf '%s\nSearch\nLive TV\nQuick Resume\nContinue Watching\nStremio Account\nSettings\nExit\n' \
        "$server_action" >/tmp/pocketstremio-home.tsv
      action=$(select_from_file "PocketStremio" /tmp/pocketstremio-home.tsv)
    fi
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
      "Server: Connected"|"Server: Connecting..."|"Server: Offline"|"Connect to Server")
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

quick_resume_flow() {
  if [ ! -s "$LAST_PLAY_FILE" ]; then
    message "PocketStremio" "No recent stream to resume"
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
    message "PocketStremio" "Quick Resume is unavailable for this server"
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
    quick_error=$("$JQ" -r '.error // ""' /tmp/pocketstremio-play.json 2>/dev/null)
    if [ "$quick_error" = "stream_not_found" ] || [ "$quick_error" = "subtitle_not_found" ]; then
      rm -f "$LAST_PLAY_FILE"
      message "PocketStremio" "Saved stream expired; choose it again"
      media_flow "$quick_type" "$quick_id" "$quick_title" "$quick_year" "$quick_position"
      return $?
    fi
  fi
  return "$quick_rc"
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
  # Keep a failed provider/session out of this title's current picker.  The
  # server also caches deterministic incompatibilities; this handles transient
  # provider failures without forcing the user back through Continue Watching.
  FAILED_STREAM_IDS=""
  STREAM_RETRY_SUBTITLE_ID=""

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
  ' /tmp/pocketstremio-streams.json)
  case "$track_count" in
    ''|0|1) printf '0'; return 0 ;;
  esac
  : > /tmp/pocketstremio-audio-tracks.tsv
  "$JQ" -r --arg id "$stream_id" '
    .items[] | select(.id == $id) | (.compatibility.audio_tracks // [])[] |
    ("Track " + ((.ordinal + 1)|tostring) + ": " +
      (if .language == "" then "language unknown" else .language end) +
      (if .title == "" then "" else " - " + .title end)) + "\t" + (.ordinal|tostring)
  ' /tmp/pocketstremio-streams.json >/tmp/pocketstremio-audio-tracks.tsv
  selected_audio=$(select_from_file "Select audio track" /tmp/pocketstremio-audio-tracks.tsv)
  [ -n "$selected_audio" ] || { printf 'back'; return 0; }
  grep -F "$selected_audio	" /tmp/pocketstremio-audio-tracks.tsv | head -n 1 | cut -f2
}

streams_flow() {
  type="$1"
  id="$2"
  title="$3"
  year="$4"
  resume_seconds="${5:-0}"
  preferred_subtitle_id="${6:-}"
  log "resolve streams type=$type id=$id preflight=1"
  start_loading "PocketStremio" "Checking available streams..."
  api_get "/api/streams/$type/$id?preflight=1" 120 >/tmp/pocketstremio-streams.json
  stream_lookup_rc=$?
  stop_loading
  if [ "$stream_lookup_rc" -ne 0 ]; then
    message "PocketStremio" "Stream lookup failed"
    return 1
  fi

  source_filter=""
  audio_filter=""
  if [ "${POCKETSTREMIO_DRY_RUN:-0}" != "1" ]; then
    printf 'All sources\tall\n' > /tmp/pocketstremio-source-filters.tsv
    "$JQ" -r '.items[] | select(.playable == true) | (.source_label // .name) + "\t" + (.source_label // .name)' \
      /tmp/pocketstremio-streams.json | sort -u >> /tmp/pocketstremio-source-filters.tsv
    selected_source=$(select_from_file "Stream source" /tmp/pocketstremio-source-filters.tsv)
    if [ -n "$selected_source" ] && [ "$selected_source" != "All sources" ]; then
      source_filter="$selected_source"
    fi

    printf 'All audio languages\t\n' > /tmp/pocketstremio-audio-filters.tsv
    "$JQ" -r '.items[] | select(.playable == true) | (.compatibility.audio_languages // [])[]' \
      /tmp/pocketstremio-streams.json | sort -u | while IFS= read -r language; do
        [ -n "$language" ] && printf '%s (verified)\t%s\n' "$language" "$language"
      done >> /tmp/pocketstremio-audio-filters.tsv
    selected_audio=$(select_from_file "Audio language (verified tags)" /tmp/pocketstremio-audio-filters.tsv)
    if [ -n "$selected_audio" ]; then
      audio_filter=$(grep -F "$selected_audio	" /tmp/pocketstremio-audio-filters.tsv | head -n 1 | cut -f2)
    fi
  fi

  "$JQ" -r --arg failed_ids "$FAILED_STREAM_IDS" --arg source_filter "$source_filter" --arg audio_filter "$audio_filter" '
    .items[] | select(.playable == true) | . as $stream
    | select(($failed_ids | contains("|" + $stream.id + "|")) | not)
    | select(($source_filter == "") or (($stream.source_label // $stream.name) == $source_filter))
    | select(($audio_filter == "") or (($stream.compatibility.audio_languages // []) | map(ascii_downcase) | any(. == ($audio_filter | ascii_downcase))))
    | "\(if .playback_mode == "direct" then "[DIRECT] " elif .playback_mode == "convert" then "[CONVERT]" else "[CHECK]" end) \(.source_label // .name)\\n\(.release_label // "release metadata unavailable")\\n\((.compatibility.width // "?")|tostring)x\((.compatibility.height // "?")|tostring) \(.compatibility.video_codec // "?")/\(.compatibility.audio_codec // "?")\t\(.id)\t\(.description // "")"' /tmp/pocketstremio-streams.json >/tmp/pocketstremio-streams.tsv
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

    "$JQ" -r --arg id "$stream_id" '.items[] | select(.id == $id) |
      ("Source: " + (.source_label // .name)),
      ("Release: " + ((.release_label // "not provided") | .[0:42])),
      ("Media: " + ((.compatibility.width // "?")|tostring) + "x" + ((.compatibility.height // "?")|tostring) + " " + (.compatibility.video_codec // "?") + "/" + (.compatibility.audio_codec // "?")),
      ("Mode: " + ((.playback_mode // "check") | ascii_upcase)),
      "Use this stream"' /tmp/pocketstremio-streams.json |
      while IFS= read -r detail; do printf '%s\t%s\n' "$detail" "$detail"; done >/tmp/pocketstremio-stream-details.tsv
    while :; do
      detail_choice=$(select_from_file "Stream Details" /tmp/pocketstremio-stream-details.tsv)
      [ "$detail_choice" = "Use this stream" ] && break
      [ -z "$detail_choice" ] && break
    done
    [ "$detail_choice" = "Use this stream" ] || continue
    audio_stream_index=$(select_audio_track "$stream_id")
    [ "$audio_stream_index" = "back" ] && continue
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
    break
  done

  play_selected_stream "$type" "$id" "$title" "$year" "$resume_seconds" \
    "$stream_id" "$subtitle_id" "$audio_stream_index"
  play_selected_rc=$?
  if [ "$play_selected_rc" -eq 10 ]; then
    return 10
  fi
  if [ "$play_selected_rc" -ne 0 ]; then
    FAILED_STREAM_IDS="${FAILED_STREAM_IDS}|${stream_id}|"
    STREAM_RETRY_SUBTITLE_ID="$subtitle_id"
    log "stream failed; returning to filtered picker stream_id=$stream_id"
    return 11
  fi
  return 0
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
    message "PocketStremio" "Selectable subtitle player is unavailable"
    return 1
  fi
  if [ "$MATROSKA_SUBTITLES" = "1" ]; then
    subtitle_id=none
    start_loading "PocketStremio" "Preparing video and selectable subtitles..."
    api_get "/api/subtitles/$type/$id?stream_id=$stream_id&all=1" \
      >/tmp/pocketstremio-subtitles.json
    subtitle_lookup_rc=$?
    if [ "$subtitle_lookup_rc" -ne 0 ]; then
      log "matroska subtitle discovery failed"
      fallback_matroska_playback "subtitle-discovery" "$type" "$id" "$title" \
        "$year" "$resume_seconds" "$stream_id" "$audio_stream_index"
      return $?
    fi
    subtitle_count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-subtitles.json)
    if [ "$subtitle_count" -le 0 ] 2>/dev/null; then
      stop_loading
      subtitle_error=$("$JQ" -r '.unavailable_reason // "No supported English subtitles are available"' \
        /tmp/pocketstremio-subtitles.json 2>/dev/null)
      log "matroska subtitle discovery returned no supported tracks message=$subtitle_error"
      message "PocketStremio" "$subtitle_error"
      return 1
    fi
    log "matroska subtitle discovery cached tracks=$subtitle_count"
  else
    start_loading "PocketStremio" "Checking compatibility..."
  fi
  api_post_play "$type" "$id" "$stream_id" "$subtitle_id" "$resume_seconds" "$audio_stream_index" >/tmp/pocketstremio-play.json
  play_setup_rc=$?
  if [ "$play_setup_rc" -ne 0 ]; then
    stop_loading
    play_error=$(playback_setup_error "$play_setup_rc")
    log "playback setup transport failure rc=$play_setup_rc reason=$play_error"
    message "PocketStremio" "$play_error"
    return 1
  fi
  play_url_value=$("$JQ" -r '.url // ""' /tmp/pocketstremio-play.json)
  if [ -z "$play_url_value" ]; then
    play_error_code=$("$JQ" -r '.error // ""' /tmp/pocketstremio-play.json 2>/dev/null)
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
    play_error=$("$JQ" -r '.message // "Playback setup failed"' /tmp/pocketstremio-play.json 2>/dev/null)
    [ -n "$play_error" ] || play_error="PSS returned an invalid playback response"
    log "playback setup rejected message=$play_error"
    message "PocketStremio" "$play_error"
    return 1
  fi
  save_last_play "$type" "$id" "$title" "$year" "$resume_seconds" "$stream_id" "$subtitle_id" "$audio_stream_index"
  server_field_test=$("$JQ" -r '.field_test // false' /tmp/pocketstremio-play.json)
  if [ "$FIELD_TEST" = "1" ] && [ "$server_field_test" != "true" ]; then
    stop_loading
    log "field-test rejected because server mode is disabled"
    message "PocketStremio" "Subtitle field test is disabled on the server"
    return 1
  fi
  server_matroska_subtitles=$("$JQ" -r '.matroska_subtitles // false' /tmp/pocketstremio-play.json)
  if [ "$MATROSKA_SUBTITLES" = "1" ] && [ "$server_matroska_subtitles" != "true" ]; then
    log "matroska subtitles rejected because server mode is disabled"
    fallback_matroska_playback "server-mode-disabled" "$type" "$id" "$title" \
      "$year" "$resume_seconds" "$stream_id" "$audio_stream_index"
    return $?
  fi
  duration_seconds=$("$JQ" -r '(.duration_seconds // 0) | floor' /tmp/pocketstremio-play.json)
  compatibility_status=$("$JQ" -r '.compatibility.status // "unknown"' /tmp/pocketstremio-play.json)
  compatibility_message=$("$JQ" -r '.compatibility.message // ""' /tmp/pocketstremio-play.json)
  log "media preflight status=$compatibility_status message=$compatibility_message"

  transcoded=$("$JQ" -r '.transcoded // false' /tmp/pocketstremio-play.json)
  server_seek_applied=$("$JQ" -r '.server_seek_applied // false' /tmp/pocketstremio-play.json)
  ffplay_resume_seconds="$resume_seconds"
  [ "$server_seek_applied" = "true" ] && ffplay_resume_seconds=0
  log "playback conversion=$transcoded subtitle_id=${subtitle_id:-none} server_seek=$server_seek_applied"

  FIELD_TEST_SUBTITLE_FILE=""
  if { [ "$FIELD_TEST" = "1" ] && [ -n "$subtitle_id" ] && [ "$subtitle_id" != "none" ]; } \
    || [ "$MATROSKA_SUBTITLES" = "1" ]; then
    FIELD_TEST_SUBTITLE_FILE="$BASE_DIR/experiments/ffplay/.field-test-subtitle-$$.mkv"
    subtitle_pack_url="$SERVER_BASE/subtitle/$subtitle_id?format=matroska&offset_seconds=$resume_seconds"
    if [ "$MATROSKA_SUBTITLES" = "1" ]; then
      subtitle_pack_url=$("$JQ" -r '.subtitle_pack_url // ""' /tmp/pocketstremio-play.json)
      track_count=$("$JQ" -r '(.subtitle_tracks // []) | length' /tmp/pocketstremio-play.json)
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
    start_loading "PocketStremio" "Starting video..."
  fi
  playback_result=0
  nonseekable_mode=0
  [ "$FIELD_TEST" = "1" ] && nonseekable_mode=1
  [ "$MATROSKA_SUBTITLES" = "1" ] && nonseekable_mode=1
  if ! play_url "$play_url_value" "$ffplay_resume_seconds" "$FIELD_TEST_SUBTITLE_FILE" \
    "$nonseekable_mode" "$subtitle_id" "$resume_seconds"; then
    message "PocketStremio" "$PLAYBACK_ERROR"
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
    if api_post_progress "$type" "$id" "$title" "$year" "$new_position" "$duration_seconds" "$completed" >/tmp/pocketstremio-progress.json; then
      log "progress saved position_seconds=$new_position duration_seconds=$duration_seconds completed=$completed"
      save_last_play "$type" "$id" "$title" "$year" "$new_position" "$stream_id" "$subtitle_id" "$audio_stream_index"
    else
      log "progress save failed"
    fi
  fi
  return "$playback_result"
}

select_subtitle() {
  type="$1"
  id="$2"
  stream_id="$3"

  subtitle_all=0
  while :; do
    subtitle_query="/api/subtitles/$type/$id?stream_id=$stream_id"
    [ "$subtitle_all" = "1" ] && subtitle_query="$subtitle_query&all=1"
    start_loading "PocketStremio" "Loading subtitles..."
    api_get "$subtitle_query" >/tmp/pocketstremio-subtitles.json
    subtitle_lookup_rc=$?
    stop_loading
    if [ "$subtitle_lookup_rc" -ne 0 ]; then
      log "subtitle lookup failed"
      printf '%s' "none"
      return 0
    fi
    count=$("$JQ" -r '.count // 0' /tmp/pocketstremio-subtitles.json)
    other_count=$("$JQ" -r '.other_count // 0' /tmp/pocketstremio-subtitles.json)
    if [ "$AUTO_FIRST" = "1" ]; then
      log "auto-selected subtitles=none"
      printf '%s' "none"
      return 0
    fi
    if [ "$count" = "0" ] && [ "$other_count" = "0" ]; then
      printf '%s' "none"
      return 0
    fi

    printf 'No subtitles\tnone\n' >/tmp/pocketstremio-subtitles.tsv
    "$JQ" -r '.items[] | "\(.name) [\(.lang)]\t\(.id)"' /tmp/pocketstremio-subtitles.json >>/tmp/pocketstremio-subtitles.tsv
    if [ "$subtitle_all" != "1" ] && [ "$other_count" -gt 0 ]; then
      printf 'Show other English subtitles\tmore\n' >>/tmp/pocketstremio-subtitles.tsv
    fi
    selected=$(select_from_file "Select Subtitles" /tmp/pocketstremio-subtitles.tsv)
    if [ -z "$selected" ]; then
      printf '%s' "back"
      return 0
    fi
    line=$(grep -F "$selected	" /tmp/pocketstremio-subtitles.tsv | head -n 1)
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
start_server_monitor
home_flow
log "PocketStremio UI exit"
sync
