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

Endpoints:

```text
GET /api/status
GET /api/search?q=alien
GET /api/meta/{type}/{id}
GET /api/streams/{type}/{id}
GET /api/subtitles/{type}/{id}?stream_id=...
GET /api/continue-watching
POST /api/play
POST /api/progress
GET /play/{session}
GET /subtitle/{subtitle_id}
GET /media/test-video.mp4
```

`/media/test-video.mp4` is only for the later FFplay network playback experiment. It returns `404` until a compatible MP4 is placed at `server/media/test-video.mp4`.

The media endpoint supports single HTTP byte-range requests because FFplay seeks inside MP4 files.

Search and metadata use the official Cinemeta addon protocol endpoints. Stream results are resolved server-side from configured stream addon manifest URLs.

The server also probes local Stremio Service through `http://127.0.0.1:11470/local-addon/manifest.json` by default. Keep Stremio Service bound to localhost; do not expose port `11470` to the Miyoo.

To configure stream-capable addons without committing private URLs or tokens:

```powershell
Copy-Item .\server\config\stream_addons.example.json .\server\config\stream_addons.json
notepad .\server\config\stream_addons.json
```

`stream_addons.json` is ignored by git. You can also set `POCKETSTREMIO_STREAM_ADDONS` to a comma-separated list of manifest URLs.

Configured addons are also queried for Stremio subtitle resources. Subtitle URLs
remain server-side and are proxied through opaque `/subtitle/{subtitle_id}`
routes. The bundled `fixtures/test-subtitle.srt` is a deterministic rendering
fixture for Big Buck Bunny.

Continue-watching entries are written to
`server/data/continue_watching.json`, which is ignored by git. The server keeps
at most 50 entries and removes completed items.

Run the automated server checks with:

```powershell
python -m unittest server.test_pocketstremio_server -v
```
