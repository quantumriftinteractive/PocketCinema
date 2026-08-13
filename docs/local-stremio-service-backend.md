# Local Stremio Service Backend

Milestone 15 proves a bounded server-side integration with Stremio Service
without exposing its API or desktop file paths to the Miyoo.

## Confirmed Runtime

The installed Stremio Service reports:

```text
serverVersion: 4.20.8
local addon: org.stremio.local 1.10.0
local addon enabled: true
```

The service root serves the Stremio web application, `/settings` exposes runtime
settings, and `/local-addon/manifest.json` exposes the bundled Local Files addon.
The addon scans Windows Search results at service startup and maps recognized
local movie and episode names to IMDb IDs.

The service runtime listens on more than loopback and does not expose a supported
bind-address setting. An enabled Windows Firewall block rule therefore enforces
the project boundary for TCP ports `11470-11474` and `12470`:

```powershell
New-NetFirewallRule `
  -DisplayName "PocketStremio - Block Stremio Service Remote" `
  -Group "PocketStremio" `
  -Description "Keep Stremio Service ports local; PocketStremio uses 127.0.0.1." `
  -Enabled True -Direction Inbound -Action Block -Protocol TCP `
  -LocalPort 11470-11474,12470 -Profile Any
```

Confirmed after installing the rule:

```text
desktop -> 127.0.0.1:11470/settings: HTTP 200
Miyoo -> tailnet address:11470/settings: blocked, curl 000/rc 28
Miyoo -> desktop LAN address:11470/settings: blocked, curl 000/rc 28
Miyoo -> PocketStremio:8755/api/status: HTTP 200
```

No OnionOS core file or Tailscale state was changed.

## Backend Boundary

`server/stremio_service.py` is a dedicated adapter rather than a generic addon
entry. It enforces these rules:

- the configured service origin must use HTTP on `127.0.0.1`, `::1`, or
  `localhost`;
- only direct `file://` results from the Local Files addon are accepted;
- each resolved file must exist under an explicitly allowed media root;
- torrent identifiers, remote URLs, missing files, and paths outside an allowed
  root are ignored;
- service settings, raw file URLs, and desktop paths are not returned through
  the Miyoo API.

The launch scripts allow `%USERPROFILE%\Videos\PocketStremio` when that dedicated
directory exists. Other user Videos directories are not allowed implicitly.

`GET /api/status` now reports bounded service health, version, Local Files state,
and manifest capability. It omits the service `baseUrl` and local paths. Stream
lookups distinguish an unavailable service, a disabled Local Files addon, no
matching file, and a rejected result.

An accepted local file enters the existing opaque PocketStremio flow:

```text
Miyoo /api/streams request
  -> PocketStremio loopback adapter
  -> Stremio Service Local Files result
  -> allowlisted local path held server-side
  -> ffprobe compatibility preflight
  -> opaque /play/{session}
  -> PocketStremio byte-range file response
  -> Miyoo FFplay
```

The existing open-media addon and compatibility fixtures remain available.

## Legal Test Item

The proof uses the public-domain Internet Archive derivative already confirmed
in earlier milestones:

```text
Night of the Living Dead (1968)
IMDb ID: tt0063350
container: MP4
duration: 5752 seconds
size: 333,938,666 bytes
video: H.264 Constrained Baseline, 320x240
audio: AAC-LC stereo, 48 kHz
```

The media file is an ignored gaming-PC fixture and is not committed. Stremio
Local Files returned one direct file result and no torrent identifier. A normal
full Stremio restart was required because Local Files scans at startup. Killing
only the child runtime caused the desktop shell to display a transient streaming
server error and is not the documented restart procedure.

The official Blender Big Buck Bunny 640x360 file was also discovered by Windows
Search, but the bundled name matcher produced an empty Local Files record. It was
not used as evidence for this milestone.

## API Verification

Automated coverage increased from 16 to 22 tests. The new tests cover loopback
origin validation, bounded status output, unavailable-service diagnostics,
allowed local-file playback, path opacity, byte ranges, rejection outside the
configured root, and local-file revalidation when a play session is served.

The live production server confirmed:

```text
PocketStremio version: 0.10-stremio-service-backend
service-backed streams for tt0063350: 1
preflight: confirmed H.264/AAC Miyoo profile
Range bytes=0-4095: HTTP 206, 4096 bytes
file URL leaked in public JSON: false
desktop path leaked in public JSON: false
```

## Apps-Context Playback

Physically confirmed on August 13, 2026:

```text
Apps -> PocketStremio
  -> search Night of the Living Dead
  -> Play
  -> [TEST] Night of the Living Dead (1968).mp4
  -> FFplay video and audio
  -> Menu exit
  -> PocketStremio exit
  -> OnionOS Apps
```

The device log confirmed the `stremio-local` stream ID, compatibility preflight,
two-second video readiness, H.264 320x240 video, AAC stereo `/dev/dsp` audio,
FFplay exit code `0`, ten seconds of measured progress, and a clean UI exit.
No stale FFplay, selector, infoPanel, `/tmp/stay_awake`, or
`/tmp/dismiss_info_panel` state remained.

## Remaining Limits

- This backend exposes Local Files only; it does not expose Stremio account
  addons, library data, or watch history.
- Stremio Service must be restarted normally to rescan newly indexed files.
- The dedicated local fixture consumes gaming-PC storage and must remain outside
  git.
- Torrent, debrid, transcoding, and account authentication remain out of this
  milestone.
