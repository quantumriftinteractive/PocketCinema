# Stremio Account Addon Discovery

## Status

Server-side account linking, addon collection discovery, conservative stream
filtering, Live TV browsing, and account-backed playback are confirmed through
the OnionOS Apps context. Roadmap Milestone 16 is complete.

## Supported Account Flow

PocketStremio does not accept a Stremio email address or password and does not
read the desktop application's private state. The helper uses Stremio's official
temporary link flow:

```powershell
python .\server\link_stremio_account.py
```

The user approves the temporary `link.stremio.com` URL in a browser. The helper
polls the official link API and writes only the returned auth key to:

```text
server/config/stremio_account.json
```

That file is ignored by git. It stays on the gaming PC and is never deployed to
the Miyoo. Existing configuration is not replaced unless the helper is run with
`--replace`.

The OnionOS client also exposes **Stremio Account** on its home menu. When no
account is configured, `POST /api/account/link` creates one server-owned pairing
session and returns only the short approval link. The Miyoo generates its QR
symbol locally, the user approves it on another device, and A calls
`GET /api/account?poll=1`. The retrieval code and resulting auth key never enter
the Miyoo API, process arguments, or app log. A configured account cannot be
replaced or removed through the remote API.

The implementation follows the current interfaces in the official Stremio Core
repository:

- `GET https://link.stremio.com/api/v2/create?type=Create`
- `GET https://link.stremio.com/api/v2/read?type=Read&code=...`
- `POST https://api.strem.io/api/addonCollectionGet`
- addon resources derived from the collection's `transportUrl`

Research was performed against Stremio Core commit
`474ffaa` and Stremio Web commit `1748dc1`. No opaque desktop account files were
read or copied.

## PocketStremio API

`GET /api/addons` returns a bounded, read-only collection containing addon name,
version, declared types and resources, capability flags, and a generic support
message. `GET /api/addons?refresh=1` bypasses the five-minute collection cache.

`GET /api/status` reports only bounded account state: configured, checked,
authenticated, addon count, stream-addon count, and a generic error message.

`GET /api/account` reports bounded account and pairing state. With `?poll=1`, it
checks an active approval session. `POST /api/account/link` starts a five-minute
session only when no account configuration exists; otherwise it returns HTTP
409.

Neither response includes the auth key, manifest transport URL, addon manifest,
or upstream stream URL. Account stream IDs are opaque. `/api/streams` caches an
accepted upstream URL only on the gaming PC, and `/api/play` exposes the normal
short opaque play-session URL.

`GET /api/live-tv` reads only account addons that declare both `catalog` and
`stream` support for `tv`. It returns at most 128 normalized channel IDs, titles,
and source labels. Transport URLs and raw catalog responses remain server-side.

## Acceptance Policy

Account addon transports must use HTTPS, end in `/manifest.json`, omit URL
credentials, query strings, and fragments, and not use localhost, `.local`, or a
private literal IP address. P2P manifests are unusable.

Stream results are accepted only when they provide a public HTTP(S) URL. The
server rejects:

- `infoHash` and other torrent-only results;
- external-player URLs;
- local files and private literal addresses;
- URL credentials or fragments;
- P2P identifiers and results that do not provide a direct HTTP(S) media URL;
- media that fails the existing ffprobe compatibility policy.

This is deliberately conservative. Addon discovery does not imply that an addon
is an approved PocketStremio playback source.

Milestone 18 later extended this boundary with explicit user authorization:
debrid-labeled results are accepted only when the configured account addon
returns a direct public HTTP(S) media URL. The gaming-PC server uses that URL
behind an opaque play session. P2P identifiers and external-player shapes remain
rejected, and no addon or media token is sent to the Miyoo.

## Confirmed Live Results

On 2026-08-14, the linked account returned 15 normalized addons. Five declared a
stream resource. Public PocketStremio responses contained no auth-key field,
manifest URL, transport URL, or upstream media URL.

The account was then rebound from the OnionOS Apps context using the new QR
flow. The QR scanned successfully, approval completed, A refreshed to
**Connected - 15 addons**, selecting that status refreshed normally, and B
returned to the PocketStremio home menu. Device logs contained pairing states
and controller results but no approval URL. No selector, infoPanel, FFplay,
`/tmp/stay_awake`, or dismiss flag remained after exit.

With the QR-capable PocketStremio selector waiting on its home menu, it measured
3,452 kB RSS, 9,528 kB virtual size, and 0 kB process swap. The system reported
5,220 kB free and 69,200 kB available. The encoder is linked into the existing
selector and creates no additional resident service.

For *Night of the Living Dead* and *Big Buck Bunny*:

- Torrentio RD returned only explicitly RD/debrid-labeled direct links; all were
  rejected.
- AIOStreams returned explicitly RD-labeled direct links plus an external launch
  result; all were rejected.
- Account Local Files used a desktop-local transport and remained unusable.
- The existing allowlisted Local Files, open-media, and deterministic fixture
  sources remained available independently.

Those observations describe the original Milestone 16 policy. Milestone 18
permits the direct HTTPS entries while continuing to reject the external launch
result.

## Direct Account Playback

On August 14, 2026, the first Torrentio RD result for *Alien* (1979) was ordered
ahead of larger renditions using its advertised 360p quality. Server preflight
confirmed MP4/MOV with H.264 Main 640x272 video and AAC audio. The stream then
played visibly and audibly from the OnionOS Apps context.

The addon's display name contained a newline between its source and quality.
That initially appeared as two selector choices even though both lines belonged
to one opaque stream ID. Account display text is now collapsed to one line so
the selector shows `[RD+] Torrentio 360p` as one choice.

The real series path is also physically confirmed with *Grimm* S1E1. The
Torrentio RD 480p result opened as H.264 High 852x480 at 23.98 fps with AAC
48 kHz stereo. FFplay reached video readiness in 36 seconds, played visible
video and audible audio, tracked nine paused seconds and 37 valid watched
seconds, exited cleanly, and saved a 37-second Continue Watching position.

The Greek TV account addon resolved the public broadcaster ERT News as one
direct HTTP stream. Its HLS master offers a 640x360, 25 fps H.264 High/AAC
rendition at approximately 1.5 Mb/s. PocketStremio now accepts HLS as a candidate
container, prefers sane `avg_frame_rate` data over invalid transport time-base
rates, and invalidates compatibility results produced by the earlier cache
schema.

## HLS Bridge

The gaming-PC server owns the entire HLS transport. It:

- limits playlists to 1 MiB and 4,096 lines;
- selects an H.264 rendition no larger than 640x360, 30 fps, and 1.6 Mb/s;
- validates public HTTP(S) addresses and redirects;
- rejects encrypted HLS, fragmented-MP4 media playlists, and byte-range segments;
- polls the selected live media playlist and streams its MPEG-TS segments as one
  `video/mp2t` response through the opaque `/play/{session}` URL;
- retains the normal six-hour bounded play-session lifetime.

No master playlist, media playlist, child URI, or segment URL reaches the Miyoo.
The bridge performs no transcoding or codec conversion.

Directly relaying a rewritten HLS playlist was tested first. The target FFplay
downloaded valid MPEG-TS segments but repeatedly refreshed the playlist without
completing input probing. Flattening the master to the selected media playlist
did not change that behavior. Desktop FFmpeg opened both forms immediately.
Serving the same segments as a continuous MPEG-TS response avoided the old
device demuxer's HLS behavior and retained the existing FFplay launch path.

## Confirmed Device Playback

Confirmed from the OnionOS Apps context on August 14, 2026:

- `Apps -> PocketStremio -> Live TV -> ERT News -> [TEST] ERT News` completed;
- the loading panel remained visible through preflight and FFplay launch;
- FFplay reached SDL video readiness in 4 seconds;
- it detected MPEG-TS with H.264 High 640x360 at 25 fps and AAC 48 kHz stereo;
- video was physically reported smooth and audio was reported perfect;
- Menu exited after 29 valid watched seconds and B returned through both Live TV
  and the PocketStremio home screen;
- no FFplay, selector, pause monitor, info panel, `/tmp/stay_awake`, dismiss flag,
  or playback temporary file remained after exit;
- live playback did not create a Continue Watching progress update.

Measured during playback:

```text
ffplay RSS:          28,440 kB
ffplay VmSwap:            0 kB
tailscaled RSS:      37,208 kB
tailscaled VmSwap:    1,540 kB
MemAvailable:        31,688 kB
system swap used:     2,856 kB
```

The device clock was also found 1,601 seconds slow even though Onion's automatic
internet-time setting and `/tmp/ntp_synced` marker were active. Onion accepted a
stale HTTP time API response; direct Google NTP corrected the system and hardware
clocks. Playback still stalled with the corrected clock until the MPEG-TS bridge
was deployed, confirming that clock drift was not the HLS playback blocker. No
OnionOS core file was modified.

## Candidate Channel Audit

A server-side structural audit covered all current account TV catalogs without
exposing their URLs. Of 46 Greek TV entries, 26 supplied a compatible H.264
rendition, an unencrypted MPEG-TS media playlist, and valid TS sync bytes. Thirteen
returned upstream HTTP errors and seven were unsupported or unreachable. The USA
TV catalog was unavailable. These 25 additional bridge-eligible channels remain
candidates until each is physically tested; only ERT News is confirmed.
