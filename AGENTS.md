# PocketCinema Agent Instructions

## Scope

These instructions apply to the entire repository.

PocketCinema is an experimental thin client for the Miyoo Mini Plus running
OnionOS. The active PCServer host owns metadata, stream resolution, media proxying,
and server-side state. The Miyoo owns controller interaction, compact JSON
parsing, and FFplay launch. The confirmed deployment uses the gaming PC as the
PCServer host; macOS is also a supported development host when its prerequisites are
verified.

In development discussion and documentation, `PCServer` is the accepted shorthand
for the PocketCinema server. Spell it out on first use in user-facing material.

Read `docs/roadmap.md` before starting feature work. Only the milestone marked
**Next** should receive new feature scope unless the user explicitly changes the
priority.

## Non-Negotiable Boundaries

- Keep PocketCinema persistent device files under
  `/mnt/SDCARD/App/PocketCinema/`. The independent `onion-tailscale/`
  subproject targets `/mnt/SDCARD/App/Tailscale/` under its local instructions.
- Do not modify OnionOS core files. If no app-local solution exists, stop and
  explain the required change before touching a core file, then document it.
- The standalone Tailscale app now owns the live daemon and copied state under
  `/mnt/SDCARD/App/Tailscale/`. Preserve that identity and the original rollback
  state at `/mnt/SDCARD/App/PocketStremio/tailscale/state/tailscaled.state`.
  Never run both daemons, reset either state, reauthenticate the working node,
  or delete the rollback copy during ordinary development.
- PocketCinema must be transport-agnostic. Direct HTTP is the default; a
  generic HTTP proxy is optional configuration. PocketCinema must never start,
  stop, or inspect Tailscale.
- The Miyoo must never reach Stremio Service directly; PocketCinema Server is
  the only device-facing service. The local default is
  `http://127.0.0.1:11470`. Milestone 23 may configure a validated, non-secret
  PCServer-only Stremio Service endpoint for a separately reachable host. Keep
  the inbound Windows Firewall block for TCP `11470-11474` and `12470` whenever
  the service runs locally on the gaming PC; never make that local listener
  reachable from the Miyoo, LAN, or tailnet.
- Do not commit private addon URLs, tokens, Tailscale state, downloaded binaries,
  logs, generated caches, or the local test video. Respect `.gitignore`.
- Do not add torrent ingestion, transcoding, subtitle, progress, poster, or
  full-UI scope unless the roadmap and user request explicitly call for it.

## Source of Truth / State Ownership

`PROJECT_STATE.md` owns the current operational and production state of
PocketCinema, including the active milestone, confirmed behavior, invariants,
experimental work, regressions, and development handoff. Do not duplicate
detailed current-state narratives in `AGENTS.md`.

`AGENTS.md` defines how Codex must work: stable architecture boundaries,
implementation constraints, verification requirements, and repository
conventions. When implementation status changes, update `PROJECT_STATE.md`, the
roadmap, and the relevant evidence or release document as required. Change
`AGENTS.md` only when a permanent development rule changes.

## Current Architecture Baseline

Do not infer feature status, milestone status, release scope, or latest physical
test results from this file. Read `PROJECT_STATE.md` first, then the roadmap,
release-readiness document, and relevant evidence.

```text
Miyoo shell/SDL client
  -> direct HTTP or configured generic HTTP proxy
  -> PocketCinema server (PCServer host)
  -> metadata, addon, compatibility, conversion, and media services
```

The Miyoo owns controller interaction, compact JSON parsing, and playback
launch. The PCServer host owns metadata, stream resolution, compatibility checks,
conversion, private credentials, upstream transports, and server-side state.
The app remains transport-agnostic and does not manage the network provider.

## Repository Layout

- `app/`: OnionOS app metadata and root launcher. `app/launch.sh` is the
  production entry point; `app/playback-poc.sh` preserves the standalone
  playback experiment.
- `client/miyoo/`: BusyBox shell client, SDL selector source, and prebuilt ARMv7
  selector binary.
- `server/`: dependency-free Python HTTP server and optional stream-addon
  configuration example.
- `onion-tailscale/`: independent OnionOS userspace-networking app subproject.
  Its runtime binaries, state, downloads, and logs are intentionally ignored.
- `docs/`: confirmed POC evidence, architecture decisions, and canonical roadmap.
- `experiments/`: isolated experiments that must not replace the production app
  path until confirmed.
- `scripts/`: repeatable Miyoo deployment and ARM selector build entry points.

Deployment maps repository files as follows:

```text
app/launch.sh
  -> /mnt/SDCARD/App/PocketCinema/launch.sh
app/playback-poc.sh
  -> /mnt/SDCARD/App/PocketCinema/playback-poc.sh
client/miyoo/pocketcinema-ui.sh
  -> /mnt/SDCARD/App/PocketCinema/client/pocketcinema-ui.sh
client/miyoo/bin/pocketcinema-selector
  -> /mnt/SDCARD/App/PocketCinema/bin/pocketcinema-selector
client/miyoo/bin/pocketcinema-pause-monitor
  -> /mnt/SDCARD/App/PocketCinema/bin/pocketcinema-pause-monitor
client/miyoo/bin/pocketcinema-discovery
  -> /mnt/SDCARD/App/PocketCinema/bin/pocketcinema-discovery
client/miyoo/pocketcinema.conf.example
  -> /mnt/SDCARD/App/PocketCinema/config/pocketcinema.conf.example
```

Do not store target addresses or credentials in new committed files. Use the
existing defaults or environment overrides and keep deployment credentials out
of git.

The optional live device config is
`/mnt/SDCARD/App/PocketCinema/config/pocketcinema.conf`. Deployment must never
overwrite it. Environment variables take precedence over app-local config.

## Implementation Rules

### Miyoo Shell Client

- Target BusyBox `/bin/sh`; avoid Bash-only syntax, arrays, and large runtimes.
- Prefer OnionOS-provided `curl`, `jq`, `kbinput`, `infoPanel`, and FFplay.
- Unset `LD_PRELOAD` around non-audio network helpers. Apply the OnionOS padsp
  preload only when launching FFplay.
- When a proxy is configured, send Miyoo HTTP requests through both uppercase
  and lowercase proxy variables. When it is empty, unset inherited proxy
  variables and connect directly.
- Quote paths and user-derived values. Use `jq` for JSON rather than parsing it
  with `grep` or `sed`.
- Keep logs under the app-local `logs/` directory and avoid logging private
  upstream stream URLs.
- Retain only the current UI log and one bounded previous UI log. Playback
  failures must record and display a concise sanitized cause instead of only
  `Playback failed`.
- Always remove `/tmp/stay_awake` after playback, including failure paths.
- Derive watched time from SDL video readiness, not total FFplay process time;
  initial remote media startup must not advance Continue Watching.
- Observe A-button pause toggles through a non-grabbing app-local evdev reader.
  If pause tracking fails, suppress the progress update rather than overcounting.
- Use OnionOS `infoPanel --persistent` for blocking network/preflight work and
  dismiss only the app-started panel with `/tmp/dismiss_info_panel`. Clear the
  flag during cleanup so it cannot affect a later panel.

### SDL Selector

- Keep the selector on SDL 1.2 with its built-in bitmap font. Do not introduce
  SDL_ttf, libpng, or another runtime without measuring memory and compatibility.
- QR rendering uses the vendored Project Nayuki MIT-licensed C encoder linked
  into each app's existing selector. Pass one-time approval links through stdin,
  never process arguments or logs, and do not use an online QR service.
- The Miyoo framebuffer requires a 180-degree rendering correction.
- Confirmed keys are Up `273`, Down `274`, A `32`, and B `306`.
- B/back applies to PocketCinema selector screens. During FFplay playback, the
  Miyoo Menu button exits; B advances video frame by frame on this FFplay build.
- Stdout is a strict data channel: on success emit exactly the selected value and
  a newline; on cancel emit nothing and return nonzero.
- Vendor SDL diagnostics must stay off stdout. Send diagnostics to stderr or the
  app-local selector log.
- Keep item text bounded so it cannot overflow the 640x480 display.

### Server

- Keep the Miyoo-facing API small and JSON-based.
- Preserve current endpoints and response compatibility unless the change is
  explicitly versioned and deployed with the client.
- Keep private upstream URLs server-side. `/api/streams` returns opaque stream
  IDs and `/api/play` creates a PocketCinema play URL.
- Keep account addon transports, credentials, and media URLs server-side. Only
  safe direct HTTP(S) results are eligible; reject P2P, external-player,
  local/private-address, credential-bearing, and unsafe results.
- Keep the Stremio Local Files backend restricted to its explicit server-side
  `file://` allowlist. Never expose local paths or broaden that allowlist to
  general user media directories.
- Continue forwarding HTTP Range semantics required by FFplay.
- Keep HLS playlists and child URLs server-side. The device-facing HLS path must
  remain a bounded unencrypted MPEG-TS bridge unless a replacement is physically
  measured.
- Keep Stremio-specific and source-specific logic on the PCServer. The Miyoo
  never contacts Stremio Service directly; the default local endpoint is
  loopback, while a later desktop UI may configure and validate a PCServer-only
  endpoint on another reachable host.
- Prefer the Python standard library until a dependency removes demonstrated
  complexity and has a clear deployment story.
- Use `server/manage-server.ps1` for normal background lifecycle operations and
  `server/start-server.ps1` only when an attached foreground process is useful.

### Playback / FFplay

- Treat direct-play compatibility as a measured envelope. H.264/AAC and the
  confirmed VP8/Vorbis profile are safe only within their documented bounds;
  other advertised demuxers and decoders remain candidates until measured in
  the OnionOS Apps context.
- Reject Opus before FFplay unless a separately measured compatible path exists.
  Do not present 720p/1080p sources as assumed direct-play media; downscale
  when the measured target path requires it.
- The stock OnionOS FFplay build has no usable `subtitles` video filter and
  cannot render external SRT directly. Use a measured server-side burn-in or
  measured app-local player path, with the normal MPEG-TS burn-in path retained
  as the safe fallback where applicable.
- Count watched time from SDL video readiness, exclude startup and unverified
  pause intervals, and suppress progress updates when pause tracking fails.
- During playback the Miyoo Menu button exits FFplay. B is frame-step on the
  target build; B/back is the selector navigation control.
- Preserve cleanup on success, cancellation, FFplay failure, and Menu exit:
  no stale player, helper, conversion, bridge, panel, marker, or temporary
  subtitle state may remain.

## OnionOS Execution Context

### Miyoo SSH Access

- The Miyoo SSH user is `root`. Modern OpenSSH clients require the legacy MAC
  algorithm explicitly:
  `ssh -o MACs=hmac-sha1 root@<MIYOO_IP>`.
- For file transfers, use:
  `scp -o MACs=hmac-sha1 <source> root@<MIYOO_IP>:<destination>`.
- A default SSH failure is not evidence that the Miyoo is unreachable until
  the connection has been retried with `-o MACs=hmac-sha1`.
- Do not modify OnionOS core SSH configuration to avoid this compatibility
  option.

- Framebuffer and audio behavior cannot be proven over SSH. FFplay and SDL apps
  launched over SSH can block at `VT_WAITACTIVE` or fail to open `/dev/dsp`.
- Use SSH for file inspection, deployment, syntax checks, logs, process state,
  and network-only dry runs.
- Run visual, audio, and controller tests from the OnionOS Apps menu.
- Ask for the minimum physical interaction needed, then verify the result from
  app-local logs over SSH.
- Follow Onion's FFplay context: work from `/mnt/SDCARD/.tmp_update`, preload
  `/mnt/SDCARD/miyoo/lib/libpadsp.so`, create `/tmp/stay_awake`, and use
  `-vf "hflip,vflip"`.
- Do not describe B as the FFplay exit control. The physically confirmed
  playback exit control is the Miyoo Menu button.

### Miyoo Deployment Authentication

The development Miyoo uses the confirmed interactive root SSH login with a blank password.

A blank-password prompt is not a deployment blocker.

When scripts/deploy-miyoo.ps1 requires SSH/SCP authentication, run it interactively and complete the blank-password prompt as required.

Do not abandon the repeatable deployment path merely because authentication is interactive.

Do not replace scripts/deploy-miyoo.ps1 with ad-hoc manual SCP when the deployment script supports the required deployment.

If the deployment script itself actually fails after authentication, report the concrete command/error. Do not infer failure merely from the presence of an interactive password prompt.

When product/client changes require physical Miyoo validation, deploy the changed tracked files using the normal deployment script before asking the user to test from Apps.

## Verification

Scale tests to the change. Before committing, run the relevant checks:

- `python -m py_compile server/pocketcinema_server.py`
- `python -m unittest server.test_stremio_account server.test_pocketcinema_server -v`
- Parse every changed `.sh` with `sh -n` or Git Bash `sh -n`.
- Parse all changed `.ps1` files with the PowerShell parser.
- For server changes, exercise `/api/status`, search, metadata, streams, play
  session creation, and a byte-range media request on an alternate local port.
- For selector changes, cross-compile with `-Wall -Wextra -Werror` and verify the
  rebuilt binary matches the committed binary when using the same toolchain.
- For discovery-helper changes, use `scripts/build-miyoo-discovery.ps1` with
  `-Wall -Wextra -Werror`, verify the committed binary, and test a real local
  broadcast response from the device.
- For deployment, verify executable permissions, absence of stale test markers,
  and absence of leftover selector, FFplay, or UI processes.
- For controller, framebuffer, or audio changes, obtain a physical Apps-menu
  confirmation and collect the corresponding device log.

The cross-toolchains used during development live under ignored `.tmp/` paths
and are not repository dependencies. Do not commit them.

Use `scripts/deploy-miyoo.ps1` for repeatable tracked-file upgrades. It must
continue preserving the live client config, logs, all networking-provider
runtime/state, and OnionOS files. Use
`scripts/build-miyoo-selector.ps1 -VerifyCommitted` for the documented
reproducible selector check.

When tracked Miyoo client changes require Apps-context physical testing,
deployment with `scripts/deploy-miyoo.ps1` is part of test preparation and must
be performed automatically unless the user explicitly declines deployment.
Interactive blank-password SSH authentication is expected and is not a reason
to skip deployment.

## Regression Impact and Evidence Inheritance

Historical automated and physical evidence remains valid unless a later change
materially intersects the behavior it validated. Do not equate a new commit,
time elapsed, or a test not repeated in the current session with an invalidated
milestone.

Before requesting physical testing for a meaningful change, establish the
baseline and inspect the diff, history, rename detection, relevant callers, and
tests. Classify each affected area as behaviorally changed, mechanically
renamed, unchanged, or uncertain, then intersect it with the validated
workflows and evidence. Record a concise regression-impact matrix with: changed
area; affected evidence/workflow; required verification; inherited evidence;
and reason. Run applicable automated/static checks first.
Request only the smallest Apps-context physical acceptance that resolves the
remaining risk, naming the changed component and exact reason.

Evidence must be revisited only when a change materially affects validated
code, dependency behavior, configuration semantics, deployment/runtime paths,
platform assumptions, or a documented invariant; when relevant automated
regression checks fail; or when evidence itself is invalidated. Cosmetic work,
documentation-only changes, nonsemantic assets, and mechanical renames do not
invalidate unrelated evidence.

For an identity rename, target paths, script names, environment/configuration
keys, migration, process detection, app metadata, and deployment endpoint names.
Do not blanket-rerun playback, subtitle, transcoding, or account-compatibility
matrices when their code and semantics are unchanged. Physical observation stays
authoritative, but it is expensive: request focused evidence rather than a full
historical matrix. A milestone remains Confirmed when its historical evidence
is inherited; "not re-tested today" is not "unconfirmed."

## Documentation and Milestones

- `docs/roadmap.md` is authoritative for status and sequencing.
- POC evidence documents record only confirmed observations. Clearly label
  assumptions and unmeasured behavior.
- A milestone becomes **Confirmed** only when its acceptance criteria have been
  met; device-facing criteria require a physical Miyoo test.
- When completing a milestone, update the roadmap and its evidence document in
  the same commit.
- Keep one milestone marked **Next**. Move unrelated ideas to **Deferred** rather
  than expanding active scope.

## Git Discipline

- Preserve unrelated user changes and the working network/playback baseline.
- Do not commit generated logs, Python caches, local addon configuration, media,
  downloaded toolchains, or runtime networking-provider files.
- Review staged changes for private URLs and tokens before pushing.
- Use focused commits that describe the completed milestone or fix.
- Push only after local checks pass and the worktree contains the intended files.

## Mandatory Session Bootstrap

Previous Codex conversation context is non-authoritative. At the start of every
session, reconstruct current truth from, in order:

1. `PROJECT_STATE.md`;
2. current code and tests;
3. `docs/roadmap.md`;
4. `RELEASE_READINESS.md`;
5. relevant evidence;
6. Git history.

Conversation memory comes after repository evidence and must never override it.
If the repository changes after a conversation begins, re-read the relevant
state before relying on an older conclusion.

Before coding, every Codex session MUST:

1. Read `PROJECT_STATE.md` and `AGENTS.md`.
2. Run `scripts/dev-status.ps1` on Windows or `scripts/dev-status.sh` through
   `/bin/sh` on macOS/Unix.
3. Check the current branch, local `HEAD`, complete working-tree state, and
   configured remote branch. Inspect every existing change before proceeding.
4. Verify the latest checkpoint recorded in `PROJECT_STATE.md` and whether it
   is reachable from `origin/main`. Fetch explicitly when the read-only status
   script reports the remote state unverified.
5. Stop and report before development if the checkout is behind, diverged, or
   contains unexplained work. Never overwrite or silently discard dirty files.
6. Read the active milestone in `docs/roadmap.md`, relevant gates in
   `RELEASE_READINESS.md`, and evidence relevant to the task.
7. Inspect recent feature history with `git log`, `git show`, `git blame`, or
   `git diff` as appropriate.
8. Compare current code and tests with physically confirmed production behavior.
9. Continue from `Next exact action` in the latest verified checkpoint unless
   the user's new request explicitly changes scope.
10. If Miyoo access is required, verify SSH using the documented legacy MAC
    option before reporting the device unreachable.

`Follow the repository guidelines and continue where I left off.` means:
perform this bootstrap, verify synchronization and the remote checkpoint, then
resume its exact handoff. Do not ask the user to reconstruct the previous task
unless repository evidence is genuinely ambiguous.

### Document precedence and conflicts

Use this precedence unless repository evidence establishes a better structure:

1. `PROJECT_STATE.md` — current operational truth, production invariants, and
   handoff.
2. Current code and tests — implementation reality, which may contain a
   regression.
3. `docs/roadmap.md` — milestone sequencing and official status.
4. `RELEASE_READINESS.md` — release gates and scope.
5. Latest feature/milestone evidence — physical validation and test history.
6. Older evidence and historical docs — historical reference only.

Current code does not automatically override a physically confirmed invariant.
If `PROJECT_STATE.md`, code, roadmap, release readiness, evidence, or recent
history disagree, STOP before changing code and report:

```text
STATE CONFLICT DETECTED

Feature:
Current code behavior:
PROJECT_STATE behavior:
Roadmap status:
Latest evidence:
Relevant recent commits:

Assessment:
```

Do not silently choose the most convenient source. A physically confirmed
feature that later disappears is a regression, not a simplification. For an
existing feature, record the latest implementation, relevant commit, physical
behavior, invariant, and whether current code matches before editing. Restore
confirmed behavior when it has regressed while preserving newer valid work.

### Promotion and handoff rules

Experimental work becomes production only when implementation, automated
checks, required physical Miyoo tests, evidence, roadmap, and
`PROJECT_STATE.md` are updated, and all related changes are committed together.
Every meaningful session must update `PROJECT_STATE.md`'s Development Handoff.

Use these terms precisely: Implemented means code exists; Tested means
automated or non-device validation exists; Physically Confirmed means observed
working on the actual Miyoo Mini Plus; Production means accepted baseline
behavior; Experimental means not yet accepted as baseline; Regressed means
previously confirmed production behavior is missing or broken; Deferred means
intentionally inactive work.

Use `scripts/dev-status.ps1` on Windows or `scripts/dev-status.sh` on macOS
for the read-only synchronization check. A stale, dirty, diverged, or
unverified checkout must be reported before development proceeds. These
scripts never pull, rebase, reset, or stash.

## Session Checkpoint and Handoff

A development session is not safely handed off while valuable project work
exists only in a local checkout. The configured remote repository is the durable
cross-machine checkpoint.

Treat `I will continue later`, equivalent pause/end wording, or an indicated
Windows/macOS machine switch as an instruction to run the full checkpoint
procedure automatically. Do not merely acknowledge the pause and leave work
local. A verified remote checkpoint should exist before any machine switch.

### Verified checkpoint

A checkpoint is valid only when:

- intended work has been reviewed and appropriately validated;
- acceptance state and evidence are updated where required;
- all intended project changes are committed and pushed without force;
- `PROJECT_STATE.md` identifies a concrete checkpoint commit;
- a subsequent `git fetch origin` confirms that commit is reachable from
  `origin/main`;
- the local branch is not behind or diverged; and
- no valuable implementation work remains only locally.

The working tree should be clean. Intentionally retained local or untracked
files must be reported and must not contain valuable project work, secrets,
account configuration, runtime state, or other material needed to continue.

Git commits cannot contain their own immutable IDs. Therefore the focused work
commit is the recorded `Checkpoint commit`, and a follow-up metadata-only seal
commit may write that ID into `PROJECT_STATE.md`. Both commits must be pushed;
the recorded checkpoint must be an ancestor of the fetched `origin/main`.

Keep `PROJECT_STATE.md` concise. It answers what is production, physically
confirmed, experimental, active, broken, safely checkpointed, and next. Put
detailed test histories in the roadmap and evidence documents. A checkpoint may
contain implemented and locally tested work awaiting a Miyoo test, but it must
distinguish `Implemented/tested but not physically confirmed` from `Physically
confirmed` and name the required next physical test. Committing does not promote
unmeasured device behavior.

### Checkpoint creation procedure

At the end of every meaningful development session:

1. Inspect `git status`, including all untracked files.
2. Review every changed or untracked file.
3. Separate intended project work from logs, caches, runtime files, account
   configuration, secrets, generated media, and local screenshots unless a
   screenshot is intentionally tracked.
4. Run validation appropriate to the work.
5. Update the roadmap and evidence if acceptance state changed.
6. Update the concise current state in `PROJECT_STATE.md`.
7. Update `Latest Verified Checkpoint`, preserving the distinction between
   implementation/testing and physical confirmation. Before the focused work
   commit exists, it may still identify the prior verified checkpoint.
8. Stage only intended project files and review the staged diff for private
   URLs, tokens, credentials, generated data, and unrelated work.
9. Commit with a focused message. Never use `git reset --hard`, silently discard
   local work, or rewrite shared history.
10. If needed, create the metadata-only seal described above so
    `PROJECT_STATE.md` records the new focused work commit.
11. Push normally to `origin/main`; never force-push.
12. Run `git fetch origin`.
13. Verify the recorded checkpoint is reachable from `origin/main`, the local
    branch is not behind/diverged, and run the appropriate read-only
    `dev-status` script again.

### Handoff reporting

If any required checkpoint step cannot be completed, report exactly this shape
and do not say done, complete, ready to continue, or equivalent:

```text
HANDOFF INCOMPLETE

Reason:

Work existing only locally:

Uncommitted files:

Unpushed commits:

Remote state:

Safe to continue from another machine: NO
```

After a successful checkpoint, report:

```text
CHECKPOINT COMPLETE

Checkpoint commit:
Remote verified: YES
Branch:
origin/main:
Working tree:
Active milestone:

Completed this session:

Pending:

Next exact action:

Safe to continue from another machine: YES
```

The development-status scripts are strictly read-only. They may inspect local
and remote state but must never fetch, pull, commit, push, reset, rebase, stash,
or modify files. `Checkpoint reachable from origin/main: NO` must produce a
prominent `REMOTE HANDOFF INVALID` warning and prohibit continuation from a
different machine.
