# Onion Tailscale

A self-contained userspace-networking Tailscale app for OnionOS on the Miyoo
Mini Plus. This directory can be extracted into a separate repository.

Target device path:

```text
/mnt/SDCARD/App/Tailscale/
```

The app owns its daemon, controller UI, boot hook, socket, proxy, state, and
logs. Consumer applications only configure the local proxy and do not manage
the daemon.

```text
socket:       /tmp/onion-tailscale/tailscaled.sock
HTTP proxy:   http://127.0.0.1:1055/
SOCKS5 proxy: 127.0.0.1:1055
hostname:     miyoo-onion
```

## Controller UI

Open **Apps -> Tailscale**. The screen shows:

- Enabled or Disabled daemon state;
- the assigned Tailscale IPv4 address when connected;
- the companion-owned HTTP proxy endpoint for other applications;
- a locally generated QR code for the Tailscale admin machines page;
- Enable or Disable;
- Automatic enable on boot status and toggle;
- Connect account when the daemon has no authenticated identity;
- Refresh and Exit.

D-pad Up/Down navigates, A selects, and B exits. Runtime details are written to
`logs/app.log` without recording account verification URLs.

## First Account Connection

On a new installation:

1. Select **Enable**.
2. Select **Connect account**.
3. Scan the displayed QR code, or open its one-time
   `https://login.tailscale.com/...` URL, and approve the device.
4. Press **A** on the Miyoo to refresh.
5. The main screen shows the assigned Tailscale IP after approval.

No auth key or account token is stored by the UI. The pending verification URL
exists only under `/tmp/onion-tailscale/` and is removed after connection or
Disable. Tailscale persists the device identity in `state/tailscaled.state`. Do
not share or commit that file.

QR symbols are generated locally by the SDL selector. Login URLs are passed on
stdin, do not appear in process arguments, and are not sent to a third-party QR
service. The selector vendors Project Nayuki's compact MIT-licensed C encoder;
the Tailscale subproject remains independently buildable and deployable.

The equivalent shell operations are:

```sh
cd /mnt/SDCARD/App/Tailscale/scripts
./start.sh
./login.sh
./status.sh
```

## Automatic Enable

OnionOS 4.3 supports custom startup scripts in
`/mnt/SDCARD/.tmp_update/startup/`. The app installs only this owned hook:

```text
/mnt/SDCARD/.tmp_update/startup/onion-tailscale.sh
```

The hook starts the app-local daemon and then returns. It waits at most eight
seconds for the local Unix socket; it does not wait for Wi-Fi, internet access,
or a Tailscale peer. If the network is unavailable, `tailscaled` remains in the
background and retries connectivity. Disabling autostart removes the hook only
when it exactly matches the app's source copy; an unexpected file is reported
as a conflict and is not changed.

This uses OnionOS's extension directory and does not edit `runtime.sh` or other
core files. See the [OnionOS runtime startup loop](https://github.com/OnionUI/Onion/blob/main/static/build/.tmp_update/runtime.sh).

## Install and Deploy

Install the ignored static ARM Tailscale binaries on the PC:

```powershell
.\scripts\install-from-pc.ps1
```

Build the tracked SDL 1.2 selector from the repository toolchain:

```powershell
.\scripts\build-selector.ps1
```

Deploy application files and binaries:

```powershell
.\scripts\deploy.ps1 -DeviceHost root@DEVICE_ADDRESS
```

Deployment creates the app directories but never copies or changes `state/` or
`logs/`. Tailscale binaries, archives, node state, and logs remain ignored by
git; the small ARMv7 selector binary is tracked with its source.

## Existing State Migration

State adoption is deliberately separate from deployment. Stop every
`tailscaled` process, then copy an existing state with:

```sh
/mnt/SDCARD/App/Tailscale/scripts/migrate-state.sh /path/to/tailscaled.state
```

The command refuses to run while a daemon is active and refuses to overwrite an
existing destination. It copies rather than moves the source so rollback
remains possible. Start the standalone app, verify identity and proxy traffic,
and retain the old state until the migration has been proven across a reboot.

## Diagnostics

```sh
cd /mnt/SDCARD/App/Tailscale/scripts
./status.sh
./resource.sh
./test.sh http://TAILNET_SERVER/api/status
./stop.sh
```

Detailed historical networking measurements are in [docs/poc.md](docs/poc.md).
The controller app, migration, and autostart evidence is in
[docs/management-app.md](docs/management-app.md).

## Extract Later

Run repository extraction only in a fresh clone:

```powershell
git filter-repo --path onion-tailscale/ --path-rename onion-tailscale/:
```
