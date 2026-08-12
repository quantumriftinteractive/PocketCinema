# Subtitles and Continue Watching POC

Goal: add lightweight subtitle selection and persistent resume behavior while
preserving the confirmed OnionOS networking and FFplay path.

## Status

**Implemented; device verification pending.**

The Miyoo was offline at both its LAN and tailnet addresses when this feature
was implemented. Server contracts and shell syntax are tested, but subtitle
rendering and resume seeking must still be confirmed from the OnionOS Apps menu.

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
saved resume offset + FFplay wall-clock run time
```

This is deliberately documented as approximate. It includes some player startup
time and cannot distinguish every end-of-file condition for streams whose
duration is unknown. A later compatibility milestone should replace it with a
machine-readable player position if the OnionOS FFplay build exposes one.

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

## Required Device Test

1. Confirm `ffplay -filters` includes `subtitles`.
2. Launch PocketStremio from Apps.
3. Search for Big Buck Bunny and select the hosted stream.
4. Select English (PocketStremio test) and confirm visible subtitle text.
5. Replay with No subtitles and confirm normal video/audio.
6. Exit early and confirm a Continue Watching entry appears.
7. Select Resume and confirm playback seeks forward.
8. Verify B/back and clean return to OnionOS on all new screens.
9. Collect `logs/pocketstremio-ui.log` and confirm temporary files/processes are
   gone.
