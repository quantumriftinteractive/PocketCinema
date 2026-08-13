# Real Series Stream Validation

Milestone 12 validates a real Cinemeta series and episode against a legal direct
HTTP media source, using the same opaque stream and playback pipeline as movies.

## Source

The confirmed path is:

```text
The Beverly Hillbillies (1962)  tt0055662
  -> Season 1
  -> The Clampetts Strike Oil   tt0055662:1:1
  -> Open Media - Internet Archive
```

[Cinemeta series metadata](https://v3-cinemeta.strem.io/meta/series/tt0055662.json)
provides the real season and episode records. The matching
[Internet Archive item](https://archive.org/details/Beverly_Hillbillies_Ep01_The_Clampetts_Strike_Oil)
marks the episode public domain and exposes a 512 Kb/s MP4 derivative. The
localhost-only PocketStremio open-media addon maps only this exact episode ID to
that exact derivative.

The upstream URL remains server-side. `/api/streams` returns an opaque stream ID
and `/api/play` returns an expiring PocketStremio session URL.

## Measured Media

Gaming-PC ffprobe measured:

```text
container:       MP4
duration:        1492.33 seconds
overall bitrate: 580795 b/s
video:           H.264 Constrained Baseline, 320x240, 23.98 fps
audio:           AAC-LC, 48000 Hz, stereo
```

The source followed an HTTP redirect and honored byte ranges. Both the direct
upstream check and PocketStremio `/play/{session}` returned `206` with bytes
`0-4095` and total size `108342026`.

## API Validation

An alternate local server and the production 0.9 server confirmed:

- nine real seasons and the first season's 36 episode records were normalized;
- `tt0055662:1:1` resolved to one playable open-media stream;
- the public stream response contained no upstream URL or source field;
- ffprobe classified the stream `confirmed` as H.264/AAC 320x240;
- `/api/play` created an opaque session with duration 1492 seconds;
- a 4096-byte Range request traversed the PocketStremio media relay.

The Miyoo headless client independently searched the real title, parsed the
same nine seasons and season-one episodes through its configured proxy, and
completed a production play-session and Range request.

## Episode Metadata Fix

The first physical attempt reached season and episode selection but displayed
`Details unavailable`. Logs showed
`/api/meta/series/tt0055662:1:1 -> 502`.

Cinemeta stores episode records inside parent series metadata. The server now
parses Stremio episode video IDs, loads the parent series, finds the exact video
record, and normalizes standalone episode details. This is generic behavior,
not a title-specific exception. A regression test covers title, parent series,
season, episode, release year, and description.

## Apps-Context Playback

The retry was physically confirmed on August 13, 2026:

```text
Apps -> PocketStremio -> Search
  -> The Beverly Hillbillies (1962)
  -> Season 1
  -> The Clampetts Strike Oil
  -> Play
  -> Open Media - Internet Archive
  -> FFplay
```

The user reported that the stream worked fine. Device logs confirmed:

- server version `0.9-real-series-poc` was ready on the first health attempt;
- all result, season, episode, action, and stream choices were manual;
- compatibility preflight returned the confirmed Miyoo profile;
- startup from FFplay launch to `SDL_SetVideoMode` took 32 seconds;
- `/dev/dsp` opened and SDL audio initialized at 48 kHz stereo;
- FFplay detected the measured H.264 and AAC tracks;
- 44 seconds of valid unpaused playback were recorded;
- Menu exit returned FFplay `rc=0`;
- progress saved at 44 of 1492 seconds with `completed=false`;
- the app exited normally to OnionOS `MainUI`;
- no stale UI, selector, FFplay, infoPanel, or temporary playback files remained.

The local two-season generated fixture remains the deterministic offline
regression path. This real stream remains a deliberately narrow legal source,
not a general series resolver.

## Verification

The server suite now contains 16 passing tests. Relevant coverage includes real
episode metadata normalization, open-media series resolution, opaque stream
responses, compatibility preflight, play sessions, redirects, and Range relay.

Validated commands:

```powershell
python -m py_compile server/pocketstremio_server.py server/open_media_addon.py
python -m unittest server.test_pocketstremio_server -v
```
