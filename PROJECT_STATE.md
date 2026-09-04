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
burn-in/downscaling, selectable Matroska subtitles enabled by default with an
explicit opt-out, and clean Miyoo Menu exit/cleanup.

Milestone 22's three-track English Matroska acceptance—R1 cycling, subtitles
off, synchronized A/V/subtitles, progress saving, and cleanup—is physically
confirmed. The normal production fallback remains server-mediated MPEG-TS
burn-in when Matroska setup cannot proceed or the user explicitly opts out.

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
- Any accepted PASS behavior is production behavior: its normal deployment
  includes the required assets/configuration and it must not require test-only
  activation. Later loss of that normal path is a regression to restore at its
  smallest boundary; historical PASS evidence remains valid after restoration
  unless the accepted behavior or material dependency changed.

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
shell is implemented and automatically tested; its revised main screen is
visually confirmed, but owned-start/stop and Miyoo acceptance remain pending and
it is not packaged. Its Tk UI owns only a tracked PCServer child, persists non-secret
settings under the per-user PocketCinema directory, validates the editable
PCServer-only Stremio Service HTTP origin, detects FFmpeg/FFprobe, displays
sanitized status/log output, and uses the canonical server PNG as its window
icon. The server core remains independently source-runnable.
The documented direct macOS source entry point now resolves the repository
package root correctly instead of requiring `PYTHONPATH` or `python -m`.
The current development shell uses Homebrew Python 3.14 with `python-tk@3.14`
(Tcl/Tk 9.0.4). Apple Tcl/Tk 8.5 opened a blank dark-mode window and is not a
supported development launcher.
The M23 UX refinement is implemented and visually confirmed on macOS: the main
screen now derives concrete PocketCinema connections through Automatic / Local
network, keeps Stremio Service clearly separate, reports detected media tools,
and moves manual address/label/tool paths behind Advanced Settings. Existing
desktop preferences preserve their explicit Custom/manual behavior.

The M23 networking-model correction is implemented and automated-tested. The
desktop shell now treats PCServer bind, Local PocketCinema route, optional
Tailscale/Remote PocketCinema route, and the PCServer-only Stremio Service
endpoint as separate concepts. It reads ordinary macOS interface data without
managing or inspecting Tailscale state, displays concrete Local and detected
Remote routes for one all-interface PCServer child, and keeps returned device
URLs on the approved request route. The Mac's observed LAN address changed from
`192.168.20.x` to `192.168.0.x` during diagnosis; this means the earlier Local
failure cannot establish an address-selector regression. The current development
Mac cannot reach the gaming PC's intentionally localhost-contained Stremio
Service through its tailnet address; that is an expected split-host limitation,
not a Stremio or historical playback regression.

Focused Local M23 physical acceptance is **PASS**. The desktop-managed Mac
PCServer ran with Automatic / Local network on port 8757, displayed its concrete
Local and detected Remote routes without Advanced Settings, and accepted a
same-LAN Miyoo's `/api/status`, addon refresh, account-link creation and poll,
and `friday` search requests successfully. The recorded Miyoo source was on the
same `192.168.0.x` LAN; exact transient addresses remain out of committed state.
The Mac's configured Remote Stremio Service endpoint remained unreachable, as
expected because the gaming PC deliberately keeps that service localhost-only.
This does not invalidate the Local PCServer/account acceptance or inherited
account/playback evidence, and no Stremio listener, firewall, or network-provider
setting was changed. The desktop-managed Tailscale / Remote PocketCinema route
was displayed but has not yet had a physical Miyoo smoke test.

The server now emits a sanitized Stremio Service status diagnostic only for the
first failure, a changed failure reason, recovery, or a later failure after
recovery; repeated identical `/api/status` failures do not flood the desktop
log. Status response and owned-child lifecycle behavior are unchanged, while the
desktop's explicit connection check continues to show a fresh reachable or
unreachable result.

The next M23 desktop networking UX refinement is implemented and
automated-tested. The dynamic PocketCinema connection list now follows the
selected listen mode: Automatic / Local network binds and displays usable Local
routes only; All interfaces displays all usable Local and detected Remote
routes; Custom displays only its explicit route. It filters loopback,
link-local, multicast, unspecified, and wildcard addresses from automatic
routes, refreshes the stopped desktop display for mode, port, and custom-address
changes, and keeps Status concise with an available-route count. It does not
inspect or manage Tailscale state/lifecycle, change the Stremio Service model,
or alter PCServer API/discovery behavior. The existing Local physical acceptance
is inherited; the new presentation and Remote route remain physically pending.

The M22 production-promotion gap is corrected and locally verified. The Miyoo
runtime fallback and shipped example now enable selectable Matroska subtitles;
an explicit persisted or environment value of `0` remains the opt-out and
existing configurations are preserved. Direct PCServer invocation now enables
the same mode by default with `--disable-matroska-subtitles` as its clear
opt-out; desktop and source managers retain compatible explicit startup
behavior. This changes no providers, filters, limits, cache, conversion, or
M21/M22 media behavior. Historical M22 subtitle evidence is inherited.

The current renderer/display issue remains separate and unresolved: the live
Miyoo configured with Matroska mode enabled discovered six tracks and logged R1
stream switches, but captions were not visible. This promotion correction does
not claim to fix that renderer/display symptom.

Next exact action: continue the focused dynamic-list/Remote check: visually confirm Automatic
shows only Local routes, All interfaces shows Local plus detected Remote, and
Custom shows only its explicit route. Return to All interfaces, use the
displayed Remote URL in the existing Miyoo Remote profile and unchanged generic
proxy, search `friday`, then stop the owned server. Do not rerun M21/M22
playback matrices or account playback. Keep the separate Matroska
renderer/display symptom open for focused diagnosis rather than treating this
default-promotion correction as its resolution.

## Latest Verified Checkpoint

Checkpoint commit: `3ed29b8`
Remote verified: YES (`1000731` is reachable from `origin/main`)
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

- Homebrew `python-tk@3.14` installed as the local macOS development prerequisite;
  Python 3.14/Tcl-Tk 9.0.4 desktop construction and the desktop unit suite pass.
  Physical relaunch confirmation remains pending.

- M23 user-facing UX refinement implemented, visual macOS launch confirmed, and
  automated-tested: Automatic / Local network derives concrete usable routes;
  All interfaces and Custom remain available; manual address/label/tool paths
  are secondary; Stremio Service is distinct; primary server actions are
  state-aware. Full owned-start/stop and Miyoo `friday` acceptance remains pending.

- M23 networking-model correction implemented and automated-tested: macOS host
  interface discovery derives Local plus an informational existing
  Tailscale/Remote route without Tailscale lifecycle/state access; a single
  all-interface owned child exposes both concrete PCServer URLs; discovery
  remains Local-only; and approved Host handling preserves the client route in
  returned play/subtitle URLs. Live Mac owned-child health checks passed through
  both routes. M21/M22 media and client evidence is inherited; only the focused
  desktop-managed Remote/Miyoo routing acceptance remains pending.

- M23 Local desktop-management acceptance is physically confirmed: Automatic /
  Local network on port 8757 displayed concrete Local and detected Remote
  PCServer routes without Advanced Settings; a same-LAN Miyoo completed status,
  addon refresh, account-link/poll, and `friday` search requests. The separately
  hosted, intentionally localhost-only Stremio Service was expected to be
  unreachable from this Mac and did not change its security boundary. Remote
  PocketCinema-route acceptance remains pending.

- Stremio Service status logging is transition-aware and URL-sanitized: it emits
  an initial failure, a reason change, recovery, and a later failure after
  recovery, while suppressing identical repeats. API status payloads and owned
  lifecycle behavior remain unchanged.

- M23 dynamic desktop connection-list refinement implemented and
  automated-tested: Automatic / Local binds and lists Local routes only; All
  interfaces lists usable Local and detected Remote routes; Custom lists its
  explicit route. The stopped UI refreshes these rows for mode, port, and custom
  address changes, filters non-device addresses, and reports only a concise
  available-route count in Status. Existing Local physical acceptance is
  inherited; the new presentation and Remote smoke are pending.

- M22 production-promotion correction implemented and locally verified: the
  Miyoo runtime and shipped configuration enable selectable Matroska subtitles
  by default, explicit `0` remains an opt-out, and direct PCServer startup
  matches desktop/manual manager semantics with a clear CLI opt-out. Existing
  configurations remain untouched. M22 evidence is inherited; the separate
  live renderer/display symptom (tracks switch but captions are not visible)
  remains open.

Pending:

- M23 focused dynamic-list presentation and desktop-managed Tailscale / Remote
  route acceptance, if applicable to this Mac topology, then later macOS
  packaging and the required Windows clean-machine bundle/distribution phases.

- ARM selector reproducibility rebuild: unavailable on this checkout because the
  ignored ARM cross-toolchain is absent. The deployed prebuilt-helper ABI is
  retained and documented.
