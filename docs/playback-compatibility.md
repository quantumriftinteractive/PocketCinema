# Playback Compatibility and Reliability

Goal: reject clearly unsupported media before FFplay, distinguish physically
confirmed profiles from unmeasured candidates, and make playback sessions
bounded and diagnosable.

## Status

**In progress. Server implementation, remote-network path, and confirmed-profile
Apps-context regression pass; broader format testing remains.**

This work preserves the existing direct relay. It does not add remuxing,
transcoding, or another player.

## Target Player

The OnionOS player reports FFplay/FFmpeg `2.4.14`. Its build advertises these
relevant demuxers and decoders:

```text
containers: MP4/MOV, AVI, Matroska/WebM, MPEG-TS, Ogg
video:      H.264, HEVC, MPEG-4 Part 2, VP8, VP9
audio:      AAC, AC-3, MP3, Vorbis
```

Advertised decoder support is not treated as proof that a format is usable at
the Miyoo's resolution, bitrate, frame rate, and memory constraints.

## Compatibility States

- `confirmed`: physically tested inside the OnionOS Apps context.
- `candidate`: the target build advertises the required demuxer and decoders,
  but this profile has not been physically measured.
- `unsupported`: a required container, video codec, or audio codec is absent
  from the target build's declared support.

The current confirmed envelope is deliberately conservative:

```text
container: MP4/MOV
video: H.264, at most 640x360 and 30 fps
audio: AAC, at most stereo
total bitrate: at most 1.6 Mb/s
```

This envelope is based on the physically confirmed Big Buck Bunny 640x360
fixture and *Night of the Living Dead* 320x240 stream. Formats outside it can be
offered as candidates, but are not labeled safe.

## Server Preflight

`POST /api/play` runs the gaming PC's `ffprobe` before creating a play session.
The server inspects only normalized format information:

- container;
- video and audio codecs;
- video profile, dimensions, and frame rate;
- audio channels and sample rate;
- duration and total bitrate.

Probe results are cached for seven days by a SHA-256 hash of the upstream URL.
The normalized cache persists in the ignored `server/data/probe_cache.json`
file, stores no upstream URL, and is bounded to 256 entries. The first
remote-film preflight took 3.48
seconds under normal source conditions, while a later Internet Archive slowdown
took 33.3 seconds. The server therefore allows 45 seconds for an initial probe
and the Miyoo keeps the loading panel visible for up to 60 seconds. Subsequent
requests and server restarts use the cache.

An unsupported profile returns HTTP `409` with a concise message before FFplay
starts. Probe timeout or source inspection failure returns HTTP `502`. The
Miyoo client now displays the server's message instead of a generic missing-URL
error.

Stream choices use compact prefixes:

```text
[OK]   declared confirmed profile
[TEST] candidate profile requiring measurement
```

The final ffprobe result is logged by status and summary when playback is
created. Private source URLs are not logged.

The Miyoo displays an OnionOS-native persistent loading panel while resolving
streams and while waiting for ffprobe/session creation. PocketStremio tracks the
panel process it starts and dismisses it through OnionOS's standard
`/tmp/dismiss_info_panel` flag before showing an error, returning to a selector,
launching FFplay, or exiting.

After session creation the panel changes to `Starting video...` before FFplay
takes over the framebuffer. This prevents a slow upstream connection from
leaving a stale compatibility message on screen. Remote media reads have a
separate 30-second timeout because the confirmed Internet Archive edge has been
observed taking 14-23 seconds to establish a byte-range response.

The client validates each FFplay run from its isolated run log. Progress is
saved only when FFplay opened the input and video output without HTTP, partial
file, or input/output errors. Startup time is measured separately, and watched
time starts only when FFplay logs `SDL_SetVideoMode`. This prevents network and
decoder startup, as well as FFplay's misleading zero exit code on input failure,
from advancing Continue Watching.

FFplay exposes no machine-readable playback clock or pause state in this OnionOS
build. Its documented A button maps to `KEY_SPACE`, so a small app-local ARM
helper observes that evdev event without grabbing input and subtracts complete
pause intervals. The client suppresses progress updates if the helper does not
return a valid duration.

## Session Reliability

Play sessions now use random opaque IDs and are bounded to:

```text
TTL: 6 hours
maximum active sessions: 128
```

Expired sessions return HTTP `410`. When the maximum is reached, the oldest
session is removed. Expired entries are cleaned during create, lookup, and
status requests. Play sessions remain in memory and reset on server restart;
normalized probe results persist for seven days in the ignored cache file.

## Confirmed Checks

Desktop checks on August 13, 2026:

```text
Night of the Living Dead preflight:
  status: confirmed
  container: mov/mp4
  video: H.264 Constrained Baseline, 320x240, 29.97 fps
  audio: AAC stereo, 48 kHz
  bitrate: 464,439 b/s
  duration: 5,752 seconds
  preflight time: 3.48 seconds

opaque play response: no archive.org URL
Range bytes=1048576-1114111:
  206 Partial Content
  video/mp4
  65,536 bytes returned
```

A later work-network regression exposed a source-latency failure:

```text
compatibility cache lookup: less than 1 second
old media relay timeout: 15 seconds
observed Internet Archive range startup: 14-23 seconds
FFplay result: HTTP 502/partial-file errors but rc=0
incorrect saved position: advanced from 114 to 322 seconds
```

The relay timeout is now 30 seconds, FFplay runs with isolated validation logs,
and invalid input runs no longer update progress. The incorrect position was
restored to the last physically confirmed 114 seconds. After deployment, a
Miyoo-originated 1 KiB range request completed through the Tailscale HTTP proxy
with HTTP `206` in 3.71 seconds.

The first physical regression of that validation still exposed incorrect
progress accounting. Two 5-10 second playback checks had FFplay process
lifetimes of 86 and 56 seconds because startup was included, advancing progress
from 114 to 256 seconds. Progress accounting now begins at SDL video readiness,
not process launch.

A subsequent physical pause regression confirmed the app-local observer:

```text
resume position: 117 seconds
media startup before SDL video readiness: 10 seconds
time after video readiness: 231 seconds
A-button pause time: 228 seconds
counted watched time: 3 seconds
saved position: 120 seconds
```

The user confirmed video pause/resume behavior during the run. Pause tracking
returned valid, Menu exited FFplay normally, and no FFplay, pause observer,
loading panel, or temporary marker remained. A separate device measurement
reported the 5.6 KiB helper at 164 KiB RSS and 1,588 KiB virtual size.

Physically confirmed from a work network over Tailscale on August 13, 2026:

```text
Continue Watching -> Night of the Living Dead at 60 seconds
stream choice -> [OK] Open Media - Internet Archive
preflight -> confirmed H.264/AAC profile
FFplay -> resumed video and audio playback
Menu button -> FFplay rc=0 after 54 seconds
progress -> saved at 114 / 5752 seconds
PocketStremio home -> restored, then exited normally
```

No FFplay, selector, or client process remained, and playback temporary files
were absent. This also confirms the full client path works when the Miyoo and
gaming PC are on different physical networks.

Confirmed playback controls:

```text
PocketStremio selector B: back
FFplay B: frame step
FFplay Menu button: exit playback
```

Automated tests cover:

- confirmed H.264/AAC MP4 classification;
- unsupported AV1 rejection before session creation;
- candidate VP9/Vorbis WebM classification;
- probe-result caching;
- normalized compatibility in `/api/play`;
- session TTL and oldest-session eviction;
- existing search, stream, relay, subtitle, and progress contracts.

## Remaining Milestone Work

- Physically regress the Big Buck Bunny fixture with preflight enabled; the
  open-media confirmed stream has passed.
- Test representative candidate formats at conservative resolutions and
  bitrates.
- Record startup time, buffering, smoothness, RSS, free memory, and swap.
- Define practical rejection limits from measurements rather than decoder lists.
- Decide whether any common candidate needs remuxing or transcoding.

The milestone remains **Next** until supported profiles play predictably and a
representative unsupported profile returns a useful device-visible failure.
