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
- The Miyoo reaches the server only through the Tailscale userspace HTTP proxy
  at `127.0.0.1:1055`.
- PocketStremio server is the only service exposed to the Miyoo.
- Stremio Service remains bound to `127.0.0.1:11470` on the gaming PC.
- Persistent Miyoo files remain under `/mnt/SDCARD/App/PocketStremio/`.
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

Evidence: [Tailscale userspace POC](tailscale.md)

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

## Next Milestone

### 6. Subtitles and Continue Watching

**Status: Next**

Goal: add lightweight external subtitle selection and persistent resume entries
without introducing a larger Miyoo runtime.

Implemented for device verification:

- server-side Stremio subtitle discovery with opaque Miyoo-facing IDs;
- subtitle proxy URLs that keep private upstream URLs on the gaming PC;
- a subtitle selection screen after stream selection;
- local temporary SRT download and FFplay subtitle-filter launch;
- persistent server-side continue-watching state;
- Search and Continue Watching home actions;
- Resume and Play from Start actions;
- approximate progress updates based on FFplay wall-clock playback time.

Acceptance criteria:

- The test SRT appears over the hosted Big Buck Bunny video on the Miyoo.
- No subtitles remains selectable and preserves normal playback.
- Exiting playback early creates a Continue Watching entry.
- Selecting Resume starts FFplay near the saved position using `-ss`.
- Completing a video removes its Continue Watching entry when duration is known.
- B/back works from the new home, resume, and subtitle screens.
- Playback exits cleanly without stale subtitle files or `stay_awake` state.

The feature remains unconfirmed until the target FFplay build reports the
`subtitles` filter and the full interaction is physically tested from Apps.

## Planned Milestones

### 7. Real Stream Resolution

**Status: Planned**

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
- subtitles, accounts, library, or playback progress;
- posters or a larger UI framework.

### 8. Playback Compatibility and Reliability

**Status: Planned**

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

**Status: Planned**

- Extend search and metadata normalization to series.
- Add season and episode selection screens using the existing SDL selector.
- Resolve streams using the selected Stremio video ID.
- Preserve B/back navigation at every level.

Acceptance criterion: a user can search for a series, choose an episode, select
a compatible stream, and start playback.

### 10. Operational Resilience

**Status: Planned**

- Add bounded play-session lifetime and cache cleanup.
- Improve server health details and client connectivity errors.
- Make server address and non-secret client settings easy to configure.
- Define repeatable deployment and upgrade steps.
- Expand automated server API tests and add a reproducible selector build process.

Acceptance criterion: expected network and server failures return the user to a
working OnionOS screen without stale processes or persistent-state damage.

## Deferred Features

These features should begin only after real stream playback and compatibility
behavior are stable:

- server-side transcoding or remuxing;
- audio-track selection;
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
- The server currently keeps stream and play-session state only in memory and
  does not expire it.
- Resume positions currently use elapsed wall-clock time because the OnionOS
  FFplay build has not exposed a confirmed machine-readable progress channel.
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
