# PocketStremio Roadmap

This is the canonical project roadmap. It separates behavior confirmed on the
Miyoo Mini Plus from planned work and keeps each milestone independently
testable.

## Status Legend

- **Confirmed**: implemented and physically verified on the target device.
- **Next**: the only milestone that should receive feature work now.
- **Planned**: sequenced work whose prerequisites are understood.
- **Deferred**: intentionally out of scope until earlier milestones are stable.

## Stable Baseline

The current prototype completes this path:

```text
OnionOS Apps
  -> PocketStremio search
  -> controller-driven result selection
  -> media action selection
  -> stream selection
  -> PocketStremio play session
  -> FFplay video and audio
```

Architectural boundaries:

- The Miyoo remains a lightweight shell and SDL client.
- PocketStremio uses direct HTTP by default and can use a configured HTTP proxy.
- Network providers such as Tailscale are operated independently from
  PocketStremio.
- PocketStremio server is the only service exposed to the Miyoo.
- Stremio Service remains bound to `127.0.0.1:11470` on the gaming PC.
- PocketStremio persistent files remain under
  `/mnt/SDCARD/App/PocketStremio/`; independent provider apps own their own app
  directories.
- OnionOS core files and Tailscale persistent state are not modified.

## Confirmed Milestones

### 1. Device and OnionOS Runtime

**Status: Confirmed**

- ARMv7 hardware and available memory were measured.
- OnionOS app layout, launch context, framebuffer, VT, and audio behavior were
  investigated.
- Persistent application files are isolated under the PocketStremio app path.

Evidence: [Miyoo hardware notes](miyoo-hardware.md)

### 2. Tailscale Userspace Networking

**Status: Confirmed**

- `tailscaled` runs in userspace networking mode.
- The local HTTP proxy is reachable at `127.0.0.1:1055`.
- State and logs remain inside the PocketStremio directory.
- Miyoo-to-gaming-PC HTTP traffic works across the tailnet.

Evidence: [Tailscale userspace POC](../onion-tailscale/docs/poc.md)

### 3. Structured JSON Communication

**Status: Confirmed**

- The Miyoo requests `/api/status` and `/api/search` through the proxy.
- OnionOS `jq` parses structured API responses.
- Server and client resource usage was measured.

Evidence: [JSON communication POC](json-poc.md)

### 4. OnionOS Network Playback

**Status: Confirmed**

- FFplay launches from the OnionOS Apps context.
- A remote H.264 640x360 and AAC stereo MP4 plays visibly and audibly.
- The framebuffer orientation, `/dev/dsp` audio path, and clean UI return are
  confirmed.
- Active playback measurements captured tailscaled at roughly 30-34 MB RSS and
  FFplay at roughly 19-20 MB RSS.

Evidence: [FFplay playback POC](ffplay-playback-poc.md)

### 5. Controller-Driven Vertical Slice

**Status: Confirmed**

- Cinemeta-backed movie search and metadata work through PocketStremio server.
- The server exposes `/api/streams`, `/api/play`, and private play sessions.
- D-pad navigation, A selection, and B/back work in the custom SDL selector.
- Big Buck Bunny can be selected manually and played through the full pipeline.
- The automatic first-item path remains available as a diagnostic fallback.

Evidence: [First vertical slice](vertical-slice.md) and
[Stremio integration](stremio-integration.md)

### 6. Continue Watching and Subtitle Feasibility

**Status: Confirmed**

Continue Watching is implemented and physically confirmed:

- persistent, bounded server-side progress state;
- Search, Continue Watching, and Exit home actions;
- Resume and Play from Start actions;
- FFplay resume seeking with `-ss`;
- approximate progress updates measured after video readiness with A-button
  pause intervals excluded;
- completed-item removal when duration is known;
- clean return to the home menu with no stale processes or temporary files.

The target FFplay build advertises `-ss` but does not include the `subtitles`
video filter. It can select subtitle streams already embedded in an input, but
cannot render a separate SRT alongside the current direct MP4 path. Server-side
Stremio subtitle discovery, opaque IDs, and proxying are implemented and tested,
but external subtitle rendering is deferred until a remux/burn-in path or
another compatible player is deliberately introduced and measured.

Evidence: [Subtitles and Continue Watching POC](subtitles-progress-poc.md)

### 7. Real Stream Resolution

**Status: Confirmed**

The public-domain *Night of the Living Dead* (1968) Internet Archive derivative
is resolved through a localhost-only Stremio addon. PocketStremio hides the
upstream URL and relays redirects and byte ranges through Tailscale. Manual
selection, visible and audible playback, acceptable initial smoothness,
Menu-button exit, progress saving, and cleanup were physically confirmed from
the OnionOS Apps context.

Evidence: [Real Stream Resolution POC](real-stream-resolution.md)

Goal: replace the hosted test stream as the only proven source with at least one
real, legally accessible HTTP(S) stream resolved by a server-side addon or
service.

Scope:

- Identify one reproducible direct-URL stream source for a movie.
- Resolve it behind `/api/streams/{type}/{id}` without exposing its upstream URL
  to the Miyoo.
- Preserve the localhost-only Stremio Service boundary.
- Handle common upstream redirects, Range requests, content types, and failures.
- Show useful stream names and concise failure messages in the Miyoo client.
- Keep the hosted Big Buck Bunny stream as a deterministic regression fixture.

Acceptance criteria:

```text
search real movie
  -> manually select result
  -> select Play
  -> manually select resolved stream
  -> receive /play/{session}
  -> visible and audible FFplay playback
```

The device log must show manual selections, the selected stream source, FFplay
format detection, and a clean playback exit. Raw private upstream URLs must not
appear in Miyoo-facing API responses.

Not part of this milestone:

- torrents or peer-to-peer handling;
- debrid integration;
- transcoding;
- series or episodes;
- accounts or library integration;
- posters or a larger UI framework.

### 8. Playback Compatibility and Reliability

**Status: Confirmed**

Gaming-PC ffprobe preflight, confirmed/candidate/unsupported classification,
client-visible rejection messages, cached probes, and bounded six-hour play
sessions are implemented. H.264/AAC MP4 and VP8/Vorbis WebM played visibly,
audibly, and smoothly from the Apps context. H.264/Opus was rejected with a
useful message before FFplay started. Startup, RSS, free memory, and swap were
measured for both playable profiles.

Evidence: [Playback Compatibility and Reliability](playback-compatibility.md)

- Record the codecs, containers, resolution, bitrate, and audio formats FFplay
  can sustain on the device.
- Add server-side compatibility classification before playback.
- Improve timeout, cancellation, stale-session, and upstream error handling.
- Measure startup time, buffering, smoothness, RSS, free memory, and swap with
  multiple representative direct streams.
- Decide from evidence whether remuxing or transcoding is required.

Acceptance criterion: supported streams play predictably, while unsupported
streams fail before FFplay with a useful message.

### 9. Series and Episode Browsing

**Status: Confirmed**

Movie and series search results are normalized together. Series metadata exposes
compact season and episode records, and the Miyoo adds controller-driven season
and episode selectors before the existing stream and playback flow. A local
two-season fixture proved the full path without an Internet media dependency;
episode progress and B/back navigation were also physically confirmed.

Evidence: [Series and Episode Browsing](series-episode-browsing.md)

- Extend search and metadata normalization to series.
- Add season and episode selection screens using the existing SDL selector.
- Resolve streams using the selected Stremio video ID.
- Preserve B/back navigation at every level.

Acceptance criterion: a user can search for a series, choose an episode, select
a compatible stream, and start playback.

### 10. Operational Resilience

**Status: Confirmed**

Server health now exposes bounded runtime-state details. A background lifecycle
manager handles health checks and stale PID files, persistent cache/progress
state survives restarts, and ephemeral play sessions are deliberately cleared.
The Miyoo supports app-local non-secret configuration and specific connectivity
errors. Repeatable client deployment and selector build scripts are included.
An unreachable-server test physically displayed the expected error from the
OnionOS Apps context and left no stale UI, selector, FFplay, infoPanel, or
temporary playback state.

Evidence: [Operational Resilience](operational-resilience.md)

- Verify session and cache cleanup across restarts and expected failures.
- Improve server health details and client connectivity errors.
- Make server address and non-secret client settings easy to configure.
- Define repeatable deployment and upgrade steps.
- Expand automated server API tests and add a reproducible selector build process.

Acceptance criterion: expected network and server failures return the user to a
working OnionOS screen without stale processes or persistent-state damage.

### 11. Transport Independence and Tailscale Extraction

**Status: Confirmed**

PocketStremio now requires an explicit server URL, uses direct HTTP when its
generic proxy setting is empty, and contains no Tailscale lifecycle or state
knowledge. Direct and configured-proxy requests passed on the Miyoo. The normal
Apps selector and B exit were physically confirmed after deployment, with clean
process and temporary-file state. The live legacy Tailscale state remained
byte-for-byte unchanged. Tailscale-specific source is isolated in an
independently deployable `onion-tailscale/` subproject, but that app and its
separate state migration were deliberately not deployed.

Evidence: [Transport Independence and Tailscale Extraction](transport-independence.md)

- Make PocketStremio direct HTTP the default and its HTTP proxy optional.
- Require an explicit server URL instead of shipping a provider-specific target.
- Remove all Tailscale daemon lifecycle, socket, state, and status knowledge from
  PocketStremio production and diagnostic clients.
- Isolate the userspace-networking proof under the self-contained
  `onion-tailscale/` subproject with `/mnt/SDCARD/App/Tailscale/` as its target.
- Preserve the currently authenticated legacy state without moving, deleting,
  resetting, or reauthenticating it.
- Keep the current remote Miyoo setup working by explicitly configuring its
  existing proxy until a separate Tailscale-app migration is physically tested.

Acceptance criterion: PocketStremio can reach a server directly when `PROXY` is
empty, can retain the confirmed remote path when a generic proxy is configured,
and contains no code that starts or inspects Tailscale. The standalone
Tailscale folder must be independently deployable without PocketStremio files.

### 12. Real Series Stream Validation

**Status: Confirmed**

The real Cinemeta series *The Beverly Hillbillies* exposes nine normalized
seasons. Its public-domain S1E1 Internet Archive derivative resolves through the
localhost open-media addon and remains hidden behind an opaque play session.
The H.264/AAC 320x240 stream played successfully from the Apps context with
audio, progress saving, Menu exit, and clean OnionOS return. A generic parent
series lookup now supplies standalone episode details.

Evidence: [Real Series Stream Validation](real-series-stream.md)

- Search Cinemeta for a real series and normalize its real season/episode data.
- Resolve one legal direct-HTTP episode through a server-side addon.
- Reuse compatibility preflight, opaque play sessions, progress, and the current
  OnionOS player path without exposing the upstream URL.
- Keep the local two-season fixture as the deterministic regression path.
- Document stream availability, compatibility, startup, controls, audio/video,
  progress behavior, and cleanup from an Apps-context run.

Acceptance criterion: a user can search for a real series, choose a real episode
and compatible direct stream, and complete visible and audible playback startup
on the Miyoo through the configured network transport.

Not part of this milestone: accounts, library sync, torrents, debrid,
transcoding, external subtitle rendering, posters, or a larger UI framework.

### 13. Real Episode Resume and Reliability

**Status: Confirmed**

The real episode appears in Continue Watching with a clear series, season,
episode, year, and position label. B navigation returned cleanly from its action
menu. Resume passed the saved 44-second offset to FFplay, visibly started
partway into the episode, and advanced progress to a plausible 69 seconds after
25 measured playback seconds. Play from Start passed a zero offset, visibly
showed the opening, and replaced progress with only 3 seconds measured after
video readiness. Both Menu exits returned cleanly to OnionOS.

Evidence: [Real Episode Resume and Reliability](real-episode-resume.md)

- Verify the real episode appears in Continue Watching with a clear series and
  episode label.
- Resume the same episode through the real source and measure seek accuracy.
- Confirm Play from Start resets the requested position without corrupting saved
  progress.
- Exercise B navigation before playback and Menu exit during resumed playback.
- Measure repeat startup time and confirm cleanup after both paths.

Acceptance criterion: the real episode can be resumed from Continue Watching,
starts near the saved position, reports plausible new progress, and returns
cleanly to OnionOS without stale state or processes.

## Next Milestone

### 14. Local Stremio Service Backend

**Status: Next**

- Inspect and document the localhost Stremio Service API and runtime capabilities
  actually available at `127.0.0.1:11470`.
- Add a bounded PocketStremio backend adapter instead of exposing the service to
  the Miyoo or tailnet.
- Route one legal test title through the service-backed metadata or stream path
  while preserving the current direct-addon regression fixtures.
- Surface specific server-side diagnostics when the service is unavailable or
  has no usable addon result.
- Confirm PocketStremio remains the Miyoo's only server endpoint and that raw
  upstream URLs remain private.

Acceptance criterion: PocketStremio obtains a usable metadata or direct-stream
result for one legal test item through the localhost Stremio Service, relays it
through the existing opaque API, and completes an Apps-context playback without
making port `11470` remotely reachable.

Not part of this milestone: Stremio account authentication or library sync,
torrents, debrid, transcoding, external subtitle rendering, or a larger UI.

## Deferred Features

These features should begin only after real stream playback and compatibility
behavior are stable:

- server-side transcoding or remuxing;
- audio-track selection;
- external subtitle rendering through server-side remuxing/burn-in or another
  measured compatible player;
- Stremio account, library, and authentication work;
- posters, image caching, and richer media details;
- favorites, history, and settings UI;
- torrent, debrid, or other source-specific integrations.

Each deferred feature should become a separate milestone with its own device
acceptance criteria rather than expanding an earlier milestone.

## Known Risks

- Active playback leaves only about 1.9-3.1 MB reported free RAM, so new Miyoo
  runtimes or image-heavy UI work carry significant memory risk.
- Stremio Service's local addon is reachable but returned no streams in the
  confirmed probes.
- Direct streams may use codecs, headers, redirects, or seek behavior that the
  current FFplay proxy path does not support.
- Stream and play-session state remains in memory. Play sessions expire after
  six hours and are bounded to 128 entries; normalized probe results persist for
  seven days in an ignored cache file.
- Resume positions remain approximate because the OnionOS FFplay build has not
  exposed a machine-readable progress channel. Startup and A-button pauses are
  excluded, but seeks and buffering after video readiness are not yet measured.
- The client depends on OnionOS utilities and SDL 1.2 behavior that should be
  rechecked when the target OnionOS version changes.

## Roadmap Rules

- Keep only one feature milestone in **Next** status.
- Do not mark a milestone **Confirmed** without a physical Miyoo test where its
  acceptance criteria require device behavior.
- Update the evidence document and this roadmap in the same change.
- Preserve the working networking and playback baseline while developing the
  next layer.
- Do not modify OnionOS core files unless a requirement cannot be met otherwise;
  document any exception before deployment.
