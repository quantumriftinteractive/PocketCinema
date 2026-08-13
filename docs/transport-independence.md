# Transport Independence and Tailscale Extraction

## Decision

PocketStremio is an HTTP client, not a network-manager frontend. Its only
network settings are:

```text
SERVER_BASE=http://required-server-address:8755
PROXY=
```

`SERVER_BASE` is explicit and required. `PROXY` is empty for direct HTTP and may
contain a generic HTTP proxy URL. When direct mode is selected, the client
unsets inherited HTTP, HTTPS, and all-proxy variables. When proxy mode is
selected, it supplies both uppercase and lowercase HTTP/HTTPS variables to curl
and FFplay.

PocketStremio contains no Tailscale binary path, socket path, PID path, state
path, lifecycle command, status probe, hostname, or authentication behavior.
Server reachability errors remain provider-neutral.

## Standalone Subproject

All Tailscale-specific source is under `onion-tailscale/`. It targets:

```text
/mnt/SDCARD/App/Tailscale/
```

The folder includes independent OnionOS metadata and launcher, BusyBox daemon
scripts, ARM binary installers, deployment, ignore rules, operating guidance,
historical POC evidence, and local agent instructions. It has no PocketStremio
runtime dependency and can later be extracted with history using a path-filtered
fresh clone.

The launcher metadata follows the relative icon and `launch.sh` convention
checked against the
[OnionOS Package Manager app at commit `07505ea`](https://github.com/OnionUI/Onion/tree/07505ea58c7bba698d6b9220ff43946a43cac76b/static/build/App/PackageManager)
from January 21, 2026. The standalone app uses the confirmed
userspace-networking mode and loopback proxy listeners. PID files are validated
as numeric and matched against the expected daemon command before scripts report
or signal the process.

## State Safety

The live authenticated daemon remains under the legacy path:

```text
/mnt/SDCARD/App/PocketStremio/tailscale/
```

This milestone does not deploy the new Tailscale app and does not copy, move,
delete, reset, or reauthenticate that state. The standalone deployment script
copies tracked app files and locally installed ARM binaries only; it excludes
`state/` and `logs/`.

A future migration is separate work. It must stop the legacy daemon, copy state
with a rollback copy retained, start the standalone daemon, verify the same
tailnet identity and proxy traffic, and only then consider retiring the legacy
files. It must not run two daemons against one state or the same listener.

## Current Validation

Confirmed locally:

- no PocketStremio production or diagnostic code refers to Tailscale;
- direct and proxy branches use explicit environment handling;
- all changed BusyBox shell scripts pass `sh -n`;
- all changed PowerShell scripts pass the PowerShell parser;
- all 15 PocketStremio server tests pass;
- generated Tailscale binaries, downloads, node state, and logs remain ignored.

Still required before this milestone becomes **Confirmed**:

- run a headless direct-HTTP PocketStremio request on the Miyoo;
- write the current proxy as explicit PocketStremio config and run a remote
  headless request;
- launch PocketStremio from Apps and confirm normal controller UI and clean exit;
- verify the legacy daemon and authenticated state were not changed.

The standalone Tailscale app itself needs a later physical deployment and state
migration milestone. That work is intentionally not an acceptance requirement
for decoupling PocketStremio.
