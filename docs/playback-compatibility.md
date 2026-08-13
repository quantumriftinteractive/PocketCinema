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

Probe results are cached by opaque stream ID. The first remote-film preflight
took 3.48 seconds; subsequent requests use the cache. The raw upstream URL
remains server-side and is never returned in compatibility data.

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

## Session Reliability

Play sessions now use random opaque IDs and are bounded to:

```text
TTL: 6 hours
maximum active sessions: 128
```

Expired sessions return HTTP `410`. When the maximum is reached, the oldest
session is removed. Expired entries are cleaned during create, lookup, and
status requests. Session and probe caches remain in memory and reset on server
restart.

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
