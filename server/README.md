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
GET /media/test-video.mp4
```

`/media/test-video.mp4` is only for the later FFplay network playback experiment. It returns `404` until a compatible MP4 is placed at `server/media/test-video.mp4`.

The media endpoint supports single HTTP byte-range requests because FFplay seeks inside MP4 files.
