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
- The Miyoo never reaches Stremio Service directly; PocketCinema Server is the
  device-facing boundary. The current local default is `http://127.0.0.1:11470`;
  preserve the inbound firewall block for TCP `11470-11474` and `12470` when
  the service runs locally on the PCServer host. M23 implements a validated,
  PCServer-only configurable endpoint on another reachable host.
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

Automated and static validation is complete. The renamed app is **Physically
Confirmed** by a focused Apps-context migration smoke test: PocketCinema
appeared alongside the retained PocketStremio app, launched, searched `friday`,
saved Local and Remote PCServer routes, traversed Local → Remote → Local under
Automatic routing, and exited with B. This confirms rename/deployment wiring
only; Milestones 21 and 22 remain physically confirmed under their historical
PocketStremio evidence and were not re-qualified.

Historical evidence is inherited unless a later material change intersects the
validated behavior. The rename impact assessment classified path, deployment,
migration, configuration-key, process-detection, and metadata wiring as the
only targeted smoke-test surface; unchanged playback, subtitle, transcoding,
and account-compatibility evidence for Milestones 21 and 22 remains confirmed.
The current development machine cannot reach its configured Stremio Service, so
account playback was not re-tested in this session; this does not invalidate
the historical evidence.

The canonical source artwork for the independent OnionOS Tailscale companion is
tracked at `UI_concept/Icons/PocketCinema_Tailscale_Companion_icon.png`. Its
74×74 app-local runtime copy, `onion-tailscale/icon.png`, is referenced by
`onion-tailscale/config.json` and copied by the normal deployer to
`/mnt/SDCARD/App/Tailscale/`. This visual-only packaging update retains the
companion's separate `Tailscale` application label. It is **Physically
Confirmed**: the Apps menu displayed the custom icon without a reboot, the
normal companion screen retained its current state, proxy endpoint, and tailnet
IP, and B exited cleanly.

The canonical PocketCinema client artwork is implemented as the tracked 74×74
app-local runtime copy `app/icon.png`, deployed to
`/mnt/SDCARD/App/PocketCinema/icon.png` and referenced by its `config.json`.
It is **Physically Confirmed**: OnionOS Apps displayed the custom PocketCinema
icon, the app reached its normal Home/UI and server status, and B exited cleanly.
The independent Tailscale companion retained its separate custom icon. This is
visual metadata and packaging only, with no network, playback, migration,
Tailscale, or PCServer behavior change.

## Intentional Legacy Identifiers

- `POCKETSTREMIO_DISCOVER_V1` and `POCKETSTREMIO_PSS_V1` remain the private UDP
  discovery wire marker, avoiding a protocol migration.
- The prebuilt selector retains `POCKETSTREMIO_SELECTOR_*` as its private
  compiled-helper ABI. PocketCinema supplies it internally and passes
  PocketCinema titles explicitly.
- `/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state` remains the
  protected rollback copy and is never migrated or deleted by ordinary work.

## Active Work and Next Action

Milestone 23 is active. The initial functional macOS source-development desktop
shell is implemented and automatically tested, but is not physically confirmed
or packaged. Its Tk UI owns only a tracked PCServer child, persists non-secret
settings under the per-user PocketCinema directory, validates the editable
PCServer-only Stremio Service HTTP origin, detects FFmpeg/FFprobe, displays
sanitized status/log output, and uses the canonical server PNG as its window
icon. The server core remains independently source-runnable.
The documented direct macOS source entry point now resolves the repository
package root correctly instead of requiring `PYTHONPATH` or `python -m`.
Apple Tcl/Tk 8.5 initially opened a blank dark-mode window; the shell now applies
an explicit visible compatibility theme for that legacy macOS runtime and awaits
relaunch confirmation.

Next exact action: perform the focused macOS desktop-shell physical acceptance:
launch, verify title/icon, save and reload one harmless setting, configure the
known Stremio endpoint, start/stop the owned PCServer, and run one `friday`
Miyoo connection/search smoke test. Do not rerun M21/M22 playback matrices
unless this new lifecycle/configuration path exposes a specific regression.

## Latest Verified Checkpoint

Checkpoint commit: `50ebf4ad6c08872a2ab0096ec525f5c64750afd5`
Remote verified: YES (`50ebf4a` is reachable from `origin/main`)
Machine: macOS development checkout
Branch: `main`
Active milestone: Milestone 23 — PocketCinema Server Desktop Distribution

Completed:

- Controlled PocketCinema/PocketCinema Server/PCServer rename with no API-path
  redesign and no Tailscale lifecycle change; focused Apps-context deployment,
  connection-route, search, and B-exit smoke test physically confirmed.
- Explicit Miyoo configuration/state migration, current documentation updates,
  and canonical client/server artwork documentation.
- Canonical independent OnionOS Tailscale companion source artwork tracked,
  documented, and wired as a 74×74 app-local runtime icon without a label or
  runtime behavior change; Apps-context display and normal companion screen
  behavior are physically confirmed.
- Canonical PocketCinema client artwork wired as a 74×74 app-local OnionOS icon;
  the Apps-menu icon, normal Home/UI and server status, B exit, and separate
  Tailscale icon are physically confirmed.
- Durable regression-impact/evidence-inheritance policy recorded. It preserves
  M21/M22 confirmation, requires diff/history-based targeted testing, and
  specified M23's configurable PCServer-only Stremio Service endpoint before
  implementation began.
- Python compilation, 70 server unit tests, shell syntax and focused
  connection/proxy/status tests, PowerShell parsing, alternate-port API/play/
  Range verification, and `git diff --check`.

- M23 initial macOS desktop shell implemented and automated-tested: stdlib Tk
  presentation, atomic non-secret config, tool/status checks, PCServer-only
  remote-or-local Stremio Service origin validation, explicit per-user child
  paths, and owned-process start/stop/crash handling. This is not a release
  artifact and awaits the focused physical macOS/Miyoo acceptance above.

- Direct source launch regression fixed and tested: `/usr/bin/python3
  server/pocketcinema_desktop.py` now bootstraps the repository import path
  before loading the Tk shell.

- Apple Tcl/Tk 8.5 dark-mode rendering regression fixed and construction-tested
  with its explicit `clam` compatibility theme; physical relaunch confirmation
  remains pending.

Pending:

- M23 focused macOS desktop-shell physical acceptance, then later macOS
  packaging and the required Windows clean-machine bundle/distribution phases.

- ARM selector reproducibility rebuild: unavailable on this checkout because the
  ignored ARM cross-toolchain is absent. The deployed prebuilt-helper ABI is
  retained and documented.
