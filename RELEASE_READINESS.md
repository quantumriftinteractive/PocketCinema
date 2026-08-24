# PocketStremio Release Readiness

This document is derived from `AGENTS.md`, `README.md`, `docs/roadmap.md`, the
deployment scripts, and the evidence documents. It describes the work needed
for a conservative v1.0 release; it is not a claim that v1.0 is currently
ready.

Current assessment: **not release-ready**. The normal PocketStremio vertical
slice and Milestone 20 bounded subtitle/downscaling path are physically
confirmed. The remaining release work includes fresh-install regression,
packaging and licensing review, and a deliberate decision about whether the
confirmed Milestone 22 selectable-Matroska mode is included in v1.0.
The opt-in app-local FFplay/libass path now opens a real account stream without
a redundant subtitle picker, packages three English text tracks, cycles them
and off with R1, displays a one-second track notice, and cleans up after Menu
exit. Automatic fallback into the unchanged production MPEG-TS burn-in flow is
physically confirmed from Apps after a server-mode negotiation failure. The
normal subtitle picker selected the test subtitle, the production converter
burned its 0.5-second cue into a 640x268 stream, and the app-local player
presented it centered at `0,106`; the user reported that it did not look
stretched. Two runs saved 26 and 5 valid watched seconds and exited cleanly. A
separate forced missing-candidate diagnostic reached the same burn-in flow but
showed that Onion FFplay visibly distorts the correctly encoded output. A final
110-second real-account run explicitly confirmed smooth, synchronized video,
audio, and subtitles, bounded resource use, status-0 Menu exit, progress
saving, and complete PSS/Miyoo cleanup. Milestone 22 is therefore physically
**Confirmed**.

## What v1.0 requires

### Product requirements

- Apps-context browsing works for search, movies, series, seasons, episodes,
  stream selection, Play, Continue Watching, Resume, Play from Start, B/back,
  and Menu exit.
- At least one reproducible legal direct HTTP(S) movie and episode path works
  through the server-side resolver without exposing upstream URLs or tokens.
- Direct-play compatibility is bounded and measured; unsupported codecs and
  unsafe stream shapes fail before FFplay with a useful message.
- The bounded conversion path produces synchronized H.264/AAC output at the
  supported resolution profile, burns a correctly matched English subtitle,
  saves progress correctly, and cleans up after Menu exit.
- 720p/1080p sources are downscaled when required rather than presented as
  assumed direct-play streams.
- A clean account can be linked through the official temporary approval flow,
  with credentials remaining on the gaming PC.
- A fresh SD-card installation can be configured without copying private URLs,
  tokens, generated media, logs, or runtime state from the development machine.
- The app returns to OnionOS cleanly after success, cancellation, network
  failure, FFplay failure, and Menu exit.

### Release gates

- Keep the physically confirmed Milestone 20 acceptance evidence aligned in
  `docs/bounded-transcoding.md` and `docs/roadmap.md`; do not regress its
  production MPEG-TS burn-in fallback.
- Milestone 22's selectable-Matroska acceptance criteria, including fallback
  and synchronized A/V, are physically confirmed. If the feature does not ship
  in v1.0, keep the mode disabled and omit its experimental player artifacts.
- Resolve the current app-local-player packaging dependency explicitly: either
  ship a physically accepted, reproducible binary with its source/configuration
  and notices, or change the release configuration to a verified player that
  is actually present on a fresh installation.
- A fresh-SD test passes with a clean account or explicitly documented no-account
  mode.
- A normal direct-play movie, a series episode, a converted subtitle case, and
  a server restart/recovery case pass from Apps.
- A converted multi-audio stream allows choosing a verified audio track before
  playback; this is now physically confirmed. Persistent language preferences
  remain outside the current release gate.
- R1/R2 behavior is documented from the deployed builds. The current candidate
  physically confirmed all three R1 track transitions, off, return to the first
  track, and one-second notices. R2 did not trigger the earlier candidate and
  is not the selectable-subtitle control.
- Server unit tests, Python compilation, shell parsing, PowerShell parsing, and
  selector reproducibility checks pass.
- No private configuration, account key, Tailscale state, upstream URL, token,
  generated binary, local fixture, or log is staged for release.
- Installation, rollback, support, known limitations, and license notices are
  included with the GitHub release.

## What can be deferred

These are explicitly outside a minimal v1.0 unless the release scope is
expanded:

- account library/catalog browsing;
- favorites, richer history, posters, image caching, and a full UI;
- persistent audio-language preferences beyond the now-confirmed per-play
  converted-track selection;
- arbitrary seeking in a nonseekable live converted response;
- offline downloads;
- torrent ingestion, P2P handling, or local torrent management;
- server discovery and automatic hostname discovery;
- an integrated FFplay pause menu;
- support for arbitrary codecs, HDR, HEVC, AV1, multichannel audio, encrypted
  HLS, fragmented MP4 HLS, or unmeasured containers;
- Tailscale account replacement/removal from the remote PocketStremio UI.

Deferred work must remain outside the active milestone and receive its own
acceptance criteria before implementation.

## Installation prerequisites

### Gaming PC

- Windows with PowerShell and Python available on `PATH`.
- The repository checked out to a stable directory.
- `ffprobe.exe` and `ffmpeg.exe` available, normally from the installed
  Stremio runtime or explicit `-FFprobePath`/`-FFmpegPath` arguments.
- The PocketStremio server host address reachable from the Miyoo. Direct LAN
  HTTP is supported; Tailscale is optional transport infrastructure.
- Optional Stremio Service installed and reachable locally at
  `http://127.0.0.1:11470`.
- Optional stream addon manifests configured in ignored
  `server/config/stream_addons.json`.
- Optional account binding performed only through the official temporary
  approval flow.

### Miyoo

- Miyoo Mini Plus running the tested OnionOS version or a separately measured
  compatible version.
- SD card with sufficient free space for app files, logs, and any explicitly
  bounded local data.
- Wi-Fi configured and connectivity to the server address.
- PocketStremio persistent files under
  `/mnt/SDCARD/App/PocketStremio/` only.
- Onion-provided `curl`, `jq`, `kbinput`, `infoPanel`, SDL 1.2, and FFplay.
- SSH access for deployment and log collection during testing.
- Do not overwrite the live config during deployment.

## Clean-account onboarding path

1. Install and start the gaming-PC server with no account key present.
2. Configure only the required server host, port, and legal addon manifests.
3. Verify `GET /api/status` locally and from the intended Miyoo transport.
4. On the Miyoo, install the tracked PocketStremio app files and create the
   app-local config from `client/miyoo/pocketstremio.conf.example`.
5. Set `SERVER_BASE` to the gaming-PC address. Set `PROXY` only if the
   independently managed network provider requires it.
6. Open PocketStremio and confirm status/search before linking an account.
7. Choose **Stremio Account -> Connect Account**. Scan or open the one-time
   official link, approve it, then press A to poll.
8. Confirm that the Miyoo receives only the approval UI and sanitized account
   status. The auth key remains in ignored
   `server/config/stremio_account.json` on the gaming PC.
9. Play one legal direct HTTPS movie and one episode, then test a subtitle/
   converted case if that path is in the release scope.
10. To reset for another clean-account test, stop the server and remove the
    ignored server-side account config only after preserving no production
    identity that must remain. Never reset or reauthenticate the working
    Tailscale node as part of account testing.

## Fresh-SD test checklist

- [ ] Use a freshly formatted or disposable SD card and the target OnionOS
      version.
- [ ] Install only the release files and the documented OnionOS app metadata.
- [ ] Confirm no app files are written outside PocketStremio’s app directory,
      except the separately documented Tailscale startup hook when Tailscale is
      installed.
- [ ] Create `config/pocketstremio.conf` from the example and set `SERVER_BASE`.
- [ ] Verify direct transport; verify proxy transport separately if supported.
- [ ] Open Apps -> PocketStremio and test B cancellation on every selector.
- [ ] Search and play the deterministic compatibility fixture.
- [ ] Play one direct legal movie and one series episode.
- [ ] Test Continue Watching, Resume, Play from Start, pause tracking, and
      Menu exit.
- [ ] Test a converted English-subtitle/downscale case, including subtitle
      synchronization and cleanup.
- [ ] If the selected source has multiple audio tracks, verify the displayed
      FFprobe labels and choose the intended track before converted playback.
- [ ] If selectable Matroska subtitles are included, cycle all packaged tracks
      and off, then force one setup failure and confirm automatic return to the
      normal subtitle/burn-in flow without stale state.
- [ ] Test a bad server address and confirm a specific error followed by clean
      return to the UI.
- [ ] Reboot, reopen Apps, and confirm no stale process, panel, marker, or
      temporary playback state remains.
- [ ] Collect only sanitized logs needed for evidence; remove them before
      packaging the card or release archive.

## Windows server setup checklist

- [ ] Clone the repository and read `AGENTS.md` and `docs/roadmap.md`.
- [ ] Run `python -m py_compile server/pocketstremio_server.py`.
- [ ] Run `python -m unittest server.test_stremio_account server.test_pocketstremio_server -v`.
- [ ] Configure `POCKETSTREMIO_HOST` or pass `-HostAddress` to
      `server/manage-server.ps1`.
- [ ] Start with `server/manage-server.ps1 start`; use `status`, `restart`, and
      `stop` for lifecycle operations.
- [ ] Confirm `/api/status`, search, metadata, streams, play-session creation,
      and a byte-range media request.
- [ ] Confirm Stremio Service is local-only at `127.0.0.1:11470`.
- [ ] Keep the inbound Windows Firewall block for TCP `11470-11474` and
      `12470`; verify LAN and tailnet denial to those ports.
- [ ] Configure only legal, intended addon manifests in ignored files.
- [ ] Keep `server/config/stremio_account.json`, `server/data/`, logs, caches,
      and local media ignored and out of release artifacts.
- [ ] Verify server restart persistence for Continue Watching and bounded probe
      cache, and expected expiration of ephemeral play sessions.

## Tailscale setup checklist

- [ ] Treat Tailscale as an independent provider app, not a PocketStremio
      dependency or lifecycle component.
- [ ] Install the standalone app under `/mnt/SDCARD/App/Tailscale/`.
- [ ] Preserve its authenticated `state/tailscaled.state` and logs; never copy
      them into a release archive.
- [ ] Preserve the original PocketStremio rollback state and never run two
      daemons simultaneously.
- [ ] Connect a new account only through the Tailscale app’s official QR/login
      flow; do not use PocketStremio to manage identity.
- [ ] Confirm the Tailscale app shows Enabled and the assigned IP.
- [ ] Confirm the local proxy at `127.0.0.1:1055` if proxy transport is used.
- [ ] Confirm PocketStremio can reach the server through the proxy.
- [ ] Test Disable/Enable and reboot autostart only in the Tailscale app.
- [ ] Do not alter OnionOS core files; the only supported startup extension is
      the app-owned hook documented by the Tailscale subproject.

## Security and privacy review

### Required controls

- [ ] No account email, password, auth key, addon token, private addon URL,
      upstream media URL, subtitle URL, or Tailscale state appears in the
      Miyoo API, logs, process arguments, Git history, or release archive.
- [ ] `/api/streams` returns opaque stream IDs; `/api/play` returns opaque play
      URLs/session IDs.
- [ ] Account media is limited to safe direct HTTP(S) results; reject P2P,
      external-player, local/private-address, credential-in-URL, and unsafe
      schemes.
- [ ] Stremio Service remains loopback-only from PocketStremio’s perspective,
      with the Windows Firewall inbound block preserved.
- [ ] Local Files allowlisting remains explicit and never broadens to general
      user directories.
- [ ] HTTP proxy settings are optional and never cause PocketStremio to start,
      stop, inspect, or reauthenticate Tailscale.
- [ ] QR payloads are passed through stdin or local rendering paths rather than
      process arguments or third-party QR services.
- [ ] All user-derived paths, IDs, and URLs are quoted and JSON-encoded.
- [ ] Temporary subtitle, relay, progress, and stay-awake files are cleaned up
      on success, cancellation, failure, and Menu exit.
- [ ] Release review includes `git diff --cached`, `git status`, ignored files,
      and a search for `token`, `password`, `auth`, private IPs, and private
      URLs.

### Threats that remain operational

The server is intended for a trusted LAN/tailnet deployment, not an internet-
facing public service. Access control, TLS termination, addon trust, media
legality, and the security of the host operating system remain deployment
responsibilities. Do not expose the PocketStremio port publicly without a
separately reviewed authentication and transport design.

## Known limitations

- Miyoo memory is tight; active playback has measured very little reported free
  RAM. New resident processes and image-heavy UI features are risky.
- The Onion FFplay baseline has no built-in `subtitles` filter and cannot render
  external SRT directly.
- The app-local selectable-Matroska path is opt-in and integrated, with a
  physically confirmed real-stream no-picker flow, three-track R1 cycling,
  one-second notices, readiness-based progress, Menu cleanup, and zero active
  conversions after exit. Its automatic setup fallback is also physically
  confirmed from Apps for a server-mode negotiation failure: the normal picker
  and production burn-in path were used, the app-local player preserved the
  640x268 aspect ratio, and both runs saved readiness-based progress. The latest
  real multi-track run then explicitly confirmed smooth synchronized video,
  audio, and subtitles for 110 valid watched seconds. FFplay used at most
  20,304 kB RSS with zero process swap, Menu exit returned status 0, progress
  advanced from 766 to 876 seconds, and all PSS/Miyoo playback state cleaned up.
- A forced missing-candidate fallback proved normal subtitle selection,
  production burn-in, progress, and cleanup, but Onion FFplay visibly stretched
  a correctly encoded 640x268, 160:67 stream. Missing app-local player artifacts
  must therefore fail clearly; they are not an acceptable release fallback.
- The converted MPEG-TS path is nonseekable; D-pad seeking remains restricted.
- Resume positions are approximate and exclude startup/A-button pause time but
  do not model every buffering or seek interval.
- Direct-play support is bounded to measured envelopes. H.264/AAC and selected
  VP8/Vorbis cases are confirmed; other advertised formats remain candidates
  until Apps-context testing.
- Opus audio is rejected in the current compatibility envelope.
- The HLS bridge is bounded to unencrypted MPEG-TS and has only limited long-
  duration physical evidence.
- Account catalog browsing, persistent audio-language preferences, offline
  downloads, torrent/P2P ingestion, posters, and a full UI are not v1.0
  requirements. Per-play verified audio-track selection for converted streams
  is implemented and physically confirmed, but remains a limited preference
  rather than a full language-preference system.
- Tailscale clean-account onboarding and disconnected-boot behavior require
  separate physical testing; the working authenticated identity must not be
  reset during ordinary development.

## Licensing and dependency audit

This is a release-preparation inventory, not legal advice. Before publishing,
confirm every version actually shipped and include the applicable notices.

### Repository and runtime inventory

- PocketStremio server/client scripts: repository-authored code; retain the
  repository’s chosen license file if one is added before release.
- Project Nayuki `qrcodegen`: vendored MIT-licensed component; retain its
  notice and source attribution.
- SDL 1.2, `curl`, `jq`, `kbinput`, `infoPanel`, and Onion FFplay: runtime
  components supplied by OnionOS; do not redistribute OnionOS core files
  without checking Onion’s distribution terms.
- FFmpeg/FFplay experiment: FFmpeg 2.4.14 is LGPL 2.1-or-later when built and
  distributed under the selected configuration; preserve corresponding source,
  build configuration, and notices for any distributed binary.
- libass, FreeType, FriBidi, HarfBuzz, Fontconfig, zlib, bzip2, libpng,
  expat, glib, PCRE, libuuid, libts, and SDL runtime libraries: record exact
  versions, licenses, source URLs, and whether each is redistributed or merely
  linked from OnionOS.
- Tailscale binaries and dependencies: keep under the independent Tailscale
  subproject’s distribution and notice process; do not bundle its state.

### Audit actions before release

- [ ] Record `--version` output and build configuration for every bundled
      executable/library.
- [ ] Preserve source or written source-offer information for LGPL/GPL-covered
      components as applicable.
- [ ] Check static versus dynamic linking and ensure corresponding notices and
      relink/source obligations are met.
- [ ] Add a `THIRD_PARTY_NOTICES` file to the release archive.
- [ ] Confirm no ignored downloaded binary is silently included without an
      identified license and provenance.
- [ ] Review OnionOS, Stremio, Tailscale, FFmpeg, libass, and vendored QR
      notices against the exact release contents.

## GitHub release packaging checklist

- [ ] Release from a clean, reviewed tag on the intended branch.
- [ ] Run all automated checks listed in `AGENTS.md`.
- [ ] Generate only reproducible, release-appropriate selector binaries and
      explicitly documented app assets.
- [ ] Exclude `.tmp/`, server data, logs, caches, local media, account config,
      addon config, Tailscale state, downloaded toolchains, and test markers.
- [ ] Exclude the experimental FFplay binary unless the release scope explicitly
      promotes it after physical acceptance; never replace Onion’s original
      FFplay in an archive.
- [ ] Include tracked app/client/server files, documentation, setup examples,
      third-party notices, and a short changelog.
- [ ] Include SHA-256 checksums for release archives and any bundled binaries.
- [ ] State tested OnionOS version, Miyoo model, network modes, server OS, and
      required FFmpeg/FFprobe/Stremio versions.
- [ ] State that media sources and account/addon configuration are user-owned
      and must not be included.
- [ ] Provide installation, rollback, clean-account onboarding, and fresh-SD
      test instructions.
- [ ] Publish known limitations and explicitly label unconfirmed features.
- [ ] After publishing, test the downloaded archive—not the working tree—on a
      disposable SD card and clean Windows server profile.

## Current release decision

**Do not publish v1.0 yet.** The working burn-in/downscaling path remains the
safe production fallback, and Milestone 20 is no longer an open release blocker.
Milestone 22's selectable-Matroska path and corrected automatic fallback are
physically confirmed. A v1.0 that excludes selectable Matroska must keep the
option disabled and omit the experimental player artifacts. Fresh-SD
onboarding, final movie/episode/converted regressions, reproducible release
artifacts, third-party notices, and the privacy review must still pass before
publishing.
