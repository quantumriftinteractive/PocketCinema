#!/bin/sh
set -u
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd) || exit 1
cd "$ROOT" || exit 1
branch=$(git branch --show-current 2>/dev/null || printf '%s' unknown)
head=$(git rev-parse HEAD 2>/dev/null || printf '%s' unknown)
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || printf 'origin/%s' "$branch")
remote_name=${upstream%%/*}
remote_branch=${upstream#*/}
remote_head=$(git ls-remote "$remote_name" "refs/heads/$remote_branch" 2>/dev/null | awk 'NR == 1 {print $1}')
baseline=$(sed -n 's/^Production baseline commit: `\([^`]*\)`.*/\1/p' PROJECT_STATE.md)
milestone=$(sed -n 's/^Active milestone: //p' PROJECT_STATE.md)
last_commit=$(sed -n 's/^Last commit: `\([^`]*\)`.*/\1/p' PROJECT_STATE.md)
dirty=0
git status --porcelain | grep . >/dev/null 2>&1 && dirty=1
ahead='?'; behind='?'; diverged=UNKNOWN; sync=REMOTE_UNAVAILABLE
if [ -n "$remote_head" ]; then
  counts=$(git rev-list --left-right --count "$head...$remote_head" 2>/dev/null || true)
  ahead=$(printf '%s' "$counts" | awk '{print $1}')
  behind=$(printf '%s' "$counts" | awk '{print $2}')
  if [ -n "$ahead" ] && [ -n "$behind" ]; then
    if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then diverged=YES; sync=DIVERGED
    elif [ "$behind" -gt 0 ]; then diverged=NO; sync=BEHIND_REMOTE
    elif [ "$ahead" -gt 0 ]; then diverged=NO; sync=AHEAD_REMOTE
    else diverged=NO; sync=OK
    fi
  fi
fi
[ "$dirty" -eq 1 ] && [ "$sync" = OK ] && sync=DIRTY
[ -n "$baseline" ] && [ "$head" != "$baseline" ] && [ "$sync" = OK ] && sync=BASELINE_MISMATCH
printf '%s\n' 'PocketStremio Development State'
printf 'Machine/OS: macOS or Unix / %s\n' "$(uname -s 2>/dev/null || printf unknown)"
printf 'Branch: %s\nLocal HEAD: %s\nRemote HEAD: %s\nProduction baseline: %s\n' "$branch" "$head" "${remote_head:-UNAVAILABLE}" "$baseline"
printf 'Working tree: %s\nAhead: %s\nBehind: %s\nDiverged: %s\nActive milestone: %s\nLast handoff commit: %s\n' "$( [ "$dirty" -eq 1 ] && printf DIRTY || printf CLEAN )" "$ahead" "$behind" "$diverged" "$milestone" "$last_commit"
printf '\nSYNC STATUS: %s\n' "$sync"
case "$sync" in
  BEHIND_REMOTE|DIVERGED) printf '\nDO NOT BEGIN DEVELOPMENT UNTIL THE CHECKOUT IS SYNCHRONIZED.\n' ;;
  REMOTE_UNAVAILABLE) printf '\nREMOTE STATUS UNVERIFIED\n' ;;
esac
