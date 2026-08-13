# Real Stream Resolution POC

Goal: resolve and relay one legal, reproducible remote movie stream through a
Stremio addon while preserving PocketStremio's existing network and device
boundaries.

## Status

**Confirmed on the Miyoo Mini Plus.**

The resolver, opaque API response, play session, redirects, byte ranges, and
Apps-context playback are confirmed. The user reported that playback was
working, seemed okay during the physical test, and had audible audio. The device
log independently confirmed video/audio initialization, normal controller exit,
progress saving, and cleanup.

## Source

The test title is *Night of the Living Dead* (1968), Cinemeta ID `tt0063350`.
The selected Internet Archive item identifies the film and marks it public
domain:

- item: https://archive.org/details/Night.Of.The.Living.Dead_1080p
- license: http://creativecommons.org/licenses/publicdomain/
- derivative: `NightOfTheLivingDead_DVD5_512kb.mp4`

Internet Archive metadata reports a 333,938,666-byte, 5,752-second, 320x240 MP4
derivative. A range probe of the file found `avc1` and `mp4a` sample entries,
indicating H.264 video and AAC audio. The upstream returned `206 Partial
Content`, `video/mp4`, and a correct total size.

This source is deliberately narrow. It proves addon-based direct HTTP media
resolution; it is not a general catalog, torrent resolver, or substitute for
the existing deterministic Big Buck Bunny fixture.

## Architecture

The dependency-free addon in `server/open_media_addon.py` exposes the standard
Stremio routes:

```text
http://127.0.0.1:8756/manifest.json
http://127.0.0.1:8756/stream/movie/tt0063350.json
```

It is started inside the PocketStremio server process and binds only to
`127.0.0.1`. PocketStremio validates the manifest's resource and media type,
then requests the stream resource. Stremio Service remains separately bound to
localhost at `127.0.0.1:11470`.

The Miyoo path remains:

```text
OnionOS client
  -> HTTP proxy 127.0.0.1:1055
  -> Tailscale userspace networking
  -> PocketStremio 100.85.171.67:8755
  -> localhost open-media addon
  -> Internet Archive media
```

`/api/streams/movie/tt0063350` returns an opaque stream ID, display name,
compatibility description, and duration. It does not return the upstream URL
or addon address. `/api/play` stores the upstream URL in server memory and
returns only `/play/{session}` on PocketStremio.

## Relay Behavior

The play relay now:

- follows ordinary HTTP redirects through Python's standard HTTP client;
- forwards the client's `Range` header;
- requests identity encoding so byte offsets remain meaningful;
- returns upstream status, content type, length, range, cache, ETag, and
  last-modified headers;
- returns concise JSON for upstream HTTP and connection failures;
- treats an early FFplay disconnect as a normal client disconnect instead of
  attempting a second response after media headers were sent.

The Miyoo client displays the first normalized source failure when no playable
stream is available. Raw upstream URLs remain absent from client logs and API
responses.

## Confirmed Results

Confirmed on `desktop-gaming` on August 13, 2026:

```text
GET /api/search?q=night of the living dead
  -> first result: Night of the Living Dead (1968), tt0063350

GET /api/streams/movie/tt0063350
  -> Open Media - Internet Archive
  -> H.264/AAC, 320x240, 512 Kb/s
  -> no upstream URL in response

POST /api/play
  -> PocketStremio /play/{session} URL

GET /play/{session}, Range: bytes=0-1048575
  -> 206 Partial Content
  -> Content-Type: video/mp4
  -> Content-Range: bytes 0-1048575/333938666
```

Confirmed by SSH on the Miyoo using OnionOS `curl` and `jq`, with both proxy
variables set to `http://127.0.0.1:1055/`:

```text
status=ok version=0.4-real-stream-poc
search=Night of the Living Dead id=tt0063350
stream=Open Media - Internet Archive count=1 leaked_url=0
GET /play/{session}, Range: bytes=0-65535
  -> 206 Partial Content
  -> Content-Type: video/mp4
  -> Content-Range: bytes 0-65535/333938666
```

The production listeners were confirmed as:

```text
100.85.171.67:8755  PocketStremio, reachable through the tailnet
127.0.0.1:8756      open-media addon, loopback only
```

No OnionOS core file or Tailscale persistent state was modified. The updated
client remained under `/mnt/SDCARD/App/PocketStremio/`.

## Automated Verification

`server/test_pocketstremio_server.py` covers:

- loopback addon manifest and stream-resource resolution;
- normalized stream metadata and duration;
- omission of source and upstream URL from public responses;
- play-session range forwarding through an HTTP redirect;
- preservation of content type and content range;
- the existing search, fixture playback, subtitle, and progress behavior.

Run:

```powershell
python -m unittest server.test_pocketstremio_server -v
```

## Confirmed Physical Playback

Confirmed from the OnionOS Apps menu on August 13, 2026:

```text
PocketStremio
  -> Search
  -> night of the living dead
  -> Night of the Living Dead (1968)
  -> Play
  -> Open Media - Internet Archive
  -> FFplay
```

The user confirmed that the film was playing, its audio was audible, and the
tested playback seemed okay. The app-local log recorded manual result, Play, and
stream selections, with no automatic-selection fallback:

```text
selected media: Night of the Living Dead (1968), tt0063350
selected action: Play
selected stream: Open Media - Internet Archive
```

FFplay detected and opened:

```text
container: MP4
duration: 01:35:52.12
bitrate: 464 kb/s
video: H.264 Constrained Baseline, yuv420p, 320x240, 23.98 fps, 409 kb/s
audio: AAC, 48 kHz, stereo, 49 kb/s
audio output: /dev/dsp opened successfully
```

Active playback measurements:

```text
tailscaled RSS: 33,452 kB
FFplay RSS:     25,416 kB
free RAM:        1,912 kB
system swap:     1,028 kB used
process swap:        0 kB for tailscaled and FFplay
```

After the Miyoo Menu button was pressed, the log confirmed this was a normal
exit rather than a crash. A later control check established that B is FFplay's
frame-step control, not its exit control:

```text
FFplay exit: rc=0 after 97 seconds
progress: saved at 97 / 5752 seconds
home selector: resumed
PocketStremio UI: clean exit
```

No FFplay, selector, or client process remained. `/tmp/stay_awake` and the
temporary subtitle path were absent. Tailscaled remained running with its
existing persistent state.
