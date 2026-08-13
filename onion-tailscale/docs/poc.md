# Tailscale Userspace POC

> Historical evidence: these measurements were collected while Tailscale lived
> under PocketStremio and used `miyoo-pocketstremio` paths and names. The current
> standalone target and operating commands are documented in
> [../README.md](../README.md). The authenticated legacy state has intentionally
> not been migrated yet.

This milestone tests only secure HTTP communication from the Miyoo Mini Plus to another device on the user's tailnet. Stremio integration, catalogs, torrent handling, transcoding, and UI work are intentionally out of scope.

## Compatibility Research

Checked on August 12, 2026:

- Tailscale's current stable package page lists version `1.102.2` static tarballs for `386`, `amd64`, `arm`, `arm64`, and other architectures. The `arm` tarball is the candidate for the Miyoo's `armv7l` CPU.
- Tailscale documents static binaries for Linux distributions not covered by package-manager installs. The static tarballs contain `tailscale`, `tailscaled`, and systemd files.
- The static package page explicitly describes those tarballs as static builds. That reduces libc risk, but the Miyoo still needs to prove the ARM binary can execute on its kernel/userland.
- Tailscale's Linux install docs say normal Linux operation requires the `tun` kernel module. The Miyoo lacks `/dev/net/tun`, so normal TUN mode is expected to fail.
- Tailscale's userspace networking docs confirm `tailscaled --tun=userspace-networking`.
- Userspace mode can expose a SOCKS5 proxy and an outbound HTTP proxy. SOCKS5 is documented as available since Tailscale v1.8; HTTP proxy support since v1.16.
- Userspace networking is proxy based. Normal applications will not automatically reach tailnet IPs unless they use the local SOCKS5 or HTTP proxy.
- Tailscale userspace/netstack mode supports TCP and UDP at layer 4. It is not equivalent to full kernel layer-3 networking.

Unknown until tested on the Miyoo:

- Whether authenticated userspace proxy traffic is stable over time.
- Whether `curl`, `wget`, or another proxy-capable HTTP client is present on the Miyoo.

Confirmed on device:

- `tailscale_1.102.2_arm.tgz` launches on OnionOS/Linux `4.9.84` ARMv7.
- `tailscaled --tun=userspace-networking` starts successfully after moving the Unix socket to `/tmp`.
- Initial unauthenticated idle memory was about 24 MB RSS, with `VmSwap: 0 kB`.
- The Miyoo clock was behind the current date, causing TLS validation to fail with `x509: certificate has expired or is not yet valid`. The clock must be correct before `tailscale up`.
- After authentication, the Miyoo appeared as `miyoo-pocketstremio` with Tailscale IPv4 `100.97.46.26`.
- HTTP through the local userspace proxy succeeded from the Miyoo to `desktop-gaming` at `100.85.171.67:8754`: `proxy_http_code=200`, `size=10479`.
- A direct non-proxied HTTP request to the same Tailscale IP failed with `direct_http_code=000`, which is expected without a TUN interface.
- After the HTTP test, `tailscaled` used about 32 MB RSS with `VmSwap: 0 kB`.
- During the JSON client POC, `tailscaled` used about 32 MB RSS with no process swap.
- During the FFplay network probe, `tailscaled` used about 34 MB RSS and 872 kB process swap; system swap usage was about 8 MB.

Primary references:

- Tailscale userspace networking: https://tailscale.com/docs/concepts/userspace-networking
- Tailscale Linux install and static binaries: https://tailscale.com/docs/install/linux
- Tailscale stable packages: https://pkgs.tailscale.com/stable/
- Kernel vs userspace/netstack behavior: https://tailscale.com/docs/reference/kernel-vs-userspace-routers

## Installation Layout

Target SD-card path:

```text
/mnt/SDCARD/App/PocketStremio/tailscale/
```

Repository layout:

```text
tailscale/
  bin/
  state/
  logs/
  scripts/
  README.md
```

Runtime files:

- `bin/tailscale`: Tailscale CLI.
- `bin/tailscaled`: Tailscale daemon.
- `state/tailscaled.state`: persistent node state.
- `/tmp/pocketstremio-tailscale/tailscaled.sock`: transient local CLI socket. This cannot live on the SD card because the Miyoo's SD card filesystem rejected Unix socket creation with `bind: operation not permitted`.
- `state/tailscaled.pid`: daemon PID file created by `start.sh`.
- `logs/tailscaled.log`: daemon stdout/stderr.

## Install Binaries From A PC

On Windows PowerShell from the repository root:

```powershell
.\tailscale\scripts\install-from-pc.ps1
```

This downloads `tailscale_1.102.2_arm.tgz`, verifies its SHA256 file from Tailscale's package server, and copies `tailscale` and `tailscaled` into `tailscale/bin/`.

Then copy the whole `tailscale/` directory to the Miyoo:

```text
/mnt/SDCARD/App/PocketStremio/tailscale/
```

## Install Binaries On The Miyoo

If the Miyoo has working DNS/TLS and either `curl` or `wget`:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
chmod +x *.sh
./install-arm-static.sh
```

If direct download fails, download on the PC and copy the archive to the Miyoo, then run:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
./install-arm-static.sh /path/to/tailscale_1.102.2_arm.tgz
```

## Start Userspace Tailscale

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
./start.sh
```

The script launches:

```sh
tailscaled \
  --tun=userspace-networking \
  --state=/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state \
  --socket=/tmp/pocketstremio-tailscale/tailscaled.sock \
  --socks5-server=127.0.0.1:1055 \
  --outbound-http-proxy-listen=127.0.0.1:1055
```

Both proxy listeners intentionally use loopback only. Persistent state remains on the SD card; only runtime socket/cache files go under `/tmp`.

## Authentication

Do not store auth keys or secrets in this repository.

First verify the Miyoo clock is close to the real date:

```sh
date
```

If the clock is wrong, set it for the current session before login:

```sh
date -s '2026-08-12 18:50:00'
```

This changes runtime system time, not project files. OnionOS time persistence still needs a separate decision.

After `start.sh` succeeds:

```sh
./login.sh
```

Open the printed URL from another device and authenticate the Miyoo into the tailnet. Then verify:

```sh
./status.sh
```

Also check the Tailscale admin console's Machines page.

## HTTP Connectivity Test

Because there is no TUN device, direct commands such as `curl http://100.x.y.z:8754/...` may fail unless they use the userspace proxy.

On the gaming PC, run a tiny HTTP server bound to its Tailscale interface or all interfaces. For example, from a directory containing a test file:

```powershell
python -m http.server 8754
```

From the Miyoo:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
./test.sh http://<gaming-pc-tailnet-name-or-100.x-ip>:8754/
```

`test.sh` sets `HTTP_PROXY=http://127.0.0.1:1055/` for `curl` or `wget`.

Success means:

```text
Miyoo HTTP client
  -> local HTTP proxy on 127.0.0.1:1055
  -> tailscaled userspace networking
  -> Tailscale
  -> gaming PC HTTP server
```

Validated result:

```text
Miyoo 100.97.46.26
  -> HTTP_PROXY=http://127.0.0.1:1055/
  -> tailscaled userspace networking
  -> desktop-gaming 100.85.171.67:8754
  -> HTTP 200, 10479 bytes
```

The direct control request without proxy returned no HTTP status, confirming regular applications must opt into the proxy path in this no-TUN setup.

## Resource Usage

Run:

```sh
./resource.sh
```

Capture:

- total/free memory
- swap total/free
- `tailscaled` RSS
- `tailscaled` VmSwap
- process list line for `tailscaled`

Then start FFplay separately and run `resource.sh` again while both are active. The POC is only viable if the system avoids heavy swapping and remains responsive.

## Future PocketStremio Traffic

Recommended next approach:

- Make the future Miyoo app's HTTP client proxy-aware.
- Prefer HTTP proxy support for simple REST API calls.
- Keep SOCKS5 available for clients that support it better than HTTP proxying.
- Avoid assuming tailnet IPs work as normal routes on the Miyoo.

FFplay needs a separate experiment. Things to test later:

- Whether this OnionOS `ffplay` build honors `http_proxy`.
- Whether FFmpeg/FFplay options such as protocol-specific HTTP proxy settings are compiled in.
- Whether a tiny local relay should accept `http://127.0.0.1:<port>/video` from FFplay and fetch the upstream stream through Tailscale's proxy.

The local relay is likely the most controllable design for video, but it should not be chosen until FFplay's proxy behavior is tested on-device.

On-device FFplay proxy findings:

- `curl` can fetch the hosted MP4 through `HTTP_PROXY=http://127.0.0.1:1055/`.
- `ffplay` launched with the same proxy environment reached the MP4 and identified H.264/AAC streams.
- The Python POC server needed HTTP byte-range support for MP4 seeking.
- The SSH-launched `ffplay` process blocked at `VT_WAITACTIVE`, so full interactive framebuffer playback still needs to be run from the OnionOS/app context rather than SSH.

## Troubleshooting

Check the daemon log:

```sh
tail -n 80 /mnt/SDCARD/App/PocketStremio/tailscale/logs/tailscaled.log
```

Common issues:

- `Permission denied`: run `chmod +x tailscale/scripts/*.sh tailscale/bin/tailscale tailscale/bin/tailscaled`.
- `not found` when the file exists: the ARM binary may be incompatible with the Miyoo userland/kernel, or the filesystem mount may prevent execution.
- Proxy test hangs: confirm the gaming PC server is running and reachable from another Tailscale device.
- `tailscale status` cannot connect: confirm `start.sh` is still running and that `/tmp/pocketstremio-tailscale/tailscaled.sock` exists.

## First Test To Run

Run this on the Miyoo after copying `tailscale/` and installing binaries:

```sh
cd /mnt/SDCARD/App/PocketStremio/tailscale/scripts
chmod +x *.sh
../bin/tailscaled --version
../bin/tailscale version
./start.sh
./resource.sh
tail -n 40 ../logs/tailscaled.log
```

Return the full output. That confirms whether the ARM binary launches, whether userspace mode starts, and the initial memory footprint.
