#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
UI_SCRIPT="$ROOT_DIR/client/miyoo/pocketcinema-ui.sh"
CONFIG_EXAMPLE="$ROOT_DIR/client/miyoo/pocketcinema.conf.example"

test_root=$(mktemp -d "${TMPDIR:-/tmp}/pocketcinema-matroska-config.XXXXXX")
trap 'rm -rf "$test_root"' EXIT HUP INT TERM
CONFIG_FILE="$test_root/pocketcinema.conf"

assert_equal() {
  [ "$1" = "$2" ] || {
    printf 'expected [%s], got [%s]\n' "$2" "$1" >&2
    exit 1
  }
}

# Exercise the exact client config loader, rather than duplicating its parsing
# rules in the test. The following fallback line is the normal runtime default.
awk '/^load_config\(\) \{/{copy=1} copy {print} copy && /^}/ {exit}' "$UI_SCRIPT" \
  >"$test_root/load_config.sh"
. "$test_root/load_config.sh"

effective_matroska_setting() {
  printf '%s\n' "$1" >"$CONFIG_FILE"
  SERVER_BASE=""
  PROXY=""
  LOCAL_PCSERVER=""
  REMOTE_PCSERVER=""
  CONNECTION_MODE=""
  DEFAULT_QUERY=""
  AUTO_FIRST=""
  AUDIO_GAIN=""
  AUDIO_LANGUAGES=""
  AUDIO_FALLBACK=""
  SUBTITLE_LANGUAGES=""
  SUBTITLE_FALLBACK=""
  MAX_SUBTITLES_PER_LANGUAGE=""
  MATROSKA_SUBTITLES=""
  CONFIG_ERROR=""
  load_config
  MATROSKA_SUBTITLES="${MATROSKA_SUBTITLES:-1}"
  printf '%s\n' "$MATROSKA_SUBTITLES"
}

assert_equal "$(effective_matroska_setting 'SERVER_BASE=http://192.0.2.1:8755')" "1"
assert_equal "$(effective_matroska_setting 'POCKETCINEMA_MATROSKA_SUBTITLES=1')" "1"
assert_equal "$(effective_matroska_setting 'POCKETCINEMA_MATROSKA_SUBTITLES=0')" "0"
assert_equal "$(grep '^POCKETCINEMA_MATROSKA_SUBTITLES=' "$CONFIG_EXAMPLE")" \
  'POCKETCINEMA_MATROSKA_SUBTITLES=1'

# Connection-profile writes preserve unrelated explicit settings, including the
# opt-out, rather than replacing an existing user configuration.
. "$ROOT_DIR/client/miyoo/pocketcinema-connection.sh"
cat >"$CONFIG_FILE" <<'EOF'
SERVER_BASE=http://192.0.2.1:8755
POCKETCINEMA_MATROSKA_SUBTITLES=0
EOF
pocketcinema_save_connection_profile "$CONFIG_FILE" "http://192.0.2.4:8755" "" local ""
grep -Fx 'POCKETCINEMA_MATROSKA_SUBTITLES=0' "$CONFIG_FILE" >/dev/null

printf 'Miyoo Matroska configuration tests passed\n'
