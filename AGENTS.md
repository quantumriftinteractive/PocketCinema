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

- Keep all persistent device files under
  `/mnt/SDCARD/App/PocketStremio/`.
- Do not modify OnionOS core files. If no app-local solution exists, stop and
  explain the required change before touching a core file, then document it.
- Preserve the existing Tailscale setup and persistent state. Never replace,
  reset, delete, or reauthenticate `tailscale/state/tailscaled.state` as part of
  ordinary development.
- The Miyoo must communicate only with PocketStremio server through the existing
  userspace HTTP proxy at `http://127.0.0.1:1055/`.
- Keep Stremio Service bound to localhost on the gaming PC. Never expose port
  `11470` to the Miyoo or tailnet.
- Do not commit private addon URLs, tokens, Tailscale state, downloaded binaries,
  logs, generated caches, or the local test video. Respect `.gitignore`.
- Do not add torrent, debrid, transcoding, subtitle, account, progress, poster,
  or full-UI scope unless the roadmap and user request explicitly call for it.

## Current Working Baseline

The physically confirmed flow is:

```text
Apps -> PocketStremio -> search -> result -> Play -> stream -> FFplay
Apps -> PocketStremio -> Continue Watching -> Resume -> stream -> FFplay
```

Both the hosted Big Buck Bunny regression fixture and the public-domain *Night
of the Living Dead* stream resolved by the localhost open-media addon have been
physically played from the OnionOS Apps context. The latter confirmed H.264
Constrained Baseline 320x240 video, AAC stereo audio initialization, normal B
exit, progress saving, and cleanup.

Continue Watching persists on the gaming PC and resume uses FFplay `-ss` with
an approximate wall-clock-derived position. The target FFplay build does not
include the `subtitles` video filter; do not expose an external subtitle option
unless a remux/burn-in path or another compatible player has been implemented
and measured.

Current network and service boundaries:

```text
Miyoo shell/SDL client
  -> HTTP_PROXY 127.0.0.1:1055
  -> Tailscale userspace networking
  -> PocketStremio server 100.85.171.67:8755
  -> Cinemeta and server-side stream sources
  -> localhost-only Stremio Service 127.0.0.1:11470
```

The hosted Big Buck Bunny video is a deterministic regression fixture, not a
general stream resolver.

## Repository Layout

- `app/`: OnionOS app metadata and root launcher. `app/launch.sh` is the
  production entry point; `app/playback-poc.sh` preserves the standalone
  playback experiment.
- `client/miyoo/`: BusyBox shell client, SDL selector source, and prebuilt ARMv7
  selector binary.
- `server/`: dependency-free Python HTTP server and optional stream-addon
  configuration example.
- `tailscale/`: app-local userspace Tailscale lifecycle scripts. Runtime binaries,
  state, and logs are intentionally ignored.
- `docs/`: confirmed POC evidence, architecture decisions, and canonical roadmap.
- `experiments/`: isolated experiments that must not replace the production app
  path until confirmed.

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
```

Do not store target addresses or credentials in new committed files. Use the
existing defaults or environment overrides and keep deployment credentials out
of git.

## Implementation Rules

### Miyoo Shell Client

- Target BusyBox `/bin/sh`; avoid Bash-only syntax, arrays, and large runtimes.
- Prefer OnionOS-provided `curl`, `jq`, `kbinput`, `infoPanel`, and FFplay.
- Unset `LD_PRELOAD` around non-audio network helpers. Apply the OnionOS padsp
  preload only when launching FFplay.
- Send all Miyoo HTTP requests through both uppercase and lowercase proxy
  variables for compatibility.
- Quote paths and user-derived values. Use `jq` for JSON rather than parsing it
  with `grep` or `sed`.
- Keep logs under the app-local `logs/` directory and avoid logging private
  upstream stream URLs.
- Always remove `/tmp/stay_awake` after playback, including failure paths.

### SDL Selector

- Keep the selector on SDL 1.2 with its built-in bitmap font. Do not introduce
  SDL_ttf, libpng, or another runtime without measuring memory and compatibility.
- The Miyoo framebuffer requires a 180-degree rendering correction.
- Confirmed keys are Up `273`, Down `274`, A `32`, and B `306`.
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
- Keep Stremio-specific and source-specific logic on the gaming PC.
- Prefer the Python standard library until a dependency removes demonstrated
  complexity and has a clear deployment story.

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

## Verification

Scale tests to the change. Before committing, run the relevant checks:

- `python -m py_compile server/pocketstremio_server.py`
- `python -m unittest server.test_pocketstremio_server -v`
- Parse every changed `.sh` with `sh -n` or Git Bash `sh -n`.
- Parse `server/start-server.ps1` with the PowerShell parser.
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

- Preserve unrelated user changes and the working Tailscale/playback baseline.
- Do not commit generated logs, Python caches, local addon configuration, media,
  downloaded toolchains, or runtime Tailscale files.
- Review staged changes for private URLs and tokens before pushing.
- Use focused commits that describe the completed milestone or fix.
- Push only after local checks pass and the worktree contains the intended files.
