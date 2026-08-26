# PocketStremio Current Project State

Last updated: 2026-08-26
Last updated by machine: macOS development checkout
Current branch: `main`
Production baseline commit: `3b4962fcbd97e569195ae5b94d6f1c8794fa1adf`
Expected remote branch: `origin/main`
Active milestone: Milestone 21 — Device Settings and Playback Preferences
Release state: Not release-ready; Milestone 22 is physically confirmed, while
fresh-install, packaging/licensing, and final release-scope gates remain open.

## Production Baseline

The committed baseline includes the confirmed PocketStremio vertical slice:

- movie and series search;
- season and episode browsing;
- opaque server-side stream selection and play sessions;
- direct compatible playback and bounded converted playback;
- Continue Watching, Resume, and Play from Start;
- account-backed direct HTTPS playback with host-side token isolation;
- verified converted audio-track selection;
- English subtitle burn-in and bounded 640x360 downscaling;
- selectable Matroska subtitles as an opt-in app-local mode: up to three
  server-normalized text tracks per preferred language, R1 cycling, and
  automatic burn-in fallback;
- clean Miyoo Menu exit and cleanup of playback/conversion state.

The normal production fallback remains the server-mediated MPEG-TS burn-in
path. Selectable Matroska playback is confirmed, but its inclusion in a v1.0
release is still a release decision.

## Production Invariants

- Keep upstream addon URLs, subtitle URLs, and account credentials on the PSS
  host; device APIs, logs, and process arguments expose only opaque IDs.
- PocketStremio uses direct HTTP by default and an optional generic proxy. It
  does not start, stop, inspect, or authenticate Tailscale.
- Stremio Service access remains loopback-only on the PSS host, with the
  existing inbound firewall block preserved.
- Continue Watching must preserve Resume and Play from Start semantics.
- Playback readiness, Menu exit, cancellation, and failure must leave no stale
  FFplay, helper, conversion, bridge, marker, or temporary subtitle state.
- Converted output must preserve the measured compatibility envelope and
  reject unsupported media before FFplay.

### Matroska subtitle tracks

- Multiple subtitle tracks are required in selectable Matroska mode.
- The physical acceptance run used three English text tracks.
- R1 cycling through tracks, subtitles off, and back to the first track is
  production-confirmed and must remain available.
- A one-subtitle implementation is a regression unless explicitly approved.

### Converted audio

- Verified multi-audio converted streams must allow manual track selection.
- The selected ordinal must reach the bounded converter and Quick Resume path.

```yaml
production_invariants:
  matroska_subtitles:
    multi_track: true
    maximum_packaged_tracks: 15
    maximum_tracks_per_language: 3
    minimum_physically_confirmed_tracks: 3
    track_switching: true
    off_toggle: true
    status: physically_confirmed
  converted_audio:
    manual_track_selection: true
    status: physically_confirmed
  continue_watching:
    resume: true
    play_from_start: true
    status: physically_confirmed
  stream_opacity:
    upstream_urls_hidden_from_device: true
    account_tokens_host_only: true
    status: physically_confirmed
```

## Physically Confirmed Behavior

Milestones 1–16, 18, 20, and 22 are marked Confirmed in the roadmap.
Milestone 17 remains incomplete and Milestone 21 is active. The latest
physical Milestone 22 evidence confirms three-track Matroska playback,
synchronized audio/video/subtitles, R1 notices, progress saving, status-0
Menu exit, and complete PSS/Miyoo cleanup.

## Experimental / Not Yet Production

- Milestone 21 work recovered from the Windows checkout is committed on the
  reconciled `main`, but remains pending acceptance and is not yet part of the
  production baseline.
- The selectable Matroska player remains an opt-in release-scope decision.
- Generalized preferred-language packaging and the normal-deployment player
  bundle are implemented and automated-tested, but only the three-track
  English Apps-context invariant is physically confirmed. A six-track,
  multi-language Apps-context run is still required before expanding that
  physical claim.
- Unmeasured codecs, containers, encrypted or fragmented-MP4 HLS, arbitrary
  seeking in live converted output, and offline downloads remain outside the
  production baseline.

## Known Regressions / Broken Behavior

- No Matroska multi-track regression is present in the audited committed code.
- The Windows implementation and state/documentation recovery have been
  reviewed and reconciled with the updated Mac `origin/main`; acceptance and
  release gates remain open.
- Milestone 17 long-duration bridge acceptance, fresh-SD validation, and final
  packaging/licensing gates remain open.

## Active Work

Milestone 21: device settings and playback preferences. The reconciled `main`
contains the recovered implementation and documentation changes for language
preferences, stream/audio filtering, Continue Watching removal, and related
client/server behavior. Do not label them production until they are physically
confirmed where required and the milestone is accepted.

## Last Completed Work

Milestone 22 selectable Matroska subtitles was accepted as Confirmed. The
relevant implementation history is `b240328`, `3c29d15`, and `bd6d91a`.
The current working tree generalizes packaging to five preferred languages,
up to three tracks each, and promotes the app-local player/runtime/font bundle
into normal Miyoo deployment; the generalized behavior remains physically
pending.

## Next Action

Run the remaining Milestone 21 automated and Apps-context checks. Update the
roadmap, evidence, and this file together only when the milestone is actually
accepted.

## Latest Verified Checkpoint

Checkpoint commit: `42b0861dfdf6853cbcc974f55401c1d7b15c8fd7`
Remote verified: YES
Machine: macOS development checkout
Branch: `main`
Active milestone: Milestone 21 — Device Settings and Playback Preferences

Completed:
- Added the permanent session bootstrap, pause/machine-switch handoff protocol,
  verified-checkpoint rules, and read-only cross-platform status reporting.

Physically confirmed:
- Milestone 22 three-track Matroska switching, off toggle, synchronized
  playback, progress, Menu exit, and cleanup; a later run also exercised three
  English and three Greek tracks.

Implemented/tested but not physically confirmed:
- Milestone 21 language-priority reordering and remaining settings/preferences
  acceptance work.
- Both checkpoint-status implementations parse and run; no Miyoo product
  behavior changed and no device test applies to the protocol itself.

Known issue / blocker:
- Milestone 21 remains pending Apps-context acceptance; release gates remain
  open.

Next exact action:
- Physically test language-priority reordering, then complete the remaining
  Milestone 21 acceptance checks without changing release scope.

Required next physical test:
- Reorder preferred languages from the controller UI, save, and verify the
  chosen order affects subsequent language-prioritized choices.

DO NOT:

- collapse Matroska subtitles to one track;
- replace the production burn-in fallback without measured acceptance;
- change Tailscale lifecycle from PocketStremio;
- treat dirty working-tree changes as committed production state.
