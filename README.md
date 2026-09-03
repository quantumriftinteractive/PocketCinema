# PocketCinema for Miyoo Mini Plus

A lightweight Stremio-style streaming client for the **Miyoo Mini Plus running OnionOS**.

## Confirmed Prototype

The current prototype completes this controller-driven OnionOS flow:

```text
Apps -> PocketCinema -> search -> select media or episode -> Play -> select stream -> FFplay
```

It uses direct HTTP or an optional configured HTTP proxy, a lightweight SDL 1.2
selector, a Python server on the gaming PC, and the PC's localhost-only Stremio
Service as an optional backend. The PCServer can also run on macOS while reaching a
Windows Stremio Service through a loopback-only SSH tunnel. Tailscale is an
independent network provider, not a PocketCinema runtime dependency. The
known-compatible Big Buck Bunny test
stream plays as H.264 640x360 with AAC audio. See
`docs/vertical-slice.md`, `docs/ffplay-playback-poc.md`, and
`docs/operational-resilience.md` for confirmed results and current limitations.

See [docs/roadmap.md](docs/roadmap.md) for milestone status, acceptance criteria,
sequencing, deferred features, and known risks.

Normal server operations use `server/manage-server.ps1` on Windows or
`server/manage-server.sh` on macOS. Tracked Miyoo app files can be upgraded with
`scripts/deploy-miyoo.ps1`; the deployment preserves the app's real config,
logs, networking-provider state, and OnionOS core files.

For the pre-Milestone-23 development-device rename and its intentionally
limited configuration migration, see
[PocketCinema Rename Migration](docs/pocketcinema-rename-migration.md).

The goal is to turn the Miyoo Mini Plus into a small remote streaming client that can browse media, search for content, select episodes or movies, and play them using the device's existing video playback capabilities.

The Miyoo is intentionally kept lightweight. Heavy tasks such as stream resolution, torrent handling, transcoding, and Stremio-related processing should be performed by a remote PC.

## Project Idea

The basic architecture is:

```text
┌──────────────────────┐
│   Miyoo Mini Plus    │
│      OnionOS         │
│                      │
│  PocketCinema UI    │
│        │             │
│        ▼             │
│   HTTP / REST API    │
│        │             │
│        ▼             │
│      FFplay          │
└─────────┬────────────┘
          │
          │ Tailscale
          │
          ▼
┌──────────────────────┐
│  Gaming PC or Mac    │
│                      │
│ PocketCinema Server │
│        │             │
│        ├─ Stremio    │
│        ├─ Addons     │
│        ├─ Streams    │
│        ├─ ffmpeg     │
│        └─ Transcode  │
└──────────────────────┘
```

## Goals

The final client should ideally support:

* Browse available media
* Search for movies and series
* View metadata
* Browse seasons and episodes
* Access a user's library
* Continue watching
* Select available streams
* Resume playback
* Subtitle support
* Send playback progress back to the server
* Play remote video through OnionOS/FFplay
* Connect securely to the server through a trusted network or VPN

The Miyoo client should remain as lightweight as possible.

## Design Philosophy

The Miyoo Mini Plus should act primarily as a **thin client**.

It should not be responsible for:

* Torrent downloading
* Torrent peer management
* Heavy Stremio processing
* Video transcoding
* High-resolution video decoding
* Complex addon resolution
* Large local databases

Instead, the gaming PC should perform the expensive operations and expose a small API designed specifically for the Miyoo.

Example:

```text
Miyoo
  │
  │ GET /api/search?q=alien
  ▼
PocketCinema Server
  │
  ▼
Stremio / Addons
  │
  ▼
JSON response
```

Playback:

```text
Miyoo
  │
  │ GET /api/play/<media-id>
  ▼
PocketCinema Server
  │
  ├─ Resolve source
  ├─ Determine compatibility
  ├─ Transcode if necessary
  │
  ▼
HTTP video stream
  │
  ▼
FFplay on Miyoo
```

## Why a Remote Server?

The Miyoo Mini Plus has limited CPU, memory, networking, and codec capabilities.

The gaming PC can handle:

* Stream resolution
* Torrent-based sources
* Debrid sources
* Unsupported codecs
* HEVC / AV1 sources
* High bitrate media
* Audio conversion
* Subtitle processing
* Resolution scaling
* Video transcoding

A source such as:

```text
2160p
HEVC Main10
HDR
EAC3
```

could therefore be converted by the PC into something much more suitable for the Miyoo:

```text
640x360 / 640x480
H.264
AAC
```

The Miyoo only needs to receive and display the resulting stream.

## Networking

Remote communication is intended to use **Tailscale**.

Example:

```text
Miyoo Mini Plus
      │
      │ Wi-Fi
      ▼
   Internet
      │
      │ Tailscale
      ▼
 Gaming PC
```

This would allow the PocketCinema client to connect to the gaming PC without exposing the server directly to the public internet.

A major early objective of this project is determining the best method of running Tailscale on OnionOS / Miyoo Mini Plus.

Possible approaches include:

1. Native ARM build
2. Existing compatible Tailscale binary
3. TUN-based networking
4. Tailscale userspace networking
5. A lightweight client/proxy solution if full Tailscale cannot run

## Proposed Components

### PocketCinema Client

Runs on:

```text
Miyoo Mini Plus
OnionOS
```

Responsibilities:

* UI
* Controller input
* HTTP communication
* JSON parsing
* Image/poster loading
* Search
* Catalog browsing
* Episode selection
* Playback requests
* Launch FFplay
* Report playback state

The client should contain as little Stremio-specific logic as possible.

### PocketCinema Server

Runs on:

```text
Gaming PC
```

Responsibilities:

* Stremio integration
* Addon communication
* Catalog retrieval
* Metadata retrieval
* Stream resolution
* Authentication
* Torrent/debrid handling
* Playback URL generation
* Transcoding
* Subtitle processing
* Playback state
* API communication with the Miyoo

## Possible API

The API is intentionally simple.

Examples:

```http
GET /api/status
```

```http
GET /api/home
```

```http
GET /api/search?q=alien
```

```http
GET /api/meta/{id}
```

```http
GET /api/series/{id}
```

```http
GET /api/streams/{id}
```

```http
GET /api/play/{id}
```

```http
POST /api/progress
```

Example response:

```json
{
  "id": "tt0078748",
  "title": "Alien",
  "year": 1979,
  "type": "movie",
  "poster": "https://example.com/poster.jpg"
}
```

Playback response:

```json
{
  "url": "http://gaming-pc:8754/stream/session-id",
  "resume": 1842,
  "subtitles": []
}
```

## UI Concept

PocketCinema should be designed around the Miyoo controls rather than attempting to reproduce the desktop Stremio interface.

Example:

```text
┌──────────────────────┐
│    POCKETCINEMA     │
├──────────────────────┤
│ > Continue Watching  │
│   Movies             │
│   Series             │
│   Library            │
│   Search             │
│   Settings           │
└──────────────────────┘
```

Possible controls:

```text
D-Pad    Navigate
A        Select / Play
B        Back
X        Search
Y        Options
Menu     Main Menu / Exit
```

## Development Roadmap

The original phases below describe the initial concept. The evidence-based
[project roadmap](docs/roadmap.md) is authoritative for current status,
sequencing, acceptance criteria, and deferred work.

### Phase 0: Research

Determine the Miyoo Mini Plus / OnionOS runtime environment.

Investigate:

* CPU architecture
* Linux kernel
* libc
* available libraries
* `/dev/net/tun`
* permissions
* available RAM
* networking stack
* OnionOS application structure
* FFplay capabilities

### Phase 1: Tailscale Proof of Concept

Goal:

```text
Miyoo → Tailscale → Gaming PC
```

Tasks:

* Test compatible Tailscale binaries
* Test TUN support
* Test userspace networking
* Store Tailscale state on the SD card
* Create startup/shutdown scripts
* Verify connectivity outside the local network

### Phase 2: HTTP Proof of Concept

Create a minimal server endpoint:

```http
GET /api/status
```

Response:

```json
{
  "status": "ok",
  "message": "hello tiny potato"
}
```

The Miyoo should retrieve and display the response.

### Phase 3: Remote Video Test

Host a known compatible video from the gaming PC.

Test:

```text
Gaming PC
    │
    ▼
HTTP stream
    │
 Tailscale
    │
    ▼
Miyoo FFplay
```

Confirm:

* buffering
* stability
* audio
* controls
* Wi-Fi performance

### Phase 4: PocketCinema Server

Implement the initial server API.

Start with:

* `/api/status`
* `/api/search`
* `/api/meta`
* `/api/play`

Stremio integration can then be added behind the API.

### Phase 5: Miyoo UI

Implement:

* Main menu
* Search
* Result lists
* Media details
* Series / season / episode browsing
* Playback

### Phase 6: Playback Compatibility

Add server-side detection and conversion for unsupported media.

Possible transcoding target:

```text
H.264
AAC
640x360 or 640x480
Miyoo-friendly bitrate
```

### Phase 7: Quality of Life

Potential features:

* Continue Watching
* Watch progress
* Recently watched
* Favorites / Library
* Poster caching
* Subtitle selection
* Audio track selection
* Stream quality selection
* Server discovery
* Tailscale hostname configuration
* Connection status indicator

## Repository Structure

```text
PocketCinema/
├── app/
├── client/miyoo/
│
├── server/
│
├── onion-tailscale/
│   ├── bin/
│   ├── docs/
│   ├── scripts/
│   └── README.md
│
├── experiments/
│   └── ffplay/
│
├── docs/
├── scripts/
├── AGENTS.md
└── README.md
```

## Current Status

**Experimental / working vertical slice**

Optional Tailscale networking, structured JSON communication, OnionOS FFplay playback,
and controller-driven movie and series episode selection are confirmed on the
Miyoo Mini Plus.
Continue Watching and resume seeking are now physically confirmed. External SRT
rendering is blocked because the target FFplay build lacks the `subtitles`
filter. Real server-side stream resolution is now confirmed through a
localhost-only addon and a public-domain direct stream. Series, season, and
episode browsing are confirmed with a deterministic local fixture. Direct and
optional-proxy transport modes are confirmed, and Tailscale-specific code is
isolated under `onion-tailscale/`. A real public-domain series episode now plays
through the same opaque server pipeline. Its Continue Watching label, Resume,
Play from Start, progress replacement, B navigation, and Menu exit are also
physically confirmed. The standalone Tailscale app now shows connection state
and IP, supports controller-driven enable/disable, and starts through an
app-owned OnionOS boot hook. The active PocketCinema milestone is localhost
Stremio Service backend integration. See
[docs/roadmap.md](docs/roadmap.md) for
details.

The first compatibility layer now performs gaming-PC ffprobe inspection before
playback, labels confirmed versus unmeasured profiles, rejects unsupported
codecs before FFplay, and bounds opaque play sessions. See
[docs/playback-compatibility.md](docs/playback-compatibility.md).

The original priority sequence was:

```text
1. Tailscale on Miyoo Mini Plus
        ↓
2. Miyoo → PC HTTP communication
        ↓
3. Remote FFplay playback
        ↓
4. PocketCinema Server
        ↓
5. Stremio integration
        ↓
6. Full Miyoo UI
```

The project should avoid implementing later stages until the underlying networking and playback experiments have been proven reliable.

## Inspiration

This project is inspired by lightweight network-based applications created for the Miyoo Mini Plus, particularly projects demonstrating that OnionOS applications can retrieve remote media and hand playback to FFplay.

PocketCinema is not intended to be a port of the official Stremio application.

Instead, it aims to provide a purpose-built controller-first interface suited to the capabilities and limitations of the Miyoo Mini Plus.

## Disclaimer

PocketCinema is an independent experimental project and is not affiliated with Stremio, OnionOS, Miyoo, or Tailscale.

Users are responsible for the media sources and services they configure and for complying with applicable laws and service terms.
