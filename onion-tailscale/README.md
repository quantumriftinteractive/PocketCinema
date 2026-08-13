# Onion Tailscale

A self-contained userspace-networking Tailscale app for OnionOS on the Miyoo
Mini Plus. This directory is intentionally independent from PocketStremio so it
can be extracted into a separate repository later.

Target device path:

```text
/mnt/SDCARD/App/Tailscale/
```

Layout:

```text
onion-tailscale/
  config.json
  launch.sh
  bin/                 # ignored Tailscale ARM binaries
  state/               # ignored node identity and PID
  logs/                # ignored runtime logs
  scripts/
  docs/
```

The app owns its daemon, socket, proxy, state, and logs. Applications using its
proxy are ordinary consumers and must not start, stop, or inspect this daemon.
The defaults are:

```text
socket:       /tmp/onion-tailscale/tailscaled.sock
HTTP proxy:   http://127.0.0.1:1055/
SOCKS5 proxy: 127.0.0.1:1055
hostname:     miyoo-onion
```

All runtime values can be overridden with the existing `TS_*` environment
variables in the scripts.

## Install Binaries

On a PC:

```powershell
.\scripts\install-from-pc.ps1
```

Or on the Miyoo:

```sh
./scripts/install-arm-static.sh
```

The downloaded archives and ARM binaries are intentionally ignored by git.

Deploy the independent app files and installed binaries from a PC with:

```powershell
.\scripts\deploy.ps1 -DeviceHost root@DEVICE_ADDRESS
```

Deployment never copies or changes `state/` or `logs/`.

## Operate

Launching **Apps -> Tailscale** starts or verifies the userspace daemon and
shows a concise result. Initial authentication remains an explicit operation:

```sh
cd /mnt/SDCARD/App/Tailscale/scripts
./start.sh
./login.sh
./status.sh
```

Stop it explicitly with `./stop.sh`. Detailed proof-of-concept results and
resource measurements are in [docs/poc.md](docs/poc.md).

## Existing PocketStremio State

Do not copy or move a live node state while its old daemon is running. The
currently authenticated state under PocketStremio remains in place until a
separate migration is physically tested. A later migration must stop the old
daemon, copy rather than delete the state, start this app against the copy,
verify tailnet identity and proxy traffic, and retain a rollback path.

No migration is performed merely by adding or deploying this subproject.

## Extract Later

Because all source, scripts, docs, and ignore rules live below this directory,
it can be split while retaining history with a tool such as `git filter-repo`:

```powershell
git filter-repo --path onion-tailscale/ --path-rename onion-tailscale/:
```

Run repository extraction only in a fresh clone, not in the working
PocketStremio checkout.
