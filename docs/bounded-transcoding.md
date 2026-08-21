# Bounded Subtitle and Downscaling Pipeline

## Status

Implemented on the gaming PC and deployed to the Miyoo client. Automated and
desktop-side account-stream checks pass. Apps-context subtitle rendering,
resume clock correction, pause accounting, and one synchronized episode track
are physically confirmed. Multi-track switching and the remaining milestone
acceptance tests are still pending.

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

The stream selector uses retained ffprobe evidence without inspecting every
candidate up front. Known-compatible entries display `DIRECT`, entries which
require bounded downscaling display `CONVERT`, and uninspected candidates
display `CHECK`. A cached unsupported result is no longer selectable.

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

## Subtitle Clock Correction

Physical use proved that the initial subtitle build did not remain synchronized
with resumed playback. A deterministic desktop reproduction established the
cause: input `-ss` reset video filter timestamps to zero, so a playback resumed
at 10 seconds rendered the subtitle cue for 0 seconds instead of the cue for 10
seconds.

The corrected filter temporarily offsets video PTS by the server-applied resume
position before subtitle rendering, then resets output PTS for FFplay. FFmpeg
also reads the source at media rate with `-re`. This prevents file conversion
from racing far ahead of a paused device and accumulating avoidable converted
data in player and socket buffers.

The continuous MPEG-TS response is not seekable. FFplay D-pad seeks therefore
cannot be treated as synchronized or included in progress accounting on a
converted session. Correct arbitrary seek support requires the client to stop
the current conversion and create a new play session at a known timestamp; it
must not be approximated by changing subtitle offsets independently.

A subsequent Apps-context regression resumed *Invincible* S1E4 at 32 seconds,
selected the known 720p Torrentio result, rendered English subtitles, measured
a 31-second A-button pause, and exited cleanly with Menu. The selected subtitle
was visibly still out of sync. Inspection showed that the stream was a 720p WEB
x264 season-pack encode while the previous first subtitle was an untrusted
`ION10` WEBRip result. The stream supplied a filename but no OpenSubtitles video
hash or size, so a guaranteed hash match was unavailable.

PocketStremio now sends the standard server-side filename hint to account
subtitle addons, ranks results by an available hash, release-token and
resolution similarity, and trusted-source indication, and removes duplicate
display names. For this episode, the list changed from 20 ambiguous rows with
`ION10` first to six distinct rows with the trusted 720p AMZN WEB-DL/NTb result
first. The first ranked result was still noticeably mismatched. The second
manual choice, `invincible.2021.s01e04.1080p.web.h264-ggwp`, was physically
confirmed synchronized. Ranking substantially reduces the search space, but it
cannot guarantee a match when the media result supplies no hash or size.

The same run exposed a shell-variable collision in converted resume progress:
FFplay correctly received a zero seek because FFmpeg had already applied the
32-second offset, but that zero replaced the saved offset before progress was
calculated. The player seek variable is now separate; a resumed 32-second item
with 80 valid playback seconds will save 112 seconds rather than 80.

Two subsequent Apps-context runs confirmed the correction. Fourteen valid
seconds advanced progress from 80 to 94 seconds, and the synchronized GGWP run
advanced it from 94 to 130 seconds after 36 valid seconds. Both runs exited
cleanly with Menu.

## In-Player Subtitle Switching Feasibility

Burned-in subtitles cannot be changed by FFplay because the text is already
part of each video frame. A measured candidate for instant switching is to
multiplex several text subtitle tracks into the converted Matroska response.
The deployed OnionOS FFplay advertises SubRip, ASS/SSA, WebVTT, and DVB subtitle
decoders and documents `t` as its subtitle-channel cycle key. The gaming-PC
FFmpeg advertises the Matroska muxer and compatible text subtitle encoders.

This is capability evidence, not a replacement for the production path. The
deterministic `subtitle-switch-fixture.mkv` is available through the existing
optional compatibility-fixture path when generated locally. It carries two
visibly distinct English SubRip tracks. The working single-subtitle MPEG-TS
burn-in path remains the production fallback.

The first Apps-context Matroska test detected both embedded SubRip tracks, but
the original Onion build rendered neither. An app-local FFplay 2.4.14 rebuild
enabled the `subtitles` and `ass` filters with an app-local fontconfig file and
font. The track-aware candidate was then physically confirmed: subtitles were
upright and bottom-positioned, and R1 changed the visible fixture from red
Track One to blue Track Two and then to no subtitle. R2 did not trigger this
candidate on the device, despite earlier control evidence for the original
Onion build. This proves the isolated rendering and switching experiment, not
production integration; the burn-in fallback and production client remain
unchanged.

An opt-in account field test then packaged the selected external SRT as a
small Matroska subtitle file because the candidate device build exposes the
Matroska demuxer but not the standalone SubRip demuxer. The subtitle rendered
on the Miyoo, confirming the wrapper path. The candidate audio failure was
fixed app-locally by keeping the candidate libraries first while explicitly
preloading Onion's SDL library; a subsequent device run restored audio and
kept video close to fluid. The server now rewrites SRT/WebVTT cue timestamps
before packaging, so a nonzero resume offset is applied to the subtitle
timeline itself. The Spider-Man field run is not timing evidence: its selected
subtitle could not be proven to match the stream release, although the
subtitle rendered and moved relative to the earlier run. A deterministic
fixture test is still required before declaring synchronization confirmed.

The deterministic Apps-context follow-up used a subtitle-only Matroska package
whose cues were 0--4 and 6--10 seconds after applying an 8-second resume
shift. The candidate successfully initialized libass, loaded the bundled
DejaVuSans font, opened audio, reached video readiness, rendered subtitles,
and exited cleanly. FFprobe verified the package cue timestamps. This confirms
the shifted Matroska rendering path; exact first-frame visual timing is not
machine-observable in the FFplay log, and account subtitle/release matching
remains unresolved.

The candidate can report a nonzero FFplay exit after Menu disconnects the
converted stream even though input and video reached readiness. The explicit
field-test client path now treats that post-readiness disconnect as an
experimental cleanup result; startup failures remain rejected. The wrapper
remains experimental and disabled after the test; the normal MPEG-TS burn-in
path remains unchanged.

## Confirmed Desktop Results

The server test suite contains 48 passing tests. Dedicated conversion tests
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

An Apps-context run later established a known-good release match for
*Spider-Man: No Way Home*: the selected stream was `Torrentio RD - 720P
BluRay x265 HEVC PSA`, and the synchronized subtitle was
`Spider-Man.No.Way.Home.2021.1080p.BluRay.x265-YAWNTiC_eng`. This pair is now
the controlled account comparison for the experimental Matroska wrapper.

That controlled wrapper run then used the same stream and subtitle through the
app-local candidate FFplay. The device log confirmed Matroska subtitle handoff,
video readiness, audio, subtitle rendering, and clean Menu exit with
`valid=1`; 63 watched seconds were saved. D-pad seeking made playback freeze,
as expected for the nonseekable converted response. The candidate also did not
respond to the normal aspect-ratio control, so those controls remain outside
the wrapper acceptance scope.

The first full Apps-context converted run sampled 30 intervals and measured:

```text
gaming-PC FFmpeg RSS:  14,044-101,624 kB
Miyoo FFplay RSS:       6,824-26,948 kB
Miyoo FFplay swap:      0 kB
tailscaled RSS:        29,836-37,572 kB
tailscaled swap:       up to 556 kB
minimum MemFree:        2,016 kB
minimum MemAvailable:  37,876 kB
minimum SwapFree:     129,096 kB
```

The device reached video readiness in 10 seconds, measured 31 paused seconds
and 80 valid unpaused seconds, and left no FFplay process after Menu exit.

## Pending Device Confirmation

- an account-addon movie has a synchronized English subtitle match;
- a deterministic Matroska response can carry switchable subtitle tracks on
  the deployed FFplay build;
- smooth playback of the previously stuttering 720p *Invincible* episode;
- audible synchronized audio and Menu-button cleanup;
- controller mapping for FFplay's subtitle-channel cycle command.

## Protocol References

- [Stremio subtitle request parameters](https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/api/requests/defineSubtitlesHandler.md)
- [Stremio stream behavior hints](https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/api/responses/stream.md)
- [FFplay options and interactive commands](https://ffmpeg.org/ffplay.html)

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
