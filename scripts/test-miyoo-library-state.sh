#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
UI_SCRIPT="$SCRIPT_DIR/../client/miyoo/pocketcinema-ui.sh"
JQ="${JQ:-$(command -v jq || true)}"

[ -n "$JQ" ] || { printf '%s\n' "jq is required" >&2; exit 1; }
grep -F 'episode_state.seasons' "$UI_SCRIPT" >/dev/null
grep -F 'episode_state.episodes' "$UI_SCRIPT" >/dev/null

fixture='{
  "seasons": [
    {"number": 1, "episode_count": 2},
    {"number": 2, "episode_count": 2}
  ],
  "episodes": [
    {"id": "series:1:1", "season": 1, "episode": 1, "title": "Watched"},
    {"id": "series:1:2", "season": 1, "episode": 2, "title": "Watched Current"},
    {"id": "series:2:1", "season": 2, "episode": 1, "title": "Unwatched"},
    {"id": "series:2:2", "season": 2, "episode": 2, "title": "Current"}
  ],
  "episode_state": {
    "seasons": {
      "1": {"watched": true},
      "2": {"watched": false}
    },
    "episodes": {
      "series:1:1": {"watched": true, "current": false},
      "series:1:2": {"watched": true, "current": true},
      "series:2:1": {"watched": false, "current": false},
      "series:2:2": {"watched": false, "current": true}
    }
  }
}'

season_output=$(
  printf '%s\n' "$fixture" | "$JQ" -r '
    . as $meta
    | .seasons[]
    | ((($meta.episode_state.seasons // {})[(.number | tostring)] // {}).watched // false) as $watched
    | "Season \(.number) (\(.episode_count) episodes)\(if $watched then " WATCHED" else "" end)"
  '
)
expected_seasons='Season 1 (2 episodes) WATCHED
Season 2 (2 episodes)'
[ "$season_output" = "$expected_seasons" ] || {
  printf '%s\n' "unexpected season markers:" "$season_output" >&2
  exit 1
}

episode_output=$(
  printf '%s\n' "$fixture" | "$JQ" -r --argjson season 1 '
    . as $meta
    | $meta.episodes[]
    | select(.season == $season)
    | (($meta.episode_state.episodes // {})[.id] // {}) as $state
    | (if $state.watched then " WATCHED" else "" end) as $watched
    | (if $state.current then " *" else "" end) as $current
    | "\(.episode). \(.title)\($watched)\($current)"
  '
)
expected_episodes='1. Watched WATCHED
2. Watched Current WATCHED *'
[ "$episode_output" = "$expected_episodes" ] || {
  printf '%s\n' "unexpected episode markers:" "$episode_output" >&2
  exit 1
}

printf '%s\n' "Miyoo library state tests passed"
