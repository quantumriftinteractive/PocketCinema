# PocketStremio Server POC

Minimal stdlib-only Python server for the Miyoo JSON communication proof.

Run on the gaming PC Tailscale address:

```powershell
python .\server\pocketstremio_server.py --host 100.85.171.67 --port 8755
```

or:

```powershell
.\server\start-server.ps1
```

For normal background operation, use the health-checked lifecycle manager:

```powershell
$env:POCKETSTREMIO_HOST = "TAILSCALE_IP_OR_INTERFACE_ADDRESS"
.\server\manage-server.ps1 start
.\server\manage-server.ps1 status
.\server\manage-server.ps1 restart
.\server\manage-server.ps1 stop
```

Its PID and redirected logs are stored under ignored `server/data/`. It removes
stale PID files, rejects duplicate managed instances, and verifies `/api/status`
after startup. `start-server.ps1` remains the foreground development entry
point.

Endpoints:

```text
GET /api/status
GET /api/addons
GET /api/account
GET /api/search?q=alien
GET /api/meta/{type}/{id}
GET /api/streams/{type}/{id}
GET /api/subtitles/{type}/{id}?stream_id=...
GET /api/continue-watching
POST /api/play
POST /api/progress
POST /api/account/link
GET /play/{session}
GET /subtitle/{subtitle_id}
GET /media/test-video.mp4
```

`/api/status` includes uptime, bounded play-session and probe-cache counts and
TTLs, progress count, and which state survives a server restart. Existing
top-level status fields remain available for client compatibility.

`/media/test-video.mp4` is only for the later FFplay network playback experiment. It returns `404` until a compatible MP4 is placed at `server/media/test-video.mp4`.

The media endpoint supports single HTTP byte-range requests because FFplay seeks inside MP4 files.

To link the gaming PC to a Stremio account without giving PocketStremio an email
address or password:

```powershell
python .\server\link_stremio_account.py
```

Approve the temporary official Stremio link in the browser. The resulting auth
key is stored only in ignored `server/config/stremio_account.json`.
`GET /api/addons` exposes a sanitized, read-only capability list; add
`?refresh=1` to refresh its five-minute cache. Auth keys, addon transport URLs,
and raw stream URLs remain server-side. Account results are limited to direct
public HTTP(S) media and reject P2P, debrid-labeled, external-player, local, and
private-address results. See [Stremio Account Addon Discovery](../docs/stremio-account-addons.md).

The Miyoo **Stremio Account** screen uses `POST /api/account/link` and
`GET /api/account?poll=1` for the same official flow. Linking is allowed only
when the ignored account config is absent. Existing accounts cannot be replaced
or removed remotely.

Search and metadata use the official Cinemeta addon protocol endpoints. Stream results are resolved server-side from configured stream addon manifest URLs.

Search includes movies and series. Series detail responses normalize Stremio
video records into compact season and episode lists, and episode video IDs are
used directly with `/api/streams/series/{video_id}`.

The server uses a dedicated backend for Stremio Service Local Files at
`http://127.0.0.1:11470`. Only direct local files inside an allowed media root
are accepted; desktop paths remain behind opaque play sessions. If the dedicated
`%USERPROFILE%\Videos\PocketStremio` directory exists, the PowerShell launchers
allow it automatically. Override the root explicitly when needed:

```powershell
.\server\start-server.ps1 `
  -StremioLocalMediaRoot "D:\PocketStremio Media"
```

The installed Stremio runtime listens beyond loopback, so a Windows Firewall
inbound block for TCP `11470-11474,12470` is required. Verify that local
`127.0.0.1:11470` remains reachable and that LAN and tailnet requests to those
ports fail. See [Local Stremio Service Backend](../docs/local-stremio-service-backend.md).

To configure stream-capable addons without committing private URLs or tokens:

```powershell
Copy-Item .\server\config\stream_addons.example.json .\server\config\stream_addons.json
notepad .\server\config\stream_addons.json
```

`stream_addons.json` is ignored by git. You can also set `POCKETSTREMIO_STREAM_ADDONS` to a comma-separated list of manifest URLs.

For playback compatibility measurements, generate the ignored local fixtures
from the hosted Big Buck Bunny clip:

```powershell
.\experiments\ffplay\generate-compatibility-fixtures.ps1
```

When present, the confirmed VP8/Vorbis and H.264/Opus rejection fixtures appear
beside the normal Big Buck Bunny stream. Only explicitly allowlisted fixture
filenames can be served through `/media/compatibility/`.

For deterministic season, episode, and A/V synchronization testing, generate
the ignored local series fixture:

```powershell
.\experiments\ffplay\generate-series-av-sync-fixture.ps1
```

Search for `test series` to use the two-season fixture without an upstream
metadata or media dependency.

For a real legal series path, search for `the beverly hillbillies`. The
localhost open-media addon exposes only S1E1 `The Clampetts Strike Oil` from its
public-domain Internet Archive item. The measured 320x240 H.264/AAC derivative
is hidden behind the normal opaque stream and play-session APIs. Other episodes
currently return no open-media streams.

Configured addons are also queried for Stremio subtitle resources. Subtitle URLs
remain server-side and are proxied through opaque `/subtitle/{subtitle_id}`
routes. The bundled `fixtures/test-subtitle.srt` is a deterministic rendering
fixture for Big Buck Bunny.

Continue-watching entries are written to
`server/data/continue_watching.json`, which is ignored by git. The server keeps
at most 50 entries and removes completed items.

Run the automated server checks with:

```powershell
python -m unittest server.test_stremio_account server.test_pocketstremio_server -v
```
