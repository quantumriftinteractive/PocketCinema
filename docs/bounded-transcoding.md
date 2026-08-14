# Bounded Subtitle and Downscaling Pipeline

## Status

Implemented on the gaming PC and deployed to the Miyoo client. Automated and
desktop-side account-stream checks pass. Apps-context playback confirmation is
still pending.

## Device Evidence

The OnionOS FFplay build does not include the `subtitles` video filter, so it
cannot render the already-discoverable external subtitle files directly.

Playback limits are also source dependent:

- H.264 Main 640x272 with AAC played correctly for *Alien*;
- H.264 High 852x480 with AAC played correctly for *Grimm* S1E1;
- a 720p *Invincible* episode dropped many frames during startup and continued
  to stutter enough to be exhausting, although it remained watchable;
- Action24 H.264 High 10 at 1920x1080 lost video continuity and later ran in
  slow motion while AAC audio continued.

Advertised quality is therefore only a sorting hint. FFprobe results and a
measured device envelope must decide whether direct playback is allowed.

## Implemented Architecture

The gaming PC should own one bounded FFmpeg pipeline. The Miyoo continues to
receive only an opaque PocketStremio play URL.

1. Resolve the selected account stream and English subtitle server-side.
2. Give FFmpeg an opaque loopback PocketStremio input URL, never the upstream
   media URL or addon token in its command-line arguments.
3. Burn the English subtitle into video with the gaming-PC FFmpeg subtitle
   filter.
4. Downscale only when the source exceeds the direct-play envelope, preserving
   aspect ratio inside 640x360.
5. Encode bounded H.264/AAC and emit continuous MPEG-TS to the existing opaque
   playback response.
6. Terminate FFmpeg promptly on Menu/client disconnect, timeout, server stop, or
   upstream failure.

The initial output is MPEG-TS containing H.264 Main level 3.0, 8-bit YUV420p at
640x360 and 30 fps, plus AAC-LC stereo at 44.1 kHz. Video uses the `veryfast`
preset, `zerolatency` tune, a 700 Kb/s target, 900 Kb/s maximum, and a 1.4 Mb
buffer. Aspect ratio is preserved and unused pixels are padded black.

Conversion is selected when an English subtitle is chosen, or automatically
when ffprobe reports video above 640x360, above 30 fps, or a 10-bit profile.
Compatible media still uses the existing byte-range direct-play path when no
subtitle is selected.

The public API accepts only the selected opaque stream and subtitle IDs.
`/api/play` creates an inner opaque source session and gives only that
PocketStremio URL to FFmpeg. It then returns a separate opaque MPEG-TS play
session to the Miyoo. Resume offsets are applied by FFmpeg so the Miyoo does not
seek the converted response a second time.

The Miyoo now requests English subtitle choices from PocketStremio and shows a
controller-driven `No subtitles` plus English-results selector. Subtitle files
are downloaded only by the gaming PC and burned into the picture; no subtitle
URL or file is sent to the device.

## Safety and Resource Bounds

- English is the only subtitle language in the first slice.
- Allow at most one transcode job initially.
- Keep subtitle and process files under ignored gaming-PC server data paths.
- Never log account transports, media URLs, subtitle URLs, or tokens.
- Bound startup, input probing, total process lifetime, stderr size, and cleanup
  waits.
- Do not expose a general-purpose URL or FFmpeg argument endpoint.
- Preserve direct playback for already-compatible media.
- Treat resume seeking, progress, pause accounting, and Menu cleanup as required
  regressions.

The implementation enforces one nonblocking conversion job. A second request
receives a bounded `transcode_busy` response. FFmpeg is terminated on client
disconnect, temporary subtitles are deleted in `finally`, stderr retention is
bounded to 32 KiB, and URL-bearing FFmpeg diagnostics are omitted from logs.

## Confirmed Desktop Results

The server test suite contains 47 passing tests. Dedicated conversion tests
confirm opaque FFmpeg input, seek forwarding, MPEG-TS output, single-job state,
and temporary-file cleanup. Account subtitle tests confirm normalized source
discovery without public addon transports or subtitle URLs.

A live smoke test used the linked account's Torrentio RD 480p *Grimm* S1E1
result and its first English subtitle. The input preflight measured H.264 High
at 852x480 with AAC. PocketStremio returned only an opaque converted play URL;
the captured output measured:

```text
container: MPEG-TS
video:     H.264 Main, 640x360, 30 fps
audio:     AAC-LC stereo, 44.1 kHz
sample:    2,097,716 bytes
```

Closing the smoke-test client returned the active conversion count to zero and
left zero temporary subtitle files. The account subtitle response contained 20
English choices and no HTTP URL.

## Pending Device Confirmation

- visible burned-in English text;
- smooth playback of the previously stuttering 720p *Invincible* episode;
- audible synchronized audio and Menu-button cleanup;
- gaming-PC and Miyoo resource measurements during converted playback.

## Acceptance Criteria

- One account-addon movie plays with burned-in English subtitles.
- One otherwise-stuttering 720p account-addon episode plays smoothly after
  downscaling.
- Audio remains synchronized and audible.
- Startup time, gaming-PC CPU/RAM, Miyoo RAM/swap, and playback smoothness are
  measured.
- Menu exit leaves no FFmpeg, FFplay, selector, relay, or temporary subtitle
  process/file behind.
- Upstream URLs and tokens remain absent from APIs, logs, process arguments, and
  git.
