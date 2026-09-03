# Miyoo Client

`pocketcinema-ui.sh` is the current controller-driven OnionOS client. It:

- calls PocketCinema directly or through an optional generic HTTP proxy;
- uses OnionOS `kbinput` for search text and the bundled SDL 1.2 selector for lists;
- supports D-pad navigation, A selection, and B/back in selector screens;
- parses API responses with OnionOS `jq`;
- browses normalized series seasons and episodes with the SDL selector;
- launches FFplay in the working OnionOS framebuffer/audio context.
- offers Search and Continue Watching from a lightweight home menu;
- removes a highlighted Continue Watching item with X after controller
  confirmation, while A keeps the normal open/resume flow;
- builds ordered audio/subtitle preferences from a controller-friendly language
  name picker, with custom codes available only as an advanced option;
- links and reports a Stremio account through a local QR screen while keeping
  the auth key on the gaming PC;
- selects external subtitles through the server when FFplay advertises the
  `subtitles` filter;
- uses the confirmed app-local Matroska mode to package up to three selectable
  subtitle tracks and cycle them with R1, with burn-in as setup fallback;
- resumes saved items with FFplay `-ss` and reports approximate progress.
- shows persistent OnionOS loading panels during stream discovery and server-side
  media compatibility inspection.
- excludes network startup and A-button pause intervals from reported progress
  with the app-local `pocketcinema-pause-monitor` helper.

Inside FFplay, the Miyoo Menu button exits playback. B advances one frame; it is
not the playback exit control on the confirmed OnionOS FFplay build.

The prebuilt ARMv7 selector is `bin/pocketcinema-selector`; its source is
`sdl_selector.c`. Manual selection is the default. Set
`POCKETCINEMA_AUTO_FIRST=1` to restore the development auto-select path.

The selector's QR mode uses the vendored Project Nayuki C encoder and SDL 1.2;
it adds no PNG, SDL_image, font, or online QR-service dependency. Approval links
arrive through stdin and only the literal `refresh` action is emitted on stdout.

The production UI optionally reads app-local non-secret settings from:

```text
/mnt/SDCARD/App/PocketCinema/config/pocketcinema.conf
```

Use `pocketcinema.conf.example` as the template. Environment variables take
precedence over the file. `SERVER_BASE` is required and may use a LAN or overlay
network address. Leave `PROXY` empty for direct HTTP, or set it to an HTTP proxy
such as `http://127.0.0.1:1055/`. The client validates settings and reports
PocketCinema server connectivity failures without knowing which network
provider is in use.

From the repository root, deploy tracked app files without replacing the real
config or any networking-provider state:

```powershell
.\scripts\deploy-miyoo.ps1 -DeviceHost root@DEVICE_ADDRESS
```

Rebuild and compare the selector with the committed ARMv7 binary using:

```powershell
.\scripts\build-miyoo-selector.ps1 -VerifyCommitted
```

The pause observer is `bin/pocketcinema-pause-monitor`; its source is
`pause_monitor.c`. It opens `/dev/input/event0` as an additional reader and does
not grab, transform, or consume controller events.

Confirmed device flow:

```text
Apps -> PocketCinema -> search -> result -> Play -> stream -> FFplay
Apps -> PocketCinema -> search -> series -> season -> episode -> Play -> stream -> FFplay
```

The standalone `json-client.sh` remains as the lightweight structured JSON
connectivity probe.

Continue Watching and resume seeking are physically confirmed from the OnionOS
Apps menu. External subtitle selection is capability-gated and remains hidden on
the target FFplay build because its `subtitles` filter is unavailable. See
`docs/subtitles-progress-poc.md` for evidence and progress accuracy limits.

`json-client.sh` is a lightweight OnionOS shell client for the first structured JSON proof.

It uses direct HTTP by default. To use a local userspace HTTP proxy, set:

```sh
HTTP_PROXY=http://127.0.0.1:1055/
```

Run on the Miyoo after the selected network path is available:

```sh
cd /mnt/SDCARD/App/PocketCinema/client
chmod +x json-client.sh
./json-client.sh
```

The client writes parsed values to:

```text
/mnt/SDCARD/App/PocketCinema/client/logs/json-client.log
```
