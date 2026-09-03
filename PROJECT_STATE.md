# PocketStremio Current Project State

Last updated: 2026-09-03
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

The current Mac PSS/Miyoo path is also physically confirmed with an FFmpeg
build lacking libass: it discovered and packaged six selectable tracks, served
the opaque package, switched tracks through R1, and saved progress. Normal
MPEG-TS subtitle burn-in remains unavailable on that FFmpeg build.

The Milestone 21 controller reordering flow has also been physically exercised:
Spanish was placed first, the next app launch loaded `spa,jpn,eng,ell`, and the
user reported the subsequent playback test as working. A menu inconsistency was
was then characterized and fixed: B from Stream source now returns directly to
the title action screen rather than falling into a filtered stream list. The
device log records the cancellation path. The unrelated provider-result
stability follow-up remains pending its own physical retest.

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
- The first physical no-preferred-subtitle test exposed a Milestone 21 defect:
  a missing preferred language silently started playback without subtitles.
  The user-directed correction now has Apps-context confirmation: it names the
  missing preference, offers no subtitles, offers English only when available
  and not already preferred, and returns Back to the stream list. Its earlier
  file-level alternate-subtitle picker was deliberately removed.
- The Windows implementation and state/documentation recovery have been
  reviewed and reconciled with the updated Mac `origin/main`; acceptance and
  release gates remain open.
- The no-config first-run path cannot currently connect to a tailnet-only PSS:
  it starts direct, so manual entry and discovery validation cannot use the
  app-local generic proxy that the saved configuration normally supplies. The
  discovery response is seen but rejected at status validation; the original
  live configuration was restored unchanged after this test.
- Milestone 17 long-duration bridge acceptance, fresh-SD validation, and final
  packaging/licensing gates remain open.

## Active Work

Milestone 21: device settings and playback preferences. The reconciled `main`
contains the recovered implementation and documentation changes for language
preferences, stream/audio filtering, Continue Watching removal, and related
client/server behavior. Do not label them production until they are physically
confirmed where required and the milestone is accepted.

The first-run local/remote onboarding design is documented in
`docs/portable-connection-onboarding-plan.md`. Its companion endpoint-display
phase is implemented, statically validated, and deployed to the Miyoo, but
pending an OnionOS Apps-context test; no PocketStremio client or network
behavior changed.

## Last Completed Work

Milestone 22 selectable Matroska subtitles was accepted as Confirmed. The
relevant implementation history is `b240328`, `3c29d15`, and `bd6d91a`.
The current code also makes Matroska subtitle discovery explicit, so its
packageable text tracks remain available on a PSS whose FFmpeg lacks libass.
The normal deployment script can now verify and reuse an already-installed
player/runtime bundle for tracked client upgrades when its ignored local build
inputs are unavailable.

## Next Action

Run the remaining settings/preference Apps-context checks. Update the roadmap,
evidence, and this file together only when the milestone is actually accepted.

## Latest Verified Checkpoint

Checkpoint commit: `7af07d6b1b9d0f9aa29e514d941f82abe4a5c5fc`
Remote verified: YES
Machine: macOS development checkout
Branch: `main`
Active milestone: Milestone 21 — Device Settings and Playback Preferences

Completed:
- Implemented the companion-only HTTP proxy endpoint display. The shared
  listener source preserves the `127.0.0.1:1055` default and the existing
  launch-time overrides; shell/static checks pass and the change was deployed
  through the tailnet with existing device binaries preserved. The Apps test
  remains pending.
- Recorded the proposed portable local/remote connection design, including the
  independent companion proxy display, editable generic proxy, first-run flow,
  two-route automatic behavior, release packaging boundary, and acceptance
  tests. This is planning only; no product behavior changed.
- Added explicit Matroska subtitle discovery, preserving the libass requirement
  for the normal burn-in path.
- Added an opt-in, verified reuse mode to the standard Miyoo deployment script
  for tracked upgrades where the player/runtime bundle already exists.
- Recorded the physical Spanish-first language-priority persistence and
  user-confirmed playback test, while preserving the reported menu inconsistency
  as an unconfirmed follow-up.
- Fixed and physically confirmed source-menu B/back cancellation; added the
  automated-tested stream-list stability cache and no-verified-audio-tag path.
- Recorded the physical same-title stream-list stability confirmation.
- Added and deployed the bounded multi-line infoPanel message wrapper.
- Corrected unavailable subtitle preferences with an explicit bounded fallback:
  no subtitles, a safe other-language picker, or Back to the existing stream
  list. The correction is automated-tested and deployed.
- Replaced that file-level picker with the user-directed named-preference,
  no-subtitles, English-if-available, and Back-to-streams fallback. It is
  automated-tested and deployed.

Physically confirmed:
- Milestone 22 three-track Matroska switching, off toggle, synchronized
  playback, progress, Menu exit, and cleanup; a later run also exercised three
  English and three Greek tracks.
- On a Mac PSS without libass, six selectable tracks were packaged and played;
  R1 switched tracks, and progress was saved.
- Controller language-priority reordering persisted Spanish first across an app
  restart; the user reported the subsequent playback test working.
- B from Stream source cancels to the title action screen; this was observed in
  Apps and logged as `stream source selection canceled`.
- Same-title stream reopening remained stable during the navigation-debug
  interval. The device logged repeated resolution, while PSS served later
  identical requests without a repeated addon fetch.
- The normal PSS no-verified-audio-tag path appeared and continued to explicit
  stream selection. Its original one-line notice was hard to read on the Miyoo.
- A PSS scan response rendered cleanly as a wrapped two-line infoPanel message
  from the Apps context.
- The controller offered three selectable subtitle tracks in deterministic
  preference order: Greek first, followed by English.
- With Greek preferred and the local compatibility video selected, the
  unavailable-preference dialog named the English fallback, and choosing
  `Use English subtitles` reached the selectable-subtitle playback stream.
- That fallback cached three English tracks; R1 cycled all three and subtitles
  off, then playback exited cleanly and saved progress. With `ell,eng` saved,
  replay correctly bypassed the fallback dialog.
- Source-name filtering selected the local compatibility source from a
  multi-provider result, showed its filtered stream list, and B returned
  cleanly through the title screen with no stale app markers.

Implemented/tested but not physically confirmed:
- The standalone Tailscale companion now shows its HTTP proxy listener in the
  controller footer. Startup and UI share the existing `TS_HTTP_PROXY_LISTEN`
  default/override source; the required Apps-context visual/controller test is
  pending.
- Remaining separate Milestone 21 settings/preferences acceptance work,
  including first-run local/remote proxy onboarding and the precise
  subtitle-download and conversion-startup failure categories.

Known issue / blocker:
- Milestone 21 remains pending Apps-context acceptance; release gates remain
  open.
- Tailnet first-run onboarding is blocked until the app can obtain its generic
  HTTP proxy without relying on an already-existing PocketStremio config.

Next exact action:
- Run the required OnionOS Apps-context visual/controller test before beginning
  PocketStremio proxy/onboarding work.

Required next physical test:
- From Apps -> Tailscale, confirm both Enabled and Disabled screens retain their
  existing state/IP/control behavior and visibly show the exact configured HTTP
  proxy endpoint. Then perform the existing enable/disable/re-enable check
  without changing PocketStremio or Tailscale identity/state.

DO NOT:

- collapse Matroska subtitles to one track;
- replace the production burn-in fallback without measured acceptance;
- change Tailscale lifecycle from PocketStremio;
- treat dirty working-tree changes as committed production state.
