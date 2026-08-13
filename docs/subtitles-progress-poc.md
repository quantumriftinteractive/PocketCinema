# Subtitles and Continue Watching POC

Goal: add lightweight subtitle selection and persistent resume behavior while
preserving the confirmed OnionOS networking and FFplay path.

## Status

**Continue Watching confirmed. External SRT rendering is blocked by the target
FFplay build.**

After the Miyoo came online, its FFplay build confirmed `-ss` support but did
not advertise the `subtitles` video filter. The client therefore suppresses the
external subtitle menu on this build. Server subtitle discovery and proxying
remain tested for a future remux, burn-in, or compatible-player path. Resume
seeking is physically confirmed from the OnionOS Apps menu.

## Subtitle Flow

PocketStremio follows the Stremio addon subtitle resource shape documented in
the official addon protocol:

```text
GET /api/subtitles/{type}/{id}?stream_id={opaque-stream-id}
GET /subtitle/{opaque-subtitle-id}
```

The server queries configured addon subtitle resources, normalizes language and
name fields, caches the private upstream URL, and exposes only an opaque ID to
the Miyoo. If stream behavior hints include a video hash and size, the server
also tries the hash-based subtitle route described by the protocol.

The client:

1. checks whether the target FFplay advertises the `subtitles` video filter;
2. shows No subtitles plus normalized subtitle choices;
3. downloads the selected subtitle through PocketStremio and Tailscale to
   `/tmp/pocketstremio-subtitle.srt`;
4. launches FFplay with
   `-vf "subtitles=/tmp/pocketstremio-subtitle.srt,hflip,vflip"`;
5. removes the temporary subtitle on playback exit or signal.

A small original SRT fixture is included for the hosted Big Buck Bunny test
stream so rendering can be tested without a third-party subtitle service.

Confirmed target FFplay behavior:

```text
-ss pos: available
subtitles video filter: unavailable
-sst: available only for subtitle streams already embedded in the input
```

External SRT rendering therefore requires a later server-side remux/burn-in path
or a different compatible player. It is not presented as working support.

References:

- https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/protocol.md
- https://ffmpeg.org/ffplay.html

## Continue Watching Flow

Server endpoints:

```text
GET  /api/continue-watching
POST /api/progress
```

State is stored in the ignored file:

```text
server/data/continue_watching.json
```

The store is bounded to 50 items and sorted by most recent update. Entries are
removed when the client reports completion or reaches at least 90 percent of a
known duration.

The Miyoo home menu now contains Search, Continue Watching, and Exit. A saved
item offers Resume, Play from Start, and Back. Resume passes the stored offset
to FFplay with `-ss`.

## Progress Accuracy

This POC estimates position as:

```text
saved resume offset + (time after SDL video readiness - A-button pause time)
```

This remains approximate because the OnionOS FFplay build exposes no confirmed
machine-readable player position. Network and decoder startup are excluded, and
an app-local non-grabbing evdev observer excludes A-button pause intervals. The
client suppresses progress updates when playback validation or pause tracking
fails. Seeks and buffering after video readiness can still differ from the
estimated position.

## Confirmed Device Result

Confirmed from the OnionOS Apps menu on August 12, 2026:

```text
home -> Continue Watching
item -> Big Buck Bunny (2008) - 0m 2s
action -> Resume at 0m 2s
stream -> PocketStremio hosted test video
FFplay -> resume_seconds=2, H.264 640x360 + AAC stereo
FFplay exit -> rc=0
progress -> completed=true, entry removed
home -> Exit
```

The user confirmed playback resumed correctly. The device log also confirmed:

- the server was ready through the Tailscale proxy;
- after an app-local tailscaled stop, the client restarted it with the existing
  persistent state, waited for readiness, and completed its first API request;
- the subtitle filter was unavailable and no subtitle option was shown;
- video and `/dev/dsp` audio opened successfully;
- the Continue Watching list was empty after completion;
- no `/tmp/stay_awake`, temporary SRT, FFplay, selector, or client process was
  left behind.

## Automated Verification

`server/test_pocketstremio_server.py` covers:

- normalized search and metadata;
- opaque stream and subtitle responses;
- subtitle proxy content;
- play-session byte ranges;
- progress persistence;
- completed-entry removal.

Run:

```powershell
python -m unittest server.test_pocketstremio_server -v
```

## Remaining Subtitle Work

External subtitle rendering requires a separately scoped compatibility
milestone. The next investigation should compare server-side remuxing an SRT
into a subtitle-capable container, burning subtitles into H.264, and a different
lightweight player. Any option must be measured against the Miyoo's limited free
memory and must preserve the current direct playback path as a fallback.
