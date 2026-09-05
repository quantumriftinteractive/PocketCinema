#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
UI_SCRIPT="$ROOT_DIR/client/miyoo/pocketcinema-ui.sh"
CONFIG_EXAMPLE="$ROOT_DIR/client/miyoo/pocketcinema.conf.example"

assert_contains() {
  grep -F -q -- "$2" "$1" || {
    printf 'expected [%s] in %s\n' "$2" "$1" >&2
    exit 1
  }
}

# The production script resolves a missing value to the accepted 1.5x default,
# accepts only the six supported presets, and rejects invalid/corrupt values.
assert_contains "$UI_SCRIPT" 'SUBTITLE_FONT_SCALE="${SUBTITLE_FONT_SCALE:-1.5}"'
assert_contains "$UI_SCRIPT" '1.0|1.25|1.5|2.0|2.5|3.0)'
assert_contains "$UI_SCRIPT" 'SUBTITLE_FONT_SCALE must be 1.0, 1.25, 1.5, 2.0, 2.5, or 3.0'

# Settings persistence replaces or appends only the selected key and updates
# the live value for future playback without touching subtitle track state.
assert_contains "$UI_SCRIPT" 'save_subtitle_font_scale()'
assert_contains "$UI_SCRIPT" 'SUBTITLE_FONT_SCALE='
assert_contains "$UI_SCRIPT" 'Subtitle size (current ${SUBTITLE_FONT_SCALE}x)'
assert_contains "$UI_SCRIPT" 'Subtitle size set to ${SUBTITLE_FONT_SCALE}x'
assert_contains "$CONFIG_EXAMPLE" 'SUBTITLE_FONT_SCALE=1.5'

# The existing selectable-track path remains the only renderer handoff.
assert_contains "$UI_SCRIPT" 'export POCKETCINEMA_SUBTITLE_FONT_SCALE="$SUBTITLE_FONT_SCALE"'
assert_contains "$UI_SCRIPT" 'POCKETCINEMA_SUBTITLE_FILE'

printf 'Miyoo subtitle font-scale checks passed\n'
