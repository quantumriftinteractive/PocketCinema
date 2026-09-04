# PocketCinema Roadmap

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
  -> PocketCinema search
  -> controller-driven result selection
  -> media action selection
  -> stream selection
  -> PocketCinema play session
  -> FFplay video and audio
```

Architectural boundaries:

- The Miyoo remains a lightweight shell and SDL client.
- PocketCinema uses direct HTTP by default and can use a configured HTTP proxy.
- Network providers such as Tailscale are operated independently from
  PocketCinema.
- PocketCinema server is the only service exposed to the Miyoo.
- PocketCinema Server is the only service exposed to the Miyoo; the local
  Stremio Service default is `http://127.0.0.1:11470`. A Windows Firewall block
  prevents remote access to that local service. M23 plans a validated,
  PCServer-only configurable endpoint for a separately reachable service host;
  the Miyoo never contacts it directly.
- PocketCinema persistent files remain under
  `/mnt/SDCARD/App/PocketCinema/`; independent provider apps own their own app
  directories.
- OnionOS core files and Tailscale persistent state are not modified.

## Confirmed Milestones

### 1. Device and OnionOS Runtime

**Status: Confirmed**

- ARMv7 hardware and available memory were measured.
- OnionOS app layout, launch context, framebuffer, VT, and audio behavior were
  investigated.
- Persistent application files are isolated under the PocketCinema app path.

Evidence: [Miyoo hardware notes](miyoo-hardware.md)

### 2. Tailscale Userspace Networking

**Status: Confirmed**

- `tailscaled` runs in userspace networking mode.
- The local HTTP proxy is reachable at `127.0.0.1:1055`.
- State and logs remain inside the PocketCinema directory.
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

- Cinemeta-backed movie search and metadata work through PocketCinema server.
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
is resolved through a localhost-only Stremio addon. PocketCinema hides the
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
- Preserve the local-default Stremio Service firewall containment while keeping
  any configured endpoint PCServer-only.
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

PocketCinema now requires an explicit server URL, uses direct HTTP when its
generic proxy setting is empty, and contains no Tailscale lifecycle or state
knowledge. Direct and configured-proxy requests passed on the Miyoo. The normal
Apps selector and B exit were physically confirmed after deployment, with clean
process and temporary-file state. The live legacy Tailscale state remained
byte-for-byte unchanged. Tailscale-specific source is isolated in an
independently deployable `onion-tailscale/` subproject, but that app and its
separate state migration were deliberately not deployed.

Evidence: [Transport Independence and Tailscale Extraction](transport-independence.md)

- Make PocketCinema direct HTTP the default and its HTTP proxy optional.
- Require an explicit server URL instead of shipping a provider-specific target.
- Remove all Tailscale daemon lifecycle, socket, state, and status knowledge from
  PocketCinema production and diagnostic clients.
- Isolate the userspace-networking proof under the self-contained
  `onion-tailscale/` subproject with `/mnt/SDCARD/App/Tailscale/` as its target.
- Preserve the currently authenticated legacy state without moving, deleting,
  resetting, or reauthenticating it.
- Keep the current remote Miyoo setup working by explicitly configuring its
  existing proxy until a separate Tailscale-app migration is physically tested.

Acceptance criterion: PocketCinema can reach a server directly when `PROXY` is
empty, can retain the confirmed remote path when a generic proxy is configured,
and contains no code that starts or inspects Tailscale. The standalone
Tailscale folder must be independently deployable without PocketCinema files.

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

### 14. Standalone Tailscale Management App

**Status: Confirmed**

The independent OnionOS app now displays Enabled or Disabled state and the
current Tailscale IPv4 address, supports controller-driven enable/disable and
Refresh, and toggles an app-owned OnionOS startup hook. The authenticated node
state was copied into `/mnt/SDCARD/App/Tailscale/` while retaining the original
rollback state. Two disable/enable cycles restored `100.97.46.26` and proxy
traffic. A physical reboot returned normally to MainUI and started the
standalone daemon without opening the app.

The home screen also renders a local QR code for the admin machines page. Its
orientation, scan target, IP layout, D-pad navigation, and B exit are physically
confirmed. The same renderer is wired to first-account verification without
logging the one-time URL, though that unauthenticated path remains deliberately
untested against the preserved working identity.

Evidence: [OnionOS Tailscale Management App](../onion-tailscale/docs/management-app.md)

- Show daemon state and the assigned Tailscale IPv4 address.
- Provide Enable, Disable, Refresh, and B/Exit controller actions.
- Offer an explicit first-account verification URL without storing auth keys or
  logging the URL in the normal app log.
- Toggle only the app-owned OnionOS 4.3 startup hook and detect conflicts.
- Keep boot bounded when Wi-Fi or internet is unavailable.
- Refuse daemon collisions and use copy-only state adoption with rollback.

Acceptance criterion: the app can control its standalone userspace daemon,
display the correct IP, preserve authenticated identity across restart, and
start automatically during a normal OnionOS boot without modifying core files.

The Connect account screen is implemented but remains unconfirmed against a
fresh unauthenticated state. Deliberately offline boot is bounded by design but
has not been physically timed.

### 15. Local Stremio Service Backend

**Status: Confirmed**

PocketCinema now uses a dedicated, loopback-only backend adapter for Stremio
Service Local Files. One allowlisted public-domain file resolved through the
service, passed the existing compatibility preflight, remained hidden behind an
opaque play session, and played visibly and audibly from the OnionOS Apps
context. Windows Firewall blocks raw service access from both the Miyoo LAN and
tailnet paths while desktop loopback remains healthy.

Evidence: [Local Stremio Service Backend](local-stremio-service-backend.md)

- Inspect and document the localhost Stremio Service API and runtime capabilities
  actually available at `127.0.0.1:11470`.
- Add a bounded PocketCinema backend adapter instead of exposing the service to
  the Miyoo or tailnet.
- Route one legal test title through the service-backed metadata or stream path
  while preserving the current direct-addon regression fixtures.
- Surface specific server-side diagnostics when the service is unavailable or
  has no usable addon result.
- Confirm PocketCinema remains the Miyoo's only server endpoint and that raw
  upstream URLs remain private.

Acceptance criterion: PocketCinema obtains a usable metadata or direct-stream
result for one legal test item through the localhost Stremio Service, relays it
through the existing opaque API, and completes an Apps-context playback without
making port `11470` remotely reachable.

Not part of this milestone: Stremio account authentication or library sync,
torrents, debrid, transcoding, external subtitle rendering, or a larger UI.

### 16. Stremio Account Addon Discovery

**Status: Confirmed**

The linked gaming-PC account exposes 15 normalized addons without credentials or
transport URLs. Torrentio RD and AIOStreams results remain rejected. The Greek TV
addon supplies ERT News through HLS; PocketCinema selects its compatible
640x360 H.264/AAC rendition and converts only the transport from HLS segments to
a continuous opaque MPEG-TS response. No transcoding or raw upstream URL reaches
the Miyoo.

Server-mediated account binding is also physically confirmed from the OnionOS
Apps context: QR scan, browser approval, A refresh, 15-addon status, and B return
all passed without placing an auth key or approval URL in Miyoo logs. Milestone
16's account-backed Live TV browsing, playback, audio, smoothness, Menu exit,
resource use, and cleanup are now also physically confirmed.

Evidence: [Stremio Account Addon Discovery](stremio-account-addons.md)

- Research the current supported account and addon-collection interfaces used by
  Stremio without reading or copying opaque desktop application state.
- Keep authentication material and private addon URLs on the gaming PC in
  ignored configuration; never send them to the Miyoo or commit them.
- Normalize a read-only account addon list behind PocketCinema and report
  per-source capability and availability without exposing manifest URLs.
- Permit only direct HTTP(S) stream results through the existing compatibility
  and opaque play-session path.
- Explicitly reject torrent identifiers, debrid-only results, external launch
  URLs, and unsupported stream shapes.
- Preserve Local Files, open-media, and deterministic fixtures as independent
  regression sources.

Acceptance criterion: PocketCinema discovers the authenticated account's addon
collection server-side, resolves one legal direct-HTTP result through an account
addon when available, and completes Apps-context playback without exposing an
auth token, private addon URL, or raw stream URL to the Miyoo.

Not part of this milestone: library or watch-history sync, torrent playback,
debrid integration, transcoding, or storing account credentials on the Miyoo.

## Next Milestone

### 17. Long-Running Live Playback Resilience

**Status: In Progress (deprioritized)**

The first account-backed live session is confirmed for 29 watched seconds. The
next milestone hardens the bounded MPEG-TS bridge for normal viewing durations
without adding transcoding or source-specific behavior.

Evidence in progress: [Long-Running Live Playback Resilience](live-playback-resilience.md)

- Run a continuous 30-minute Apps-context playback and sample memory and swap.
- Confirm playlist refresh, media-sequence rollover, and segment deduplication.
- Exercise one brief upstream fetch failure and provide a bounded user-facing
  failure instead of an indefinite black screen.
- Confirm Menu exit promptly closes the server bridge and leaves no handler or
  device process behind.
- Recheck the progressive movie and episode regression paths after bridge
  hardening.

Acceptance criterion: ERT News plays smoothly with audio for 30 minutes, memory
remains viable, transient failure behavior is bounded, Menu cleanup is complete,
and existing movie and episode playback remain unchanged.

### 18. Account Addon Direct HTTPS Playback

**Status: Confirmed**

The linked Torrentio RD and AIOStreams configurations return direct HTTPS media
objects for normal movies and series. The user explicitly authorized using
those account-bound results. Tokens and configured addon transports remain on
the gaming PC behind opaque PocketCinema play sessions.

- Accept a direct public HTTP(S) `url` even when its display text is debrid
  labeled.
- Continue rejecting `infoHash`, magnet/P2P-only, external-player, YouTube,
  private-address, credential-in-URL, fragment, and non-HTTP shapes.
- Keep addon configuration, tokens, and resolved media URLs off the Miyoo API
  and out of logs and git.
- Reuse ffprobe compatibility checks and the existing progressive/HLS proxy
  paths without adding torrent ingestion or transcoding.
- Physically validate one movie and one episode from a linked account addon.

Movie evidence: *Alien* (1979) played visibly and audibly from the Torrentio RD
360p direct HTTPS result. Its preflight measured H.264 Main 640x272 with AAC.

Episode evidence: *Grimm* S1E1 played visibly and audibly from a Torrentio RD
480p result. FFplay measured H.264 High 852x480 with AAC stereo, reached video
readiness after 36 seconds, recorded 37 valid watched seconds, tracked a pause,
exited cleanly, and saved progress.

Acceptance criterion: a linked account addon resolves a direct HTTPS movie or
episode, PocketCinema exposes only an opaque stream ID and play URL, and the
media starts visibly and audibly on the Miyoo without exposing account or media
tokens.

### 19. Account Addon Catalog Browsing

**Status: Planned**

Search and playback now use linked account addons, but the home screen does not
yet expose their movie and series catalogs. Add lightweight server-normalized
catalog browsing without sending addon transports or tokens to the Miyoo.

- List account catalogs by safe addon and catalog labels.
- Browse bounded movie and series pages through opaque PocketCinema endpoints.
- Reuse the current media details, season/episode, stream, playback, and back
  navigation paths.
- Keep catalog extras, addon transports, tokens, posters, and raw responses on
  the gaming PC.

Acceptance criterion: a user can open an account addon catalog, select one movie
or series with the controller, and reach the existing physically confirmed
account-addon playback flow.

### 20. Bounded English Subtitles and Downscaling

**Status: Confirmed**

External subtitles cannot render on the target FFplay build, and physically
tested 720p and 1080p sources exceed reliable direct-play behavior. Add one
bounded gaming-PC FFmpeg path for English subtitle burn-in and conditional
downscaling while keeping the Miyoo client and account credentials unchanged.

The first deployed build rendered subtitles but exposed a reproducible resume
timestamp defect and unsupported seek behavior on its continuous MPEG-TS
output. The timestamp correction and rate-limited conversion are implemented;
a focused Apps-context regression confirmed pause tracking and cleanup but the
generic first subtitle still mismatched the selected release. Subtitle results
now use available stream hash/size/filename hints, trusted-source and release
matching, and label deduplication. The second manually selected GGWP subtitle
was physically confirmed synchronized for *Invincible* S1E4, and two resumed
runs confirmed correct progress accumulation. Stream browsing labels retained
ffprobe results as `DIRECT`, `CONVERT`, or `CHECK`, and hides cached unsupported
results without probing every candidate before showing the list.
PCServer also hides cached media that its actual container, video codec, or audio
codec preflight has rejected; it hides cached conversion-only streams if that
PCServer has no FFmpeg conversion service, and omits external subtitle choices when
its FFmpeg build lacks subtitle burn-in support. Unprobed sources remain marked
`CHECK` so opening a stream list never probes every addon result.

On the split-host Mac PCServer, the stock Homebrew FFmpeg lacked libass and was
therefore correctly reported as unable to burn external subtitles. A separate
Mac-local FFmpeg build with libass restored the production burn-in capability;
the previously failing stream/subtitle pair then rendered burned-in subtitles
correctly on the Miyoo. Subtitle results now show strong release/hash matches
first, with an explicit controller option to show the remaining English
choices. This is focused subtitle evidence only; the Milestone 20 acceptance
criteria remain pending.
Inspected but non-confirmed media is now routed through the bounded conversion
path rather than direct FFplay; E-AC-3 is accepted only as a server-side
conversion input and is emitted to the Miyoo as AAC.
The unchanged aspect-preserving production converter can yield an odd 4:2:0
height for some ultra-wide sources (for example 1920x800 becomes 640x267),
which libx264 cannot encode. Such geometry is now rejected at preflight and
cached as unsupported rather than failing after FFplay starts. The 1920x800
HEVC/E-AC-3 field source physically displayed that specific message on the
Miyoo and was absent after reopening the stream list. Changing the production
MPEG-TS filter remains out of scope for this slice.

The current MPEG-TS path burns one subtitle into the video and therefore cannot
switch it inside FFplay. The deterministic Matroska experiment passes startup
and embedded-track detection. An isolated, app-local FFplay 2.4.14 rebuild with
libass, fontconfig, and a bundled font was physically confirmed to render
upright, bottom-positioned subtitles and switch visibly from red Track One to
blue Track Two with R1, then disable subtitles. R2 did not trigger this
candidate, so the controller mapping differs from the earlier original-FFplay
observation. Keep burn-in as the production fallback; the experiment is not
integrated into the normal client path.

The opt-in account field test now packages the selected external subtitle as a
small Matroska file because the candidate device build lacks the standalone
SubRip demuxer. Matroska subtitle rendering and restored candidate audio were
physically confirmed. Server-side SRT/WebVTT cue rewriting now applies a
nonzero resume offset before packaging. The recent Spider-Man run is not
subtitle-sync evidence because the selected subtitle could not be proven to
match the stream release; deterministic shifted-Matroska fixture rendering is
now confirmed, but the account candidate-wrapper comparison was still pending
at that stage.
The candidate's post-readiness disconnect is handled as experimental cleanup
in the field-test client only. The wrapper remains disabled outside explicit
tests; normal production playback and burn-in behavior are unchanged.

The deterministic follow-up then used a subtitle-only Matroska package with
cue timestamps 0--4 and 6--10 after an 8-second simulated resume shift.
Apps-context logs confirmed libass, the bundled font, audio, video readiness,
subtitle-filter initialization, and clean completion. This confirms the
shifted Matroska rendering path. Exact first-frame visual timing is not
machine-observable in FFplay logs, so the full Milestone 20 acceptance remained
open at that point despite the later controlled account-wrapper run below.

A known-good account release match is now recorded for *Spider-Man: No Way
Home*: `Torrentio RD - 720P BluRay x265 HEVC PSA` with
`Spider-Man.No.Way.Home.2021.1080p.BluRay.x265-YAWNTiC_eng`. The pair was
physically synchronized through the production converted burn-in path and is
the controlled candidate for the remaining experimental wrapper comparison.

The controlled candidate run is now physically confirmed for video, audio,
subtitle rendering, and clean Menu exit: the Matroska handoff ran for 63 valid
watched seconds and saved progress without a playback error. D-pad seeking
froze the nonseekable converted response, and the candidate did not respond to
the aspect-ratio control; both limitations remain documented and excluded from
the wrapper acceptance criteria.

Latest visual-isolation checkpoint: production burn-in passed without the
artifact, while the candidate displayed it even with no subtitle selected. The
deployed candidate matched the local rebuild byte-for-byte. Clearing its SDL
surface removed stale top-of-screen PocketCinema pixels but not the bottom
artifact. The remaining investigation is ordered around candidate SDL versus
Miyoo SDL, display geometry, and other candidate build/runtime differences.
At this checkpoint, Milestone 20 remained In Progress and was not Confirmed.

The first runtime comparison also forced the candidate to use Miyoo's system
SDL instead of its bundled SDL library; the bottom artifact remained with no
subtitle selected. SDL library selection is therefore crossed off as the
primary cause. The next comparison is candidate display geometry/framebuffer
presentation.

An app-local copy of Onion's `ffplay_16_9` removed the artifact but visibly
stretched the video vertically. This confirms display geometry as the cause;
stretching is not an acceptable solution for films with intentional letterbox
content. The original candidate was restored after the comparison.

The decisive candidate test then forced the SDL surface to 640x480 using
app-local FFplay `-x 640 -y 480`, while preserving the approximately 640x360
video rectangle. This removed the bottom artifact, prevented the partial
PocketCinema title during exit, and produced smooth playback. The prior
candidate requested 640x360 and Miyoo SDL returned 640x400, leaving the bottom
framebuffer area outside the surface. This display-surface fix is physically
confirmed; candidate subtitle/audio acceptance remains separate.

A final short field run with the known-good Spider-Man stream/subtitle pair
confirmed smooth candidate playback, no bottom artifact, and clean full-frame
Menu exit. This confirms the app-local display-surface fix, but not the full
Milestone 20 duration, synchronization, and resource acceptance criteria.

A later no-subtitle candidate run used the same 640x480 surface and logged a
640x264 source with SAR 195:197 rendered as a centered 640x266 rectangle at
`0,106` in that surface. A subsequent display-only one-shot candidate run
played a 640x268, square-pixel 160:67 (about 2.39:1) MPEG-TS stream and the
user confirmed correct proportions. Normal FFplay still visibly stretched that
same correctly encoded stream, isolating the defect to normal-player surface
presentation. The initially reported candidate A/V concern was a quiet,
non-English source track rather than a synchronization failure. This does not
change the production MPEG-TS fallback or complete Milestone 20.

The latest Apps-context duration/resource run used a 720p *Invincible* S1E4
account stream with an English subtitle selected for burn-in. It reached video
readiness in 10 seconds, played for 1,128 valid unpaused seconds, and the user
confirmed smooth, synchronized A/V. The bounded output was 640x360 H.264 with
AAC stereo. FFmpeg used 94,164--111,676 kB RSS and 153 CPU seconds across the
run. The corrected Miyoo FFplay monitor recorded 1,168--17,048 kB RSS, zero
process swap, at least 36,704 kB MemAvailable, and at least 129,212 kB
SwapFree. Menu exit left zero active PCServer conversions and no FFplay, stay-awake,
subtitle, pause, or FFplay-log temporary state. The user later clarified that
the burn-in subtitle selected for this duration run was not the matching release.
That is a subtitle-choice limitation, not a burn-in pipeline failure: earlier
Apps-context evidence already verified a synchronized selected English track.
Together these runs meet the milestone acceptance criteria. The server tests
and device-facing logs continue to preserve opaque URLs and tokens.

Evidence and design: [Bounded Subtitle and Downscaling Pipeline](bounded-transcoding.md)

Acceptance criterion: one account-addon movie displays burned-in English
subtitles, one stuttering 720p episode becomes smooth at a bounded output
profile, audio remains synchronized, resource use is measured, and Menu exit
cleans up every server and device process without exposing upstream tokens.

### 21. Device Settings and Playback Preferences

**Status: Confirmed**

The user-prioritized server-connectivity slice is implemented for split-host
development. The home screen reports connected, offline, or unconfigured
state without preventing access to Settings. Settings can discover PCServer
instances by local UDP broadcast or accept a controller-keyboard HTTP(S)
address manually, validates candidates through `/api/status`, and atomically
updates only `SERVER_BASE` in the authoritative app-local config. Each PCServer
advertises one preferred address and a stable ignored instance identity, so a
machine with both LAN and overlay addresses is not presented as multiple PCServer
instances. Choices are labeled `name - IP:port - network`; the transport label
is explicit PCServer configuration rather than Tailscale inspection. Device-shell
and Apps-context scans displayed both the Mac and Windows PCServer instances as two
distinct name/address/network choices. Controller selection switched from Mac
to Windows, atomically preserved the other live settings, and survived an app
restart. With the configured Mac PCServer intentionally stopped, the menu appeared
immediately with no black screen and dynamically reported `Server: Offline`;
selecting that row opened Settings, which restored the Windows connection.
When the current Wi-Fi prevented direct LAN peer traffic and therefore UDP
discovery, controller keyboard entry of the Mac PCServer tailnet address passed
`/api/status`, atomically saved `SERVER_BASE`, and returned to a connected home
menu. Manual entry is therefore physically confirmed with the existing generic
proxy configuration. A no-config first-run test then confirmed a tailnet gap:
the client starts direct, so it discovered the Mac PCServer but rejected both its
manual address and discovery result during status validation because no proxy
was available. The original device configuration was restored unchanged. A
first-run proxy/onboarding design is required before tailnet first-run can be
accepted. The proposed direct-first, generic-proxy remote route is documented
in [Portable Connection and First-Run Onboarding Plan](portable-connection-onboarding-plan.md);
the companion's endpoint-display phase is implemented, statically tested,
deployed, and physically confirmed; the PocketCinema onboarding work is
implemented, automated/static-tested, deployed, and physically confirmed.
Legacy startup and manual Local-only direct setup/search passed from
OnionOS Apps; the hotspot scan also advertised the direct PCServer and passed
selection validation. Remote-only setup/search through the proxy and the
found-but-unreachable Local validation case also passed, as did Remote proxy
failure/default recovery and Remote-profile restart persistence. It now includes
first-run Local/Remote/Both setup, separate direct discovery/reachability
handling, and direct-first Automatic routing through the existing generic
proxy; its complete Local-unavailable → Remote → Local fallback and its
three-second Both/Automatic information message are physically confirmed. A
separate config-free temporary Apps installation opened the setup controller
before home without altering the preserved live profile, completing Phase 3
first-run confirmation. Playback failure reporting now classifies
bounded,
sanitized FFplay and transport symptoms instead of displaying only `Playback
failed`, and the client retains one bounded previous UI log so a later restart
does not erase the immediately preceding diagnostic evidence. Physical failure
testing confirmed the bounded generic PCServer/provider category for a pre-readiness
`502`. Controlled OnionOS Apps runs now also confirmed the specific,
sanitized `Selected subtitle could not be downloaded` and `PCServer conversion could
not start` messages, each returning cleanly to stream selection. The
device-local Quick Resume entry stores only
the selected PCServer address and opaque stream/subtitle IDs; it skips the prior
menus while that PCServer remains running, then clears the stale selection and
returns to normal selection after a PCServer restart or server change. Its first
physical run resumed a converted movie at 165 seconds, reached video readiness,
and saved progress at 185 seconds.

- Show concise PocketCinema server reachability on the main screen.
- Edit the server host and port from an app-local Settings screen while keeping
  `/mnt/SDCARD/App/PocketCinema/config/pocketcinema.conf` authoritative.
- Discover one preferred address per PCServer on the local network, deduplicate it
  by instance rather than interface, and show name, IP:port, and configured
  network label before selection.
- Keep manual HTTP(S) entry available for routed hosts. Warn that PCServer has no
  public-facing authentication and must not be exposed directly without an
  authenticated gateway.
- Offer Quick Resume for the last valid opaque stream selection on the current
  PCServer, with a normal-selection fallback when its in-memory IDs expire.
- Store ordered audio-language and subtitle-language preferences with an
  explicit fallback choice; never infer language solely from a filename.
- Apply preferences to server-normalized tracks and subtitle results without
  exposing addon transports or media URLs.
- When one or more preferred audio languages are present, hide unrelated
  languages and automatically choose the highest-priority match. If none
  match, do not silently choose an arbitrary language: explain that no
  preferred track is available and offer the bounded other-track picker.
- Apply the same ordered matching to subtitles. Package only matching
  preferred languages when selectable Matroska subtitles are active. If none
  match, offer `Continue with no subtitles`, `Use English subtitles` only when
  English is available and not already preferred, and `Back to streams` instead
  of silently substituting an unrelated language.
- Keep the ordering independent for audio and subtitles. For example, audio
  can prefer Japanese then English while subtitles prefer English then Greek.
  `und` and missing language metadata never count as a preference match.
- Resolve multiple tracks in the same preferred language deterministically
  from normalized default disposition, match quality, and source order. Keep
  the manual picker available as an explicit override rather than making it a
  mandatory step for every playback.
- Add an explicit Remove action for individual Continue Watching entries.
- Keep compatibility modes visible and allow a bounded preference between
  direct, converted, and uninspected candidates.
- Report a concise actionable playback failure category while keeping upstream
  media URLs and provider details out of device messages and logs.

The stream picker now supports local filtering by normalized addon/source name,
so a user can show only Torrentio, AIOStreams, or another configured source
without exposing addon transports or media URLs.  It also offers audio-language
filters only for language tags verified by server-side media preflight; streams
without a verified language tag remain available under the all-audio choice.
This avoids guessing from release filenames while keeping the feature useful
for sources that expose correct FFprobe language metadata. Apps-context testing
selected the local compatibility source from a multi-provider result, showed
only its filtered stream list, and returned with B through the title screen;
the device log confirmed the exact controller path and no stale markers remained.

Audio track metadata is now collected during FFprobe preflight. When a source
has multiple detected audio tracks, the Miyoo picker presents their verified
language/title labels before playback. The selected track is passed to the
bounded converter and preserved for Quick Resume; this is necessary because
converted MPEG-TS/Matroska output cannot reliably use FFplay's L1 cycling.
Direct-play audio cycling remains an FFplay responsibility. Physical testing
with a real multi-audio converted source is now confirmed by the user: the
track picker appeared and the selected audio played correctly. This confirms
audio-track selection for converted playback, but does not complete the wider
Milestone 20 acceptance criteria.

Ordered language preferences are implemented with a controller-friendly
language-name catalog rather than fixed presets or code-first entry. No
language is preselected. Users add up to five named languages in priority order,
can change an existing language's priority with its current position marked by
`*`, can remove entries, and retain custom 2- or 3-letter source-code entry as
an advanced escape hatch. Audio and subtitle orders are stored
separately in the app-local config with explicit fallbacks: ask, first verified
track, or stop for audio; ask or no subtitles for external subtitles. Empty
preferences preserve the existing per-playback pickers. PCServer canonicalizes
common language aliases, keeps the subtitle API English-only for older clients,
and accepts at most five requested languages from updated clients. Automated
coverage confirms canonical audio tags and deterministic requested subtitle
ordering. Apps-context settings saved Japanese, English, and Greek audio order
and English and Greek subtitle order; a later app launch loaded those values,
confirming persistence. A controller playback check then offered three
selectable subtitle tracks with Greek first and English next, physically
confirming deterministic subtitle-priority application. The no-preferred-
language fallback initially regressed: an Azerbaijani-only preference found no
matching tracks and silently started playback without subtitles. The corrected
flow is user-directed: it names the missing preferred language, offers
`Continue with no subtitles`, offers `Use English subtitles` only when English
is actually available and is not already preferred, and offers `Back to
streams`. Choosing English packages its bounded selectable-Matroska tracks for
R1 cycling. The earlier file-level alternate-subtitle picker was deliberately
replaced before acceptance. The revised dialog is automated-tested and deployed
to the Miyoo. An Apps-context local-video run with Greek preferred reached the
named fallback dialog and, after `Use English subtitles`, the selectable-
subtitle playback stream. The device log confirmed three packaged English
tracks and R1 transitions through all tracks to subtitles-off; the run exited
cleanly and saved progress. With English subsequently added to the preference
list, replay correctly bypassed the fallback dialog.

Saved audio order is also applied before stream selection. The client chooses
the highest-priority saved language that exists in the currently playable,
verified stream set, filters providers and releases to that language, and then
selects its matching track ordinal. This prevents an untagged dub from silently
winning while a verified preferred-language source remains available. Stream
details show audio languages by name. If the confirmed selectable-Matroska mode
cannot be prepared, its normal fallback remains burned in and fixed during
playback; the fallback startup panel states that R1 cannot switch that path.
Apps-context testing confirmed the new audio filtering with *My Hero Academia*
S1E1. The selected AIOStreams 1280x720 source exposed eight audio tracks:
Spanish, French, German, Italian, Portuguese, Polish, Hungarian, and Japanese.
The saved Japanese-first preference selected ordinal 7, and the user confirmed
Japanese audio. FFplay exited cleanly after 19 valid watched seconds; PCServer then
reported zero active conversions and bridges, and the Miyoo retained no player,
client helper, infoPanel, or temporary playback state.

A later controller follow-up moved Spanish to priority 1. The next app launch
loaded `spa,jpn,eng,ell`, and the user reported the ensuing playback test as
working. This confirms reordering persistence and the exercised playback path.
The initial retained log did not identify the reported menu inconsistency; the
subsequent controller report below provided the exact reproduction.

That follow-up identified a concrete navigation defect: B at `Stream source`
was treated as `All sources`, so it opened an unintended filtered stream list.
The client now treats that cancellation as the existing title-screen back result.
An Apps-context retest confirmed it returns directly to the title action screen;
the device log records `stream source selection canceled`.

PCServer now retains the already-sanitized response for an item’s stream request in a
bounded server-only cache (32 items, five minutes), so backtracking into the
same title does not depend on a new provider response or a new preflight pass.
The cache is automated-tested and keeps upstream URLs out of the cached device
response. Apps-context navigation debugging reopened the same title repeatedly
through the cache interval; the user reported its one returned source and stream
choice stayed consistent. The device logged repeated resolution of that title,
while PCServer served later identical stream requests without a repeated addon fetch.
The audio-language picker excludes `und`, which is unverified rather than a
verified language; when it has no verified tags to offer, it explains the
condition and proceeds to explicit stream selection. The normal PCServer branch was
physically exercised, but its original one-line notice was too long for the
Miyoo display. All infoPanel message bodies now preserve explicit newlines,
wrap at 32 characters, and show at most four lines with an ellipsis. An
Apps-context PCServer scan response rendered cleanly in two lines, physically
confirming the wrapped-message presentation.

The same run also regression-checked confirmed Milestone 22 after restoring the
client and PCServer Matroska mode flags. PCServer packaged three selectable subtitle
tracks, and the user pressed R1 and visibly reached the `Subtitles 2/3` notice.
This confirms that the reported fixed-subtitle behavior was disabled
configuration, not a loss of the established switching capability.

Continue Watching now binds X to removal of the highlighted row while A keeps
the normal open and resume flow. X opens a controller confirmation before PCServer
deletes only the selected type-and-ID key through a bounded JSON endpoint and
persists the remaining entries. The selector preserves stdout as the selected
row and reports X through an app-local temporary action file. Automated server
coverage confirms targeted, idempotent removal and rejects incomplete
identities. Apps-context testing confirmed X as SDL key 304, the confirmation
screen, removal of three individually highlighted movie and episode rows, and
the refreshed list. The PCServer list fell from 10 entries to 7 with only those IDs
absent. B then returned normally and app exit left no selector, FFplay,
infoPanel, or temporary removal-action state behind.

Acceptance criterion: controller-only settings persist across app restarts, a
Spanish-first source can prefer an available English audio track or clearly
report that none exists, subtitle priorities are deterministic, and a Continue
Watching item can be removed without marking unrelated media complete. When no
preferred language matches, the client must clearly offer the bounded other-audio
track or, for subtitles, explicit no-subtitles, English-if-available, and Back
choices rather than silently substituting an unrelated language. This is
confirmed from OnionOS Apps, including the bounded playback-failure messages.

### 22. Selectable Matroska Subtitles

**Status: Confirmed**

Burn-in remains the confirmed bounded fallback, but it fixes one subtitle choice
for an entire run. Build on the physically proven app-local candidate player to
offer a bounded set of release-matched English text tracks in a converted
Matroska response, so the user can cycle tracks with R1 during playback.

- Keep source URLs, subtitle URLs, account tokens, and FFmpeg inputs entirely
  on the PCServer host through the opaque relay.
- Package no more than three server-normalized text tracks, with explicit track
  labels and deterministic ordering; reject image-only subtitle formats.
- Use the app-local 640x480 SDL candidate only for this mode and retain the
  normal MPEG-TS burn-in path as automatic fallback on setup failure.
- Preserve compatible audio conversion, downscaling, readiness-based progress,
  Menu cleanup, and bounded resource use.
- Do not change OnionOS files or the production MPEG-TS fallback.

The normal-flow checkpoint now skips the redundant burn-in subtitle picker in
Matroska mode. The client displays one continuous preparation status while PCServer
discovers English tracks, and PCServer packages the first three deterministic
matches automatically. A real account-backed playback completed this no-picker
flow successfully on the Miyoo. The app-local candidate now also has a bounded
top-right R1 notice (`Subtitles 1/3` through `3/3`, or `Subtitles off`) that is
removed after one second. Its physical display and expiry are confirmed: the
user reported that it worked as expected, while the device log recorded all
three track transitions, off, and back to the first track during 68 valid
watched seconds. Menu exit returned FFplay status 0, saved progress, left zero
active PCServer conversions, and left no FFplay/client helpers, stay-awake marker,
info-panel marker, or temporary subtitle package on the Miyoo.

This confirms the no-picker, bounded-track, R1-notice, and cleanup checkpoint.

The subsequent working-tree implementation generalizes the packaging bound to
up to three tracks for each of five ordered preferred languages (15 tracks
maximum), preserves per-track language metadata, and passes the existing
Milestone 21 language preferences through Matroska setup. The app-local FFplay,
runtime libraries, font configuration, and font asset are now included by the
normal Miyoo deployment script. Automated server and packaging tests cover the
six-track case; the three-track English Apps-context run above remains the
minimum physical confirmation until a multi-language run is completed.
The client now bounds Matroska setup failure by returning to the existing
normal subtitle selector and retrying with Matroska and field-test modes off;
the app-local 640x480 presentation remains active so the fallback does not
reintroduce Onion FFplay's physically reproduced aspect-ratio defect, and the
production MPEG-TS burn-in implementation itself is unchanged. Discovery,
mode-negotiation, and subtitle-package failures take this fallback, while a
missing candidate or genuine no-supported-English result displays a useful
error. Canceling the fallback returns normally without hiding an otherwise
valid stream. A forced missing-candidate run confirmed the selector, burn-in,
61 valid watched seconds, progress saving, and cleanup, but also reproduced the
Onion player aspect defect; it is diagnostic evidence, not fallback acceptance.
The corrected fallback was then physically exercised from Apps by connecting to
a PCServer with Matroska mode disabled. The normal picker selected the deterministic
test subtitle, whose only cue runs from 0.5 to 4.5 seconds, and the unchanged
production converter emitted 640x268 H.264/AAC MPEG-TS. The app-local player
logged a centered `640x268` rectangle at `0,106` on its 640x480 surface, and the
user reported that the result did not look stretched and that the subtitle
appeared near the beginning. Two runs recorded 26 and 5 valid watched seconds,
returned status 0, saved progress, and left no playback helper or active
conversion. The final real-account Apps-context run packaged three English
SubRip tracks with H.264/AAC in a 640x268 Matroska response. The user explicitly
confirmed that video, audio, and subtitles remained smooth and synchronized.
FFplay recorded 110 valid watched seconds, returned status 0, and advanced
progress from 766 to 876 seconds. Across 2,414 playback samples its mean
absolute A/V delta was 0.015 seconds. Miyoo FFplay used 3,784--20,304 kB RSS
with zero process swap and at least 45,940 kB MemAvailable; Mac FFmpeg used
23,056--122,912 kB RSS with a measured peak of 40.8 percent CPU. Menu exit left
no PCServer conversion or bridge, FFplay/client helper, stay-awake or info-panel
marker, or temporary subtitle package. Together with the earlier logged R1
transitions through all three tracks, off, and back to the first track, this
satisfies the acceptance criterion.

The Mac PCServer's default FFmpeg build does not include libass, so it cannot support
the normal MPEG-TS subtitle burn-in path. Selectable Matroska tracks do not need
that filter: the Miyoo now explicitly requests that mode during subtitle
discovery, and PCServer accepts the request only while its Matroska mode is enabled.
This retains the libass gate for ordinary subtitle selection. An Apps-context
run discovered and packaged six tracks, downloaded the opaque package, switched
from streams 2 to 3, 3 to 4, and 4 to 5 through R1, and saved progress at 200
seconds. This is physical confirmation of the no-libass Matroska packaging path,
not a claim that burn-in is available on that host.

The later M23 production-promotion correction makes this accepted mode the
normal Miyoo and direct-PCServer default. An explicit Miyoo configuration value
of `POCKETCINEMA_MATROSKA_SUBTITLES=0` and the PCServer
`--disable-matroska-subtitles` option retain the bounded burn-in opt-out path.
This configuration correction inherits the M22 acceptance evidence and does
not resolve the separately reported renderer/display symptom where tracks
switch but captions are not visible.

That display regression was traced to the identity migration boundary, not
subtitle discovery: a retained pre-rename FFplay binary reads
`POCKETSTREMIO_*` subtitle/font bindings while the renamed client supplied only
`POCKETCINEMA_*`, and retained `fonts.conf` named the old app directory. The
normal runtime repair supplies both compiled identities with the same selected
subtitle package/font settings and rewrites migrated fontconfig paths. It does
not alter providers, Matroska mode, conversion, stream selection, or the
renderer algorithm. The normal deployment script now explicitly targets the
documented Miyoo `root` account, and successfully installed the repair while
preserving live configuration and networking-provider state. One focused normal
Apps playback—visible captions plus one R1 transition and clean exit—remains
required before marking the regression restored.

The repaired normal path is now physically reported to render selectable
captions again, but their default size is too small on the 640×480 Miyoo
display. This is a renderer readability follow-up, not a discovery or Matroska
mode regression: the deployed app-local binary hard-codes its selected-track
filter as `filename=…:si=…` and exposes no runtime font-size/`force_style`
setting. A bounded production scale therefore requires rebuilding the app-local
ARM FFplay with that filter style, then one focused larger-caption/R1 visual
check. Do not use fontconfig, a marker, provider work, or conversion changes as
a substitute.

The reproducible app-local patch now adds FFmpeg 2.4's
`original_size=426x240` subtitle-filter reference, producing a bounded 1.5x
scale for the known 640x360 envelope. The ARM candidate rebuild succeeds on the
Windows checkout under Git Bash and remains un-deployed and physically pending
until the Miyoo can be reached.

Acceptance criterion: a real account-backed stream opens with multiple English
Matroska tracks, R1 visibly cycles through them and off, audio/video remains
smooth and synchronized, and a Menu exit cleans up the PCServer and Miyoo state.

### 23. PocketCinema Server Desktop Distribution

**Status: Next**

Replace the developer-oriented PocketCinema server launch experience with a
small cross-platform desktop control application while preserving the existing
Python server as the core implementation. The first implementation target is a
macOS development shell; Windows remains the required first end-user release
target. Milestone 23 implementation must not
begin until Milestone 21 is marked **Confirmed** and its device-facing
acceptance criteria are supported by the required evidence. Code presence alone
does not satisfy that gate.

- Persist non-secret desktop settings in the platform-appropriate per-user
  application-data directory, separately from account credentials, private
  addon configuration, logs, and runtime data.
- Expose PCServer name, validated listen interface/address and port, a distinct
  device-facing address, and a non-secret Stremio Service endpoint. The endpoint
  must have a sensible local default (`http://127.0.0.1:11470`), an editable
  host/address and port (or equivalent URL), manual override, persistence,
  validation, reachability status, and actionable errors; it may name the same
  PC or another reachable host, but remains PCServer-only. Also expose
  FFmpeg/FFprobe detection with manual path selection.
- Provide Stopped, Starting, Running, and Error states plus Start, Stop, Restart,
  and Copy Miyoo Address controls.
- Extract configuration, interface selection, validation, capability detection,
  and owned-child lifecycle into reusable Python modules instead of coupling
  them to PowerShell or GUI event handlers.
- Keep the server independently runnable from source and preserve
  `manage-server.ps1` and `manage-server.sh` as developer/admin tools.
- Produce a one-directory Windows application bundle first. Do not redistribute
  FFmpeg/FFprobe or other external binaries until exact provenance, licensing,
  notices, and update responsibilities are approved.
- Prepare the same architecture for a later macOS `.app`, with Apple Silicon,
  Intel/universal-build feasibility, signing, hardened-runtime, and notarization
  requirements documented and tested before release claims.
- Preserve direct play, conversion/downscaling, subtitle modes, multi-audio,
  account linking, progress, Continue Watching, Resume, Menu cleanup, opaque
  upstream URLs, PCServer-only Stremio Service access (with the secure local
  default), and Tailscale independence.

Design and release plan: [PocketCinema Server Desktop Distribution Plan](desktop-distribution-plan.md)

Acceptance criterion: a clean supported Windows PC can install or extract the
actual PocketCinema Server release artifact, configure and persist the PCServer
name, listen interface/address, port, advertised Miyoo address, and Stremio
Service endpoint (including a manual host/address-and-port override) through the
desktop application, detect or manually select FFmpeg and
FFprobe, start and stop only its owned server, and connect a real Miyoo Mini Plus
without Python, PowerShell, a repository checkout, or manual environment
variables. The packaged-artifact run must pass the documented playback,
restart, failure, cleanup, licensing, and privacy checks before this milestone
can be marked **Confirmed**.

### 24. Offline Downloads

**Status: Planned**

Treat downloading as a separate storage lifecycle rather than another Play
action bolted onto FFplay:

- download only a server-authorized opaque stream or bounded converted output;
- check free SD-card space before starting and keep partial files app-local;
- expose progress, cancellation, retry/resume where the source supports Range,
  playback, and deletion;
- preserve tokens and addon URLs on the gaming PC;
- never make PocketCinema responsible for torrent or P2P ingestion.

Acceptance criterion: one compatible legal test video can be downloaded,
played offline after networking is disabled, and deleted from the app without
leaving a partial file or modifying OnionOS directories.

### 25. Unified PocketCinema UI

**Status: Deferred**

Gradually replace the mixed helper-driven presentation with a lightweight,
app-local SDL 1.2 interface based on the 640x480 Affinity SVG concept. The
reusable layout places the current navigation or list on the left and contextual
details, status, help, or actions on the right. Keep the BusyBox shell as the
initial API, state, and playback orchestrator; use one-shot UI processes that
fully exit before FFplay rather than adding a resident framework.

- Reproduce the concept's header, equal panes, strong dividers, focus treatment,
  and bottom PCServer-status area with fixed logical coordinates and simple drawing
  primitives.
- Add the native home behind an opt-in fallback, then migrate bounded lists,
  the QWERTY keyboard, dialogs/loading states, and the existing secure QR flow
  one screen at a time.
- Keep `pocketcinema-selector`, `kbinput`, and `infoPanel` available until each
  replacement passes Apps-context controller, memory, failure, and cleanup
  tests.
- Surface only implemented behavior and server-normalized public data. Do not
  add History, posters, new settings semantics, or playback/network scope as UI
  work.
- Preserve the authoritative app-local config, opaque PCServer IDs and URLs, the
  release playback path, and all current physical control behavior.

Design and migration plan: [Unified PocketCinema UI Plan](ui-redesign-plan.md)

Acceptance criterion: the unified UI renders correctly and readably at 640x480,
all migrated screens preserve controller/back behavior and current features,
status work never blocks the home screen, the UI releases its resources before
playback, direct and converted playback regressions remain unchanged, and a
forced UI failure returns to the physically confirmed legacy path without stale
processes or files.

## Deferred Features

These features should begin only after real stream playback and compatibility
behavior are stable:

- audio-track selection;
- arbitrary seeking within a live converted response until session-restart or
  seekable-output behavior is designed and measured;
- Stremio library and watch-history sync;
- posters, image caching, and richer media details;
- favorites and watch history (the unified UI refresh is Milestone 25);
- torrent ingestion and addon results that do not provide direct HTTP media.

Each deferred feature should become a separate milestone with its own device
acceptance criteria rather than expanding an earlier milestone.

## Known Risks

- Active playback leaves only about 1.9-3.1 MB reported free RAM, so new Miyoo
  runtimes or image-heavy UI work carry significant memory risk.
- Stremio Local Files depends on Windows Search and filename-to-IMDb matching;
  unmatched or newly added files may not appear until a normal service restart.
- Direct streams may use codecs, headers, redirects, or seek behavior that the
  current FFplay proxy path does not support.
- A 720p *Invincible* episode was physically watchable but dropped many frames
  initially and continued to stutter. Treat 720p as requiring downscaling unless
  later measurements establish a narrower direct-play exception.
- The HLS bridge currently supports only unencrypted MPEG-TS renditions. It
  rejects encrypted and fragmented-MP4 playlists and remains physically measured
  only for a 29-second ERT News session.
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
