# PocketStremio Agent Instructions

## Scope

These instructions apply to the entire repository.

PocketStremio is an experimental thin client for the Miyoo Mini Plus running
OnionOS. The gaming PC owns metadata, stream resolution, and media proxying. The
Miyoo owns controller interaction, compact JSON parsing, and FFplay launch.

Read `docs/roadmap.md` before starting feature work. Only the milestone marked
**Next** should receive new feature scope unless the user explicitly changes the
priority.

## Non-Negotiable Boundaries

- Keep PocketStremio persistent device files under
  `/mnt/SDCARD/App/PocketStremio/`. The independent `onion-tailscale/`
  subproject targets `/mnt/SDCARD/App/Tailscale/` under its local instructions.
- Do not modify OnionOS core files. If no app-local solution exists, stop and
  explain the required change before touching a core file, then document it.
- The standalone Tailscale app now owns the live daemon and copied state under
  `/mnt/SDCARD/App/Tailscale/`. Preserve that identity and the original rollback
  state at `/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state`.
  Never run both daemons, reset either state, reauthenticate the working node,
  or delete the rollback copy during ordinary development.
- PocketStremio must be transport-agnostic. Direct HTTP is the default; a
  generic HTTP proxy is optional configuration. PocketStremio must never start,
  stop, or inspect Tailscale.
- PocketStremio must access Stremio Service only through loopback on the gaming
  PC. Preserve the inbound Windows Firewall block for TCP `11470-11474` and
  `12470`; never make those ports reachable from the Miyoo, LAN, or tailnet.
- Do not commit private addon URLs, tokens, Tailscale state, downloaded binaries,
  logs, generated caches, or the local test video. Respect `.gitignore`.
- Do not add torrent ingestion, transcoding, subtitle, progress, poster, or
  full-UI scope unless the roadmap and user request explicitly call for it.

## Current Working Baseline

The physically confirmed flow is:

```text
Apps -> PocketStremio -> search -> result -> Play -> stream -> FFplay
Apps -> PocketStremio -> Continue Watching -> Resume -> stream -> FFplay
Apps -> PocketStremio -> series -> season -> episode -> Play -> stream -> FFplay
```

Both the hosted Big Buck Bunny regression fixture and the public-domain *Night
of the Living Dead* stream have been physically played from the OnionOS Apps
context. The latter is confirmed through both the localhost open-media addon and
the allowlisted Stremio Service Local Files backend. It confirmed H.264
Constrained Baseline 320x240 video, AAC stereo audio initialization, Menu-button
exit, progress saving, and cleanup.

The real *Beverly Hillbillies* S1E1 path is also physically confirmed through
search, season and episode browsing, playback, Continue Watching, Resume, and
Play from Start. Resume advanced a saved 44-second position to 69 seconds after
25 measured playback seconds. Play from Start used a zero seek and replaced the
saved position with only post-readiness playback time. B returned from the
pre-playback action menu and Menu exited FFplay cleanly.

The server uses gaming-PC `ffprobe` during `/api/play` to classify media. The
measured H.264/AAC MP4 and VP8/Vorbis WebM envelopes at up to 640x360 and 30
fps are confirmed. Opus audio is rejected before FFplay. Treat other advertised
FFplay demuxers and decoders as candidates until Apps-context measurements are
documented.

Continue Watching persists on the gaming PC and resume uses FFplay `-ss` with
an approximate wall-clock-derived position. The target FFplay build does not
include the `subtitles` video filter; do not expose an external subtitle option
unless a remux/burn-in path or another compatible player has been implemented
and measured.

Current network and service boundaries:

```text
Miyoo shell/SDL client
  -> direct HTTP or configured generic HTTP proxy
  -> PocketStremio server 100.85.171.67:8755
  -> Cinemeta and server-side stream sources
  -> loopback-accessed, firewall-contained Stremio Service 127.0.0.1:11470
```

Stremio Service 4.20.8 listens beyond loopback even though PocketStremio uses
only `127.0.0.1`. The gaming PC therefore has an enabled inbound Windows
Firewall block for TCP `11470-11474` and `12470`. Preserve that rule and verify
remote denial after service or firewall changes.

The confirmed Local Files backend accepts only `file://` results under an
explicit server-side allowlist. Do not expose local paths, broaden the allowlist
to general user media directories, or accept torrent identifiers from this
backend.

The hosted Big Buck Bunny video is a deterministic regression fixture, not a
general stream resolver.

The server has a read-only Stremio account addon adapter. Account linking uses
the official temporary browser approval flow and stores only the auth key in the
ignored gaming-PC file `server/config/stremio_account.json`. Never print, copy,
commit, or deploy that file. Account addon transports and stream URLs remain
server-side. Direct HTTPS media returned by the user's configured account addons
is permitted even when debrid-labeled; P2P identifiers, external-player,
local/private-address, and non-HTTP results are rejected. The legal ERT News
account result is physically confirmed through the bounded server-side
HLS-to-MPEG-TS bridge. Do not expose
upstream playlists or segment URLs, broaden the bridge beyond unencrypted
MPEG-TS without tests, or describe the bridge as transcoding.

Milestone 17 bridge hardening has deterministic coverage for sliding media
sequences, segment deduplication, bounded transient playlist and segment
retries, sanitized persistent failure, and downstream disconnect cleanup.
`/api/status` reports only the active bridge count. The 30-minute Apps-context
playback and final movie and episode physical regressions remain pending; do not
mark Milestone 17 confirmed without them.

Milestone 18 direct account playback is physically confirmed for Torrentio RD:
*Alien* (1979) used H.264 Main 640x272 with AAC, and *Grimm* S1E1 used H.264
High 852x480 with AAC stereo. Both had visible video and audible audio. The
episode also confirmed pause tracking, Menu exit, and progress saving. Account
display text must remain whitespace-collapsed because embedded newlines become
separate SDL selector values.

The next milestone is the bounded gaming-PC subtitle/downscaling pipeline in
`docs/bounded-transcoding.md`. The first slice is English subtitle burn-in plus
conditional 640x360 downscaling. Feed FFmpeg through an opaque loopback relay so
account media tokens never appear in Miyoo APIs, logs, or FFmpeg process
arguments. A 720p *Invincible* episode is physically watchable but drops frames
and stutters substantially; do not classify 720p as direct-play compatible.

Server-mediated Stremio account binding is physically confirmed. The Miyoo
receives only an official short approval link, renders it locally as QR, and
polls after A; the retrieval code and auth key stay on the gaming PC. A linked
account cannot be replaced or removed through the remote API. Tailscale's home
screen QR for the admin machines page is also physically confirmed without
changing the working node identity.

Series browsing is physically confirmed with the local two-season
`PocketStremio Test Series` fixture. Its generated 30-second H.264/AAC media is
ignored by git and reproducible through
`experiments/ffplay/generate-series-av-sync-fixture.ps1`. Real-series playback
through an addon remains unconfirmed.

Operational resilience is physically confirmed for an unreachable gaming-PC
server. The Apps-context client displayed a specific error and exited without
stale UI, selector, FFplay, infoPanel, or temporary playback state. The server
runs under `server/manage-server.ps1`; play sessions are ephemeral across a
restart while the bounded probe cache and Continue Watching state persist.

Transport independence is physically confirmed. `SERVER_BASE` is explicit,
`PROXY` is optional, and PocketStremio does not manage or inspect Tailscale.
Both direct loopback and configured-proxy requests passed on the Miyoo, followed
by a normal Apps-context selector and B exit. The authenticated legacy state was
later copied into the deployed standalone `/mnt/SDCARD/App/Tailscale/` app with
the original retained as rollback. Controller-driven status/IP display,
autostart toggle, two disable/enable cycles, proxy recovery, B exit, and reboot
autostart are physically confirmed. PocketStremio remains only a proxy consumer.

Real series playback is physically confirmed with *The Beverly Hillbillies*
S1E1 `tt0055662:1:1`. Cinemeta supplies nine seasons; the localhost open-media
addon maps that exact episode to a public-domain Internet Archive H.264/AAC
320x240 derivative. Apps-context playback, audio initialization, Menu exit,
44-second progress saving, and cleanup are confirmed. Real episode metadata must
continue to be derived generically from parent series metadata.

Account-backed Live TV is physically confirmed with ERT News. The Apps-context
flow reached video readiness in four seconds, played smooth 640x360 H.264 High
video with AAC stereo audio, and exited with Menu after 29 valid watched
seconds. During playback FFplay used 28,440 kB RSS with no process swap;
MemAvailable was 31,688 kB. Direct rewritten-HLS playback stalls on the target
FFplay, so preserve the server-side continuous MPEG-TS handoff.

## Repository Layout

- `app/`: OnionOS app metadata and root launcher. `app/launch.sh` is the
  production entry point; `app/playback-poc.sh` preserves the standalone
  playback experiment.
- `client/miyoo/`: BusyBox shell client, SDL selector source, and prebuilt ARMv7
  selector binary.
- `server/`: dependency-free Python HTTP server and optional stream-addon
  configuration example.
- `onion-tailscale/`: independent OnionOS userspace-networking app subproject.
  Its runtime binaries, state, downloads, and logs are intentionally ignored.
- `docs/`: confirmed POC evidence, architecture decisions, and canonical roadmap.
- `experiments/`: isolated experiments that must not replace the production app
  path until confirmed.
- `scripts/`: repeatable Miyoo deployment and ARM selector build entry points.

Deployment maps repository files as follows:

```text
app/launch.sh
  -> /mnt/SDCARD/App/PocketStremio/launch.sh
app/playback-poc.sh
  -> /mnt/SDCARD/App/PocketStremio/playback-poc.sh
client/miyoo/pocketstremio-ui.sh
  -> /mnt/SDCARD/App/PocketStremio/client/pocketstremio-ui.sh
client/miyoo/bin/pocketstremio-selector
  -> /mnt/SDCARD/App/PocketStremio/bin/pocketstremio-selector
client/miyoo/bin/pocketstremio-pause-monitor
  -> /mnt/SDCARD/App/PocketStremio/bin/pocketstremio-pause-monitor
client/miyoo/pocketstremio.conf.example
  -> /mnt/SDCARD/App/PocketStremio/config/pocketstremio.conf.example
```

Do not store target addresses or credentials in new committed files. Use the
existing defaults or environment overrides and keep deployment credentials out
of git.

The optional live device config is
`/mnt/SDCARD/App/PocketStremio/config/pocketstremio.conf`. Deployment must never
overwrite it. Environment variables take precedence over app-local config.

## Implementation Rules

### Miyoo Shell Client

- Target BusyBox `/bin/sh`; avoid Bash-only syntax, arrays, and large runtimes.
- Prefer OnionOS-provided `curl`, `jq`, `kbinput`, `infoPanel`, and FFplay.
- Unset `LD_PRELOAD` around non-audio network helpers. Apply the OnionOS padsp
  preload only when launching FFplay.
- When a proxy is configured, send Miyoo HTTP requests through both uppercase
  and lowercase proxy variables. When it is empty, unset inherited proxy
  variables and connect directly.
- Quote paths and user-derived values. Use `jq` for JSON rather than parsing it
  with `grep` or `sed`.
- Keep logs under the app-local `logs/` directory and avoid logging private
  upstream stream URLs.
- Always remove `/tmp/stay_awake` after playback, including failure paths.
- Derive watched time from SDL video readiness, not total FFplay process time;
  initial remote media startup must not advance Continue Watching.
- Observe A-button pause toggles through a non-grabbing app-local evdev reader.
  If pause tracking fails, suppress the progress update rather than overcounting.
- Use OnionOS `infoPanel --persistent` for blocking network/preflight work and
  dismiss only the app-started panel with `/tmp/dismiss_info_panel`. Clear the
  flag during cleanup so it cannot affect a later panel.

### SDL Selector

- Keep the selector on SDL 1.2 with its built-in bitmap font. Do not introduce
  SDL_ttf, libpng, or another runtime without measuring memory and compatibility.
- QR rendering uses the vendored Project Nayuki MIT-licensed C encoder linked
  into each app's existing selector. Pass one-time approval links through stdin,
  never process arguments or logs, and do not use an online QR service.
- The Miyoo framebuffer requires a 180-degree rendering correction.
- Confirmed keys are Up `273`, Down `274`, A `32`, and B `306`.
- B/back applies to PocketStremio selector screens. During FFplay playback, the
  Miyoo Menu button exits; B advances video frame by frame on this FFplay build.
- Stdout is a strict data channel: on success emit exactly the selected value and
  a newline; on cancel emit nothing and return nonzero.
- Vendor SDL diagnostics must stay off stdout. Send diagnostics to stderr or the
  app-local selector log.
- Keep item text bounded so it cannot overflow the 640x480 display.

### Server

- Keep the Miyoo-facing API small and JSON-based.
- Preserve current endpoints and response compatibility unless the change is
  explicitly versioned and deployed with the client.
- Keep private upstream URLs server-side. `/api/streams` returns opaque stream
  IDs and `/api/play` creates a PocketStremio play URL.
- Continue forwarding HTTP Range semantics required by FFplay.
- Keep HLS playlists and child URLs server-side. The device-facing HLS path must
  remain a bounded unencrypted MPEG-TS bridge unless a replacement is physically
  measured.
- Keep Stremio-specific and source-specific logic on the gaming PC.
- Prefer the Python standard library until a dependency removes demonstrated
  complexity and has a clear deployment story.
- Use `server/manage-server.ps1` for normal background lifecycle operations and
  `server/start-server.ps1` only when an attached foreground process is useful.

## OnionOS Execution Context

- Framebuffer and audio behavior cannot be proven over SSH. FFplay and SDL apps
  launched over SSH can block at `VT_WAITACTIVE` or fail to open `/dev/dsp`.
- Use SSH for file inspection, deployment, syntax checks, logs, process state,
  and network-only dry runs.
- Run visual, audio, and controller tests from the OnionOS Apps menu.
- Ask for the minimum physical interaction needed, then verify the result from
  app-local logs over SSH.
- Follow Onion's FFplay context: work from `/mnt/SDCARD/.tmp_update`, preload
  `/mnt/SDCARD/miyoo/lib/libpadsp.so`, create `/tmp/stay_awake`, and use
  `-vf "hflip,vflip"`.
- Do not describe B as the FFplay exit control. The physically confirmed
  playback exit control is the Miyoo Menu button.

## Verification

Scale tests to the change. Before committing, run the relevant checks:

- `python -m py_compile server/pocketstremio_server.py`
- `python -m unittest server.test_stremio_account server.test_pocketstremio_server -v`
- Parse every changed `.sh` with `sh -n` or Git Bash `sh -n`.
- Parse all changed `.ps1` files with the PowerShell parser.
- For server changes, exercise `/api/status`, search, metadata, streams, play
  session creation, and a byte-range media request on an alternate local port.
- For selector changes, cross-compile with `-Wall -Wextra -Werror` and verify the
  rebuilt binary matches the committed binary when using the same toolchain.
- For deployment, verify executable permissions, absence of stale test markers,
  and absence of leftover selector, FFplay, or UI processes.
- For controller, framebuffer, or audio changes, obtain a physical Apps-menu
  confirmation and collect the corresponding device log.

The cross-toolchains used during development live under ignored `.tmp/` paths
and are not repository dependencies. Do not commit them.

Use `scripts/deploy-miyoo.ps1` for repeatable tracked-file upgrades. It must
continue preserving the live client config, logs, all networking-provider
runtime/state, and OnionOS files. Use
`scripts/build-miyoo-selector.ps1 -VerifyCommitted` for the documented
reproducible selector check.

## Documentation and Milestones

- `docs/roadmap.md` is authoritative for status and sequencing.
- POC evidence documents record only confirmed observations. Clearly label
  assumptions and unmeasured behavior.
- A milestone becomes **Confirmed** only when its acceptance criteria have been
  met; device-facing criteria require a physical Miyoo test.
- When completing a milestone, update the roadmap and its evidence document in
  the same commit.
- Keep one milestone marked **Next**. Move unrelated ideas to **Deferred** rather
  than expanding active scope.

## Git Discipline

- Preserve unrelated user changes and the working network/playback baseline.
- Do not commit generated logs, Python caches, local addon configuration, media,
  downloaded toolchains, or runtime networking-provider files.
- Review staged changes for private URLs and tokens before pushing.
- Use focused commits that describe the completed milestone or fix.
- Push only after local checks pass and the worktree contains the intended files.
