# PocketCinema Current Project State

Last updated: 2026-09-09
Last updated by machine: Windows development checkout
Current branch: `main`
Production baseline commit: `10987871d10a7f7be2f1a14f1b4e5d5d7c22904c`
Expected remote branch: `origin/main`
Active milestone: Milestone 23 — PocketCinema Server Desktop Distribution
Release state: v1.0.0 platform artifacts sealed; final tag/publication pending.
Milestones 21 and 22 remain physically confirmed, and the final release
assembly is tracked separately from post-v1 engineering work.

Final v1.0.0 assembly status: Miyoo, Windows x64, and macOS arm64 platform
artifacts are sealed. The Miyoo and macOS distribution ZIPs were assembled
locally under ignored `.tmp/final-release-assembly/`; the sealed Windows ZIP
and Miyoo corresponding-source ZIP remain separate release assets identified by
their recorded SHA-256 values. Final user documentation, the 16-page public
export, and the tracked checksum plan are current. No tag or publication has
been created.

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

Milestone 23 is active. The packaged macOS `PocketCinema Server.app` v1 baseline
(1.0.0 (1)) is physically accepted: its regular foreground UI uses the canonical
icon, bundles FFmpeg/FFprobe 9.0.1, cleanly shuts down on red X, native Quit, and
Cmd+Q, and cleans up its owned PCServer child. The bundle is ad-hoc signed but
not Developer ID signed or notarized, so clean-Mac Gatekeeper warnings remain a
release-review item. The known-good baseline is
`4ec89b591ded17685eef36bc9a8d821672b6ee6a`; the discarded hide-to-background /
Dock-reopen experiment is not part of v1.
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

Advertised-route persistence is complete and sealed by
`6f9aa411f1729170c5c98efe4552c0623445236d` and
`dd0d695425c8690c7372664401ec6700b47f7fab`: Start and Restart atomically save
the requested settings before launching the owned child, so a later desktop-app
restart cannot reintroduce a previous manual route. Automatic mode resolves
current interfaces at launch, explicit Custom/manual routes remain persisted,
and `/api/status` exposes the child’s effective advertised route. Focused
configuration, lifecycle, and playback-route regression coverage passes; no
new Miyoo test is required because this changes persisted configuration only.

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
setting was changed.

Focused M23 desktop Remote-route acceptance is **PASS**. The desktop advertised
a detected Tailscale / Remote IPv6 connection, while the Miyoo smoke manually
used the known Tailscale IPv4 PCServer address through its independently
configured userspace HTTP proxy. A real direct stream played remotely and
selectable subtitles worked normally. Brief recurring millisecond-scale
micro-stutters were usable and did not fail playback, so they are a non-blocking
performance observation for later reproduction. The IPv6 advertisement versus
successful IPv4 use is likewise a non-blocking route-UX follow-up: later work
may prefer IPv4, label address families clearly, or deliberately retain both.
No exact transient address is committed.

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
or alter PCServer API/discovery behavior. The Local and supported Remote
transport smokes are physically confirmed. The observed IPv6 advertisement and
brief micro-stutters remain non-blocking future UX/performance follow-ups.

Focused Windows M23 desktop-shell diagnosis found and repaired two independent
desktop regressions. Windows previously fell back to hostname-only address
enumeration, losing interface identity and consequently presenting the
Tailscale IPv4/IPv6 tunnel and a WSL virtual adapter as Local. It now reads
active Windows interface metadata only, retains hardware LAN routes and the
recognized tunnel, omits generic virtual adapters, and labels the tunnel routes
Tailscale / Remote. The desktop lifecycle and UI also now retain the established
Windows-manager lookup for Stremio's existing per-user `ffmpeg.exe` and
`ffprobe.exe` runtime; PocketCinema neither downloads nor redistributes them.
This is automated-tested against representative Windows records and the live
Windows host, but still requires the focused desktop/Miyoo observation.

The contemporaneous empty-stream response is separately classified as current
source availability, not a desktop-shell or preflight regression. The linked
account is reread after linking and has stream-capable sources, but the checked
movie returned zero acceptable candidates: one source was unavailable and one
returned only policy-rejected P2P, external-player, private-address, or
non-HTTP shapes. The missing FFprobe had disabled preflight but did not remove
these streams; no provider, cache, eligibility, or account behavior was
changed. Historical M21/M22 evidence remains inherited.

The M22 production-promotion gap is corrected and locally verified. The Miyoo
runtime fallback and shipped example now enable selectable Matroska subtitles;
an explicit persisted or environment value of `0` remains the opt-out and
existing configurations are preserved. Direct PCServer invocation now enables
the same mode by default with `--disable-matroska-subtitles` as its clear
opt-out; desktop and source managers retain compatible explicit startup
behavior. This changes no providers, filters, limits, cache, conversion, or
M21/M22 media behavior. Historical M22 subtitle evidence is inherited.

The renderer migration regression is resolved. The PocketStremio-to-PocketCinema
deployment transition retained an app-local FFplay binary that reads legacy
`POCKETSTREMIO_*` subtitle/font bindings while the renamed client supplied only
`POCKETCINEMA_*`; its migrated `fonts.conf` also named the old app directory.
The normal client now supplies both internal identities, deployment rewrites the
fontconfig path, and the rebuilt app-local FFplay is deployed with the accepted
libass scale. This changed no provider, Matroska selection, conversion, R1, or
cleanup behavior; the corresponding M22 physical evidence is inherited.

The first readability attempt is **not accepted**: it deployed and ran, but
captions remained too small. Its `original_size=426x240` hypothesis was wrong:
the FFmpeg 2.4 subtitles filter passes only the input and original *aspect
ratios* to libass, and both `426x240` and `640x360` are 16:9. It therefore did
not produce an absolute font-size increase. The replacement app-local filter
adds a bounded `font_scale` option and calls libass's unconditional
`ass_set_font_scale`; the selected Matroska track now passes `font_scale=1.5`.
That applies to both generated SRT and styled ASS events without changing track
selection, providers, packaging, R1, or fallback behavior. The ARM rebuild and
normal deployment succeeded; the deployed player hash matches the rebuilt local
binary and contains the new filter string. Apps-context observation now confirms
that captions are noticeably larger and acceptable at the 1.5x production
default.

Configurable subtitle size is implemented through the normal PocketCinema UI
and physically confirmed PASS. It persists the bounded 1.0x, 1.25x, 1.5x,
2.0x, 2.5x, and 3.0x choices and feeds the existing app-local `font_scale`
renderer path; missing or invalid values fall back to 1.5x. Physical acceptance
confirmed 1.0x is smaller, 3.0x clearly larger, and 1.5x restores and persists.
Subtitle position controls remain future UX work; the size presets are
physically accepted through the normal UI, and the normal default remains 1.5x.

Focused Windows M23 observation found a separate desktop UI freeze boundary:
the 700 ms Tk poll synchronously refreshed routes, which on Windows spawned
PowerShell interface discovery on the UI thread. Connection refresh now runs in
a worker, start/restart/stop/close waits remain off the UI thread with owned
operations serialized, and unchanged log text is not redrawn each poll. Service
checks and child log draining remain background work. The user physically
confirmed normal Windows desktop use remained responsive after this repair, so
the focused responsiveness acceptance is **PASS**. It does not change PCServer
ownership, network-provider behavior, or the API.

Stremio-backed My Library v1 is **Physically Confirmed PASS**. Stremio owns the
library state; PCServer fetches, caches, and normalizes `libraryItem` data through
the read-only datastore API, with no library writes or add/remove operations.
The Miyoo exposes `My Library -> Movies / Series`, bounded paging at a maximum of
60 content items per page, and hands both media types into the existing
source-selection and playback flow. Series metadata carries safe episode-aware
watched/current state: fully watched seasons show `WATCHED`, watched episodes
show `WATCHED`, the current/latest episode shows `*`, and current-plus-watched
episodes retain both markers without inventing a parent-series watched label.
Physical acceptance confirmed the menu, linked-account series loading, page-one
60-item boundary, next/previous page navigation, fixture 3% seasons 1--3 and
episode markers, and movie/series playback handoff. The shared Thunderbolts
playback failure was traced to runtime configuration: PCServer advertised stale
`192.168.20.151` while the Miyoo used `100.82.23.65`; correcting the runtime
advertisement made the same stream play successfully. This was not a Library
code failure. Release-year fallback (`????`) and the roughly 60-second
Matroska subtitle-package fallback remain separate follow-ups.

The focused Next Episode / Continue Series extension is now **Physically
Confirmed PASS**. For the linked 3% series, the series-level continuation action
resolved to `NEXT EPISODE - S4E5`, entered the existing Play/source-selection
pipeline, and started with picture and audio. Ordinary selection of watched S4E4
continued to show the unchanged `Play / Back` episode action menu; watched state
does not add a second episode-level action. The resolver remains read-only,
uses canonical normalized episode order, handles season boundaries, omits
unreliable or completed targets, and reserves one of the shipped selector's 64
rows for the continuation action.

The Miyoo jq compatibility seal renamed the continuation expression variable
`$label` to `$action_label`; the resulting `CONTINUE - S4E7 Chapter 07: Sun`
row was physically re-confirmed on-device without changing continuation
semantics.

### Current Release Follow-ups

- Library metadata presentation: Search supplied Thunderbolts (2025), while
  My Library displayed `????` for the same title. This is a non-blocking
  release-year enrichment/presentation gap; it does not affect Library identity,
  watched state, navigation, or playback.
- Playback startup: the Matroska subtitle-package fallback can wait roughly
  60 seconds before ordinary playback begins. This is a separate startup UX /
  performance issue. The historical M22 subtitle acceptance remains valid and
  is not reopened by this observation.
- Runtime route advertisement: during the shared Thunderbolts failure, the
  Miyoo used `100.82.23.65:8755` while PCServer advertised stale
  `192.168.20.151:8755`. Start/Restart now persist the requested route before
  launch; the stale-route persistence regression is sealed by the automated
  PASS gate and no new Miyoo playback retest was required.
- Remaining release/distribution work includes
  Windows clean-machine packaged-artifact smoke, fresh/distribution-SD
  validation, renderer and subtitle-asset licensing/package completeness,
  final release-artifact audit, and unsigned/signing and runtime-warning review.
  The Windows packaged candidate and development-
  machine smoke already exist; they must not be recreated as part of this
  inventory.

### Development Handoff - Miyoo source preservation (2026-09-09)

The recovered matching FFplay 2.4.14 Windows source/configuration is now
preserved as small Git metadata under `release-sources/miyoo/`. The final patch
recreates both modified source files exactly; all 4,706 pristine archive members
were verified. The source staging script was tested without compiling. The
original recovered tree, player, compiler, sysroot and font remain untouched.
All fifteen deployment library files match the recovered SDK archive.

The SDK historical provenance remains C: it is strongly linked to Steward's Miyoo Mini /
Buildroot 2021.11 family, but its exact final configuration and applied package
set remain unproven. The exact fifteen Buildroot 2021.11 dependency archives, all
19 package patches, and declared license files are now preserved in the controlled
external archive C:\\Users\\ysocr\\PocketCinema-Miyoo-v1.0.0-release-inputs; each
package input is provenance A while the recovered SDK as a whole remains C. The
exact shipped font is also tied to the local Stremio Web Git checkout/blob, while
its upstream Tokotype build artifact remains unresolved. Large source/analysis
copies remain ignored and no runtime artifacts or upstream trees are committed.
No deployment, SD-card access, FFplay rebuild or selector rebuild occurred. All
physical PASS evidence is inherited; redistribution remains pending the public
notices/source bundle and final dynamic-link compliance audit.

Next exact action: assemble and audit the public notices/corresponding-source
bundle, verify the final dynamic-link and FFmpeg GPL/nonfree conditions, then
complete the independent reproduction and release-artifact gates separately.
Historical SDK configuration and Tokotype export provenance remain documented
limitations. See `release-sources/miyoo/COMPLIANCE-REVIEW.md`.

The public Miyoo compliance bundle metadata and license audit is now PASS at
`release-sources/miyoo/public/`: 56 files, 613,227 bytes, all 19 Buildroot
patches, license texts, FFmpeg configuration/patch metadata, source hashes, and
replacement instructions. The corresponding source archives remain separate
release assets and are not committed. This does not mark reproduction, fresh
install, or final release acceptance PASS.

The corresponding-source release asset is now assembled and verified outside Git:
`C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-corresponding-source.zip`, 71 files,
44,451,296 bytes, SHA-256
`75e9cd126ac893d619926f69c808b71081d56dc5f5fd7f4dd48d442bde30cc3b`. It contains
the exact 16 source archives, 19 patches, licenses, notices, and manifests while
excluding compiler/SDK/sysroot/runtime/selector/font binaries and user state.

The authorized independent FFplay reproduction attempt was run in the isolated
external workspace `C:\Users\ysocr\PocketCinema-Miyoo-v1.0.0-reproduction`.
Source and patch verification passed, but configure failed while probing libass:
the recovered Arm GNU 15.2.1 compiler's `libgcc_s.so.1` requires GLIBC_2.34
pthread symbols absent from the recovered Miyoo sysroot. No configuration or
binary was produced. The reproduction gate is classified D (build failed),
documented in `release-sources/miyoo/REPRODUCTION-2026-09-09.md`; compliance
source sufficiency remains separate, but final v1 approval remains open.

The bounded follow-up isolated the failure: the compiler selected its GLIBC_2.34
`libgcc_s.so.1`, while recovered target sysroot copies require only GLIBC_2.4.
Historical `config.mak` and configure evidence preserve
`LDFLAGS=" -L<sysroot>/usr/lib -Wl,-rpath-link,<sysroot>/usr/lib"`, placing the
target library directory first. The proposed next retry is limited to that
historical environment correction; no retry has run. Details are in
`release-sources/miyoo/REPRODUCTION-2026-09-09.md`.

### Prior Windows system-tray lifecycle handoff

The Windows tray lifecycle and its focused UX refinements are **Physically
Confirmed PASS**: X hides while PCServer keeps running, one native notification
reports that it remains in the tray, Open restores the same window, Start/Stop/
Restart work with the active listen mode in the running tooltip, and Quit exits
cleanly. The normal Windows desktop path hides its
existing window on X, restores it from Open PCServer, synchronizes tray and GUI
Start/Stop/Restart, and uses explicit Quit to stop its exact owned child through
a private graceful-shutdown pipe before joining tray/background workers and
exiting. A duplicate launch restores the existing per-user controller. The
canonical server PNG is reused; Windows-only pystray/Pillow/six dependencies
and future bundle obligations are recorded in the desktop distribution plan.
No Windows Service or Start with Windows behavior was added.

The same smoke exposed duplicate Remote IPv6 presentation and Windows console
flashes, and added dynamic hover status as a production requirement. Refinements
are **Physically Confirmed PASS**: the GUI prefers usable
Remote IPv4 over IPv6 on the same interface while preserving underlying routes
and IPv6-only fallback; PowerShell interface enumeration and the startup FFmpeg
capability probe now use no-console flags; the existing tray icon reports
`PocketCinema Server - Started` / `PocketCinema Server - Stopped` from actual
owned-child state, including busy restart polling. No dependency was added.

The user physically confirmed correct Local/Remote IPv4 presentation, duplicate
Remote IPv6 suppression, no Start/Stop/Restart console flashes, correct hover
state, X/background operation, same-window restore and clean Quit/icon removal
on `5fb2628`. This accepted evidence remains inherited.

The user physically confirmed the final additions: exactly one X-triggered native
notification, continued PCServer operation while hidden, Automatic / Local
network in the running tooltip, and `PocketCinema Server - Stopped` after Stop.
Draft settings cannot relabel a running child; a successful Restart captures the
new mode. No dependency was added.

Validation: 28 focused notification/mode/tray/lifecycle tests, Python compilation
and diff checks passed. Existing tray, silent subprocess, route presentation,
Local/Remote and M21/M22 evidence remains inherited.

Windows v1.0.0 packaging correction is implemented as an unsigned PyInstaller
one-directory x64 candidate. The windowed EXE dispatches the GUI or explicit
`--server-child` role before GUI initialization; inherited private pipes retain
sanitized logs and clean exact-owned-child shutdown. Frozen resources remain
under the existing per-user PocketCinema root. The approved static GPLv3
FFmpeg/FFprobe 9.0.1 executables are bundled under the app-local
`media-tools/bin/` path and preferred by frozen runtime resolution; Stremio and
Tailscale remain unbundled and unmanaged.

The focused v1.0.0 package audit passed: version and artifact naming, approved
tool hashes, FFmpeg/FFprobe launches, BUILD_INFO bundled-media metadata,
compliance material, package contents, and local-path scan. The package is
`.tmp/windows-package-v1.0.0/PocketCinema-Server-1.0.0-windows-x64.zip`.
The old 0.17.0 candidate remains preserved separately. The focused lifecycle
smoke and clean-machine acceptance remain pending; the unsigned package and
older Python 3.11.0/Tcl-Tk 8.6.12 runtime still require public-release review.

Next exact action: run the focused Windows lifecycle smoke against the corrected
v1.0.0 candidate, then remaining M23 clean-machine and distribution gates. The focused Windows
stream-search, Miyoo Movie/Series, subtitle font-size, My Library, and Next
Episode / Continue Series gates are physical PASS. The source tray UX and
packaged Windows smoke gates are physical PASS. Production PASS and Impact-First
Regression Testing preserve M21/M22 and accepted transport/playback/subtitle/
account evidence without broad retests. Clean-Windows acceptance, public
distribution/signing/runtime review, renderer-asset/licensing/fresh-deployment
and final release-artifact gates remain pending; M23 remains incomplete.
Micro-stutter work remains deferred.

## Development Handoff — v1.0.1 maintenance candidate (2026-10-17)

Branch: `maintenance/v1.0.1-stream-diagnostics`, based on `2278e25` in an
isolated worktree. Original checkout changes and release files are untouched.
User explicitly authorizes a local commit only: do not push, merge, bump the
version, build release artifacts, or publish. The remote checkpoint below is
historical and does not checkpoint this maintenance branch.

Implemented: empty-result detection before source/language menus, bounded
multi-source notices with optional disabled Local Files last, and an explicit
manual/built-in addon-count log label. Existing settings, addon eligibility,
security boundaries, conversion and player behavior remain unchanged.

Compatibility investigation: archived decoder source supports a wider range
than the measured device envelope. H.264 profile/pixel-format classification
remains overly broad; the proposed probe/policy/cache correction requires
approval and focused evidence before implementation. Reporter audio-only
playback remains OPEN, not reproduced. Existing diagnostics are sufficient for
initial targeted collection; no new playback logging is added.

Validation: all 136 combined server/account/desktop/client tests pass, including
six new executed shell-flow regressions; seven existing Miyoo shell checks,
Python compilation, shell parsing and diff whitespace checks pass.
A pre-existing Unix failure in the mock bundled-Windows-tool test was reproduced
on the original checkout and corrected by setting its fixture executable bit.
Physical validation/deployment awaits the requested development Miyoo SSH address;
no client behavior is newly physically confirmed. Native Windows remains pending.

Evidence and regression-impact matrix:
`docs/v1.0.1-maintenance-investigation.md`. M21/M22 evidence is inherited for
unchanged playback, subtitles, progress, conversion and account behavior.

Next exact action: deploy this branch through `scripts/deploy-miyoo.ps1` using
the existing installed player assets; verify permissions/cleanup, then perform
the focused Apps empty-result display and successful stream-selection/playback
smoke, collect logs, and review the proposed compatibility correction. Obtain
reporter diagnostics before assigning an audio-only root cause. Push requires
explicit authorization; another machine cannot obtain this candidate remotely.

## Latest Verified Checkpoint

Checkpoint commit: `b76e20d`
Remote verified: YES - `b76e20d` is reachable from fetched origin/main
Machine: macOS release-assembly checkout
Branch: `main`
Active milestone: Milestone 23 — PocketCinema Server Desktop Distribution

Completed:

- Bounded read-only FFplay material-difference investigation localized the
  earliest divergence to the generated `FFMPEG_CONFIGURATION` text in
  `cmdutils.o` and classified it as a configuration-define difference. No
  rebuild, deployment, selector access, or binary modification occurred.

- PocketCinema public user documentation was created under canonical
  `docs/user/` and exported deterministically from its allowlist to
  `public-docs/pocketcinema/`. Runtime behavior is unchanged. The separate
  selector-cap task remains blocked on the missing ARM compiler/sysroot.

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
- Python compilation, 105 server/desktop unit tests, shell syntax and focused
  connection/proxy/status tests, PowerShell parsing, alternate-port API/play/
  Range verification, and `git diff --check`.

- Production PASS audit completed against the current normal paths. It found no
  current M21/M22 behavior regression or configuration gap, fixed a
  Windows-only desktop-test path assertion, and recorded the already-known
  fresh-deployment renderer-asset packaging/licensing gap as a release blocker
  for separate M23 packaging work. See `docs/production-pass-audit.md`.

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
  available-route count in Status. Local and Remote transport acceptance are
  physically confirmed. The Remote smoke used the known Tailscale IPv4 address
  through the independent proxy while the desktop advertised a Remote IPv6
  route; address-family presentation is deferred UX work.

- M22 production-promotion correction implemented and locally verified: the
  Miyoo runtime and shipped configuration enable selectable Matroska subtitles
  by default, explicit `0` remains an opt-out, and direct PCServer startup
  matches desktop/manual manager semantics with a clear CLI opt-out. Existing
  configurations remain untouched. M22 evidence is inherited; the separate
  live renderer/display symptom (tracks switch but captions are not visible)
  remains open.

- M22 renderer/display migration repair is physically restored: the normal
  client supplies both compiled subtitle/font identities, deployment rewrites
  migrated fontconfig paths, and the rebuilt app-local ARM player supplies the
  1.5x libass font scale. The deployed hash matches the local rebuilt binary,
  and Apps-context observation confirms captions are noticeably larger and
  acceptable. The change does not alter tracks, R1, subtitle-off, playback, or
  cleanup, so the existing M22 acceptance evidence is inherited. Configurable
  subtitle size and position remain a future normal-UI UX feature.

- M23 Windows desktop-shell responsiveness repair is physically confirmed:
  recurring Windows route/tool discovery and owned lifecycle waits no longer
  block the Tk thread, operations are serialized, unchanged logs are not
  re-rendered, and normal desktop use remained responsive.

- First Windows standalone candidate implemented with pinned reproducible build,
  derived canonical ICO and version metadata, explicit frozen GUI/child roles,
  private shutdown/log pipes, per-user writable paths, licenses and artifact
  audit. Focused desktop/runtime and native frozen lifecycle checks passed;
  physical packaged and clean-machine acceptance remain pending.

- Packaged Windows developer-machine physical smoke is **PASS**: the extracted
  one-directory EXE loaded existing settings, showed the canonical identity,
  launched without a console, preserved Local/Remote IPv4-preferred routing and
  active-mode tooltip, hid to tray with exactly one native notification, restored
  the same GUI, completed Start/Stop/Restart, and Quit stopped the exact owned
  child with no observed orphan. Clean-Windows distribution remains pending.

- Running desktop settings UX is implemented and focused-tested: while the owned
  child is Starting/Running/Stopping, startup configuration controls are locked
  and the non-modal message `Server is running. Stop the server to change its
  settings.` appears only in Running. The active successful settings are shown;
  Stop/failed start/restart/unexpected exit restores editing. Tray actions use
  the same synchronization. The packaged physical gate is now PASS.

Pending:

- The packaged Windows developer-machine physical smoke and running-settings
  lock are PASS and must not be repeated unless later work materially affects
  those frozen paths. Source X-notification/Automatic-mode hover and prior tray
  acceptance remain PASS.

- Windows clean-machine acceptance, public distribution/signing/runtime review,
  Miyoo runtime/renderer packaging/licensing, and final release-artifact review
  remain M23 release work. macOS packaging/lifecycle is physically accepted;
  its unsigned/notarization and licensing review remain open. Build/artifact
  instructions: `docs/windows-packaging.md` and `docs/macos-packaging.md`.

- Subtitle font-size settings are implemented, deployed through the standard
  Miyoo path, and physically confirmed PASS. The supported presets are 1.0x,
  1.25x, 1.5x, 2.0x, 2.5x and 3.0x; `SUBTITLE_FONT_SCALE` persists the value,
  invalid or missing values fall back to 1.5x, and the existing app-local
  `font_scale` renderer path is reused. No additional Apps retest is required
  unless later work materially intersects this path.

- Two focused production UX refinements are implemented and physically
  confirmed: missed Windows background subprocess paths in
  stream/source resolution now use hidden/no-console creation flags while
  retaining captured output, errors, return codes and timeouts; Miyoo Search
  rows now visibly append bounded `[MOVIE]` or `[SERIES]` labels from existing
  result metadata. No provider, ordering, selection, playback or Live TV
  behavior was changed. Live TV is now an **ACTIVE RECONSIDERATION / VIABLE V1
  CANDIDATE** based on the successful real-world StremTV US test; generic
  TV-addon support is not implemented and StremTV-specific support must not be
  hard-coded. The existing ERT News live-HLS evidence remains preserved.
  The candidate was rebuilt after these changes and the focused frozen-child
  check passed. A focused Miyoo regression then showed the result list was
  empty: jq 1.6 treats the temporary `$label` name as its reserved `label`
  keyword. Renaming it to `$type_label` restores result generation while
  preserving the bounded labels. The corrected tracked client was redeployed
  through the independently managed Tailscale route to `100.97.46.26`; live
  config and networking-provider state were preserved. The user then physically
  confirmed the results list, readable Movie/Series labels, and normal Movie
  and Series navigation. The rebuilt packaged Windows candidate also produced
  zero terminal/PowerShell/cmd windows during stream/search activity. These
  focused gates are PASS.

- Generic account-backed Stremio TV playback is implemented through the existing
  Live TV path and now has a bounded HLS conversion-source fix. Conversion-only
  fMP4 HLS with a validated `EXT-X-MAP` is now normalized as a server-side input
  to the existing converter; direct-device HLS remains MPEG-TS-only. Investigation of
  the real StremTV US channel showed no addon request headers were required; its
  H.264/AAC 854x480 rendition exceeded the device-output HLS bound, causing the
  conversion input bridge to return 502 before FFmpeg produced media. The bridge
  now permits only bounded 1920x1080/8 Mbps H.264 conversion inputs while
  retaining the existing 640x360/1.6 Mbps direct-device bound. Focused automated
  coverage passes. The successful physical StremTV playback remains inherited
  PASS evidence. The Miyoo selector capacity is now bounded at 128 items. Its
  pointer array, per-item line buffer, dynamic rendering, wraparound navigation,
  and cleanup all scale with the parsed count, exposing the current server
  maximum without changing callers or addon behavior. The ARM reproducibility
  build remains pending; the Windows compiler/sysroot has been recovered but
  this source-preservation task explicitly excludes rebuilding; the current
  prebuilt 64-item selector remains the release
  binary, and the 128-item source change is unbuilt and unshipped. The earlier
  Greek-channel removal idea was rejected: those entries are linked
  account-addon data, not a PocketCinema-shipped catalog.

- A clean host-side Miyoo package assembler is implemented and validated at
  `scripts/build-miyoo-release-package.ps1`. It assembles a technically
  self-contained package from first-party files plus an explicit prebuilt
  runtime input, without an ARM sysroot, selector compilation, legacy-state
  migration, or bundled user state. The v1 package remains blocked from public
  redistribution until the recovered FFplay 2.4.14 source/configuration,
  bundled-library provenance, and Plus Jakarta Sans font provenance are
  resolved. Fresh-install physical acceptance has not run.

- Non-blocking M23 Remote follow-up: reproduce the brief usable micro-stutters
  only if they remain observable. Remote IPv4 presentation preference is now
  physically confirmed under the accepted focused tray UX evidence.

- ARM selector reproducibility rebuild: Windows compiler/sysroot recovered;
  rebuilding is deferred to a separate controlled task. The deployed prebuilt
  helper and its ABI remain unchanged.

The one authorized configure retry restored the historical linker flags in a
fresh isolated workspace. The libass link probe passed without the prior
GLIBC_2.34 failure, but configure stopped at `freetype2` because the recovered
pkg-config shim supplied `/usr/include/freetype2` and `ft2build.h` was not found.
No generated configuration or build output was produced; the reproduction gate
remains D and a full FFplay build is not authorized.

The bounded FreeType investigation found the recovered header under
`sysroot/usr/include/freetype2`. The archived reproduction shim emits unrooted
`-I/usr/include/freetype2`, while historical configure evidence and the retained
`experiments/ffplay/pkg-config-arm.sh` emit the sysrooted include path. The
compiler does not rewrite an explicit `-I/usr/...`; classification is D (wrong
pkg-config file selected). The next configure retry, if separately authorized,
should invoke the preserved sysroot-aware experiment shim. No retry or build was
run here.

The authorized configure retry using the preserved sysroot-aware pkg-config shim
now succeeds. libass and FreeType pass, the GLIBC_2.34 runtime failure remains
absent, and generated configuration differs from historical only by workspace
paths and duplicate equivalent linker flags. Classification is B (configure pass
with explained non-material differences). A full independent FFplay build is now
eligible for separate authorization; no build or deployment occurred.

The authorized FFplay-only build and preserved strip completed successfully, but
the candidate is not byte-identical to known-good. Runtime ELF invariants match,
while the bounded comparison shows a material `.text` difference (4-byte size
delta and 746,293 differing bytes). Classification is C; the independent
reproduction gate remains blocked and no deployment is authorized.

The bounded material-difference investigation localized the earliest divergence
to the generated `FFMPEG_CONFIGURATION` string in `cmdutils.o`: reproduced
configure-path tokens make `.rodata.str1.1` 0xb0 bytes larger, while 277 of 289
matched object pairs remain byte-identical and the toolchain, ARM ABI, compile
flags, link libraries, and archive member order match. Classification is C
(preprocessor/config define difference), not a toolchain or ABI mismatch. No
rebuild or deployment occurred. One future corrected rebuild may be separately
authorized using the historical configure-command representation and the
preserved sysroot-aware pkg-config shim resolved through PATH; the current
independent reproduction gate remains blocked.

The bounded five-object comparison found no source, compile-command, or
generated-header mismatch. `cmdutils.o` differs at one embedded build-time
`__TIME__`; `mpegaudio.o` and `rmsipr.o` have post-preprocessing code/relocation
differences; `display.o` differs in relocation/attribute metadata; and
`log2_tab.o` differs only in object metadata. Classification is G (one
object-specific cause plus unrelated others), so the independent FFplay
reproduction gate remains blocked. No rebuild occurred. One future retry, if
separately authorized, may restore the historical source-tree path and working
directory while preserving all existing flags.

The proposed historical-working-directory retry was not run: `.tmp/ffmpeg-2.4.14`
is the authoritative recovered tree containing the retained known-good FFplay,
historical configuration, and object evidence. Rebuilding there would destroy
unique evidence. Classification is D (safe historical-path test cannot be
performed); the independent reproduction gate remains blocked.
