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
5. Test controls, especially selector back and FFplay Menu-button exit.
6. After exit, confirm OnionOS UI returns cleanly.

Then collect logs over SSH:

```sh
tail -n 120 /mnt/SDCARD/App/PocketStremio/logs/app-playback.log
tail -n 200 /mnt/SDCARD/App/PocketStremio/logs/app-resource.log
```

## Confirmed Results

SSH-safe launcher dry run succeeded on August 12, 2026:

```text
tailscale status: ok
proxy video check: ok
playback skipped by POCKETSTREMIO_SKIP_PLAYBACK=1
```

Interactive playback from the OnionOS Apps menu was confirmed on August 12, 2026 through the PocketStremio vertical-slice client:

```text
query: big buck bunny
selected media: Big Buck Bunny (2008), movie, tt1254207
selected stream: PocketStremio hosted test video
play URL: http://100.85.171.67:8755/play/{session}
ffplay exit: rc=0
```

FFplay confirmed the media format from app context:

```text
Video: h264, yuv420p, 640x360, 30 fps
Audio: aac, 44100 Hz, stereo
```

Audio path from app context:

```text
open /dev/dsp return 8
opened /dev/dsp audio_fd is 8
open audio true
```

Memory snapshot after playback exit:

```text
Mem total: 103360 KB
Mem used: 88032 KB
Mem free: 15328 KB
Swap total: 131068 KB
Swap used: 8824 KB
tailscaled process still running
```

The active-playback sampler captured:

```text
tailscaled RSS: 29,880-33,924 KB
ffplay RSS after startup: 19,020-20,036 KB
free RAM: 1,888-3,104 KB
available RAM excluding buffers: 3,880-5,084 KB
swap used: 10,328-10,400 KB
ffplay swap: 0 KB
```

Confirmed by user:

- Video plays visibly from OnionOS app context.
- The sample used in the previous playback POC played through the new PocketStremio flow.
- FFplay returned cleanly with `rc=0`.

## Controller Selector Investigation

Onion's OTA script invokes the stock selector with separated arguments:

```sh
printf 'One\nTwo\nThree\n' | shellect.sh -t "Test" -b "Press A to select"
```

That exact invocation fails from the PocketStremio Apps context because the
process has `/dev/null` for stdin/stdout and a pipe for stderr. `shellect.sh`
redirects its UI through fd 2 and expects a controlling terminal, resulting in
`rc=1` and empty stdout. Binding it directly to a VT caused a black screen and
was abandoned without modifying OnionOS files.

PocketStremio now uses a self-contained SDL 1.2 selector. It uses Onion's
existing SDL runtime, a built-in bitmap font, and no SDL_ttf or large runtime.
The renderer compensates for the Miyoo framebuffer's 180-degree orientation,
as Onion's FFplay launcher does with `hflip,vflip`.

Confirmed from the OnionOS Apps context on August 12, 2026:

```text
D-pad Down: SDL key 274
A: SDL key 32
selected index: 1
selected value: Two
selector exit: rc=0
stdout: Two
```

The selector displayed right-side up and returned cleanly to Apps. The client
logs every SDL key, selected index, selected value, and selector return code.
Manual selection is now the default; the previous automatic path remains
available with `POCKETSTREMIO_AUTO_FIRST=1`.

B/back was physically confirmed from the search result screen:

```text
B: SDL key 306
selector exit: rc=1
selected value: empty
result: returned to search input
```

The complete manual forward path was confirmed from Apps on August 12, 2026:

```text
search q=big buck bunny
A -> Big Buck Bunny (2008)
A -> Play
A -> PocketStremio hosted test video
FFplay input -> /play/{session}
video -> H.264 High, 640x360, 30 fps
audio -> AAC stereo, /dev/dsp opened
FFplay exit -> rc=0
```

The user confirmed that playback started. The log contains no auto-selection
entries, proving that all three selections came from the SDL controller UI.

Still to measure during active playback:

- smooth playback quality
