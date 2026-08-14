# Stremio Account Addon Discovery

## Status

Server-side account linking, addon collection discovery, and conservative stream
filtering are implemented and confirmed on the gaming PC. Apps-context playback
through an account addon is not yet confirmed, so Roadmap Milestone 16 remains
Next.

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
- results labeled as torrent, Real-Debrid, RD, or debrid downloads;
- media that fails the existing ffprobe compatibility policy.

This is deliberately conservative. Addon discovery does not imply that an addon
is an approved PocketStremio playback source.

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

The Greek TV account addon resolved the public broadcaster ERT News as one
direct HTTP stream. ffprobe identified H.264 High profile at 640x360 with AAC
stereo, delivered through HLS. The current compatibility layer rejected the
container. Passing the playlist through the existing byte proxy would expose or
bypass opaque handling for its child playlists and segments, so it was not sent
to the Miyoo.

## Remaining Acceptance Work

Milestone 16 still requires one legal, compatible account-addon result to start
visibly and audibly from the OnionOS Apps context. None is currently available
from the linked collection under the accepted progressive-media policy.

Supporting ERT News requires a separately designed HLS relay that rewrites and
proxies every playlist, segment, key, redirect, and byte-range request, followed
by Miyoo codec, memory, controls, and cleanup measurements. It must not be added
as an implicit exception to the current opaque playback contract.
