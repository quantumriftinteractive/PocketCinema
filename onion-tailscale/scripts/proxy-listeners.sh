#!/bin/sh

# Companion-owned listener defaults. Callers may override either value at
# launch, but both the daemon startup and controller UI use this one source.
SOCKS5_LISTEN="${TS_SOCKS5_LISTEN:-127.0.0.1:1055}"
HTTP_PROXY_LISTEN="${TS_HTTP_PROXY_LISTEN:-127.0.0.1:1055}"
