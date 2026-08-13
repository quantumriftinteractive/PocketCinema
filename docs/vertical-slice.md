# First Vertical Slice

Goal:

```text
Miyoo
  -> search
  -> real Stremio-backed results
  -> select movie
  -> resolve streams server-side
  -> launch FFplay through the proven Tailscale userspace proxy path
```

## Current Status

Baseline POCs were preserved in git commit:

```text
775c12e Preserve working Miyoo playback POC
```

Confirmed unchanged infrastructure:

- Tailscale userspace proxy remains `127.0.0.1:1055`.
- Miyoo talks only to PocketStremio server at `http://100.85.171.67:8755`.
- PocketStremio accesses Stremio Service only at `http://127.0.0.1:11470`, and
  Windows Firewall blocks remote access to the service ports.
- OnionOS playback launcher was preserved as `/mnt/SDCARD/App/PocketStremio/playback-poc.sh`.

## Server

PocketStremio server endpoints:

```text
GET  /api/status
GET  /api/search?q=...
GET  /api/meta/{type}/{id}
GET  /api/streams/{type}/{id}
POST /api/play
GET  /play/{session}
```

Search and metadata use Cinemeta. Streams are resolved from server-side addon sources:

- dedicated Stremio Service Local Files backend at
  `http://127.0.0.1:11470/local-addon/manifest.json`
- optional private addon config: `server/config/stream_addons.json`
- hosted test-video stream for `tt1254207`

Confirmed server tests:

```text
/api/search?q=alien:
  count: 12
  first: Alien
  first id: tt0078748

/api/streams/movie/tt0078748:
  count: 0

/api/search?q=big%20buck%20bunny:
  first: Big Buck Bunny
  first id: tt1254207

/api/streams/movie/tt1254207:
  stream: PocketStremio hosted test video
  playable: true
```

## Miyoo Client

The Apps-menu entry now launches:

```text
/mnt/SDCARD/App/PocketStremio/launch.sh
```

which runs:

```text
/mnt/SDCARD/App/PocketStremio/client/pocketstremio-ui.sh
```

Implementation choice:

- Shell script for low RAM and fast startup.
- `kbinput` for search text entry.
- self-contained SDL 1.2 selector for D-pad/A/B result and stream selection.
- `curl` through `HTTP_PROXY=http://127.0.0.1:1055/`.
- `jq` for reliable JSON parsing.
- existing FFplay launch context for playback.

SSH dry run confirmed the Miyoo can fetch and parse real results:

```text
POCKETSTREMIO_DRY_RUN=1 POCKETSTREMIO_DEFAULT_QUERY=alien
  1. Alien (1979)
  2. Alien: Romulus (2024)
  3. Alien³ (1992)

POCKETSTREMIO_DRY_RUN=1 POCKETSTREMIO_DEFAULT_QUERY='big buck bunny'
  1. Big Buck Bunny (2008)
```

Miyoo proxy playback handoff confirmed:

```text
GET  /api/streams/movie/tt1254207 -> PocketStremio hosted test video
POST /api/play -> http://100.85.171.67:8755/play/{session}
GET  /play/{session} with Range: bytes=0-1023 -> 206 Partial Content
Content-Type: video/mp4
Content-Range: bytes 0-1023/1137884
```

## Physical Test Result

Confirmed from the Miyoo Apps menu on August 12, 2026:

```text
PocketStremio launched from Apps
search q=big buck bunny
selected media: Big Buck Bunny (2008), movie, tt1254207
selected stream: PocketStremio hosted test video
ffplay URL: http://100.85.171.67:8755/play/{session}
ffplay exit: rc=0
```

The original `shellect.sh` result selector returned an empty string in app
context because fd 2 was a pipe rather than a terminal. The initial playback
confirmation therefore used the preserved automatic fallback.

A custom SDL 1.2 selector is now deployed for the search results, media action,
and stream screens. A standalone Apps-context test confirmed correct display
orientation, D-pad navigation, A selection, exact stdout value, and `rc=0`.
Manual selection is the default; setting `POCKETSTREMIO_AUTO_FIRST=1` restores
the initial automatic path for diagnostics.

FFplay detected:

```text
Video: h264, yuv420p, 640x360, 30 fps
Audio: aac, 44100 Hz, stereo
```

User-confirmed:

- The sample video played from OnionOS app context.
- Playback used the PocketStremio search-to-stream-to-play flow.

## Manual Selection Result

Confirmed from the OnionOS Apps menu on August 12, 2026:

```text
search q=big buck bunny
selector -> 1. Big Buck Bunny (2008), rc=0
selector -> Play, rc=0
selector -> PocketStremio hosted test video, rc=0
ffplay -> http://100.85.171.67:8755/play/{session}
ffplay exit -> rc=0
```

The user confirmed playback started. No `auto-selected` entries appear in the
device log, so the search result, media action, and stream were all selected
manually with the controller. D-pad navigation and A are physically confirmed;
B/back was physically confirmed as SDL key 306 with selector `rc=1`, returning
from the result list to the search input.

After testing, collect:

```sh
tail -n 160 /mnt/SDCARD/App/PocketStremio/logs/pocketstremio-ui.log
```
