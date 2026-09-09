# Troubleshooting

## PocketCinema cannot connect

- Confirm PocketCinema Server is running and its status says **Running**.
- Use the PocketCinema connection address shown by the desktop app, not the
  Stremio Service address.
- For Local, put both devices on the same trusted network.
- For Remote, confirm the independent private-network companion and any
  configured proxy are working.
- Check the computer firewall and the configured PCServer port.

> [SCREENSHOT SHOT-17]
> **Representative PocketCinema connection failure.**
> Include this only if the final error is concise and useful; hide private
> addresses before publication.

## Search or My Library is empty

Confirm the intended Stremio account is linked, its addons or service are
available, and PCServer can reach the configured service. Account-backed
catalogues can be temporarily unavailable.

## Playback does not start

Wait for PCServer to finish preparing the source, then try another source. Some
media cannot be played directly and some sources may be unavailable or outside
the supported playback range.

## Subtitles do not appear

Return to the subtitle selection screen, confirm a track is selected, and check
the preferred subtitle languages in Settings. The source may not provide a
compatible subtitle track.

## Remote use fails

Check the separate Tailscale companion or other private network first. Then
verify that the Remote PCServer address and optional HTTP proxy are correct.
PocketCinema does not manage the companion.

When asking for help, provide the feature being used and the sanitized message
shown by PocketCinema or PCServer. Never include passwords, tokens, account
keys, or raw upstream media URLs.
