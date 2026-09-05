# Windows standalone candidate (M23)

Status: **Implemented, automated-tested, packaged developer-machine smoke PASS, and running-settings-lock physical PASS; clean-machine acceptance pending**.
This is an unsigned Windows x64 one-directory candidate, not a public release
or completion of M23. The accepted source desktop/tray PASS remains inherited.

## Build and artifact

Build on Windows x64 with the official Python **3.11.0** installation and its
Tcl/Tk **8.6.12**, using an isolated venv. These are the development machine's
measured runtime inputs, pinned for this first candidate. **This older Python/Tk
baseline must be updated and reviewed before public release**; pinning it is
reproducibility evidence, not a security-support claim.

From the repository root in PowerShell:

```powershell
py -3.11 -m venv .tmp/windows-build-venv
& ./.tmp/windows-build-venv/Scripts/python.exe -m pip install -r packaging/windows/requirements-build.txt
& ./.tmp/windows-build-venv/Scripts/python.exe scripts/build-windows.py
```

The script rejects a non-venv, mismatched Python/Tcl or dependency versions and
safely replaces only `.tmp/windows-package`. Close test copies from that output
before rebuilding. It does not load or change the user's PocketCinema settings.
All generated files, icon derivatives, build logs and artifacts remain ignored.

Outputs:

- `.tmp/windows-package/dist/PocketCinema Server/PocketCinema Server.exe`
- `.tmp/windows-package/PocketCinema-Server-0.17.0-device-discovery-windows-x64.zip`

End users extract the **entire** ZIP, keep `_internal` beside the executable,
and launch `PocketCinema Server.exe`. No Python installation, checkout, build
tools, launch script, terminal, pip or environment override is required.
This portable layout avoids one-file extraction and makes runtime files and
notices inspectable. It is portable installation, not portable user settings.

`BUILD_INFO.json` records runtime/dependency versions, the source-input digest,
audit result and unsigned/unaccepted state. `SHA256SUMS.txt` inventories every
other shipped file. The build prints the ZIP SHA-256. Fixed archive timestamps,
hash seed and pinned inputs reduce variation; rebuild verification is separate
from acceptance on a clean Windows machine.

Two clean builds on the development Windows machine produced identical ZIP
SHA-256 `03f91526b3009b3d198b915f1fbef0045d19116e9ed9683df73c4eb62570b1b1`.
The candidate has 974 shipped files / 39,049,194 bytes extracted; the content
audit covers 972 runtime/notice files before adding its two generated manifests
and 290 frozen modules. PE metadata and all seven ICO sizes were inspected.

## Runtime boundary

The existing entry point dispatches before importing/constructing the GUI:

| Invocation | Role |
| --- | --- |
| `PocketCinema Server.exe` | Existing Tk GUI, per-user instance mutex and native tray |
| `PocketCinema Server.exe --server-child ...` | Existing server child, no Tk window or tray |
| Source desktop launch | Existing Python module child path |

The desktop retains its exact `Popen` child. Frozen arguments preserve validated
settings, routes, tool paths and production Matroska enablement. Because
windowed Python has no `sys.stdin/stdout/stderr`, the child recovers only its
inherited private pipe handles without allocating a console. Stop writes the
existing `stop` command; owner-pipe EOF also triggers normal server cleanup.
The existing exact-handle terminate/kill fallback remains bounded to that child.
Direct child invocation without its owner's pipes is rejected.

The executable uses the Windows GUI subsystem. Existing no-console flags,
asynchronous workers, sanitized bounded GUI logs, busy/menu state, active-mode
tooltip, one X notification, same-window restore and explicit Quit are retained.
Bundled Python DLLs remain available through `os.add_dll_directory`; the inherited
PyInstaller DLL search directory is reset so external system/media tools do not
load the bundle's DLLs. See the official
[PyInstaller windowed/subprocess guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
and [runtime path documentation](https://pyinstaller.org/en/stable/runtime-information.html).

Normal state remains `%APPDATA%\PocketCinema`: existing `config.json`, separate
credentials/addon configuration and `data/`. All desktop settings retain their
existing schema and validation, including manual routes, service and tool paths.
Frozen child media and fixture roots are explicit empty app-private folders
there; nothing is copied from development fixtures or media. Mutable files never
belong beside the executable, including under a protected installation directory.

FFmpeg/FFprobe remain external: existing Stremio per-user installation, PATH,
or manual selection. Missing tools produce the existing capability state.
No media-tool binaries are downloaded or bundled. Stremio Service retains the
loopback default `http://127.0.0.1:11470`, validated overrides and unreachable
feedback. No firewall or provider behavior changes. Tailscale remains independent;
interface enumeration is informational and uses the existing hidden Windows
PowerShell helper. Users do not run PowerShell to launch the application.

The canonical PNG is included for GUI/tray use. The build derives 16/24/32/48/64/
128/256-pixel ICO sizes; no new artwork is tracked. Executable metadata uses
PocketCinema Server / Quantum Rift Interactive. Both displayed versions derive
from existing `SERVER_VERSION` (`0.17.0-device-discovery`); Windows numeric fields
use `0.17.0.0`. No separate version source or branding is introduced.

## Dependencies, notices and audit

Developer-only build pins: PyInstaller 6.22.2, hooks 2026.7, altgraph 0.17.5,
packaging 26.3, pefile 2024.8.26, pywin32-ctypes 0.2.3 and setuptools 65.5.0.
Runtime dependencies remain pystray 0.19.5, Pillow 12.3.0 and six 1.17.0, plus
bundled Python/Tcl/Tk. PyInstaller supplies freezing and the GUI bootloader;
pefile also audits the generated executable. No extra runtime dependency is added.

The artifact includes `THIRD_PARTY_NOTICES.txt` and collected full Python,
Tcl/Tk, Pillow, six, pystray and PyInstaller/hook licenses. Tcl's notice is a
tracked verbatim copy from its `core-8-6-12` source. Python's Windows Microsoft
runtime conditions are retained. PyInstaller's bootloader exception is included.
The complete pystray package is unmodified, replaceable `.py` source outside the
frozen module archive, with LGPLv3/GPLv3 texts and upstream source reference.
Public redistribution/signing and runtime-update review remain release gates.

The build audits file paths/content and decompressed frozen modules for local
checkout/home-path leakage; rejects logs, test packages/fixtures, caches, configs,
credentials and external-tool executables; and verifies the GUI subsystem, both
roles, canonical icon and replaceable Win32 tray source. Collection uses explicit
assets, not a repository-directory copy. Required standard-library DLLs/modules,
Tcl/Tk scripts and Pillow assets are expected runtime content.
Optional PyInstaller warnings concern other platforms, optional Pillow plugins
(numpy/olefile/defusedxml), dynamic six/import machinery and excluded tray
backends; the actual Windows PNG/ICO, GUI/tray and server paths are smoke-tested.

## Focused validation and evidence inheritance

Recorded automated result: **PASS** — 68 focused desktop/runtime unit tests,
Python/spec compilation, diff checks, artifact audit, identical clean rebuilds
and the extracted-ZIP native smoke (missing/manual/normal Stremio-runtime tools).
The packaged development-machine physical gate is **PASS**. It confirmed settings
load, canonical identity, no-console launch, Local/Remote route presentation,
active-mode tooltip, one X notification, tray restore, Start/Stop/Restart and
exact-owned-child Quit cleanup. The clean-machine gate remains **PENDING**.

```powershell
& ./.tmp/windows-build-venv/Scripts/python.exe -m unittest server.test_desktop_runtime server.test_desktop server.test_desktop_tray server.test_desktop_refinements server.test_desktop_notifications -q
& ./.tmp/windows-build-venv/Scripts/python.exe scripts/test-windows-package.py --gui --archive .tmp/windows-package/PocketCinema-Server-0.17.0-device-discovery-windows-x64.zip
```

The native test briefly moves/restores the mouse inside its own tray menu;
leave the desktop idle while it runs. It extracts outside the repository, removes
Python/development environment settings, restricts PATH to Windows helpers and
uses a temporary APPDATA profile and loopback ports. Actual user settings and
other running applications are untouched. It tests missing, manually configured
and normally discovered installed media tools, both frozen roles, log/shutdown pipes, graceful
Stop, EOF/unexpected-exit reporting, occupied-port refusal, GUI/tray actions,
restart uptime reset, X/background reachability, same-window restore, duplicate
launch, Quit, settings persistence and absence of writes to the application folder.
It does not claim that the development machine is a clean Windows installation.

| Changed area | Verification | Inherited evidence and reason |
| --- | --- | --- |
| Frozen entry/child pipes and paths | Unit tests + real frozen child lifecycle | Core API/media behavior unchanged |
| Packaged Tk/tray/dependencies | Native automated smoke; packaged developer-machine physical smoke PASS | Source tray UX PASS retained; clean-machine validation remains |
| Running settings lock | 68 focused tests and packaged physical confirmation PASS | Configuration semantics remain unchanged; no broad retest |
| Per-user settings and external-tool loading | Isolated profile, missing/manual tools, restart and content checks | Schema, route selection, validation and privacy semantics unchanged |
| Media, M21/M22, transport, subtitles, accounts, Miyoo | No broad regression matrix | No code, assets, configuration semantics or deployed runtime changes in those paths |

Production PASS and Impact-First Regression Testing remain in force. Automated
native clicks are not a physical acceptance claim.

The packaged candidate source now also carries the focused stream-search
no-console fix. FFprobe compatibility probing, subtitle-format conversion and
the Windows resource monitor use hidden process creation while retaining their
captured streams and existing errors/timeouts. A focused frozen-child check is
pending after the normal rebuild; the earlier packaged GUI/tray/settings-lock
PASS evidence remains inherited.

## Next physical gate and remaining release work

The packaged developer-machine smoke and running-settings-lock confirmation are
complete PASS gates and must not be repeated unless later work materially affects
those paths. Clean-Windows acceptance remains pending. Library / Next Episode is
the next intended product work; do not reopen playback, subtitle, account,
Remote streaming or M21/M22 matrices for this documentation update.

Later, a clean supported Windows installation must verify no Python/repository/
build-tool/launch-script requirement, normal launch/icon/no console, GUI/tray
lifecycle, settings creation and persistence, occupied port, unreachable Stremio,
missing tools, clean Stop/Restart/Quit/no orphans and sanitized logs. This is
**pending**, as are signing/public distribution, runtime updates and licensing
review, later macOS distribution, and Miyoo renderer/runtime provenance and
fresh-deployment gates. M23 remains **Next / incomplete**.
