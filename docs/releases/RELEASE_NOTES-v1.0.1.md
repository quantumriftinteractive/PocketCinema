# PocketCinema Miyoo client v1.0.1

Maintenance update for Miyoo Mini Plus users running OnionOS.

## Changes
- Fix source-specific audio-language selection that could leave a selected source with no playable streams.
- Dismiss and reap PocketCinema's preparation panel before starting FFplay, addressing the display handoff issue on the tested OnionOS 4.3.1-1 setup.
- Improve empty-source diagnostics, owned-process cleanup, and playback error reporting.

## Validation and testing limits — CONDITIONAL GO
The developer physically confirmed video and audio playback on OnionOS 4.3.1-1, disappearance of the preparation panel, and normal playback exit using the Miyoo **Menu** button. Seven focused Miyoo shell checks passed. ZIP integrity and all 30 manifest entries (file hashes, sizes, and Unix modes) were verified.

This release is published as an explicitly accepted **CONDITIONAL GO**. The full host regression suite remains outstanding: the latest attempt could not complete in its restricted environment because local socket binds and process inspection were denied. OnionOS 4.4 beta has **not** been physically retested with this candidate. Candidate post-playback logs and a final process snapshot were not retained, so successful physical observation is not presented as independent process-cleanup log evidence.

## Update an existing v1.0.0 installation
1. Exit PocketCinema and stop playback. Back up `App/PocketCinema/client/pocketcinema-ui.sh` outside the app folder.
2. Download `PocketCinema-Miyoo-v1.0.1.zip` below and verify it against `SHA256SUMS-v1.0.1.txt`.
3. Extract the ZIP on a computer. Copy only `PocketCinema-Miyoo-v1.0.1/client/pocketcinema-ui.sh` over `App/PocketCinema/client/pocketcinema-ui.sh` on the SD card.
4. Preserve your existing `config/pocketcinema.conf`, logs, and runtime files. Keep the script executable where filesystem permissions apply.
5. Safely eject the SD card and launch PocketCinema from OnionOS **Apps**.

Only the UI script differs from the v1.0.0 client distribution. Bundled FFplay, libraries, helpers, and fonts are unchanged. The app menu has no version field; the archive name, top-level folder, and manifest identify v1.0.1.

For a new installation, copy the contents of `PocketCinema-Miyoo-v1.0.1/` into `/mnt/SDCARD/App/PocketCinema/` and use the normal first-run connection setup.

## Rollback
Exit PocketCinema and restore the backed-up UI script. If unavailable, restore `client/pocketcinema-ui.sh` from the official v1.0.0 Miyoo package. Preserve configuration and runtime files.

## Server and source
PocketCinema Server (PCServer) is unchanged. Continue using the existing v1.0.0 server downloads from the [v1.0.0 release](https://github.com/quantumriftinteractive/PocketCinema/releases/tag/v1.0.0). This client retains the existing server API contract; no server upgrade is included or required by this change. The separate account-linking HTTP 502 investigation remains unresolved. No server account or torrent-addon fix is claimed.

The bundled runtime is byte-identical to v1.0.0; its [corresponding source and notices](https://github.com/quantumriftinteractive/PocketCinema/releases/download/v1.0.0/PocketCinema-Miyoo-v1.0.0-corresponding-source.zip) remain available. The v1.0.1 source tag contains the released client script and release records, based on the public repository baseline. The package manifest records the original maintenance candidate commit `137c12602ff6b4e5d445fddf3abf53bed61cf2c1`.

## SHA-256
```text
3ca28149174d8c03f6358ca17845a93fbe05e1207611b6730ffd60e9e532a1b6  PocketCinema-Miyoo-v1.0.1.zip
```
