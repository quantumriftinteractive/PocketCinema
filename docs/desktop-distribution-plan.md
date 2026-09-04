# PocketCinema Server Desktop Distribution Plan

This document records the desktop distribution architecture and acceptance plan.
Milestone 21 is confirmed and Milestone 23 is Next. The initial macOS
development shell is implemented and automatically tested; it is not a packaged
artifact or a release claim.

## Milestone gate and sequencing

Implementation must not begin until all of the following are true:

1. `docs/roadmap.md` marks Milestone 21 **Confirmed**.
2. Its evidence records the complete controller-only acceptance path, including
   persisted audio and subtitle preferences, deterministic matching/no-match
   behavior, and removal of one Continue Watching item without affecting another.
3. Any device-facing criteria are supported by physical Miyoo Mini Plus evidence,
   not only source code or automated tests.

Milestone 21 is now **Confirmed**. Milestone 23 is the sole **Next** milestone,
and implementation began with the explicitly requested macOS development shell.
Milestone 22 retains its existing number and confirmed evidence. Desktop
Distribution is Milestone 23, ahead of Milestone 24 Offline Downloads and
Milestone 25 Unified PocketCinema UI.

## Current architecture

The existing PocketCinema server should remain the core implementation.

- `server/pocketcinema_server.py` is a dependency-free Python CLI using the
  standard library HTTP server. It already separates the bind address from the
  address advertised to the Miyoo.
- `server/manage-server.ps1` and `server/manage-server.sh` own background process
  lifecycle for source deployments. They reject duplicate managed instances,
  retain a PID, redirect logs, poll `/api/status`, and stop only the process whose
  identity they validate.
- `server/start-server.ps1` remains a foreground Windows development entry point.
- Persistent progress, probe cache, discovery identity, logs, and conversion
  scratch data currently live under ignored `server/data/`.
- The default Stremio account credential is the separate ignored
  `server/config/stremio_account.json`. It contains only the auth key and is
  written atomically with user-only permissions where supported.
- Optional addon manifests default to ignored
  `server/config/stream_addons.json`; an environment variable can override them.
- The default Stremio Service URL is `http://127.0.0.1:11470` when it runs on
  the PCServer host. M23 retains that secure default and validates a non-secret
  PCServer-only HTTP origin for a separately reachable service host; the Miyoo
  never contacts Stremio Service directly. Preserve the Windows Firewall block
  for the local service listener.
- FFprobe and FFmpeg accept explicit CLI paths. The Python core otherwise searches
  `PATH`; the Windows PowerShell managers additionally check Stremio's current
  per-user runtime location. The macOS manager discovers tools from `PATH`.
- The server already accepts the principal desktop settings as CLI inputs:
  `--host`, `--port`, `--public-host`, `--server-name`, `--network-name`,
  `--stremio-service-url`, `--ffprobe`, `--ffmpeg`, `--data-dir`,
  `--stremio-account-config`, and `--stream-addons`.

The current writable paths are source-tree-relative by default. That is suitable
for development but not for an installed or read-only application bundle.

## Smallest safe architecture

The desktop application should be a thin, cross-platform control layer around the
existing server entry point:

```text
Desktop UI
  -> validated non-secret preferences
  -> reusable lifecycle and interface-selection modules
  -> existing PocketCinema server core
  -> per-user data, logs, addon config, and separate account credential
```

The first implementation should use four testable layers:

1. **Configuration:** load defaults, validate values, recover safely from invalid
   JSON, and atomically save non-secret preferences.
2. **Host capabilities:** enumerate practical interface/address pairs, detect
   FFmpeg and FFprobe, and check Stremio Service reachability.
3. **Lifecycle:** start one owned server child, poll its health, capture sanitized
   diagnostics, and stop only that owned child. This layer must not search for and
   kill unrelated Python, FFmpeg, Stremio, or Tailscale processes.
4. **UI:** render status and controls, delegate all validation and lifecycle work,
   and keep blocking checks off the UI event loop.

### Stremio Service endpoint

Persist a non-secret endpoint as a URL or equivalent host/address-and-port
fields. Default it to `http://127.0.0.1:11470`; permit an explicit manual
override for a service on the same PC or another reachable host. Validate the
scheme, host/address, and port before launch, check PCServer-to-service
connectivity, and show a concise actionable unreachable or invalid-endpoint
state. This setting changes only the PCServer's upstream connection; it never
exposes Stremio Service to the Miyoo.

`tkinter.ttk` is the chosen initial UI because it is Python's standard
cross-platform Tk interface: it supports the required basic forms, status,
buttons, log view, and PNG application/window artwork without introducing a
large runtime dependency. It keeps the same Python implementation practical for
later macOS and Windows packaging, while PyInstaller can bundle Python and the
Tk runtime. Its availability and appearance must still be verified inside every
packaged build; this is a packaging decision, not permission to couple lifecycle
logic to widget code.

PyInstaller one-directory mode is the provisional first bundler. PyInstaller's
default one-folder output includes the Python interpreter and collected runtime
dependencies, while its documentation recommends validating one-folder behavior
before attempting one-file packaging. A one-directory layout also makes bundled
assets, notices, and support diagnostics inspectable. See the official
[PyInstaller operating-mode documentation](https://pyinstaller.org/en/stable/operating-mode.html)
and [Python Tkinter documentation](https://docs.python.org/3/library/tkinter.html).

The server must remain independently runnable from source. The PowerShell and
shell lifecycle managers remain developer/admin tools and should use the same
validation rules where practical, but the end-user app must not invoke
PowerShell.

## Initial macOS development shell (implemented, not yet physically confirmed)

The source entry point is `server/pocketcinema_desktop.py`. On the current Mac,
use the Tk-capable Homebrew Python:

```sh
python3 server/pocketcinema_desktop.py
```

The Homebrew `python-tk@3.14` development dependency supplies Tcl/Tk 9.0.4.
The Apple-supplied Tcl/Tk 8.5 runtime is dark-mode-incompatible on this Mac and
is not a supported development launcher; the shell retains a visible fallback
theme only for diagnostic compatibility. This is a local development
prerequisite observation, not a macOS packaging claim.

The implementation is deliberately split into testable layers:

```text
Tk desktop UI
  -> desktop config / capabilities / lifecycle modules
  -> one tracked owned PCServer child process
  -> existing PocketCinema Server CLI core
```

- `server/desktop/config.py` persists only non-secret settings atomically under
  the platform per-user application-data root. It does not migrate or copy
  account credentials or addon configuration.
- `server/desktop/capabilities.py` detects tools and probes the configured
  Stremio Service from the PCServer host. A configured remote HTTP origin is
  valid; the Miyoo never receives or contacts it.
- `server/desktop/lifecycle.py` starts a child through the stable
  `server.desktop.server_child` entry point, retains only that `Popen` handle,
  polls `/api/status`, and terminates only that child. It does not discover or
  kill arbitrary Python, FFmpeg, Stremio, or Tailscale processes.
- The desktop child receives per-user data, credentials, and private-addon
  paths rather than source-tree writable paths. It uses a private ephemeral
  loopback port for the open-media helper and emits a bounded, URL-sanitized
  log view. It enables the established bounded selectable-Matroska subtitle
  path by default, matching the source managers without changing the server
  core's opt-in default.
- The canonical `UI_concept/Icons/PocketCinema_Server_icon.png` is used directly
  as the Tk window/application icon; it is not modified. A derived `.icns` is
  deferred to macOS packaging and a derived `.ico` to Windows packaging.

### Desktop networking model correction (implemented and automated-tested)

The desktop shell distinguishes four concepts which must not be conflated:

1. **PCServer bind address** is the server-side socket choice. A wildcard bind
   such as `0.0.0.0` can serve more than one interface through one owned
   PCServer process.
2. **Local PocketCinema connection** is a concrete LAN address copied into the
   Miyoo's direct Local route.
3. **Tailscale / Remote PocketCinema connection** is an optional concrete
   tunnel address copied into the Miyoo's Remote route, which remains subject
   to the Miyoo's independently configured generic HTTP proxy.
4. **Stremio Service endpoint** is PCServer-only upstream configuration. It is
   never displayed as a Miyoo route or exposed to the Miyoo.

The main screen shows every concrete route supported by the selected bind mode,
with an individual Copy button. On macOS the shell reads ordinary OS interface
data to recognize an active LAN interface and, when an existing tunnel interface
has the tailnet address shape, an informational **Tailscale / Remote** route. It
does not call, authenticate, start, stop, configure, or read state from
Tailscale. If the remote route is absent, PocketCinema continues as a normal
Local-only server.

- **Automatic / Local network** binds the selected Local address and displays
  all usable detected Local routes only. It neither displays nor enables a
  Tailscale / Remote route; users choose **All interfaces** when that route is
  intended.
- **All interfaces** binds `0.0.0.0` once and displays both Local and optional
  Tailscale / Remote routes; it never displays the wildcard itself.
- **Custom address** remains available for unusual deployments and displays only
  its explicit Custom route.
- The child receives all displayed routes as approved device hosts. Returned
  play, subtitle, and fixture URLs stay on the approved Host route used by the
  request, so Local and Remote clients do not switch routes mid-playback.
- UDP discovery on `8754` remains Local-only and advertises its one preferred
  Local route. Remote setup continues to use an explicitly configured URL and
  generic proxy; it does not depend on discovery.
- Advanced Settings retains manual route override, network label, and
  FFmpeg/FFprobe paths. Version-1 stored settings load as Custom plus manual
  address override, preserving their existing behavior without rewriting them.

The connection area is a dynamic series of route-label, concrete-URL, and
individual Copy rows. It immediately re-evaluates the selected listen mode,
port, and custom address while the desktop is stopped. The concise Status row
reports only None, 1, or N available; it does not repeat the URLs. The normal
Media tools section reports Available or Missing. Start and Stop are state-aware
primary actions; Restart, connection checking, copying, and manual overrides
are secondary.

### Focused macOS Local acceptance (physically confirmed)

On 2026-09-04, the desktop shell managed one PCServer on the development Mac
with **Automatic / Local network** and port `8757`. It displayed the concrete
Local LAN and detected Tailscale / Remote routes without Advanced Settings. A
Miyoo Mini Plus on that Local LAN reached the managed PCServer (the request log
showed a same-subnet `192.168.0.x` Miyoo source) and completed:

- `GET /api/status` — 200
- `GET /api/addons?refresh=1` — 200
- `POST /api/account/link` — 201
- `GET /api/account?poll=1` — 200
- a refreshed addon listing — 200
- `GET /api/search?q=friday` — 200

This is a focused Local desktop-management and account-link/search acceptance,
not a claim that this Mac reached the separately hosted Stremio Service. That
service is intentionally localhost-contained on the gaming PC, so the Mac's
configured Remote service origin was expected to report unreachable. No
listener binding, firewall rule, or network-provider state was changed. The
desktop-managed Tailscale / Remote PocketCinema route was displayed and
detected, but remains physically unexercised.

The PCServer status diagnostic logs the first Stremio Service failure, suppresses
an identical repeated failure, and logs a reason change, recovery, or later
failure after recovery. `/api/status` and the desktop's explicit connection
check retain their existing reachable/unreachable behavior; the latter still
provides fresh visible feedback without changing PCServer lifecycle behavior.

### Desktop subtitle startup parity (implemented; physical retest pending)

The desktop lifecycle now passes `--enable-matroska-subtitles` for its owned
PCServer child, matching the established macOS and Windows source managers.
This scoped M23 correction was required because the development FFmpeg build
does not provide the normal subtitle burn-in filter: without the selectable
Matroska server capability, a Miyoo selectable-Matroska request falls back to
normal discovery and returns no subtitle tracks before contacting configured
subtitle providers. It does not change provider handling,
stream preflight/filtering, cache contents, subtitle limits, conversion logic,
or the server-core flag default. A focused Miyoo acceptance remains required:
confirm the desktop child's status reports selectable Matroska subtitles, then
use the existing Miyoo subtitle mode on one known title and confirm tracks are
discovered.

### Regression impact matrix for the initial shell

| Changed area | Classification | Required verification | Inherited evidence and reason |
| --- | --- | --- | --- |
| Tk UI, preferences, capability checks, icon | Desktop-only | desktop construction and configuration tests; focused macOS UI check | M21/M22 browsing, playback, subtitle, conversion, and controller evidence is unchanged because no Miyoo code or media path changed. |
| Multi-route endpoint derivation and owned-child arguments | Server lifecycle/configuration | interface parsing, Local/Remote route, absent-remote, manual-compatibility, start/health/stop, and focused Miyoo search tests | Existing resolver, conversion, subtitle, controller, and transport-client code is unchanged. |
| Approved Host route for returned device URLs | Existing PCServer configuration | Local/Remote URL-selection and unapproved-Host tests; existing API/play/Range suite | A request keeps its existing route only; opaque stream handling and media pipeline behavior are unchanged. |
| Stremio Service origin validation | Existing PCServer configuration modified | URL validation and full server suite; configured-endpoint status check | The secure local default and opaque Local Files handling remain covered by existing tests. Historical account/playback evidence remains valid because its resolver, proxy, conversion, and client paths were not changed. |
| Stremio Service status diagnostic | Server logging only | failure-transition/recovery unit test; existing status and lifecycle suites | Status payloads, upstream access, device routes, and lifecycle ownership are unchanged; M21/M22 evidence remains inherited. |
| Desktop selectable-Matroska startup parity | Desktop child lifecycle/configuration | desktop command/status test and one focused Miyoo subtitle-discovery check | Existing M22 selectable-subtitle evidence is inherited: server-core defaults, resolver, conversion, client, and bounded track behavior are unchanged. |
| Dynamic connection list | Desktop configuration/UI | mode, route filtering, port/custom-address update, concise-status, and lifecycle tests | The PCServer API, discovery protocol, Stremio boundary, Tailscale independence, and M21/M22 media behavior are unchanged. |

The focused Local desktop-management and Miyoo `friday` connection/search smoke
is complete and remains inherited. The remaining focused physical check is the
new route-list presentation (Automatic Local-only, All interfaces complete,
Custom explicit) plus the separately displayed Tailscale / Remote PocketCinema
route, if that topology is to be supported in this development configuration.
It does not require rerunning the M21 or M22 playback, subtitle, or conversion
matrices.

## Persistent paths and privacy boundary

Use platform APIs to resolve a per-user root, with these intended locations:

```text
Windows: %APPDATA%\PocketCinema\
macOS:   ~/Library/Application Support/PocketCinema/
```

Keep ordinary preferences separate from credentials and runtime data:

```text
PocketCinema/
  config.json                  non-secret desktop preferences
  credentials/
    stremio_account.json       auth key; restricted permissions
  config/
    stream_addons.json         private addon URLs/tokens; not normal diagnostics
  data/
    continue_watching.json
    probe_cache.json
    discovery_instance_id
    transcode/
  logs/
```

Migration must be explicit and conservative. A desktop build must not silently
copy account credentials or private addon configuration from a repository
checkout. If migration is later offered, it must show the exact source and
destination, preserve the original, restrict destination permissions, avoid
printing values, and require user confirmation.

Normal preferences should initially contain only non-secret fields, for example:

```json
{
  "schema_version": 2,
  "server_name": "PocketCinema Server",
  "listen_mode": "automatic",
  "listen_address": "127.0.0.1",
  "listen_port": 8755,
  "advertised_mode": "automatic",
  "advertised_address": "127.0.0.1",
  "network_name": "Local",
  "stremio_service_url": "http://127.0.0.1:11470",
  "ffmpeg_path": null,
  "ffprobe_path": null
}
```

The exact schema should be finalized against implementation tests. Do not store
auth keys, addon tokens, or upstream media/subtitle URLs in this file, process
arguments, logs, release archives, or ordinary diagnostic output.

## Bind and PocketCinema connection addresses

The UI must treat the bind socket and every device route as different values:

- **Listen address:** the local address passed to `--host`.
- **Preferred Local address:** the address passed to `--public-host` for Local
  discovery and fallback compatibility.
- **Additional device hosts:** optional approved Local/Remote addresses passed
  to the server for route-preserving returned URLs.
- **PocketCinema connections:** copyable concrete Local and optional Remote
  URLs. They are not separate PCServer instances.
- **Stremio Service endpoint:** a separate PCServer-only upstream URL.

Interface enumeration returns stable records rather than presentation strings,
including interface identity, address, and operational state where the platform
exposes it. Filter loopback, link-local, multicast, unspecified, inactive, and
duplicate addresses. The shell uses only host interface data; it does not inspect
provider processes or state. On platforms where a tailnet tunnel is not safely
recognizable, it simply omits the optional Remote route rather than guessing.

Safe initial behavior:

- New desktop profiles default to Automatic / Local network, which chooses a
  usable Local address and additionally exposes the detected Remote route when
  one is available. Existing stored profiles retain their prior explicit
  addresses as Custom/manual settings.
- Show each Local/Remote connection with its concrete address and Copy action.
- Never display `0.0.0.0` as a Miyoo URL; show only the concrete routes it
  serves.
- Retain Custom for routed HTTP(S) deployments.
- Revalidate the selected local address before startup and report when it is no
  longer assigned.
- Continue warning that PCServer has no public-facing authentication and is supported
  only on a trusted LAN, tailnet/VPN, or authenticated gateway.

## Desktop UI scope

The initial control panel should expose only:

- PCServer name;
- listening interface/address and port;
- advertised Miyoo address;
- Stremio Service endpoint (editable address/host and port or URL, default and
  manual override) and reachable/unreachable/invalid state;
- FFmpeg and FFprobe detected, missing, or manually configured state;
- Stopped, Starting, Running, or Error server state;
- Start, Stop, and Restart controls;
- the actual Miyoo URL and a Copy action;
- a restrained Open Logs action if it can preserve sanitized output.

Port validation must cover type/range, collisions with the open-media and
discovery ports, and an occupied bind target. Startup errors should be mapped to
concise categories while the sanitized log retains enough context to diagnose a
failure.

Tray behavior, login startup, automatic updates, playback telemetry, resource
graphs, connected-device lists, automatic remote discovery, and remote
configuration remain deferred.

## Required refactoring before packaging

No media pipeline rewrite is needed. The implementation slice should instead:

1. Extract server argument construction and startup into an importable entry
   point so a frozen child can be launched without assuming a repository path.
2. Make all writable paths explicit and direct them to the per-user root.
3. Extract cross-platform configuration, port validation, executable detection,
   interface enumeration, health polling, and owned-child lifecycle into modules
   with no GUI dependency.
4. Preserve CLI defaults and source workflows unless an installed-app path is
   deliberately supplied.
5. Ensure the packaged child receives no credential, addon URL/token, or media
   URL in its process arguments.
6. Decide whether the desktop UI owns a separate server executable or invokes an
   importable server process entry. Prefer the design with the clearest owned-PID
   and clean-shutdown behavior in packaged tests.

## Packaging sequence

### Windows first

1. Pin Python, PyInstaller, Tcl/Tk, and build-tool versions.
2. Produce a one-directory, windowed build from a clean Windows environment.
3. Include only required application code/assets and third-party notices. Do not
   include development configs, logs, data, media, credentials, or ignored files.
4. Do not bundle FFmpeg/FFprobe until the exact build provenance, configuration,
   redistribution license, source/notice obligations, and security-update process
   are approved. Support automatic and manual external detection first.
5. Test the extracted directory before selecting an installer technology.
6. Add code signing and installer/removal behavior as explicit release gates.

### macOS preparation

Build macOS artifacts on macOS. Validate Apple Silicon first, then decide whether
separate Intel and Apple Silicon builds are safer than a universal2 bundle. The
PyInstaller documentation supports architecture selection when the Python build
and collected libraries supply the required slices. Public distribution also
requires Developer ID signing, hardened-runtime review, notarization, ticket
stapling, and testing of the downloaded artifact under Gatekeeper. See
[PyInstaller's macOS notes](https://pyinstaller.org/en/stable/feature-notes.html)
and [Apple's notarization guidance](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution).

Signing and notarization may be absent from an internal development build, but
the artifact must say so and cannot be called release-ready.

## Automated verification plan

Keep GUI geometry out of core tests. Add deterministic tests for:

- default configuration and platform-specific roots;
- atomic save/reload and schema migration;
- malformed JSON and invalid field recovery without overwriting the bad file;
- port type/range/collision validation;
- interface filtering, deduplication, disappearing addresses, wildcard bind, and
  advertised-address selection;
- FFmpeg/FFprobe explicit-path and `PATH` detection, missing tools, and capability
  checks;
- Stremio Service default, manual-override, reachable/unreachable/invalid
  endpoint state;
- owned child start, health timeout, duplicate instance, port-in-use, stop,
  restart, crash, and stale metadata handling;
- proof that unrelated processes are never selected for termination;
- writable data/config/credential paths passed to the existing server;
- sanitized primary errors and logs.

Run the existing Python compilation and server suites unchanged, plus packaged
smoke tests for `/api/status`, search, metadata, streams, play-session creation,
and byte-range media behavior.

## Physical and release acceptance

Implementation and automated tests are not physical confirmation. Acceptance
requires a clean supported Windows PC with no repository checkout, Python,
PowerShell workflow, or manually prepared environment variables to:

1. install or extract the actual release artifact;
2. launch the control panel;
3. persist PCServer name, interface, port, and Stremio Service endpoint settings;
4. detect or manually configure FFmpeg and FFprobe;
5. start PCServer and show the correct device-reachable URL;
6. connect a real Miyoo Mini Plus from OnionOS Apps;
7. pass direct, converted/downscaled, subtitle, Continue Watching, Resume, and
   Play from Start regressions;
8. restart the desktop app/server and retain intended configuration and PCServer data;
9. handle invalid port, invalid or unreachable Stremio Service endpoint, missing
   FFmpeg/FFprobe, a disappeared interface, and startup failure cleanly;
10. stop only the managed PCServer process and remove the application without deleting
    unrelated or user-owned data unexpectedly;
11. confirm that credentials, addon URLs/tokens, upstream URLs, development files,
    and private logs are absent from the release and normal diagnostics.

Equivalent clean-artifact acceptance is required before a macOS build is called
supported. Release evidence must distinguish designed, implemented, automated,
packaged, physically confirmed, signed/notarized, and release-ready states.
