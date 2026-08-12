# FFplay Playback POC

Goal: prove full interactive video playback from the OnionOS Apps menu while traffic reaches the gaming PC through Tailscale userspace networking.

This milestone does not add Stremio integration.

## Confirmed Inputs

- Tailscale userspace proxy is available at `127.0.0.1:1055`.
- `desktop-gaming` serves the PocketStremio POC server at `http://100.85.171.67:8755`.
- The test media URL is `http://100.85.171.67:8755/media/test-video.mp4`.
- The current test video is H.264 640x360 with AAC stereo.
- FFplay launched over SSH can fetch and demux the stream but blocks at `VT_WAITACTIVE`; therefore final playback must be launched from OnionOS app context.

## OnionOS Launch Findings

OnionOS apps use:

```text
/mnt/SDCARD/App/<AppName>/config.json
/mnt/SDCARD/App/<AppName>/launch.sh
```

Representative app launchers are simple shell scripts. SDL/framebuffer programs normally run after MainUI exits and OnionOS runtime starts audio services.

Relevant runtime details from `/mnt/SDCARD/.tmp_update/runtime.sh`:

- MainUI writes the selected command to `/mnt/SDCARD/.tmp_update/cmd_to_run.sh`.
- Runtime calls `start_audioserver` before launching apps/games.
- MainUI/app launch commands commonly use `LD_PRELOAD=/mnt/SDCARD/miyoo/lib/libpadsp.so`.
- Runtime removes `/tmp/stay_awake` after launch post-processing.

The built-in Arcade tutorial launches local video like this:

```sh
cd /mnt/SDCARD/.tmp_update
touch /tmp/stay_awake
./bin/ffplay -autoexit -vf "hflip,vflip" -i "/mnt/SDCARD/Media/Videos/Onion/Mame2003Plus Save State Tutorial.mp4"
rm -f /tmp/stay_awake
```

The PocketStremio launcher follows that pattern and adds the Tailscale proxy environment.

## Installed App

Files installed under:

```text
/mnt/SDCARD/App/PocketStremio/
```

New app-menu files:

```text
config.json
launch.sh
```

Logs:

```text
/mnt/SDCARD/App/PocketStremio/logs/app-playback.log
/mnt/SDCARD/App/PocketStremio/logs/app-resource.log
```

## Launcher Behavior

The app launcher:

1. Logs configuration and baseline resources.
2. Starts `tailscaled` only if the local socket is missing.
3. Runs Tailscale and curl checks with `LD_PRELOAD` unset so network helpers do not inherit the audio shim.
4. Verifies the video URL through `HTTP_PROXY=http://127.0.0.1:1055/`.
5. Supports `POCKETSTREMIO_SKIP_PLAYBACK=1` for SSH-safe validation of preflight checks.
6. Touches `/tmp/stay_awake`.
7. Launches FFplay from `/mnt/SDCARD/.tmp_update` with:

```sh
HOME=/mnt/SDCARD \
HTTP_PROXY=http://127.0.0.1:1055/ \
http_proxy=http://127.0.0.1:1055/ \
LD_PRELOAD=/mnt/SDCARD/miyoo/lib/libpadsp.so \
/mnt/SDCARD/.tmp_update/bin/ffplay \
  -hide_banner \
  -autoexit \
  -vf "hflip,vflip" \
  -i "http://100.85.171.67:8755/media/test-video.mp4"
```

8. Samples memory while FFplay is running.
9. Removes `/tmp/stay_awake` and returns control to OnionOS runtime.

## Test Procedure

On the gaming PC, keep the POC server running:

```powershell
.\server\start-server.ps1
```

On the Miyoo:

1. Open Apps.
2. Launch `PocketStremio`.
3. Confirm whether video is visible.
4. Confirm whether audio is audible.
5. Test controls, especially exit/back/menu.
6. After exit, confirm OnionOS UI returns cleanly.

Then collect logs over SSH:

```sh
tail -n 120 /mnt/SDCARD/App/PocketStremio/logs/app-playback.log
tail -n 200 /mnt/SDCARD/App/PocketStremio/logs/app-resource.log
```

## Pending Results

Interactive playback from the Apps menu has not yet been confirmed in this document.

SSH-safe launcher dry run succeeded on August 12, 2026:

```text
tailscale status: ok
proxy video check: ok
playback skipped by POCKETSTREMIO_SKIP_PLAYBACK=1
```

Record:

- tailscaled RSS
- ffplay RSS
- free memory during playback
- swap usage
- audio works: yes/no
- controls work: yes/no
- smooth playback: yes/no
- UI restore works: yes/no
