# Operational Resilience

Milestone 10 makes the working prototype easier to operate and verifies that
expected server and network failures do not strand OnionOS or damage persistent
state.

## Confirmed Results

The following behavior was confirmed on August 13, 2026:

- `/api/status` reports server version and uptime, bounded play-session and
  probe-cache usage, progress item count, TTLs, and persistence behavior.
- A managed server restart removed all in-memory play sessions. An old play URL
  returned `404` after restart, as intended.
- The persistent probe cache and Continue Watching state survived that restart.
  In the measured run, sessions changed from one to zero while seven probe-cache
  records and one progress record remained available.
- A deliberately stale PID file was discarded and the server started normally.
- Automated tests confirmed that malformed probe-cache and Continue Watching
  JSON is treated as empty state and can be replaced with valid state.
- A Miyoo headless dry run loaded an app-local config, reached server version
  `0.8-operational-resilience-poc` through the Tailscale proxy, searched the
  local series fixture, and parsed its seasons and episodes.
- A headless request to an unreachable server returned nonzero with the specific
  `Gaming PC server unavailable` error. It left no UI, selector, FFplay, or
  infoPanel processes and no playback temporary markers.
- The same unreachable-server case was launched physically from the OnionOS
  Apps menu. The Miyoo displayed `Gaming PC server unavailable`; SSH inspection
  after exit found OnionOS `MainUI` active and no stale PocketStremio processes
  or temporary files.
- After removing the temporary failure config, the Miyoo immediately reached
  the normal server through `127.0.0.1:1055` again. Tailscale state was not
  changed.

The Apps-context unreachable-server behavior was intentionally improved and
reconfirmed on August 22, 2026. Startup no longer waits through the synchronous
readiness retry loop before creating SDL. The home menu appears immediately,
its first row is backed by an app-local status file, and a bounded background
probe changes that row between `Server: Connecting...`, `Server: Connected`,
and `Server: Offline` without leaving the menu. With the configured Mac PSS
stopped, the Miyoo displayed the menu directly at `Server: Offline` with no
black screen. Selecting the offline row opened Settings, scanning found the
still-running Windows PSS, and selection plus an app restart preserved the
Windows `SERVER_BASE`. The monitor and status files are app-local temporary
state and are removed on exit.

Playback diagnostics were tightened after the later Settings launch overwrote
the log from an earlier failed playback attempt. Startup now retains at most
the final 256 KiB of the preceding UI log as `pocketstremio-ui.previous.log`.
FFplay failures are reduced to a concise sanitized category for both the log
and the device message, including PSS connectivity, HTTP rejection, provider
failure, interrupted media, invalid format, unsupported codec, audio startup,
and missing video readiness. The platform server managers also launch Python
unbuffered so redirected PSS logs are useful before shutdown. These diagnostic
paths are implemented but their individual device messages remain pending
physical failure tests.

The first diagnostic field run reproduced the prior symptom with an *Alien:
Covenant* converted stream. PSS accepted playback setup, but FFplay received
`502 Bad Gateway` before parsing any media and the Miyoo displayed `PSS or the
stream provider returned an error`. The identical opaque stream without a
subtitle then returned `200` and delivered approximately 4.7 MB over a bounded
60-second request. The selected subtitle endpoint returned `200`, and the same
stream-plus-subtitle combination subsequently delivered approximately 4.2 MB
over 60 seconds. This isolates the observed failure to a transient subtitle or
conversion-startup failure rather than Miyoo decoding, audio, display geometry,
or a permanently invalid stream. The exact inner exception was not retained by
the prior server process. PSS now emits sanitized stage-specific HTTP reasons
for subtitle download, conversion launch, and missing conversion output; their
Apps-context messages remain pending physical failure tests.

The physical test exercised a PocketStremio server failure while the configured
local proxy remained healthy. PocketStremio no longer manages that proxy's
provider; provider startup and authentication are separate operational scope.

## Server Lifecycle

Use the manager for the normal background server process:

```powershell
$env:POCKETSTREMIO_HOST = "TAILSCALE_IP_OR_INTERFACE_ADDRESS"
.\server\manage-server.ps1 start
.\server\manage-server.ps1 status
.\server\manage-server.ps1 restart
.\server\manage-server.ps1 stop
```

The manager stores its PID and redirected logs under ignored `server/data/`,
rejects a second managed instance, detects a healthy unmanaged instance on the
configured address, removes stale PID files, waits for `/api/status`, and starts
the process with a hidden window. Address, port, public host, localhost Stremio
Service URL, open-media addon port, and ffprobe path remain command-line
parameters.

`server/start-server.ps1` remains the foreground development entry point.

## Miyoo Configuration

The production client reads this optional file:

```text
/mnt/SDCARD/App/PocketStremio/config/pocketstremio.conf
```

Create it from `client/miyoo/pocketstremio.conf.example`. Supported settings are:

```text
SERVER_BASE=http://server-address:8755
# Empty for direct HTTP; otherwise an HTTP proxy URL.
PROXY=
DEFAULT_QUERY=big buck bunny
AUTO_FIRST=0
```

Environment variables `POCKETSTREMIO_SERVER`, `POCKETSTREMIO_PROXY`,
`POCKETSTREMIO_DEFAULT_QUERY`, and `POCKETSTREMIO_AUTO_FIRST` take precedence.
Unknown settings and invalid URL or boolean values fail visibly before the UI
starts. The deployment script never overwrites the real config.

## Repeatable Deployment

Deploy the tracked OnionOS app files from Windows with:

```powershell
.\scripts\deploy-miyoo.ps1 -DeviceHost root@DEVICE_ADDRESS
```

The script creates only app-local directories, copies the launch scripts,
client, helper binaries, and config example, restores executable modes, and
parses the deployed shell entry points. It deliberately leaves the real client
config, logs, networking-provider binaries and state, and all OnionOS core files
alone.

## Reproducible Selector Build

With the ignored ARM GNU compiler and Miyoo SDL sysroot installed under the
existing `.tmp/` paths, run:

```powershell
.\scripts\build-miyoo-selector.ps1 -VerifyCommitted
```

The build uses `-Wall -Wextra -Werror -O2` and SDL 1.2. The verified output and
committed ARMv7 selector both had SHA-256:

```text
E1CB375F08DE7867727B373B19777471D9345CE79D5DD5DC36FC82059D13B3BF
```

The toolchain and sysroot remain ignored development inputs and are not bundled
with the repository.

## Automated Coverage

The server suite contains 15 tests covering status details, search and metadata,
series browsing, streams, compatibility classification and cache behavior,
session expiry and eviction, play and subtitle proxy opacity, Range forwarding,
Continue Watching persistence, addon normalization, and malformed-state
recovery.

Validated commands:

```powershell
python -m py_compile server/pocketstremio_server.py
python -m unittest server.test_pocketstremio_server -v
.\scripts\build-miyoo-selector.ps1 -VerifyCommitted
```

All changed shell files passed `sh -n`, and all PowerShell entry points passed
the PowerShell parser.
