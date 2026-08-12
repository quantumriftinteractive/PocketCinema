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
cd /mnt/SDCARD/App/PocketStremio/experiments/ffplay
chmod +x network-playback.sh
./network-playback.sh
```

Then capture:

```sh
/mnt/SDCARD/App/PocketStremio/tailscale/scripts/resource.sh
tail -n 80 /mnt/SDCARD/App/PocketStremio/experiments/logs/ffplay-network.log
```
