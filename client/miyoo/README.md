# Miyoo Client

`pocketstremio-ui.sh` is the current controller-driven OnionOS client. It:

- starts Tailscale if its userspace socket is missing;
- calls PocketStremio through `HTTP_PROXY=http://127.0.0.1:1055/`;
- uses OnionOS `kbinput` for search text and the bundled SDL 1.2 selector for lists;
- supports D-pad navigation, A selection, and B/back in selector screens;
- parses API responses with OnionOS `jq`;
- browses normalized series seasons and episodes with the SDL selector;
- launches FFplay in the working OnionOS framebuffer/audio context.
- offers Search and Continue Watching from a lightweight home menu;
- selects external subtitles through the server when FFplay advertises the
  `subtitles` filter;
- resumes saved items with FFplay `-ss` and reports approximate progress.
- shows persistent OnionOS loading panels during stream discovery and server-side
  media compatibility inspection.
- excludes network startup and A-button pause intervals from reported progress
  with the app-local `pocketstremio-pause-monitor` helper.

Inside FFplay, the Miyoo Menu button exits playback. B advances one frame; it is
not the playback exit control on the confirmed OnionOS FFplay build.

The prebuilt ARMv7 selector is `bin/pocketstremio-selector`; its source is
`sdl_selector.c`. Manual selection is the default. Set
`POCKETSTREMIO_AUTO_FIRST=1` to restore the development auto-select path.

The pause observer is `bin/pocketstremio-pause-monitor`; its source is
`pause_monitor.c`. It opens `/dev/input/event0` as an additional reader and does
not grab, transform, or consume controller events.

Confirmed device flow:

```text
Apps -> PocketStremio -> search -> result -> Play -> stream -> FFplay
Apps -> PocketStremio -> search -> series -> season -> episode -> Play -> stream -> FFplay
```

The standalone `json-client.sh` remains as the lightweight structured JSON
connectivity probe.

Continue Watching and resume seeking are physically confirmed from the OnionOS
Apps menu. External subtitle selection is capability-gated and remains hidden on
the target FFplay build because its `subtitles` filter is unavailable. See
`docs/subtitles-progress-poc.md` for evidence and progress accuracy limits.

`json-client.sh` is a lightweight OnionOS shell client for the first structured JSON proof.

It uses the existing Tailscale userspace HTTP proxy:

```sh
HTTP_PROXY=http://127.0.0.1:1055/
```

Run on the Miyoo after `tailscaled` is authenticated:

```sh
cd /mnt/SDCARD/App/PocketStremio/client
chmod +x json-client.sh
./json-client.sh
```

The client writes parsed values to:

```text
/mnt/SDCARD/App/PocketStremio/client/logs/json-client.log
```
