# PocketCinema Repository State

Last updated: 2026-10-20
Last updated by machine: macOS canonical development checkout
Current branch: `main`
Production baseline commit: `88ac551177999165caf45ab40251490061f101b2`
Expected remote branch: `origin/main`
Active milestone: Post-release maintenance validation — QRI-75

## Ownership and release state

This file owns the concise repository state, production invariants, and development
handoff. Linear owns current issue priorities and live planning. The authoritative
published release record index is [docs/releases/README.md](docs/releases/README.md).
`docs/roadmap.md` summarizes sequencing; older evidence records observations at its
date and must not override later release records.

- Miyoo client **v1.0.1 is released**, as CONDITIONAL GO. Exact published source
  tag: `v1.0.1` at `88ac551177999165caf45ab40251490061f101b2`.
- PocketCinema Server (PCServer) remains **v1.0.0** for Windows x64 and macOS arm64.
  No server maintenance release is included in the client update.
- OnionOS 4.3.1-1 video/audio, preparation-panel handoff and normal Menu exit are
  **Physically Confirmed**. This does not constitute retained process-cleanup log
  evidence or OnionOS 4.4 beta acceptance.
- Full unrestricted host-suite execution was outstanding at publication. The local
  consolidation run now passes: 208 tests run, 202 passed and 6 native Windows
  checks skipped. Evidence is recorded separately; the published release record
  remains unchanged. QRI-75 also requires OnionOS 4.4
  beta and retained post-playback logs/process snapshots.
- macOS account-link HTTP 502 remains **unresolved** (QRI-76). No diagnostic
  candidate or corrective server behavior is included in this consolidation.
- v1.0.0 public release, desktop distribution and sealed release artifacts are
  accepted historical baseline. Old pre-release gate lists are not current tasks.

Exact released client ZIP SHA-256:
`3ca28149174d8c03f6358ca17845a93fbe05e1207611b6730ffd60e9e532a1b6`.

## Production invariants

- Preserve all physically accepted M21/M22 playback, subtitles, audio, progress,
  account, transport and cleanup behavior unless changed and revalidated at its
  smallest material boundary. An accepted PASS stays production behavior.
- Miyoo talks only to PCServer. Credentials and private upstream URLs stay on
  PCServer; device APIs use opaque identifiers and preserve Range behavior.
- Stremio Service is PCServer-only; local default is loopback. Preserve the gaming
  PC's inbound TCP 11470–11474/12470 block. Never expose it to the Miyoo.
- PocketCinema is transport-agnostic and never manages or inspects Tailscale state.
  Preserve independent Tailscale identity and protected rollback state.
- Device files stay under `/mnt/SDCARD/App/PocketCinema/`; OnionOS core stays
  untouched. Menu exits FFplay; B navigates selector screens.
- Main and released artifacts retain the **64-item selector** and its accepted
  ARM binary. The source-only 128-item preservation branch is Experimental.

## Canonical repository and branches

Canonical path: `/Users/jdragocy/Quantum Rift Interactive/Projects/MM--PocketStremio`.
Gitea `origin` is development authority. GitHub PocketCinema is the publication
destination, not a second independently edited development main.

- `main`: reviewed integrated development.
- `maintenance/v1.0.1-stream-diagnostics`: original three maintenance commits through
  `137c126`, retained without rewriting.
- `feature/selector-128`: QRI-28 historical source-only preservation; no build,
  physical test, main merge or shipment authorized by consolidation.
- `chore/repository-consolidation`: temporary reviewed integration branch.
- QRI-76's recorded `/tmp/pocketcinema-account-link-v101` candidate was not recovered
  in this checkout, objects/reflogs, standard worktree locations or scoped session
  evidence search. Do not create a replacement and claim preservation.

See [development workflow](docs/development-workflow.md). Existing maintenance
worktree and all release files/recovery backups are retained.

## Development Handoff — local consolidation (2026-10-20)

The user authorized local preservation, exact tag import, history-preserving merges,
document reconciliation, verification and local main integration. Remote writes,
deployment, releases, cleanup, worktree removal and unrelated features remain
unauthorized. No selector or account-link implementation is promoted.

Both original histories are retained: public `88ac551` and maintenance `137c126`
have byte-identical UI scripts; maintenance additionally retains tests, evidence,
a log clarification and a Unix test-fixture executable-mode correction.

Detailed operations, SHAs, recovery findings and test results:
[consolidation evidence](docs/repository-consolidation-2026-10-20.md).
Earlier detailed state is preserved in
[historical state](docs/history/project-state-before-2026-10-20-consolidation.md).

Next exact action: review local consolidation results and obtain explicit remote
publication authorization. Then publish reviewed main/preservation branches and
the unchanged v1.0.1 tag to Gitea, fetch and verify reachability before switching
machines. GitHub writes require their own explicit scope. Continue QRI-75/76 only
under separate task scope; do not reopen unrelated historical physical matrices.

## Local Consolidation Checkpoint — not published

Local consolidation commit: `0f7a48007cc857c34e802a7c8b6d6de2168bc678`
Validation: 208 tests run, 202 passed, 6 Windows-only skips; seven shell checks,
compilation, syntax, release hashes, ancestry and preservation checks passed.
Remote verified: NO — publication is explicitly prohibited until separately
approved. This local commit is not the durable cross-machine checkpoint below.

## Latest Verified Checkpoint

Checkpoint commit: `b76e20d`
Remote verified: YES — historical checkpoint is reachable from origin/main
This is the prior remote checkpoint, not the new local consolidation checkpoint.
The current local integration has not been pushed; cross-machine handoff is
**INCOMPLETE** until explicit publication and independent remote verification.
