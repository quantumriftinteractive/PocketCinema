# Bounded Subtitle and Downscaling Pipeline

## Status

Proposed for the next development session. No transcoding path is implemented
or deployed yet.

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

## Proposed Architecture

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

An initial output target should be H.264 8-bit at no more than 640x360 and
30 fps, AAC stereo, and a bitrate measured against the successful fixtures.
Exact profile, level, bitrate, and preset must be validated on the Miyoo rather
than assumed.

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
