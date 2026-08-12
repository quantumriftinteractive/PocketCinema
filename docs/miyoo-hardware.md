# Miyoo Mini Plus Hardware Notes

Confirmed from the target device over SSH:

```text
Kernel: Linux 4.9.84
Architecture: armv7l
CPU: 2x ARMv7 Processor rev 5, SStar SoC
RAM: about 100 MB total
Swap: 127 MB
TUN: /dev/net/tun does not exist
FFplay: /mnt/SDCARD/.tmp_update/bin/ffplay
```

## Implications

- Standard Linux Tailscale networking expects `/dev/net/tun`; that path is absent on this device.
- The current proof of concept must use Tailscale userspace networking unless a later device test proves TUN can be created safely.
- Persistent state should stay on the SD card, not under `/var/lib`, `/etc`, or other OnionOS system paths.
- Unix sockets should not be placed on the SD card filesystem. The first daemon start failed with `bind: operation not permitted` for `state/tailscaled.sock`; the scripts now place the transient socket under `/tmp/pocketstremio-tailscale/`.
- The device clock was observed as `2026-05-31` during testing, while the actual date was `2026-08-12`. Tailscale login failed TLS validation until the runtime clock was corrected with `date -s`.
- Authenticated userspace `tailscaled` used about 32 MB RSS after a small HTTP proxy test, with `VmSwap: 0 kB`.
- The shell JSON client used about 1.5 MB RSS while held open for measurement.
- A SSH-launched FFplay network probe against a 640x360 H.264/AAC MP4 used about 16 MB RSS for `ffplay`; full interactive playback was not proven because FFplay blocked at virtual-terminal activation.

## First Device Test

After copying this repository's `tailscale/` directory to `/mnt/SDCARD/App/PocketStremio/tailscale/` and installing binaries, run:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
chmod +x *.sh
./start.sh
./resource.sh
```

Return the full output plus the last 40 lines of:

```sh
tail -n 40 /mnt/SDCARD/App/PocketStremio/tailscale/logs/tailscaled.log
```
