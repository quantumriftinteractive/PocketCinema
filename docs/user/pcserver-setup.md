# PocketCinema Server setup

PocketCinema Server is the computer-side service used by the Miyoo. On Windows, use `server/manage-server.ps1`; on macOS, use `server/manage-server.sh`.

The typical PCServer port is `8755`, but the configured port is authoritative. Keep the listener on a trusted LAN or private network. Do not expose it directly to the public internet.

For Stremio Service, the usual local endpoint is `http://127.0.0.1:11470`. It is configurable and must be reachable from the PCServer host. PCServer keeps addon credentials and upstream media URLs on the computer; the Miyoo receives opaque stream identifiers.

After starting the server, configure the matching PCServer URL on the Miyoo and confirm the server status from the app or a browser on the trusted network.
