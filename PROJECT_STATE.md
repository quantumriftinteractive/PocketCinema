# PocketCinema Current Project State

Last updated: 2026-09-04
Last updated by machine: macOS development checkout
Current branch: `main`
Production baseline commit: `10987871d10a7f7be2f1a14f1b4e5d5d7c22904c`
Expected remote branch: `origin/main`
Active milestone: Milestone 23 — PocketCinema Server Desktop Distribution
Release state: Not release-ready. Milestones 21 and 22 remain physically
confirmed; fresh-install, packaging/licensing, and final release-scope gates are
open.

PocketCinema is the canonical pre-release identity. PocketStremio/`PSS` names
in historical evidence describe the application that was physically tested at
the time; they do not reduce the confirmed Milestone 21 or 22 behavior.

## Production Baseline

The committed baseline supports movie/series search, season and episode browsing,
opaque server-side stream selection and play sessions, direct-compatible and
bounded converted playback, Continue Watching/Resume/Play from Start,
host-isolated account playback, converted audio-track selection, bounded subtitle
burn-in/downscaling, opt-in selectable Matroska subtitles, and clean Miyoo Menu
exit/cleanup.

Milestone 22's three-track English Matroska acceptance—R1 cycling, subtitles
off, synchronized A/V/subtitles, progress saving, and cleanup—is physically
confirmed. The normal production fallback remains server-mediated MPEG-TS
burn-in. Whether the selectable Matroska player ships in v1.0 remains a release
decision.

## Production Invariants

- Keep addon URLs, media/subtitle URLs, and account credentials on the PCServer;
  the device receives only opaque identifiers.
- Stremio Service is loopback-only on the PCServer host; preserve the inbound
  firewall block for TCP `11470-11474` and `12470`.
- PocketCinema is transport-agnostic: direct HTTP is normal, an optional generic
  HTTP proxy supports Remote routing, and it never manages Tailscale.
- Automatic routing tries Local PCServer directly, then Remote PCServer through
  the configured proxy. Discovery and reachability remain separate.
- Continue Watching excludes startup and unverified pause intervals. All exits
  clean up FFplay, helpers, conversion/bridge, markers, and temporary subtitles.
- Selectable Matroska mode retains multiple tracks (up to three per preferred
  language), R1 switching, and the off toggle. Converted multi-audio retains
  manual track selection.

## Current Identity Refactor

Commit `a8c6c42222980a1ce77388c7ef2f7cbb301b0bdb` implements the controlled
pre-Milestone-23 PocketCinema identity refactor. It renames live client/server
paths, module names, configuration/environment identifiers, UI strings, current
documentation, and the M23 title. No desktop shell or release artifact was
created.

The one-time development Miyoo migration is documented in
`docs/pocketcinema-rename-migration.md`. It atomically migrates the saved
Local/Remote/Automatic profile, proxy, playback settings, and last-play state
into `/mnt/SDCARD/App/PocketCinema/`, without copying, reading, moving, or
changing Tailscale state. The old directory is preserved for manual post-test
archival because it contains the protected rollback Tailscale state.

Automated and static validation is complete. The renamed app has not yet had its
required Apps-context smoke test, so this rename is **Implemented/tested but not
physically confirmed**. Milestones 21 and 22 remain physically confirmed under
their historical PocketStremio evidence.

The canonical source artwork for the independent OnionOS Tailscale companion is
tracked at `UI_concept/Icons/PocketCinema_Tailscale_Companion_icon.png`. It is
not wired into `onion-tailscale/config.json`; that remains a separate packaging
and UI decision with no effect on the companion's application identity.

## Intentional Legacy Identifiers

- `POCKETSTREMIO_DISCOVER_V1` and `POCKETSTREMIO_PSS_V1` remain the private UDP
  discovery wire marker, avoiding a protocol migration.
- The prebuilt selector retains `POCKETSTREMIO_SELECTOR_*` as its private
  compiled-helper ABI. PocketCinema supplies it internally and passes
  PocketCinema titles explicitly.
- `/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state` remains the
  protected rollback copy and is never migrated or deleted by ordinary work.

## Active Work and Next Action

Milestone 23 is the sole **Next** milestone, but its desktop-server shell remains
planning-only. First perform the post-rename PocketCinema Apps-context smoke
test in `docs/pocketcinema-rename-migration.md`:

1. Deploy with `scripts/deploy-miyoo.ps1`, preserving and migrating the current
   development configuration.
2. Confirm PocketCinema appears and launches from OnionOS Apps; verify the saved
   route/profile, `friday` search, Local/Remote/Automatic routing, Continue
   Watching, clean B/Menu exit, and untouched Tailscale companion state.
3. Record the result before beginning Milestone 23 implementation, which still
   requires an explicit request.

## Latest Verified Checkpoint

Checkpoint commit: `965273d353f3a24a99ead5dbd6691a8e5ac2391a`
Remote verified: YES (`965273d` is reachable from `origin/main`)
Machine: macOS development checkout
Branch: `main`
Active milestone: Milestone 23 — PocketCinema Server Desktop Distribution

Completed:

- Controlled PocketCinema/PocketCinema Server/PCServer rename with no API-path
  redesign and no Tailscale lifecycle change.
- Explicit Miyoo configuration/state migration, current documentation updates,
  and canonical client/server artwork documentation.
- Canonical independent OnionOS Tailscale companion source artwork tracked,
  documented, and left unwired.
- Python compilation, 70 server unit tests, shell syntax and focused
  connection/proxy/status tests, PowerShell parsing, alternate-port API/play/
  Range verification, and `git diff --check`.

Pending:

- Apps-context rename smoke test and device log collection.
- ARM selector reproducibility rebuild: unavailable on this checkout because the
  ignored ARM cross-toolchain is absent. The deployed prebuilt-helper ABI is
  retained and documented.
- Any companion icon metadata or packaging update; `onion-tailscale/config.json`
  still uses its existing default terminal icon.
