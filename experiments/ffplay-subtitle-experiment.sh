#!/bin/sh

# Runs the app-local libass FFplay experiment against the deterministic fixture.
# The production Onion FFplay and PocketStremio playback path are untouched.
BASE_DIR=/mnt/SDCARD/App/PocketStremio
SYS_DIR=/mnt/SDCARD/.tmp_update
MIYOO_DIR=/mnt/SDCARD/miyoo
CONFIG_FILE="$BASE_DIR/config/pocketstremio.conf"
LOG_FILE="$BASE_DIR/logs/ffplay-subtitle-experiment.log"
FFPLAY="$BASE_DIR/experiments/ffplay/bin/ffplay"
LIB_DIR="$BASE_DIR/experiments/ffplay/lib"
PADSP=/mnt/SDCARD/miyoo/lib/libpadsp.so
SERVER_BASE="${POCKETSTREMIO_SERVER:-}"
PROXY="${POCKETSTREMIO_PROXY:-}"

rm -f "$BASE_DIR/config/ffplay-subtitle-experiment.mode"

mkdir -p "$BASE_DIR/logs"
: > "$LOG_FILE"

if [ -f "$CONFIG_FILE" ]; then
  while IFS='=' read -r config_key config_value; do
    config_value=$(printf '%s' "$config_value" | tr -d '\r')
    case "$config_key" in
      SERVER_BASE) [ -n "$SERVER_BASE" ] || SERVER_BASE="$config_value" ;;
      PROXY) [ -n "$PROXY" ] || PROXY="$config_value" ;;
    esac
  done < "$CONFIG_FILE"
fi

if [ ! -x "$FFPLAY" ]; then
  "$SYS_DIR/bin/infoPanel" --persistent "Subtitle experiment unavailable" 2>/dev/null || true
  rm -f /tmp/dismiss_info_panel
  exit 1
fi
case "$SERVER_BASE" in
  http://*|https://*) ;;
  *) exit 1 ;;
esac

touch /tmp/stay_awake
trap 'rm -f /tmp/stay_awake /tmp/dismiss_info_panel' EXIT

unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy LD_PRELOAD
if [ -n "$PROXY" ]; then
  HTTP_PROXY="$PROXY"
  HTTPS_PROXY="$PROXY"
  ALL_PROXY="$PROXY"
  http_proxy="$PROXY"
  https_proxy="$PROXY"
  all_proxy="$PROXY"
  export HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
fi

URL="$SERVER_BASE/media/compatibility/subtitle-switch-fixture.mkv"
FIXTURE_FILE=/tmp/pocketstremio-subtitle-fixture.mkv
SHIFTED_SRT_FILE="$BASE_DIR/experiments/ffplay/.subtitle-offset-$$.srt"
if ! "$SYS_DIR/bin/curl" -fsS --max-time 60 -o "$FIXTURE_FILE" "$URL" >> "$LOG_FILE" 2>&1; then
  printf '%s\n' "Fixture download failed" >> "$LOG_FILE"
  exit 1
fi
cat > "$SHIFTED_SRT_FILE" <<'EOF'
1
00:00:08,000 --> 00:00:12,000
RESUME CUE - SHOULD APPEAR IMMEDIATELY AT SEEK 8

2
00:00:14,000 --> 00:00:18,000
RESUME CUE - SECOND KNOWN TIMESTAMP
EOF
trap 'rm -f /tmp/stay_awake /tmp/dismiss_info_panel /tmp/pocketstremio-subtitle-fixture.mkv "$SHIFTED_SRT_FILE"' EXIT
export LD_LIBRARY_PATH="$LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export FONTCONFIG_PATH="$LIB_DIR"
export FONTCONFIG_FILE="$LIB_DIR/fonts.conf"
export POCKETSTREMIO_FONTCONFIG_FILE="$LIB_DIR/fonts.conf"
export POCKETSTREMIO_DEFAULT_FONT="$LIB_DIR/fonts/DejaVuSans.ttf"
export POCKETSTREMIO_SUBTITLE_FILE="$SHIFTED_SRT_FILE"

printf '%s\n' "Starting deterministic subtitle timing test: seek=8 cue=8..12" >> "$LOG_FILE"
if [ -f "$PADSP" ]; then
  LD_PRELOAD="$PADSP:$MIYOO_DIR/lib/libSDL-1.2.so.0" "$FFPLAY" -hide_banner -stats -autoexit -ss 8 -sn \
    -vf "subtitles=$SHIFTED_SRT_FILE,hflip,vflip" -i "$FIXTURE_FILE" >> "$LOG_FILE" 2>&1
else
  "$FFPLAY" -hide_banner -stats -autoexit -ss 8 -sn \
    -vf "subtitles=$SHIFTED_SRT_FILE,hflip,vflip" -i "$FIXTURE_FILE" >> "$LOG_FILE" 2>&1
fi
