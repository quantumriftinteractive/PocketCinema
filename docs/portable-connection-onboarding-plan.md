# Portable Connection and First-Run Onboarding Plan

**Status:** Proposed design only — no product behavior is implemented or physically confirmed by this document.

## Purpose and confirmed starting point

PocketStremio must work on a directly reachable home LAN and, when the Miyoo is away from home, through an independently managed remote-network route. For supported v1 remote use that route is the official Tailscale client on the PSS host plus the separate Miyoo Tailscale companion's userspace HTTP proxy. Local use must not require Tailscale.

The current first-run gap is measured: with no PocketStremio configuration, the Miyoo receives a local PSS discovery response but begins with direct HTTP. It cannot validate a tailnet-only PSS address or a manually entered tailnet address through the optional proxy. The prior live configuration was restored unchanged after that test.

Current implementation facts:

- PocketStremio stores `SERVER_BASE` and `PROXY` in `/mnt/SDCARD/App/PocketStremio/config/pocketstremio.conf`. `PROXY` is an HTTP URL, not separate host and port fields; it accepts empty or `http://` values. Environment variables override saved values.
- Every Miyoo `curl` request, including PSS validation and play-session HTTP traffic, already uses the configured generic proxy. With no proxy, it clears inherited proxy variables and uses direct HTTP.
- Local UDP discovery is direct. The client currently discards a received discovery record when immediate `/api/status` validation through the current route fails, conflating *found* with *reachable*.
- The standalone Tailscale app starts `tailscaled` with `TS_HTTP_PROXY_LISTEN`, defaulting to `127.0.0.1:1055`, in `onion-tailscale/scripts/start.sh`. It also defaults the SOCKS5 listener to that address. Its UI displays daemon state and tailnet IP, but not the HTTP proxy endpoint.
- The default remains stable while the companion starts with those defaults. It can legitimately differ if `TS_HTTP_PROXY_LISTEN` is supplied at launch, a future companion-owned configuration changes it, or the companion implementation changes its default. A bind failure must be reported by the companion; it must not silently choose another port.

## Ownership boundary

| Concern | Owner |
| --- | --- |
| Tailscale binary, identity, login, state, daemon, autostart, userspace network, and proxy listener | Standalone Tailscale companion |
| Direct and remote PSS addresses, selected connection route, generic proxy URL, PSS validation, and onboarding | PocketStremio |
| PSS process, listen/advertised addresses, Stremio Service loopback access, and PSS settings | PSS host / future desktop PSS app |

PocketStremio treats the proxy as ordinary configured HTTP transport. It must not read the companion's files, socket, logs, process list, status, or configuration; start, stop, authenticate, or reconfigure it; or infer that a proxy is Tailscale. The companion displays its endpoint to the user, who can enter or confirm it in PocketStremio.

## Recommended connection model

Use one named PSS profile with two optional endpoint aliases and one optional remote proxy:

```text
PSS name
Local PSS URL       (direct HTTP(S), optional)
Remote PSS URL      (routed/tailnet HTTP(S), optional)
Remote proxy URL    (generic HTTP URL; initial default http://127.0.0.1:1055)
Connection mode     Automatic | Local only | Remote only
```

This is preferable to one endpoint plus one proxy: portable users normally have different LAN and tailnet addresses for the same PSS. A single endpoint would require editing it when leaving or returning home.

`Automatic` makes bounded, non-destructive attempts: (1) validate Local directly with no proxy variables; (2) on failure, validate Remote through the saved generic proxy; and (3) use only the route that validates. It must not persist temporary failure, rewrite endpoints, or disable a route. `Local only` and `Remote only` aid diagnosis. The home screen shows `Connected (Local)` or `Connected (Remote)`, not provider internals.

### Compatibility and migration

Do not destructively reinterpret existing saved configuration. A legacy `SERVER_BASE`/`PROXY` pair remains a usable single-route legacy profile. The UI invites the user to save local and/or remote routes only through the new setup. The runtime can resolve the selected profile to the existing active `SERVER_BASE`/`PROXY` variables, preserving current HTTP and FFplay proxy behavior.

New fields require an atomic rewrite of the same app-local config file, preserving unrelated keys. Reject credentials and URL user-info, write a temporary file in the config directory, then rename it. Environment overrides retain precedence and must state that saved edits take effect after the override is removed.

## Phased implementation plan

### 1. Expose the companion's owned HTTP proxy information

**Implementation status:** Implemented, statically validated, deployed, and
physically confirmed from OnionOS Apps.

Create one companion-owned source for the advertised HTTP proxy listener default/configuration and use it in `start.sh` and the controller UI. The smallest safe UI change is a compact read-only row or footer:

```text
Tailscale: Enabled
IP 100.x.y.z
HTTP proxy: 127.0.0.1:1055
```

When disabled, retain it as setup information but label it `HTTP proxy when enabled:`. Document that this is the address other apps enter as their HTTP proxy. Keep `127.0.0.1:1055` as the stable documented default. If a companion-owned editable setting is later added, require loopback by default, display the actual value, and derive startup and UI from one source. No ephemeral selection or silent fallback.

### 2. Add minimal PocketStremio proxy controls

**Implementation status:** Implemented, statically validated, and deployed;
pending the required Apps-context test. The first launch found that a preserved
legacy `http://host:port/` value (valid under the prior curl-only handling) was
too strictly rejected. The deployed compatibility fix canonicalizes only that
root-path spelling in memory; physical confirmation remains pending.

Preserve the HTTP-URL format. Add a `Connection settings` screen with:

- `Remote proxy: <current host:port or Off>`;
- `Edit remote proxy` (controller keyboard; normalize bare host:port to `http://host:port`);
- `Use companion default` (`http://127.0.0.1:1055`);
- `Clear remote proxy` (with confirmation); and
- `Test remote route` only after both remote URL and proxy exist.

Do not add proxy types, credentials, PAC/SOCKS support, provider discovery, or a proxy process manager. Reject spaces, URL user-info, and unsupported schemes. Keep UI logs sanitized.

### 3. Replace first-run connection setup

When no usable profile exists, open:

```text
PocketStremio setup
- Connect on this network
- Connect away from home
- Connection settings
- Back
```

`Connect on this network` uses direct-only local discovery and manual entry, saving a Local PSS URL only after direct status validation.

`Connect away from home` explains: “Use a separately installed network helper. PocketStremio does not start or configure it.” It prefills the generic proxy default, permits view/edit, asks for the Remote PSS URL, and validates only through that proxy. Save the remote URL and proxy only after validation.

Classify failures by stage. A proxy refusal/timeout says the remote route or helper could not be reached and offers `Edit proxy`, `Try again`, and `Back`; it must not claim the PSS is invalid or offline. A failed status reached through the proxy says the remote PSS could not be verified. Do not expose raw curl/PSS/provider details.

### 4. Make discovery and reachability distinct

Keep UDP discovery direct as a Local setup convenience. Keep every syntactically valid advertisement in selection data, label it `Found on local network`, and separately report direct validation as `Reachable` or `Not reachable from this route`. Selection retries direct validation before saving the Local URL.

Do not proxy UDP discovery. Remote setup uses a manually entered Remote PSS URL or a future trusted setup handoff, then validates via the selected generic proxy. A future PSS desktop app may display/copy addresses but must not make UDP discovery a remote requirement.

### 5. Add profile routing and resilient startup

After first-run setup works, add the local/remote fields and modes. Resolve one active route at launch and use it consistently for status, API calls, play URLs, subtitles, progress, and FFplay proxy environment. Quick Resume binds to the logical PSS profile plus route identity so it does not silently replay against another PSS.

Settings separately edit Local PSS, Remote PSS, mode, and remote proxy. `Automatic` changes routes per network without changing saved values. Do not add automatic address inference, provider inspection, or background probing.

### 6. Package two independent OnionOS applications

The release artifact contains separately deployable trees:

```text
App/PocketStremio/   launcher, client, default/example config
App/Tailscale/       companion launcher, binaries, scripts, notices
```

Use release-build staging that copies only reviewed payloads and approved third-party binaries/notices. Exclude both apps' live config, logs, cache, downloaded media, account data, Tailscale state/identity, and private addon URLs/tokens.

Installation creates each directory independently. Local-only users need not authenticate the companion. Remote users configure the companion independently, see its endpoint, then choose remote setup in PocketStremio. Existing deployment scripts remain separate; a convenience installer may copy both payloads but cannot merge lifecycle or state ownership.

### 7. Keep the Windows PSS desktop app within the PSS boundary

Milestone 23 remains queued until Milestone 21 is confirmed. Its future UI may show PSS name, listening and advertised local/remote addresses, port, server state, and setup guidance. It may explain that a remote PSS address is for a separately installed official Windows Tailscale client.

It must not bundle, start, stop, inspect, authenticate, or configure that client, and must not claim it configures the Miyoo's route. It owns only PSS processes and non-secret PSS configuration.

## Security, failure, and persistence requirements

- Keep PSS off public port forwarding; it has no public-facing authentication.
- Keep Stremio Service loopback-only and preserve its firewall boundary.
- Never place proxy credentials, Tailscale identity/state, Stremio auth keys, addon URLs, media/subtitle URLs, or tokens in Miyoo configuration, logs, process arguments, or archives.
- Store PSS settings only under PocketStremio; the companion owns its app directory.
- Validate input and use atomic writes. A failed save/test leaves prior known-good config usable.
- Proxy failure, companion disable, PSS outage, or route change returns to a usable selector with a concise sanitized reason and no stale panel, FFplay process, marker, conversion, or bridge.
- Stop only owned processes. PocketStremio must never kill by generic process name or control Tailscale processes.

## Required Apps-context acceptance after implementation

1. **Fresh release install:** install both payloads on a fresh SD setup; verify no private PocketStremio config, Tailscale identity, or logs was packaged.
2. **Direct first run:** leave the companion unconfigured/disabled, choose local setup, discover or enter a LAN PSS, restart, and confirm direct persistence and playback.
3. **Companion information:** independently authenticate/enable the companion; confirm tailnet IP and HTTP proxy are visible, and enable/disable/reboot-autostart remain in its UI.
4. **Remote first run:** remove only PocketStremio config, choose remote setup, accept the default proxy, enter the PSS tailnet URL, validate, restart, and play.
5. **Editable proxy:** use a controlled alternate proxy address/port, confirm validation and restart persistence; restore default; use an invalid proxy and confirm actionable error without corrupting known-good config.
6. **Portable automatic routing:** with both endpoints saved, verify home LAN uses direct, unrelated Wi-Fi/hotspot fails local cleanly then uses remote, and returning home needs no edits.
7. **Isolation and recovery:** disable the companion in its own UI and verify safe PocketStremio remote failure; re-enable there and verify recovery. Confirm PocketStremio did not control or inspect Tailscale.
8. **Regression:** verify discovery/manual entry, status, Quick Resume route binding, direct and converted playback, Menu exit, progress, and cleanup across routes.

## Documentation and release communication

Before release, update `RELEASE_READINESS.md`, the Milestone 21 roadmap entry, README/install instructions, GitHub release notes, and the product-page brief.

- **At home:** no Tailscale is required; the Miyoo and PSS need a reachable LAN path.
- **Away from home:** v1 remote access uses the official Tailscale client on the PC and the included Miyoo companion. The companion supplies the route; PocketStremio uses it but does not manage the account or app.

Technical GitHub documentation can explain the userspace HTTP-proxy architecture. Product-page material should avoid proxy terminology except in advanced settings/troubleshooting.

## Milestone impact and open decisions

This is Milestone 21 first-run/settings work, not a reason to start Milestone 23. It changes no confirmation status. Milestone 21 needs automated route/configuration coverage plus the physical tests above before it can be Confirmed. Milestone 23 can surface PSS endpoints/guidance but cannot substitute for Miyoo-side onboarding.

Recommended implementation order: companion endpoint visibility; minimal PSS proxy controls; direct/remote first-run setup; two-endpoint automatic routing; clean dual-app release packaging; then the separately gated Windows PSS desktop distribution.

Approval remains needed for:

1. the two-endpoint profile and `Automatic | Local only | Remote only` model versus an initial single endpoint route;
2. a v1 release-installer executable versus a reviewed two-app SD-card archive with installation instructions; and
3. whether the new profile UI supports `https://` endpoints now, or only the existing HTTP-first tested path pending certificate UX evidence.
