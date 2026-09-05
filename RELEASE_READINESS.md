# PocketCinema Release Readiness

`PROJECT_STATE.md` owns current operational truth. This document converts that
state into the gates for a conservative public v1.0 release, using `AGENTS.md`,
`README.md`, `docs/roadmap.md`, deployment scripts, and evidence documents for
the applicable rules and validation. It is not a claim that v1.0 is currently
ready.

Current assessment: **not release-ready**. The normal vertical slice, bounded
subtitle/downscaling path, converted audio-track selection, and selectable
Matroska mode are physically confirmed. Milestone 22 includes three-track
English Matroska packaging, R1 cycling through tracks and subtitles-off,
synchronized audio/video/subtitles, automatic burn-in fallback, and clean Menu
exit/cleanup. Remaining blockers are fresh-SD and final movie/episode/converted
regressions, app-local player packaging and licensing, privacy review, and
reproducible release artifacts. Selectable Matroska is promoted to the normal
product default, with an explicit opt-out retaining the bounded burn-in path.
Its app-local renderer's 1.5x subtitle-font default is now physically confirmed
as readable; UI-configurable subtitle size and position are future UX work, not
a current release repair.
The Production PASS audit confirms that accepted M21/M22 behavior remains on
the current normal paths. It also confirms the existing release blocker: a
fresh Miyoo deployment still depends on ignored rebuilt-player, font, and
runtime-library inputs until M23 packaging/licensing work provides reproducible
release artifacts. See `docs/production-pass-audit.md`.
Milestone 23 now makes a
user-installable PocketCinema Server desktop distribution an explicit release
requirement, but its implementation is gated on Milestone 21 completion.
The source-development desktop shell is implemented and automatically tested.
The Local desktop path, Remote-route smoke, and Windows desktop responsiveness
are physically confirmed, as recorded in `PROJECT_STATE.md` and the Production
PASS audit. Milestone 23 remains incomplete: packaged-distribution acceptance and
fresh-deployment work are still pending. Until Milestone 23 is accepted from an
actual packaged artifact, the Python/PowerShell workflow
below remains a developer/source path, not the intended end-user v1.0
installation.

Windows tray lifecycle and all focused UX refinements are physically confirmed
PASS: IPv4-preferred Remote presentation, silent server actions, active listen
mode in the running hover, one native X notification, X/background operation,
same-window restore and clean Quit. M21/M22 and accepted transport/playback/
subtitle/account evidence remains inherited under the Production PASS invariant;
no broad retest is required. The first unsigned Windows x64 one-directory
candidate is now implemented and automated-tested; see
[`docs/windows-packaging.md`](docs/windows-packaging.md) for build/artifact,
dependency notices, audit and the focused packaged physical smoke, which is the
next action and remains pending. This does not mark packaged physical or
clean-machine acceptance PASS. The pinned Python 3.11.0/Tcl-Tk 8.6.12 candidate
requires runtime updating/review before public release. Windows clean-machine,
signing/distribution, later macOS, renderer-asset/licensing and fresh-deployment
acceptance remain release gates; M23 is incomplete.

## Verified Connection and Onboarding Resolution

The pre-Phase-3 no-config test measured a tailnet onboarding gap: direct startup
could not validate a tailnet PCServer through the optional generic proxy. Phase 3
now supplies first-run Local, Remote, and Both/Automatic setup with atomically
saved profiles, direct Local validation, Remote validation through the user
configured proxy, and direct-first fallback. Its full Apps-context acceptance
matrix, including a separate config-free installation that opened setup before
home without altering the preserved live profile, is physically confirmed.

This does not ask PocketCinema to manage Tailscale or any other network
provider. The completed transport-agnostic onboarding path:

- tries direct LAN connection first without exposing unnecessary networking
  complexity to ordinary users;
- offers a clearly optional generic HTTP-proxy route when direct validation
  fails or the user intentionally chooses remote connection;
- validates and atomically saves the selected PCServer endpoint and optional proxy;
- supports a future installer, profile, or setup-code handoff without copying
  credentials, runtime state, or private configuration; and
- does not rely on public port forwarding, because the PCServer has no public-facing
  authentication. The Miyoo never reaches Stremio Service directly; its local
  default remains loopback with the firewall block preserved, while M23 may
  configure a PCServer-only endpoint on a separately reachable host.

A future desktop PCServer application can make server endpoint selection and setup
information visible, but it cannot itself create the Miyoo's network route. The
client still needs a direct route or a separately configured generic proxy.

### Confirmed v1 connection and onboarding direction

The direct-first PocketCinema Local/Remote/Automatic profile is implemented,
deployed, and physically confirmed. PocketCinema retains an editable generic
HTTP proxy with supported default `http://127.0.0.1:1055`; it validates Local
directly, validates Remote through the configured proxy, and keeps discovery
separate from reachability. Remote setup therefore does not depend on UDP
discovery. The standalone Miyoo Tailscale companion remains the sole owner of
its networking, authentication, lifecycle, and displayed proxy endpoint;
PocketCinema does not inspect or manage it. Phase 1 companion visibility,
Phase 2 proxy controls, and Phase 3 onboarding are all physically confirmed.
The architectural and packaging boundary remains recorded in
[Portable Connection and First-Run Onboarding Plan](docs/portable-connection-onboarding-plan.md).

PocketCinema's Phase 2 generic HTTP-proxy controls are implemented, statically
validated, deployed, and physically confirmed. They retain direct transport
for an absent or explicitly empty `PROXY`, and use the
PocketCinema-owned editable restore default `http://127.0.0.1:1055`; they do
not inspect or control the companion. The first Apps launch exposed a strict
validation regression for the preserved, previously supported
`http://host:port/` spelling; a minimal deployed compatibility fix canonicalizes
only that root-path form in memory. The subsequent Apps settings run confirmed
proxy persistence but found stale PCServer status after an effective transport
change; the monitor-refresh correction is physically confirmed. The disabled-
state `Enable default (127.0.0.1:1055)` control, `1056` Offline, default
Connected, disabled direct-route transitions, and a `friday` search after
restoring the default all passed from Apps.

Phase 3 first-run connection onboarding and two-endpoint routing are
implemented, automated/static-validated, deployed, and physically confirmed.
The client retains legacy single-server
configuration unchanged; new
profiles atomically store Local PCServer, Remote PCServer, and Automatic | Local only |
Remote only mode. Legacy startup and manual Local-only setup/search are
physically confirmed; normal UDP discovery and selection validation also passed
against the hotspot PCServer. Remote-only setup/search through the default proxy and
the found-but-unreachable Local validation case are also physically confirmed.
Remote proxy failure at `127.0.0.1:1056` and immediate default-proxy recovery
are also physically confirmed, as is Remote-profile restart persistence.
Automatic's complete Local-unavailable → Remote → Local fallback is physically
confirmed. Automatic probes Local directly, then Remote through the generic
proxy, and all PCServer requests use the resolved route. The Both/Automatic
three-second information message and pristine first run are physically
confirmed. The release gate remains open for the separate remaining release
requirements, not Phase 3 onboarding.
The app-local FFplay/libass path now opens a real account stream without
a redundant subtitle picker, packages three English text tracks, cycles them
and off with R1, displays a one-second track notice, and cleans up after Menu
exit. Automatic fallback into the unchanged production MPEG-TS burn-in flow is
physically confirmed from Apps after a server-mode negotiation failure. The
normal subtitle picker selected the test subtitle, the production converter
burned its 0.5-second cue into a 640x268 stream, and the app-local player
presented it centered at `0,106`; the user reported that it did not look
stretched. Two runs saved 26 and 5 valid watched seconds and exited cleanly. A
separate forced missing-candidate diagnostic reached the same burn-in flow but
showed that Onion FFplay visibly distorts the correctly encoded output. A final
110-second real-account run explicitly confirmed smooth, synchronized video,
audio, and subtitles, bounded resource use, status-0 Menu exit, progress
saving, and complete PCServer/Miyoo cleanup. Milestone 22 is therefore physically
**Confirmed**.

## What v1.0 requires

### Product requirements

- Apps-context browsing works for search, movies, series, seasons, episodes,
  stream selection, Play, Continue Watching, Resume, Play from Start, B/back,
  and Menu exit.
- At least one reproducible legal direct HTTP(S) movie and episode path works
  through the server-side resolver without exposing upstream URLs or tokens.
- Direct-play compatibility is bounded and measured; unsupported codecs and
  unsafe stream shapes fail before FFplay with a useful message.
- The bounded conversion path produces synchronized H.264/AAC output at the
  supported resolution profile, burns a correctly matched English subtitle,
  saves progress correctly, and cleans up after Menu exit.
- 720p/1080p sources are downscaled when required rather than presented as
  assumed direct-play streams.
- A clean account can be linked through the official temporary approval flow,
  with credentials remaining on the gaming PC.
- A fresh SD-card installation can be configured without copying private URLs,
  tokens, generated media, logs, or runtime state from the development machine.
- First-run client onboarding succeeds for direct LAN PCServer access and for an
  explicitly selected optional generic HTTP-proxy route, without requiring a
  pre-existing PocketCinema config file. The proxy URL is viewable and
  editable; the initial companion-oriented default is `http://127.0.0.1:1055`.
- A normal Windows user can install or extract the PocketCinema Server desktop
  application, configure it, and operate its owned server without installing
  Python, running PowerShell, cloning the repository, or preparing environment
  variables.
- The app returns to OnionOS cleanly after success, cancellation, network
  failure, FFplay failure, and Menu exit.

### Release gates

- Every passed acceptance behavior is present through the normal shipped path:
  required runtime assets/configuration are deployed, and no test-only flag,
  marker, fixture, environment override, developer launcher, or manual
  intervention is required. Treat a later loss of that path as a regression,
  not a release-scope ambiguity.
- Keep the physically confirmed Milestone 20 acceptance evidence aligned in
  `docs/bounded-transcoding.md` and `docs/roadmap.md`; do not regress its
  production MPEG-TS burn-in fallback.
- Do not begin Milestone 23 implementation until `docs/roadmap.md` marks
  Milestone 21 **Confirmed** and its controller/device acceptance evidence is
  complete. Code presence is not completion evidence.
- A clean supported Windows PC can install or extract the actual PocketCinema
  Server artifact, configure and persist PCServer name, listen interface/address,
  port, device-facing address, and a validated Stremio Service endpoint through
  the desktop UI,
  verify or select FFmpeg and FFprobe, start the server, and connect a Miyoo
  Mini Plus without Python, PowerShell, repository knowledge, or manual
  environment-variable configuration.
- The desktop release passes configuration persistence, application/server
  restart, invalid/occupied port, missing FFmpeg/FFprobe, unreachable Stremio
  Service, disappeared-interface, clean stop/removal, and sanitized-log/privacy
  tests.
- Milestone 22's selectable-Matroska acceptance criteria, including fallback
  and synchronized A/V, are physically confirmed and promoted to the normal
  default. Keep its explicit configuration/CLI opt-out and include the
  app-local player runtime in any release that retains this behavior.
- Resolve the current app-local-player packaging dependency explicitly: either
  ship a physically accepted, reproducible binary with its source/configuration
  and notices, or change the release configuration to a verified player that
  is actually present on a fresh installation.
- A fresh-SD test passes with a clean account or explicitly documented no-account
  mode.
- A fresh Miyoo can discover or enter a direct-LAN PCServer address, and can select
  an optional generic proxy before validating a routed PCServer address. Discovery
  must distinguish a received local advertisement from direct reachability;
  remote setup must not depend on UDP discovery. This must be physically tested
  without starting, stopping, inspecting, or configuring the independent
  network provider from PocketCinema.
- A normal direct-play movie, a series episode, a converted subtitle case, and
  a server restart/recovery case pass from Apps.
- A converted multi-audio stream allows choosing a verified audio track before
  playback; this is now physically confirmed. Persistent language preferences
  remain outside the current release gate.
- R1/R2 behavior is documented from the deployed builds. The physically
  confirmed app-local build completed all three R1 track transitions, off,
  return to the first track, and one-second notices. R2 did not trigger the
  earlier build and is not the selectable-subtitle control.
- Server unit tests, Python compilation, shell parsing, PowerShell parsing, and
  selector reproducibility checks pass.
- No private configuration, account key, Tailscale state, upstream URL, token,
  generated binary, local fixture, or log is staged for release.
- Installation, rollback, support, known limitations, and license notices are
  included with the GitHub release.

## What can be deferred

These are explicitly outside a minimal v1.0 unless the release scope is
expanded:

- account library/catalog browsing;
- favorites, richer history, posters, image caching, and a full UI;
- persistent audio-language preferences beyond the now-confirmed per-play
  converted-track selection;
- arbitrary seeking in a nonseekable live converted response;
- offline downloads;
- torrent ingestion, P2P handling, or local torrent management;
- server discovery and automatic hostname discovery;
- an integrated FFplay pause menu;
- support for arbitrary codecs, HDR, HEVC, AV1, multichannel audio, encrypted
  HLS, fragmented MP4 HLS, or unmeasured containers;
- Tailscale account replacement/removal from the remote PocketCinema UI.

Deferred work must remain outside the active milestone and receive its own
acceptance criteria before implementation.

## Installation paths

### End-user release installation

This is the required v1.0 direction, not a currently available artifact.

#### Windows

- A supported Windows version and the signed or clearly labeled development
  PocketCinema Server application bundle.
- Network access from the Miyoo to the selected PCServer interface/address. Direct
  LAN HTTP is supported; Tailscale remains optional, independent transport.
- Stremio/Stremio Service only where required by the existing account or Local
  Files architecture, accessed by PCServer only. The default endpoint is local
  loopback; a configured endpoint may instead be on another reachable host.
- FFmpeg and FFprobe detected automatically or selected through the desktop UI.
  They are not to be bundled until redistribution provenance and licensing are
  approved.
- No Python installation, PowerShell commands, repository checkout, `pip`, or
  manual environment variables for normal operation.

#### macOS

The architecture must support a later `.app`, but macOS is not an end-user
release target until native Apple Silicon and any claimed Intel/universal build
are tested from their actual bundles. Developer ID signing, hardened-runtime
review, notarization, ticket stapling, and Gatekeeper testing are release gates,
not optional release polish.

### Developer/source installation

#### PCServer host

- Windows with PowerShell and Python available on `PATH`, or macOS with the
  documented shell/Python prerequisites.
- The repository checked out to a stable directory.
- `ffprobe.exe` and `ffmpeg.exe` available, normally from the installed
  Stremio runtime or explicit `-FFprobePath`/`-FFmpegPath` arguments.
- The PocketCinema server host address reachable from the Miyoo. Direct LAN
  HTTP is supported; Tailscale is optional transport infrastructure.
- Optional Stremio Service installed and reachable from PCServer. The default
  local endpoint is `http://127.0.0.1:11470`; configure a non-secret endpoint
  override when the service is on another reachable host.
- Optional stream addon manifests configured in ignored
  `server/config/stream_addons.json`.
- Optional account binding performed only through the official temporary
  approval flow.

#### Miyoo

- Miyoo Mini Plus running the tested OnionOS version or a separately measured
  compatible version.
- SD card with sufficient free space for app files, logs, and any explicitly
  bounded local data.
- Wi-Fi configured and connectivity to the server address.
- PocketCinema persistent files under
  `/mnt/SDCARD/App/PocketCinema/` only.
- Onion-provided `curl`, `jq`, `kbinput`, `infoPanel`, SDL 1.2, and FFplay.
- SSH access for deployment and log collection during testing.
- Do not overwrite the live config during deployment.

## Clean-account onboarding path

The steps below describe the current developer/source workflow. The Milestone 23
desktop application must provide the equivalent official approval flow using
its separate per-user credential file; it must not expose the auth key or ask a
normal user to edit JSON.

1. Install and start the gaming-PC server with no account key present.
2. Configure only the required server host, port, and legal addon manifests.
3. Verify `GET /api/status` locally and from the intended Miyoo transport.
4. On the Miyoo, install the tracked PocketCinema app files and create the
   app-local config from `client/miyoo/pocketcinema.conf.example`.
5. Set `SERVER_BASE` to the gaming-PC address. Set `PROXY` only if the
   independently managed network provider requires it.
6. Open PocketCinema and confirm status/search before linking an account.
7. Choose **Stremio Account -> Connect Account**. Scan or open the one-time
   official link, approve it, then press A to poll.
8. Confirm that the Miyoo receives only the approval UI and sanitized account
   status. The auth key remains in ignored
   `server/config/stremio_account.json` on the gaming PC.
9. Play one legal direct HTTPS movie and one episode, then test a subtitle/
   converted case if that path is in the release scope.
10. To reset for another clean-account test, stop the server and remove the
    ignored server-side account config only after preserving no production
    identity that must remain. Never reset or reauthenticate the working
    Tailscale node as part of account testing.

## Fresh release test checklists

### Clean Windows PCServer and fresh Miyoo

Run this from the actual Milestone 23 release artifact, never from the
development working tree:

- [ ] Start with a supported Windows environment that has no PocketCinema
      development checkout and does not rely on a separately installed Python
      or PowerShell lifecycle commands.
- [ ] Install or extract only the release artifact and verify its SHA-256
      checksum.
- [ ] Launch PocketCinema Server and confirm that its per-user directories are
      created outside the application bundle.
- [ ] Configure the PCServer name, listen interface/address, port, advertised Miyoo
      address, and Stremio Service endpoint (including manual host/address and
      port or URL override) in the UI; restart the app and verify that non-secret
      settings persist.
- [ ] Confirm FFmpeg and FFprobe automatic detection and manual selection, then
      verify useful missing-tool handling without a traceback in the primary UI.
- [ ] Start PCServer, verify `/api/status`, and copy the displayed device-reachable
      URL. Confirm that a wildcard bind never displays `0.0.0.0` as that URL.
- [ ] Test an invalid port, occupied port, disappeared interface, and unreachable
      Stremio Service; each must produce a concise actionable state and preserve
      recoverability.
- [ ] Connect a clean/fresh Miyoo installation to the displayed address.
- [ ] Test direct playback, converted/downscaled playback, subtitles, Continue
      Watching, Resume, Play from Start, progress saving, and Menu cleanup.
- [ ] Restart PCServer and the desktop application; confirm intended configuration,
      account state, Continue Watching, and probe cache persistence, plus expiry
      of ephemeral play sessions.
- [ ] Stop or exit the application according to its documented behavior and
      confirm that only its owned PCServer process is stopped. Unrelated Python,
      FFmpeg, Stremio, and Tailscale processes must be untouched.
- [ ] Test removal/uninstall behavior. Preserve or explicitly offer removal of
      user data; never silently delete credentials or user-owned configuration.
- [ ] Inspect the bundle and normal diagnostics for private/development files,
      credentials, addon URLs/tokens, upstream URLs, local media, caches, and
      logs. None may be shipped or exposed.

### Fresh Miyoo SD card

- [ ] Use a freshly formatted or disposable SD card and the target OnionOS
      version.
- [ ] Install only the release files and the documented OnionOS app metadata.
- [ ] Confirm no app files are written outside PocketCinema’s app directory,
      except the separately documented Tailscale startup hook when Tailscale is
      installed.
- [ ] Create `config/pocketcinema.conf` from the example and set `SERVER_BASE`.
- [ ] Verify direct transport; verify proxy transport separately if supported.
- [ ] Open Apps -> PocketCinema and test B cancellation on every selector.
- [ ] Search and play the deterministic compatibility fixture.
- [ ] Play one direct legal movie and one series episode.
- [ ] Test Continue Watching, Resume, Play from Start, pause tracking, and
      Menu exit.
- [ ] Test a converted English-subtitle/downscale case, including subtitle
      synchronization and cleanup.
- [ ] If the selected source has multiple audio tracks, verify the displayed
      FFprobe labels and choose the intended track before converted playback.
- [ ] Confirm the fresh-install Matroska default, cycle all packaged tracks and
      off, then force one setup failure and confirm automatic return to the
      normal subtitle/burn-in flow without stale state.
- [ ] Test a bad server address and confirm a specific error followed by clean
      return to the UI.
- [ ] Reboot, reopen Apps, and confirm no stale process, panel, marker, or
      temporary playback state remains.
- [ ] Collect only sanitized logs needed for evidence; remove them before
      packaging the card or release archive.

## Windows server installation checklists

### End-user release installation

An unsigned internal Windows candidate now exists (see the packaging evidence
above). The following public-release checklist remains open; development-machine
automation or a physical smoke does not establish clean-PC acceptance:

- [ ] Download and verify the PocketCinema Server release artifact.
- [ ] Install or extract it and launch the desktop application.
- [ ] Choose a listen interface and confirm the separately displayed Miyoo
      address.
- [ ] Configure and validate the port.
- [ ] Configure and check the Stremio Service endpoint: retain the loopback
      default or manually override the host/address and port (or URL), then
      verify validation and reachability feedback.
- [ ] Verify FFmpeg and FFprobe detection or select their executable paths.
- [ ] Connect a Stremio account through the existing official approval flow if
      desired; never manually copy an auth key into the application bundle.
- [ ] Start PCServer, confirm Running status, and configure the Miyoo with the copied
      address.
- [ ] Stop/restart PCServer from the UI and verify clean owned-process lifecycle and
      persisted settings.

### Developer/source installation

- [ ] Clone the repository and read `AGENTS.md` and `docs/roadmap.md`.
- [ ] Run `python -m py_compile server/pocketcinema_server.py`.
- [ ] Run `python -m unittest server.test_stremio_account server.test_pocketcinema_server -v`.
- [ ] Configure `POCKETCINEMA_HOST` or pass `-HostAddress` to
      `server/manage-server.ps1`.
- [ ] Start with `server/manage-server.ps1 start`; use `status`, `restart`, and
      `stop` for lifecycle operations.
- [ ] Confirm `/api/status`, search, metadata, streams, play-session creation,
      and a byte-range media request.
- [ ] In the current source workflow, confirm Stremio Service is local-only at
      `127.0.0.1:11470`, keep the inbound Windows Firewall block for TCP
      `11470-11474` and `12470`, and verify LAN and tailnet denial to those ports.
      The M23 packaged UI must instead support a validated PCServer-only endpoint
      for another service host without exposing it directly to the Miyoo.
- [ ] Configure only legal, intended addon manifests in ignored files.
- [ ] Keep `server/config/stremio_account.json`, `server/data/`, logs, caches,
      and local media ignored and out of release artifacts.
- [ ] Verify server restart persistence for Continue Watching and bounded probe
      cache, and expected expiration of ephemeral play sessions.

## Tailscale setup checklist

- [ ] Treat Tailscale as an independent provider app, not a PocketCinema
      dependency or lifecycle component.
- [ ] Install the standalone app under `/mnt/SDCARD/App/Tailscale/`.
- [ ] Preserve its authenticated `state/tailscaled.state` and logs; never copy
      them into a release archive.
- [ ] Preserve the original PocketCinema rollback state and never run two
      daemons simultaneously.
- [ ] Connect a new account only through the Tailscale app’s official QR/login
      flow; do not use PocketCinema to manage identity.
- [ ] Confirm the Tailscale app shows Enabled and the assigned IP.
- [ ] Confirm the local proxy at `127.0.0.1:1055` if proxy transport is used.
- [ ] Confirm PocketCinema can reach the server through the proxy.
- [ ] Test Disable/Enable and reboot autostart only in the Tailscale app.
- [ ] Do not alter OnionOS core files; the only supported startup extension is
      the app-owned hook documented by the Tailscale subproject.

## Security and privacy review

### Required controls

- [ ] No account email, password, auth key, addon token, private addon URL,
      upstream media URL, subtitle URL, or Tailscale state appears in the
      Miyoo API, logs, process arguments, Git history, or release archive.
- [ ] Desktop preferences, Stremio account credentials, private addon
      configuration, persistent PCServer data, and logs use separate per-user paths.
      Secrets are never stored in the ordinary UI preferences file.
- [ ] A desktop migration does not silently discover or copy credentials or
      private addon configuration from a repository checkout or another PCServer
      host. Any future migration is explicit, preserves the source, restricts
      destination permissions, and never displays the values.
- [ ] The desktop lifecycle manager tracks the exact child it started and never
      kills a process merely because its name contains Python, FFmpeg, Stremio,
      PocketCinema, or Tailscale.
- [ ] `/api/streams` returns opaque stream IDs; `/api/play` returns opaque play
      URLs/session IDs.
- [ ] Account media is limited to safe direct HTTP(S) results; reject P2P,
      external-player, local/private-address, credential-in-URL, and unsafe
      schemes.
- [ ] The Miyoo never reaches Stremio Service directly. Preserve the loopback
      default and Windows Firewall inbound block when the service is local to
      PCServer; any remote endpoint remains PCServer-only and validated.
- [ ] Local Files allowlisting remains explicit and never broadens to general
      user directories.
- [ ] HTTP proxy settings are optional and never cause PocketCinema to start,
      stop, inspect, or reauthenticate Tailscale.
- [ ] QR payloads are passed through stdin or local rendering paths rather than
      process arguments or third-party QR services.
- [ ] All user-derived paths, IDs, and URLs are quoted and JSON-encoded.
- [ ] Temporary subtitle, relay, progress, and stay-awake files are cleaned up
      on success, cancellation, failure, and Menu exit.
- [ ] Release review includes `git diff --cached`, `git status`, ignored files,
      and a search for `token`, `password`, `auth`, private IPs, and private
      URLs.

### Threats that remain operational

The server is intended for a trusted LAN/tailnet deployment, not an internet-
facing public service. Access control, TLS termination, addon trust, media
legality, and the security of the host operating system remain deployment
responsibilities. Do not expose the PocketCinema port publicly without a
separately reviewed authentication and transport design.

## Known limitations

- Miyoo memory is tight; active playback has measured very little reported free
  RAM. New resident processes and image-heavy UI features are risky.
- The Onion FFplay baseline has no built-in `subtitles` filter and cannot render
  external SRT directly.
- Selectable Matroska subtitles are physically confirmed for three English
  tracks and are the normal product default; explicit configuration and CLI
  opt-outs retain the bounded burn-in path. Generalized multi-language
  packaging is automated-tested but still needs a six-track Apps-context run.
  The normal deployment now packages the app-local player, runtime libraries,
  font configuration, and font asset; its 1.5x font-scale default is physically
  confirmed as readable. User-selectable size presets and Normal, Bottom-clamped,
  or Top-clamped position belong to a later normal-UI UX feature. Fresh-SD
  validation and licensing review remain release gates.
- The converted MPEG-TS path is nonseekable; D-pad seeking remains restricted.
- Resume positions are approximate and exclude startup/A-button pause time but
  do not model every buffering or seek interval.
- Direct-play support is bounded to measured envelopes. H.264/AAC and selected
  VP8/Vorbis cases are confirmed; other advertised formats remain candidates
  until Apps-context testing.
- Opus audio is rejected in the current compatibility envelope.
- The HLS bridge is bounded to unencrypted MPEG-TS and has only limited long-
  duration physical evidence.
- Account catalog browsing, persistent audio-language preferences, offline
  downloads, torrent/P2P ingestion, posters, and a full UI are not v1.0
  requirements. Per-play verified audio-track selection for converted streams
  is implemented and physically confirmed, but remains a limited preference
  rather than a full language-preference system.
- Tailscale clean-account onboarding and disconnected-boot behavior require
  separate physical testing; the working authenticated identity must not be
  reset during ordinary development.

## Licensing and dependency audit

This is a release-preparation inventory, not legal advice. Before publishing,
confirm every version actually shipped and include the applicable notices.

### Repository and runtime inventory

- PocketCinema server/client scripts: repository-authored code; retain the
  repository’s chosen license file if one is added before release.
- PocketCinema Server desktop application, bundled Python interpreter,
  application GUI runtime, and packaging bootloader: record exact versions,
  source/provenance, licenses, build options, and whether each component is
  redistributed in the Windows directory or macOS `.app`.
- Project Nayuki `qrcodegen`: vendored MIT-licensed component; retain its
  notice and source attribution.
- SDL 1.2, `curl`, `jq`, `kbinput`, `infoPanel`, and Onion FFplay: runtime
  components supplied by OnionOS; do not redistribute OnionOS core files
  without checking Onion’s distribution terms.
- FFmpeg/FFplay experiment: FFmpeg 2.4.14 is LGPL 2.1-or-later when built and
  distributed under the selected configuration; preserve corresponding source,
  build configuration, and notices for any distributed binary.
- libass, FreeType, FriBidi, HarfBuzz, Fontconfig, zlib, bzip2, libpng,
  expat, glib, PCRE, libuuid, libts, and SDL runtime libraries: record exact
  versions, licenses, source URLs, and whether each is redistributed or merely
  linked from OnionOS.
- Tailscale binaries and dependencies: keep under the independent Tailscale
  subproject’s distribution and notice process; do not bundle its state.

### Audit actions before release

- [ ] Record the clean build operating system, architecture, Python version,
      packaging-tool version, GUI/Tcl/Tk version, spec/configuration, and exact
      reproducible build command for every desktop artifact.
- [ ] Record Windows code-signing and installer status; for macOS record target
      architecture, Developer ID signing, hardened-runtime, notarization, and
      ticket-stapling status.
- [ ] Treat FFmpeg and FFprobe as externally detected tools until the exact
      redistributed builds, configurations, provenance, notices, source
      obligations, and update process have passed review.
- [ ] Record `--version` output and build configuration for every bundled
      executable/library.
- [ ] Preserve source or written source-offer information for LGPL/GPL-covered
      components as applicable.
- [ ] Check static versus dynamic linking and ensure corresponding notices and
      relink/source obligations are met.
- [ ] Add a `THIRD_PARTY_NOTICES` file to the release archive.
- [ ] Confirm no ignored downloaded binary is silently included without an
      identified license and provenance.
- [ ] Review OnionOS, Stremio, Tailscale, FFmpeg, libass, and vendored QR
      notices against the exact release contents.

## GitHub release packaging checklist

- [ ] Release from a clean, reviewed tag on the intended branch.
- [ ] Run all automated checks listed in `AGENTS.md`.
- [ ] Build the Windows one-directory application on Windows and the macOS
      `.app` on macOS; do not claim cross-platform support from source-only tests.
- [ ] Include the bundled Python/GUI runtime and application assets required for
      normal use without including writable preferences, credentials, private
      addon configuration, PCServer data, logs, or local media.
- [ ] Record exact build-environment and packaging-tool versions and publish
      reproducible build instructions/specification.
- [ ] State code-signing, installer, macOS architecture, hardened-runtime, and
      notarization status accurately for each artifact.
- [ ] Generate only reproducible, release-appropriate selector binaries and
      explicitly documented app assets.
- [ ] Exclude `.tmp/`, server data, logs, caches, local media, account config,
      addon config, Tailscale state, downloaded toolchains, and test markers.
- [ ] Exclude the experimental FFplay binary unless the release scope explicitly
      promotes it after physical acceptance; never replace Onion’s original
      FFplay in an archive.
- [ ] Include tracked app/client/server files, documentation, setup examples,
      third-party notices, and a short changelog.
- [ ] Include SHA-256 checksums for release archives and any bundled binaries.
- [ ] State tested OnionOS version, Miyoo model, network modes, server OS, and
      required FFmpeg/FFprobe/Stremio versions.
- [ ] State that media sources and account/addon configuration are user-owned
      and must not be included.
- [ ] Provide installation, rollback, clean-account onboarding, and fresh-SD
      test instructions.
- [ ] Publish known limitations and explicitly label unconfirmed features.
- [ ] After publishing, test the downloaded archive—not the working tree—on a
      disposable SD card and clean Windows server profile.

## Current release decision

**Do not publish v1.0 yet.** The working burn-in/downscaling path remains the
safe production fallback, and Milestone 20 is no longer an open release blocker.
Milestone 22's selectable-Matroska path and corrected automatic fallback are
physically confirmed and promoted to the normal default. Fresh-SD
onboarding, final movie/episode/converted regressions, reproducible release
artifacts, third-party notices, and the privacy review must still pass before
publishing. Milestone 21 is confirmed, so Milestone 23 desktop implementation
may proceed; the Windows release must still
pass the clean-PC packaged-artifact acceptance above. A macOS build is not a
supported end-user release until its equivalent clean-bundle, architecture,
signing, notarization, privacy, lifecycle, and real-Miyoo checks pass.
