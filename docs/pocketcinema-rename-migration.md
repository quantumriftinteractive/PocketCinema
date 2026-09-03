# PocketCinema Pre-Release Rename Migration

PocketCinema was renamed from the pre-release PocketStremio project before
Milestone 23 desktop-distribution work began. This document records the limited
development-device migration; it is not a permanent compatibility layer.

## Miyoo migration

`scripts/deploy-miyoo.ps1` now deploys PocketCinema to:

```text
/mnt/SDCARD/App/PocketCinema/
```

When it finds the previous development directory and the new configuration does
not already exist, it atomically creates `config/pocketcinema.conf` from the old
configuration. The migration changes only these persisted identity keys:

```text
LOCAL_PSS                         -> LOCAL_PCSERVER
REMOTE_PSS                        -> REMOTE_PCSERVER
POCKETSTREMIO_MATROSKA_SUBTITLES  -> POCKETCINEMA_MATROSKA_SUBTITLES
```

All other configuration, including `SERVER_BASE`, `PROXY`, connection mode,
playback preferences, and account-related client settings, is retained exactly.
The script also copies `last-play.json` only when the PocketCinema copy is
absent. With `-ReuseInstalledPlayerAssets`, it can reuse the existing app-local
FFplay runtime only when PocketCinema does not already have one.

The legacy application directory is deliberately left untouched. This preserves
existing logs and the rollback Tailscale state at
`/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state`; PocketCinema
never reads, copies, moves, or manages that state. After the PocketCinema
Apps-context smoke test passes, archive or remove the old development app only
as a separate, manually verified action. A release image contains no dependency
on the old directory.

## Intentional compatibility exceptions

The UDP discovery request/response markers remain
`POCKETSTREMIO_DISCOVER_V1` and `POCKETSTREMIO_PSS_V1`. They are an unexposed
pre-release wire identifier, not a user-facing product name, and retaining them
avoids a protocol migration or a forced replacement of deployed discovery
binaries. The service name and all user-visible discovery text use PocketCinema
and PCServer.

The prebuilt selector's `POCKETSTREMIO_SELECTOR_*` environment names also remain
its private compiled-helper ABI. PocketCinema sets those names internally; they
are neither saved user settings nor a supported compatibility interface. The
helper receives PocketCinema titles explicitly, so its old compiled fallback
title is not used by the production client.

## Brand assets

`UI_concept/Icons/PocketCinema_Client_icon.png` is the canonical Miyoo/client
artwork. `UI_concept/Icons/PocketCinema_Server_icon.png` is the master artwork
for the future PocketCinema Server desktop application. Neither asset is wired
into a desktop shell or converted into packaging formats by this rename.
