# Onion Tailscale Agent Instructions

## Scope

These instructions apply to the entire `onion-tailscale/` subproject and remain
valid if this directory is extracted into its own repository.

## Boundaries

- Target only `/mnt/SDCARD/App/Tailscale/` for persistent device files.
- Do not modify OnionOS core files.
- Do not couple scripts, paths, hostnames, tests, or documentation to
  PocketStremio or another consumer application.
- Never commit Tailscale binaries, archives, logs, PID files, node state,
  authentication URLs, keys, or tokens.
- Never overwrite, move, delete, reset, or reauthenticate an existing node state
  during an ordinary deployment.
- Treat migration from another app path as a separate, physically tested
  operation with a retained source-state rollback copy.
- Keep proxy listeners bound to loopback unless the user explicitly requests and
  approves a documented security change.

## Runtime

- Target BusyBox `/bin/sh` and static ARMv7 Tailscale binaries.
- Use userspace networking; the confirmed Miyoo kernel has no usable TUN device.
- Keep the daemon socket under `/tmp/onion-tailscale/` because the SD-card
  filesystem cannot host its Unix socket.
- Keep node state and logs under the app directory.
- Make start and stop idempotent and validate PID ownership before signaling a
  process.
- The Apps launcher may explicitly start, stop, report, or initiate account
  connection. It must never authenticate, log out, reset, or replace state
  without a controller action.
- Autostart may own only `.tmp_update/startup/onion-tailscale.sh`. Refuse to
  overwrite or remove a conflicting file and never edit OnionOS `runtime.sh`.
- Keep startup bounded to local daemon readiness. Never wait indefinitely for
  Wi-Fi, internet access, coordination, or a peer.

## Verification

- Parse every changed shell file with `sh -n`.
- Parse every changed PowerShell file with the PowerShell parser.
- Verify deployment does not copy or alter `state/` or `logs/`.
- Device authentication, proxy traffic, Apps-menu messages, memory, and clean
  stop behavior require physical or SSH evidence from the Miyoo.
