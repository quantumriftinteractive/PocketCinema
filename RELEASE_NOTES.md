# PocketCinema v1.0.0

PocketCinema v1.0.0 is a thin streaming client for the Miyoo Mini Plus running
OnionOS, paired with a PocketCinema Server desktop companion.

## Included

- Movie and series browsing, search, seasons, episodes, and source selection.
- My Library and Continue Watching with resume and Play from Start.
- Stremio account and addon integration, with credentials and upstream URLs
  kept on the PCServer.
- Subtitle selection, selectable subtitle tracks, audio-track selection, and
  the bounded server-side subtitle/downscaling fallback.
- Live TV from compatible linked Stremio addons.
- Local-network connection and optional remote access through the standalone
  Tailscale companion or another configured private route.
- PocketCinema Server desktop controls for configuration, connection routes,
  owned-server lifecycle, and media-tool detection.
- Bundled desktop FFmpeg/FFprobe 9.0.1 in the macOS package. The Windows
  package uses the documented bundled media tools and notices.

## Important notes

- Windows v1 is unsigned. On a trusted home network, use a Private network
  profile and allow PocketCinema Server through Windows Defender Firewall when
  prompted. PCServer uses TCP 8755 and local discovery uses UDP 8754. Public
  network policies that disable inbound rules can block local connections.
- The macOS app is ad-hoc signed and is not Developer ID signed or notarized.
  macOS may show a Gatekeeper warning; use the normal Privacy & Security
  approval flow only when the package is trusted.
- Remote v1 uses the separately installed and configured Tailscale companion;
  PocketCinema does not start, stop, or administer Tailscale.
- The Miyoo selector retains the v1 limit of 64 displayed items where that
  limit applies.
- PocketCinema does not write to Stremio accounts or catalogs.
- Selectable subtitle preparation may take roughly 60 seconds before playback
  starts in some cases.
- A Library release year may display `????` when the source does not provide a
  usable year.

The Windows application must be extracted with its complete `_internal`
directory beside the executable. The Miyoo package is copied to the documented
PocketCinema app directory; do not copy personal configuration, logs, or state
into a release package.
