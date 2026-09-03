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
baseline=$(sed -n 's/^Production baseline commit: `\([^`]*\)`.*/\1/p' PROJECT_STATE.md | head -n 1)
milestone=$(sed -n 's/^Active milestone: //p' PROJECT_STATE.md | head -n 1)
checkpoint=$(sed -n 's/^Checkpoint commit: `\([^`]*\)`.*/\1/p' PROJECT_STATE.md | head -n 1)

dirty=0
git status --porcelain | grep . >/dev/null 2>&1 && dirty=1
ahead='?'
behind='?'
diverged=UNKNOWN
sync=REMOTE_UNAVAILABLE
remote_object=0

if [ -n "$remote_head" ] && git cat-file -e "${remote_head}^{commit}" 2>/dev/null; then
  remote_object=1
  counts=$(git rev-list --left-right --count "$head...$remote_head" 2>/dev/null || true)
  ahead=$(printf '%s' "$counts" | awk '{print $1}')
  behind=$(printf '%s' "$counts" | awk '{print $2}')
  if [ -n "$ahead" ] && [ -n "$behind" ]; then
    if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then
      diverged=YES
      sync=DIVERGED
    elif [ "$behind" -gt 0 ]; then
      diverged=NO
      sync=BEHIND_REMOTE
    elif [ "$ahead" -gt 0 ]; then
      diverged=NO
      sync=AHEAD_REMOTE
    else
      diverged=NO
      sync=OK
    fi
  fi
fi

[ "$dirty" -eq 1 ] && [ "$sync" = OK ] && sync=DIRTY

checkpoint_reachable=UNVERIFIED
if [ -n "$checkpoint" ]; then
  if ! git cat-file -e "${checkpoint}^{commit}" 2>/dev/null; then
    checkpoint_reachable=NO
  elif [ -n "$remote_head" ] && [ "$remote_object" -eq 1 ]; then
    if git merge-base --is-ancestor "$checkpoint" "$remote_head" 2>/dev/null; then
      checkpoint_reachable=YES
    else
      checkpoint_reachable=NO
    fi
  fi
fi

case "$checkpoint_reachable:$sync" in
  NO:*) remote_handoff=INVALID ;;
  YES:OK) remote_handoff=VALID ;;
  YES:*) remote_handoff=INCOMPLETE ;;
  *) remote_handoff=UNVERIFIED ;;
esac

printf '%s\n' 'PocketCinema Development State'
printf 'Machine/OS: macOS or Unix / %s\n' "$(uname -s 2>/dev/null || printf unknown)"
printf 'Branch: %s\nLocal HEAD: %s\nRemote HEAD: %s\nProduction baseline: %s\n' "$branch" "$head" "${remote_head:-UNAVAILABLE}" "$baseline"
printf 'Working tree: %s\nAhead: %s\nBehind: %s\nDiverged: %s\nActive milestone: %s\n' "$( [ "$dirty" -eq 1 ] && printf DIRTY || printf CLEAN )" "$ahead" "$behind" "$diverged" "$milestone"
printf 'Latest checkpoint commit: %s\nCheckpoint reachable from origin/main: %s\nRemote handoff status: %s\n' "${checkpoint:-UNRECORDED}" "$checkpoint_reachable" "$remote_handoff"
printf '\nSYNC STATUS: %s\n' "$sync"

case "$sync" in
  BEHIND_REMOTE|DIVERGED) printf '\nDO NOT BEGIN DEVELOPMENT UNTIL THE CHECKOUT IS SYNCHRONIZED.\n' ;;
  REMOTE_UNAVAILABLE) printf '\nREMOTE STATUS UNVERIFIED\n' ;;
esac

if [ "$checkpoint_reachable" = NO ]; then
  printf '\nREMOTE HANDOFF INVALID\n\n'
  printf '%s\n' 'PROJECT_STATE checkpoint is not present in origin/main.'
  printf '%s\n' 'Do not continue development from another machine.'
fi
