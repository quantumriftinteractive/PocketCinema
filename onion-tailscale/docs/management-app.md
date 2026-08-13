# OnionOS Tailscale Management App

The standalone management app was deployed and tested on a Miyoo Mini Plus on
August 13, 2026. It owns all new runtime files under
`/mnt/SDCARD/App/Tailscale/` except for its single supported OnionOS startup
hook.

## Controller Flow

The SDL 1.2 screen displays daemon state in the title and the current Tailscale
IPv4 address in the footer. Controller logs physically confirmed:

- Enabled state with `100.97.46.26` displayed;
- Automatic enable toggled from disabled to enabled;
- Refresh retained the correct state and IP;
- B returned cleanly to OnionOS;
- two controller-driven Disable and Enable cycles;
- each stop completed in about one second;
- each enable recreated the app-local socket and restored the same IP;
- proxy traffic succeeded after re-enabling.

The user later opened the app after reboot and confirmed that it showed
Enabled. The first-account Connect account screen is implemented with its
pending URL restricted to `/tmp`, but was not physically tested because the
working node was already authenticated and was not logged out or reset.

## State Adoption

Deployment first proved that the standalone `start.sh` detected another active
`tailscaled` and refused to compete with it. The active daemon was then stopped
over local-network SSH. `migrate-state.sh` copied the existing authenticated
state into the standalone app and retained the source as a rollback copy.

Both files had matching SHA-256 values immediately after the copy. The
standalone daemon started from the copied identity, retained Tailscale IPv4
`100.97.46.26`, and restored HTTP proxy traffic after one reconnect interval.
The rollback source remained unchanged after migration and reboot.

## Automatic Enable

The app uses OnionOS 4.3's supported `.tmp_update/startup/*.sh` extension loop.
It does not edit OnionOS `runtime.sh` or another core file. The installed hook
matched the app's source byte-for-byte.

A physical reboot confirmed:

- the Miyoo went offline and restarted normally;
- the normal OnionOS MainUI returned;
- the startup hook ran without manually opening Tailscale;
- a new standalone daemon PID was created;
- status returned Enabled with `100.97.46.26`;
- PocketStremio server status traversed the userspace HTTP proxy successfully;
- system swap remained unused after boot.

The boot hook waits at most eight seconds for the local daemon socket and does
not wait for network access. This prevents indefinite boot blocking by design.
Booting with Wi-Fi or internet deliberately unavailable has not yet been
physically measured.

## Resource Snapshot

Before reboot, the migrated standalone daemon reported approximately 29.8 MB
RSS and no process swap. A post-reboot system snapshot showed 3.3 MB free RAM,
9.7 MB available after buffers, and zero system swap in use. These are idle
snapshots, not active video-playback measurements.

## Verification

- all app shell scripts parsed with the target Miyoo `/bin/sh -n`;
- both PowerShell scripts parsed with the PowerShell AST parser;
- the ARMv7 SDL selector compiled with `-Wall -Wextra -Werror`;
- a clean rebuild matched the tracked selector binary;
- isolated autostart enable/status/disable checks passed;
- deployment left state and logs untouched;
- daemon collision refusal, copy-only migration, IP recovery, proxy traffic,
  controller actions, B exit, and reboot autostart were verified on-device.
