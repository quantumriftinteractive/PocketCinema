# JSON Communication POC

This milestone proves structured HTTP JSON communication between the Miyoo Mini Plus and the gaming PC through Tailscale userspace networking.

Out of scope:

- Stremio integration
- torrent handling
- transcoding
- posters
- media catalogs beyond dummy data
- full UI

## Server

Run on `desktop-gaming`:

```powershell
python .\server\pocketstremio_server.py --host 100.85.171.67 --port 8755
```

Endpoints:

```text
GET /api/status
GET /api/search?q=alien
```

The server uses mock media data only.

## Miyoo Client

Run after Tailscale is already authenticated and `tailscaled` is running:

```sh
cd /mnt/SDCARD/App/PocketStremio/client
chmod +x json-client.sh
./json-client.sh
```

The client uses:

```text
HTTP_PROXY=http://127.0.0.1:1055/
```

It requests `/api/status`, parses `status`, `service`, and `message`, then requests `/api/search?q=alien` and parses `query`, `count`, and result titles.

Logs:

```text
/mnt/SDCARD/App/PocketStremio/client/logs/json-client.log
```

## Resource Measurements

Use:

```sh
/mnt/SDCARD/App/PocketStremio/tailscale/scripts/resource.sh
```

Measure:

- `tailscaled` only
- `tailscaled + json-client.sh`
- `tailscaled + ffplay`

Confirmed JSON result on August 12, 2026:

```text
status.status=ok
status.service=pocketstremio-server
status.message=PocketStremio JSON POC is reachable
search.query=alien
search.count=2
search.results:
  title=Alien
  title=Aliens
json-client=ok
```

Confirmed resource snapshots:

```text
tailscaled only:
  VmRSS: 32388 kB
  VmSwap: 0 kB

json-client.sh while held open:
  VmRSS: 1540 kB
  VmSwap: 0 kB

tailscaled + json-client.sh:
  tailscaled VmRSS: 32728 kB
  tailscaled VmSwap: 0 kB
```

## FFplay Experiment

This is a separate experiment after JSON communication succeeds.

The gaming PC must serve:

```text
http://100.85.171.67:8755/media/test-video.mp4
```

The Miyoo script is:

```text
/mnt/SDCARD/App/PocketStremio/experiments/ffplay/network-playback.sh
```

Confirmed FFplay network probe:

```text
HTTP proxy video fetch:
  http_code=200
  size=1137884

ffplay input:
  container: mov/mp4
  video: H.264, 640x360, 30 fps
  audio: AAC, 44100 Hz, stereo
```

Resource snapshot while FFplay was running:

```text
ffplay:
  VmRSS: 16392 kB
  VmSwap: 0 kB

tailscaled while FFplay was running:
  VmRSS: 34196 kB
  VmSwap: 872 kB

system swap used:
  8292 kB
```

Playback caveat:

```text
ffplay reached SDL framebuffer setup and identified the H.264/AAC stream, but the SSH-launched run blocked at VT_WAITACTIVE and had audio open failures for /dev/dsp. Treat this as network fetch/demux proven, not full interactive playback proven.
```

The server needed HTTP byte-range support for MP4 playback experiments. Without it, FFplay produced repeated `partial file` warnings while seeking.
