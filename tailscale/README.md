# PocketStremio Tailscale POC

This directory is a self-contained OnionOS/Miyoo Mini Plus Tailscale proof of concept.

It is intended to live at:

```text
/mnt/SDCARD/App/PocketStremio/tailscale/
```

The layout keeps binaries, state, logs, and scripts on the SD card:

```text
tailscale/
  bin/
    tailscale
    tailscaled
  state/
  logs/
  scripts/
    install-arm-static.sh
    install-from-pc.ps1
    start.sh
    stop.sh
    status.sh
    login.sh
    test.sh
    resource.sh
```

## Quick Start On Miyoo

From SSH:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
chmod +x *.sh
./start.sh
./login.sh
```

`login.sh` should print an authentication URL. Open that URL on another device, authenticate, then check the Tailscale admin console.

After login, test HTTP through the userspace proxy:

```sh
./test.sh http://<tailnet-pc-name-or-ip>:8754/api/status
```

Stop the daemon:

```sh
./stop.sh
```

See [../docs/tailscale.md](../docs/tailscale.md) for the full workflow and current compatibility notes.
