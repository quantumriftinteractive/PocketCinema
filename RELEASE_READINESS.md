# PocketCinema Release Readiness

Current published state: **Miyoo client v1.0.1 released as CONDITIONAL GO**;
**Windows x64 and macOS arm64 PCServer remain v1.0.0**. The authoritative release
record index is [docs/releases/README.md](docs/releases/README.md).

## Accepted release evidence

v1.0.0 public distribution is complete, including accepted desktop and Miyoo
packages, compliance/corresponding-source materials, checksums and documentation.
Existing signing/provenance limitations remain documented; release completion
does not imply notarization or a change to the shipped signing identity.

For v1.0.1, physical OnionOS 4.3.1-1 observation confirmed video/audio,
preparation-panel handoff and normal Menu exit. The exact source/UI, published ZIP
checksum and all 30 manifest entries were verified during consolidation. Player,
libraries, helpers and font remain the v1.0.0 runtime. Main retains the 64-item
selector. No account-link diagnostic candidate or server fix is included.

## Outstanding validation and investigation

- QRI-75: full unrestricted host regression was outstanding at publication. Local
  consolidation results are recorded in the consolidation evidence, without
  rewriting release notes. OnionOS 4.4 beta and retained candidate post-playback
  logs/process snapshots still require focused acceptance.
- QRI-76: macOS account-link HTTP 502 is unresolved; the recorded source diagnostic
  worktree has not been recovered. No corrected server package is released.
- Local integration is not an off-machine checkpoint until authorized Gitea
  publication and fetched reachability verification.

Inherited M21/M22, desktop, transport, subtitle and playback evidence remains
valid unless a later material change intersects it. No broad physical retest is
required merely for repository consolidation.

## Historical gate lists

[The prior assessment](docs/history/release-readiness-before-2026-10-20.md) is
preserved as historical evidence. Its statements that v1.0.0 is not released,
clean-machine acceptance or packaging are pending, or M23 is incomplete are
superseded by the published release and current Linear project evidence. They
must not be resumed as development instructions.

See [repository state](PROJECT_STATE.md), [roadmap](docs/roadmap.md),
[workflow](docs/development-workflow.md) and
[consolidation evidence](docs/repository-consolidation-2026-10-20.md).
