# Troubleshooting

**The app cannot connect.** Confirm PCServer is running, `SERVER_BASE` uses the PCServer host rather than the Miyoo, the configured port is correct, and both devices can reach one another. Check the host firewall and proxy setting.

**The account or catalogs are empty.** Link the intended Stremio account again, confirm its addons are installed, and check PCServer’s account status. Addon catalogs can be unavailable temporarily or return no results.

**A stream does not start.** Wait for PCServer preflight/conversion to finish, then try another stream or channel. FFmpeg and ffprobe must be installed and available to PCServer for paths that require them. Unsupported codecs, audio, containers, or live formats may be rejected.

**Remote use fails.** Check the standalone Tailscale companion separately, then verify that the configured PCServer address is reachable through the private network. PocketCinema does not manage the companion.

When reporting a problem, include the sanitized PCServer/client error and the feature being used. Do not include credentials, tokens, or raw upstream URLs.
