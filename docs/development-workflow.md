# PocketCinema canonical development workflow

## Repository and authority

Use one Git repository/common directory. On this Mac it is
`/Users/jdragocy/Quantum Rift Interactive/Projects/MM--PocketStremio`.
Gitea `origin` (`QuantumRiftInteractive/MM--PocketStremio`) owns development
history. GitHub `quantumriftinteractive/PocketCinema` is the publication destination.
Do not develop independently on public main or assume a tag exists on both hosts.
Remote synchronization is a reviewed explicit operation; the website export
workflow does not establish source mirroring.

## Start and integrate work

1. Read PROJECT_STATE, AGENTS, the release index and relevant Linear issue.
   Run the platform dev-status script, inspect all dirty/untracked files, and
   verify actual remote state and the last durable checkpoint. Explain existing
   work before editing; never discard it to make checkout easier.
2. Use a short-lived branch associated with one issue, such as
   `fix/qri-76-account-link` or `feature/qri-27-linux`. Reuse existing branches
   instead of creating duplicates. Record its branch name in the issue when
   authorized to update Linear; a documentation task does not authorize messaging.
3. Preserve useful unfinished changes in focused commits on their own branches.
   Source-only experiments must be explicitly marked unbuilt/unshipped; they do
   not belong on main where a matching runtime asset is required.
4. Validate the actual changed behavior, review staged files for private data and
   unrelated assets, and integrate into main explicitly after checks. Preserve
   published and historical ancestry with ordinary merges; do not rewrite shared
   commits or squash away the only record of accepted maintenance work.
5. Publish reviewed development refs to Gitea only with authorization, fetch and
   verify reachability. Public synchronization is a separate explicitly scoped
   action. Verify public refs rather than assuming an automatic mirror worked.

## Worktrees and releases

Default to the canonical checkout. Use `git worktree` only for a concrete
concurrent task, sharing the same Git common directory. Record path, branch,
Linear issue and preservation status in the handoff. Do not create independent
permanent PocketCinema clones as competing development sources of truth.

Retain worktrees until their working state and all valuable commits are reviewed
and durably preserved; remove them only when authorized. Existing maintenance
worktree is deliberately retained during consolidation. Do not create a release
branch unless supporting a parallel maintenance line actually requires it.

Published tags are immutable. Import exact original refs; never recreate, move
or delete a published tag. A release snapshot and maintenance history may have
different commits even when their shipped source files match. Preserve both tips,
retain package manifests/checksums, and merge their histories deliberately.

## Documentation and artifacts

- `docs/releases/README.md` is the single release record index. Versioned release
  notes/manifests and checksum files are immutable historical release evidence.
- PROJECT_STATE owns concise repository state, invariants and handoff. Linear
  owns live issue priorities/status; roadmap summarizes sequencing.
- Historical documents retain dated observations. Label superseded candidate
  status and next actions clearly; do not silently resume old release blockers.
- Generated ZIPs, extracted distributions, private configurations, logs and
  recovery bundles stay out of source commits. Preserve unique source artwork.
  Ignoring a local artifact is not permission to remove it.

The existing `feature/selector-128` preservation commit is a specific historical
exception authorized by the user. Main retains MAX_ITEMS=64 and the accepted ARM
binary. Build, physical larger-list acceptance and any eventual promotion remain
QRI-28 work, outside consolidation.

## Machine switches and local-only sessions

A local commit is not a remote checkpoint. Before a machine switch, publish all
intended branches and required exact tags with authorization, then fetch Gitea,
verify reachability and ahead/behind state, and update the handoff. Do not claim
another machine can resume while useful work exists only locally. If publication
is prohibited, stop before remote writes and report HANDOFF INCOMPLETE with the
exact unpushed refs. Never force-push to solve a handoff problem.
