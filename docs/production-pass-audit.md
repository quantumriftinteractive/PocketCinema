# Production PASS Audit

Last audited: 2026-09-04
Scope: current `main` at repair checkpoint `030b2e9`, sealed by `b83eff2`.

## Method

This audit treats every historically accepted PASS as a current production
invariant. Historical physical evidence in `docs/roadmap.md` and the milestone
evidence documents remains valid unless current code, configuration defaults,
deployment, or runtime assets materially intersect it. It does not relabel an
unrepeated device check as unconfirmed.

Classifications: **A** production-correct; **B** configuration gap; **C**
regression; **D** deployment/packaging gap; **E** documentation/state or
verification drift; **F** intentionally superseded by a recorded product
decision.

The deliberately untracked `UI_concept/PocketCinemaUI_MainMenu_Template.png`
is outside this audit and was not read, modified, staged, or deployed.

## Master audit table

| # | Behavior / acceptance area | Historical PASS evidence | Current production path | Class | Evidence inspected | Current status / fix required? | Physical recheck? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Miyoo normal launch, controller navigation, B/back | Roadmap M1, M5, M21; rename smoke | `app/launch.sh` -> `client/miyoo/pocketcinema-ui.sh` -> selector | A | launcher, UI, deploy map, M21/M22 evidence | Normal default path retained; no fix | No | Test-only launch markers are separately default-off. |
| 2 | Menu playback exit and all client cleanup | M4-M6, M13, M20-M22 | UI traps, player helpers, app-local logs/temp paths | A | `pocketcinema-ui.sh`, M22 evidence | Normal cleanup remains enabled | No | Current scale change does not touch cleanup. |
| 3 | Movie search and normalized metadata | M5, M7, M18 | `/api/search`, `/api/meta`, UI search flow | A | server tests, UI flow | Implemented normally | No | Account/source availability is separate from resolver behavior. |
| 4 | Series, seasons, and episode browsing | M9, M12-M13 | normalized series metadata and episode IDs | A | offline-series and real-episode tests | Implemented normally | No | Deterministic fixture is regression infrastructure, not activation. |
| 5 | Source selection and same-title stream stability | M7-M8, M18 | opaque stream list/cache and selected stream IDs | A | stream-cache tests, server resolver | Implemented normally | No | No provider URL crosses the Miyoo API. |
| 6 | Continue Watching, Resume, Play from Start, FFplay `-ss`, watch-time persistence | M6, M13, M21 | `last-play.json`, `/api/progress`, play session start | A | progress/resume tests, UI launch code | Implemented normally | No | SDL-ready and pause-aware accounting remains the production rule. |
| 7 | Direct HTTP(S) eligibility and unsafe-shape rejection | M7-M8, M18 | account/addon normalization and stream validation | A | account tests, server tests | Implemented normally | No | P2P, magnet, infohash, external-player, credential, private, and unsafe shapes remain rejected. |
| 8 | Opaque URLs, play sessions, and Range forwarding | M7-M8, M18, M20 | `/api/streams`, `/api/play`, `/play` proxy | A | opaque/Range/redirect tests | Implemented normally | No | Upstream URLs remain server-side. |
| 9 | Account binding, polling, addon normalization/refresh, source persistence | M16, M18 | account-link manager and ignored credential config | A | account suite and API tests | Implemented normally | No | Auth key is never returned to the client. |
| 10 | PCServer-only Stremio Service and localhost topology | M15-M16, M23 Local PASS | server backend, default `127.0.0.1:11470`, desktop validation | A | parser/config/status tests, release gates | Implemented normally | No | Firewall/listener boundary remains a release control, not a Miyoo route. |
| 11 | Open-media addon behavior | M15, M18 | loopback helper addon enabled by default | A | open-media resolver test | Implemented normally | No | It supplies opaque, policy-filtered results only. |
| 12 | Preflight, compatibility cache, H.264/AAC and VP8/Vorbis envelope, Opus rejection | M8, M18, M20 | `playback_compatibility`, probe cache, stream filtering | A | preflight/cache/fixture tests | Implemented normally | No | Unsupported or unmeasured media is not advertised as direct play. |
| 13 | Safe unavailable-candidate handling | M8, M10, M18 | bounded resolver/preflight error path | A | rejection and status tests | Implemented normally | No | Current empty source results are availability, not a regression. |
| 14 | Accepted live HLS/remux behavior | M18 | bounded unencrypted MPEG-TS bridge | A | HLS selection/retry/bounds tests | Implemented normally | No | Encrypted, fragmented, and unsafe playlists remain rejected. |
| 15 | FFmpeg/FFprobe detection, bounded conversion, and downscaling | M8, M20 | manager/desktop detection and transcode commands | A | capability, command, and transcode tests | Implemented when host tools are available | No | Clean-release tool distribution remains separately gated. |
| 16 | Converted multi-audio choice, conversion session lifecycle, resume and cleanup | M20-M21 | normalized audio selection and bounded session management | A | conversion/resume/session tests, M21 evidence | Implemented normally | No | No conversion policy changed during M23. |
| 17 | Subtitle discovery, matching/scoring, dedupe, and source/release normalization | M6, M20-M21 | server subtitle normalization/scoring | A | subtitle normalization and matched-stream tests | Implemented normally | No | All source URLs remain server-side. |
| 18 | Language priority, caps, multiple preferred tracks, no-match fallback | M21 | client preferences and server bounded ordering | A | language/cap/fallback tests, M21 evidence | Implemented normally | No | Up to three tracks per preferred language remains bounded. |
| 19 | Subtitle-download and conversion-start failure behavior | M20-M21 | sanitized play-error route and client messages | A | controlled-failure tests, UI mapping | Implemented normally | No | Controlled failure flags are default-off test infrastructure. |
| 20 | Burn-in/downscale fallback | M20, M22 | bounded MPEG-TS conversion fallback | A | transcode and M22 fallback evidence | Implemented normally where libass-capable FFmpeg exists | No | Selectable Matroska setup failure returns here. |
| 21 | Selectable Matroska tracks, R1, Off, and cleanup | M22 | default-enabled server/client Matroska path and app-local player | A | default/opt-out, packaging tests, inherited M22 physical evidence | Production-promoted and intact | No | Explicit `0`/CLI disable is a supported opt-out, not a hidden gate. |
| 22 | App-local FFplay, libass/fontconfig/font, identity bridge, 1.5x default | M22 plus renderer repair evidence | app-local player runtime, dual legacy/current bindings, `font_scale=1.5` | A | renderer runtime test, deployed-hash evidence, physical readability result | Production default is readable | No | Size/position preferences are deferred normal-UI work. |
| 23 | Local LAN direct HTTP and editable proxy configuration | M4, M11, M21 | connection profile and proxy helper | A | connection/proxy shell tests | Implemented normally | No | Empty proxy means direct transport. |
| 24 | Remote supported-v1 proxy route without forced Tailscale auth | M2, M11, M14, M21 | Remote profile through generic HTTP proxy | A | connection profile tests, transport evidence | Implemented normally | No | PocketCinema does not authenticate or start Tailscale. |
| 25 | Independent Tailscale companion and state preservation | M11, M14; rename smoke | `onion-tailscale/` only | A | deployment/migration code and evidence | Implemented normally | No | PocketCinema does not inspect companion state. |
| 26 | Local-only UDP discovery | M3, M11 | discovery responder/client | A | responder tests and current code | Implemented normally | No | Legacy wire marker is intentionally retained. |
| 27 | Local/Remote route preservation, wildcard bind, Automatic/All/Custom, no wildcard advertisement | M11, M21, M23 Local PASS | client profile + desktop route derivation | A | connection tests and desktop tests | Implemented normally | No | M23 Remote desktop physical acceptance is pending work, not a lost historic PASS. |
| 28 | No accidental public Stremio Service exposure | M15 and security invariants | loopback default, desktop PCServer-only endpoint validation | A | server/desktop config and readiness review | Implemented normally | No | Firewall verification remains a release gate. |
| 29 | PocketStremio -> PocketCinema profile/proxy/playback-state migration | rename PASS | one-time deploy migration | A | deploy script and migration evidence | Implemented normally | No | Local/Remote settings and last-play state preserve atomically. |
| 30 | Tailscale untouched, legacy renderer bridge, stale fontconfig rewrite, required legacy identifiers | rename/M22 repair evidence | deploy migration and client runtime exports | A | deploy and renderer runtime tests | Implemented normally | No | Historical names remain only for wire/helper/runtime compatibility. |
| 31 | PocketCinema client, PCServer, and companion icons | rename artwork PASS | tracked app/desktop/companion assets and deploy mapping | A | tracked asset inventory and physical evidence | Implemented normally | No | No unrelated UI concept asset was used. |
| 32 | Normal deploy preserves config and networking state | M11, M14, rename, M22 repair | `scripts/deploy-miyoo.ps1` | A | migration/deploy checks and deployment evidence | Implemented normally on prepared development host | No | It does not overwrite live PocketCinema config or Tailscale state. |
| 33 | Fresh deploy includes app-local player runtime and renderer assets | M22 production invariant | deploy script requires rebuilt FFplay, font, and sysroot libraries | D | deploy script plus `.gitignore` inventory | **Open packaging gap; no in-scope fix** | No | Required artifacts are ignored `.tmp` inputs, so a clean checkout cannot perform a fresh deployment. This is already a fresh-SD/licensing/release-artifact blocker. |
| 34 | Supported server launch paths: desktop, managers, direct source | M15-M16, M23 Local PASS | desktop child; Windows/macOS managers; documented direct CLI | A | lifecycle/manager/parser/docs review | Parity preserved where supported | No | Direct source is documented as an explicit developer/admin invocation; it is not an end-user package. |
| 35 | Test-only/hidden-gate containment | PASS invariant | markers and `FIELD_TEST`, `AUTO_FIRST`, headless, dry-run, display-surface, forced-failure flags | A | repository-wide tracked-source scan | Defaults are production-safe | No | Test flags default off; accepted player/Matroska defaults are on. |
| 36 | Optional deterministic compatibility fixtures | M7-M9, M18 | allowlisted optional fixture routes | F | server tests and roadmap decisions | Intentionally not required for normal playback | No | Explicitly retained as regression infrastructure, never a production activation requirement. |
| 37 | Current-state/plan checkpoint and renderer narrative | M22/M23 handoffs | `PROJECT_STATE.md`, desktop plan | E | audit comparison with `b83eff2` and physical repair evidence | **Fix required: state drift** | No | Stale pending/readability language and old remote-verification text must be reconciled. |
| 38 | Windows desktop test portability | M23 Windows repair verification | `server/test_desktop.py` | E | Windows audit run | **Fixed in this audit** | No | Expected path now uses host `Path` semantics rather than POSIX separators. |
| 39 | M23 accepted Local desktop management | M23 Local PASS | desktop lifecycle, route list, owned child | A | desktop suite and recorded Local smoke | Accepted Local path retained | No | Windows responsiveness and Remote desktop checks remain pending M23 work, not historical PASS regressions. |

## Findings and disposition

1. **D — fresh-deployment/packaging gap (open release blocker).** The normal
   Miyoo deployment script correctly installs FFplay, libass/fontconfig
   libraries, and the font, but it obtains them from ignored `.tmp` build and
   font inputs. A prepared development PC can deploy (and the current Miyoo was
   verified), but a clean checkout cannot create a fresh device install. This is
   a release-artifact/licensing/fresh-SD gap, not a media-path regression. It is
   intentionally left for the separate M23 packaging work.
2. **E — state/plan drift (fixed in this audit).** The current state still
   contained superseded renderer-pending text and a pre-push checkpoint status;
   the desktop plan still described subtitle startup parity as needing a
   renderer retest. These records are reconciled with the deployed 1.5x
   `font_scale` result and verified remote checkpoint.
3. **E — Windows verification portability (fixed in this audit).** The desktop
   test expected slash separators for a Windows `Path`, failing only on Windows.
   The test now compares platform-native `Path` output; desktop behavior was not
   altered.

No **B** configuration gap or **C** regression was found. The audit does not
reopen M21/M22 physical matrices: their client, resolver, conversion, subtitle,
and cleanup paths are unchanged or restored at their smallest documented
boundary.

## Checks run

- Python compilation of the server and desktop modules.
- All 60 `PocketCinemaServerTest` cases, in four bounded partitions.
- All account, command-line configuration, discovery, and desktop tests (45
  additional cases).
- POSIX shell parsing of tracked shell sources.
- `scripts/test-miyoo-connection-profile.sh`,
  `scripts/test-miyoo-matroska-config.sh`,
  `scripts/test-miyoo-proxy-config.sh`,
  `scripts/test-miyoo-proxy-status-refresh.sh`, and
  `scripts/test-miyoo-renderer-runtime.sh`.
- PowerShell parser validation for tracked server/deployment scripts.
- `git diff --check`, tracked asset inventory, deployment-path review, and a
  repository-wide tracked-source hidden-gate scan.

## Remaining physical work

Only the existing M23 Windows desktop responsiveness smoke remains: launch the
desktop shell, inspect service/connections, start it, briefly use it, then stop
or restart without a frozen window. This is required because it exercises the
Tk UI thread on Windows; static tests cannot establish perceived responsiveness.
It does not justify replaying M21/M22 playback acceptance.
