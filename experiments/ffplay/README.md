# FFplay Network Playback Experiment

This is separate from the JSON POC.

Goal:

```text
Miyoo ffplay
  -> HTTP proxy 127.0.0.1:1055
  -> Tailscale userspace networking
  -> gaming PC /media/test-video.mp4
```

The gaming PC must host a known compatible H.264/AAC MP4 at:

```text
server/media/test-video.mp4
```

Run on the Miyoo:

```sh
cd /mnt/SDCARD/App/PocketCinema/experiments/ffplay
chmod +x network-playback.sh
./network-playback.sh
```

Then capture:

```sh
/mnt/SDCARD/App/Tailscale/scripts/resource.sh
tail -n 80 /mnt/SDCARD/App/PocketCinema/experiments/logs/ffplay-network.log
```

## App-local candidate patches

The selectable-Matroska candidate is an app-local FFplay 2.4.14 build. Apply
`ffmpeg-2.4.14-suppress-native-subtitles.patch` after the track-aware patch,
then apply `ffmpeg-2.4.14-subtitle-notice.patch`. Its build must enable the
existing `drawtext` filter in addition to the documented subtitle, scale,
orientation, format, and audio filters. The notice uses the already bundled
font, appears in the top-right corner for one second after R1, and does not
affect the OnionOS FFplay or production MPEG-TS fallback.
FFmpeg 2.4 also requires `--enable-libfreetype`; the app-local pkg-config shim
exposes the headers and library already present in the staged Miyoo sysroot.

The selected-track filter uses `font_scale=1.5`. It invokes libass's font-scale
path, so it applies the bounded 1.5x multiplier to both generated SRT and
styled ASS subtitle events in the 640x360/640x480 production path. It is part
of the app-local build and has no runtime setting.
