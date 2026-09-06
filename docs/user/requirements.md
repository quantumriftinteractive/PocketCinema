# Requirements

- Miyoo Mini Plus running OnionOS.
- A computer on the same trusted network, or a reachable remote connection, running PocketCinema Server.
- `curl`, `jq`, and the PocketCinema selector/runtime files on the Miyoo.
- FFmpeg and ffprobe on the PCServer host for compatibility checks and conversion paths.
- Optional: a Stremio account and compatible addons. PocketCinema does not require a particular addon.

The Miyoo does not contact Stremio directly. It only needs the PCServer URL and, optionally, a generic HTTP proxy setting.
