# PocketStremio Server Desktop Distribution Plan

This document queues the desktop distribution work that should begin immediately
after Milestone 21 is completed. It records a release architecture and acceptance
plan only; no desktop implementation or packaged artifact exists yet.

## Milestone gate and sequencing

Implementation must not begin until all of the following are true:

1. `docs/roadmap.md` marks Milestone 21 **Confirmed**.
2. Its evidence records the complete controller-only acceptance path, including
   persisted audio and subtitle preferences, deterministic matching/no-match
   behavior, and removal of one Continue Watching item without affecting another.
3. Any device-facing criteria are supported by physical Miyoo Mini Plus evidence,
   not only source code or automated tests.

At the time this plan was written, Milestone 21 is **Next** and its acceptance
criteria are incomplete. Milestone 23 therefore remains planned and queued.
Milestone 22 retains its existing number and confirmed evidence. Desktop
Distribution is Milestone 23, ahead of Milestone 24 Offline Downloads and
Milestone 25 Unified PocketStremio UI.

## Current architecture

The existing PocketStremio server should remain the core implementation.

- `server/pocketstremio_server.py` is a dependency-free Python CLI using the
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
- The default Stremio Service URL is `http://127.0.0.1:11470`. The server must
  continue accessing it through loopback only.
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
  -> existing PocketStremio server core
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

`tkinter.ttk` is the provisional UI choice because it is Python's standard
cross-platform Tk interface and avoids adding a large application framework. Its
availability and appearance must be verified inside each packaged build; this is
a packaging decision, not permission to couple lifecycle logic to widget code.

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

## Persistent paths and privacy boundary

Use platform APIs to resolve a per-user root, with these intended locations:

```text
Windows: %APPDATA%\PocketStremio\
macOS:   ~/Library/Application Support/PocketStremio/
```

Keep ordinary preferences separate from credentials and runtime data:

```text
PocketStremio/
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
  "schema_version": 1,
  "server_name": "PocketStremio Server",
  "listen_address": "127.0.0.1",
  "listen_port": 8755,
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

## Listen and advertised addresses

The UI must treat these as different values:

- **Listen address:** the local address passed to `--host`.
- **Advertised address:** the device-reachable address passed to `--public-host`
  and displayed for Miyoo configuration.

Interface enumeration should return stable records rather than presentation
strings, including interface identity, display name, address, address family,
and operational state where the platform exposes it. Filter out loopback,
link-local, multicast, unspecified, and duplicate addresses from normal remote
choices. Do not infer a transport provider merely from an address range or
process inspection. A user-facing label such as LAN or Tailscale remains explicit
configuration.

Safe initial behavior:

- Default to loopback until the user deliberately selects a device-reachable
  interface.
- Show interface name and IP together when available.
- Offer All interfaces only with an exposure warning and a separately selected
  advertised address; never display `0.0.0.0` as the Miyoo URL.
- Retain Custom for routed HTTP(S) deployments.
- Revalidate the selected local address before startup and report when it is no
  longer assigned.
- Continue warning that PSS has no public-facing authentication and is supported
  only on a trusted LAN, tailnet/VPN, or authenticated gateway.

## Desktop UI scope

The initial control panel should expose only:

- PSS name;
- listening interface/address and port;
- advertised Miyoo address;
- Stremio Service address and reachable/unreachable state;
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
- Stremio Service reachable/unreachable/invalid URL state;
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
3. persist PSS name, interface, port, and Stremio Service settings;
4. detect or manually configure FFmpeg and FFprobe;
5. start PSS and show the correct device-reachable URL;
6. connect a real Miyoo Mini Plus from OnionOS Apps;
7. pass direct, converted/downscaled, subtitle, Continue Watching, Resume, and
   Play from Start regressions;
8. restart the desktop app/server and retain intended configuration and PSS data;
9. handle invalid port, missing FFmpeg/FFprobe, unreachable Stremio Service, a
   disappeared interface, and startup failure cleanly;
10. stop only the managed PSS process and remove the application without deleting
    unrelated or user-owned data unexpectedly;
11. confirm that credentials, addon URLs/tokens, upstream URLs, development files,
    and private logs are absent from the release and normal diagnostics.

Equivalent clean-artifact acceptance is required before a macOS build is called
supported. Release evidence must distinguish designed, implemented, automated,
packaged, physically confirmed, signed/notarized, and release-ready states.
