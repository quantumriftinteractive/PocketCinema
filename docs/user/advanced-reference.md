# Advanced / Technical Reference

This section is for readers who need to understand how PocketCinema is built or
operated. Normal users can use the [v1 manual](index.md) without reading it.

## Architecture

The Miyoo is a lightweight client. It handles controller input, compact response
parsing, and launching playback. PCServer handles metadata, account/addon
requests, source resolution, compatibility checks, media preparation, and
server-side state.

The Miyoo contacts PCServer only. It does not contact Stremio Service directly.

## Network model

Direct HTTP on a trusted LAN is the normal transport. An optional generic HTTP
proxy can support a remote route. Tailscale is an independent OnionOS app and
owns its own identity, daemon, proxy, and state. PocketCinema never starts,
stops, authenticates, or inspects it.

PCServer may use a local Stremio Service endpoint such as
`http://127.0.0.1:11470`. That endpoint is PCServer-side and must not be entered
on the Miyoo.

## Stremio accounts, addons, and Library

Account credentials, addon configuration, upstream URLs, and account-backed
state remain on the PCServer host. PocketCinema exposes only the safe,
device-facing results needed for browsing and playback. My Library is read-only
from PocketCinema.

Useful deeper notes remain in the repository's [Stremio account
documentation](../stremio-account-addons.md) and [local Stremio Service backend
documentation](../local-stremio-service-backend.md).

## Playback and conversion

PCServer classifies sources before playback. Compatible sources can use a direct
path; other accepted sources use bounded conversion and downscaling. Unsupported
or unsafe results are rejected. The Miyoo receives a PocketCinema playback path,
not a raw upstream URL.

## Subtitles and progress

Subtitle discovery and preparation remain server-side. The accepted selectable
subtitle path can package multiple tracks for cycling; the bounded conversion
fallback burns subtitles into the prepared video. Continue Watching stores
bounded progress and excludes startup and unverified pause intervals.

## Security and privacy boundaries

- Keep PCServer on a trusted or access-controlled network.
- Do not use public port forwarding as the normal remote setup.
- Do not publish account keys, addon URLs, raw stream URLs, or local media paths.
- P2P, credential-bearing, private-address, and external-player results are not
  passed to the Miyoo.

For the full public security explanation, see
[Privacy and security](privacy-and-security.md).

## API and implementation reference

The repository contains developer-oriented endpoint, cache, selector, FFmpeg,
and implementation documentation. Those details are intentionally kept out of
the normal workflow pages. They are useful for development and support, not for
ordinary installation or playback.
