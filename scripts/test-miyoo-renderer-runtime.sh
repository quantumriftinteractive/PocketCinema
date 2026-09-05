#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
UI_SCRIPT="$ROOT_DIR/client/miyoo/pocketcinema-ui.sh"
DEPLOY_SCRIPT="$ROOT_DIR/scripts/deploy-miyoo.ps1"
FONTCONFIG="$ROOT_DIR/experiments/ffplay/fonts.conf"
SUBTITLE_PATCH="$ROOT_DIR/experiments/ffplay/ffmpeg-2.4.14-subtitle-notice.patch"

assert_contains() {
  grep -F -q -- "$2" "$1" || {
    printf 'expected [%s] in %s\n' "$2" "$1" >&2
    exit 1
  }
}

# Production launch supplies the selected subtitle package and the bundled
# fontconfig/font to both the current and migrated, accepted app-local FFplay
# identities. Neither path relies on a user-set test mode.
for name in POCKETCINEMA POCKETSTREMIO; do
  assert_contains "$UI_SCRIPT" "export ${name}_FONTCONFIG_FILE=\"\$FIELD_TEST_DIR/fonts.conf\""
  assert_contains "$UI_SCRIPT" "export ${name}_DEFAULT_FONT=\"\$FIELD_TEST_DIR/fonts/PocketCinema.ttf\""
  assert_contains "$UI_SCRIPT" "export ${name}_SUBTITLE_FILE=\"\$FIELD_TEST_SUBTITLE_FILE\""
done
assert_contains "$UI_SCRIPT" 'export POCKETCINEMA_SUBTITLE_FONT_SCALE="$SUBTITLE_FONT_SCALE"'
assert_contains "$UI_SCRIPT" 'export POCKETSTREMIO_SUBTITLE_FONT_SCALE="$SUBTITLE_FONT_SCALE"'
assert_contains "$FONTCONFIG" '/mnt/SDCARD/App/PocketCinema/experiments/ffplay/fonts'
assert_contains "$SUBTITLE_PATCH" 'subtitles=%s:font_scale=%s'
assert_contains "$SUBTITLE_PATCH" 'subtitle_font_scale ? subtitle_font_scale : "1.5"'
assert_contains "$SUBTITLE_PATCH" 'getenv("POCKETCINEMA_SUBTITLE_FONT_SCALE")'
assert_contains "$SUBTITLE_PATCH" 'ass_set_font_scale(ass->renderer, ass->font_scale);'
assert_contains "$DEPLOY_SCRIPT" 's|/mnt/SDCARD/App/PocketStremio|/mnt/SDCARD/App/PocketCinema|g'
assert_contains "$DEPLOY_SCRIPT" 's|pocketstremio-fontconfig-cache|pocketcinema-fontconfig-cache|g'
assert_contains "$DEPLOY_SCRIPT" '$deviceTarget = "root@$DeviceHost"'
assert_contains "$DEPLOY_SCRIPT" '$migration = $migration -replace "`r`n", "`n"'

printf 'Miyoo renderer runtime tests passed\n'
