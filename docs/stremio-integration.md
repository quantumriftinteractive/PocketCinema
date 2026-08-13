# Stremio Integration

This milestone keeps Stremio-specific behavior on `desktop-gaming`. The Miyoo continues to call the PocketStremio REST API through the local Tailscale userspace HTTP proxy.

## Confirmed Interfaces

The Stremio addon protocol is the clean supported integration point for this POC.

Official/source references checked on August 12, 2026:

- Stremio addon protocol: https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/protocol.md
- Stremio addon SDK README: https://github.com/stremio/stremio-addon-sdk
- Advanced SDK guide, Cinemeta notes: https://github.com/Stremio/stremio-addon-sdk/blob/master/docs/advanced.md
- Cinemeta addon page: https://v3-cinemeta.strem.io/
- Stremio Core addon type docs: https://stremio-stremio-core.mintlify.app/api/types/addon

Confirmed protocol behavior:

- An addon exposes `/manifest.json`.
- Resource routes use `/{resource}/{type}/{id}.json`.
- Current resource names include `catalog`, `meta`, `stream`, and `subtitles`.
- Catalog requests can include extra args such as search using `/{resource}/{type}/{id}/{extraArgs}.json`.
- Cinemeta is the official Stremio addon for movie and series catalogs.
- Cinemeta uses IMDB-style IDs. For movies, the metadata ID and video ID are the same, for example `tt0078748`.

Confirmed working Cinemeta routes:

```text
GET https://v3-cinemeta.strem.io/manifest.json
GET https://v3-cinemeta.strem.io/catalog/movie/top/search=alien.json
GET https://v3-cinemeta.strem.io/meta/movie/tt0078748.json
```

## PocketStremio API Mapping

PocketStremio normalizes Stremio data into smaller Miyoo-facing responses.

```text
GET /api/search?q=alien
```

Uses Cinemeta:

```text
/catalog/movie/top/search=alien.json
```

Returns:

```json
{
  "query": "alien",
  "count": 2,
  "items": [
    {
      "id": "tt0078748",
      "type": "movie",
      "title": "Alien",
      "year": 1979,
      "poster": "..."
    }
  ]
}
```

```text
GET /api/meta/movie/tt0078748
```

Uses Cinemeta:

```text
/meta/movie/tt0078748.json
```

Returns useful fields only: ID, type, title, year, poster, and description.

```text
GET /api/streams/movie/tt0078748
```

Calls configured stream-capable addon manifests server-side:

```text
{addon_base}/stream/movie/tt0078748.json
```

The server normalizes stream names/descriptions and hides raw stream URLs from the Miyoo.

```text
POST /api/play
```

Input:

```json
{
  "type": "movie",
  "id": "tt0078748",
  "stream_id": "..."
}
```

Output:

```json
{
  "url": "http://100.85.171.67:8755/play/session-id"
}
```

The server stores the private upstream URL in memory and proxies `/play/{session}` to FFplay. This avoids logging or exposing full upstream URLs on the Miyoo.

## Stream Addon Configuration

PocketStremio does not read private Stremio account data.

## Local Stremio Service

Stremio Service is confirmed running on `desktop-gaming` at:

```text
http://127.0.0.1:11470
```

Keep it bound to localhost. The Miyoo must not connect to port `11470` directly.

Confirmed local probes:

```text
GET http://127.0.0.1:11470/
  307 redirect to Stremio Web with streamingServer=http://127.0.0.1:11470

GET http://127.0.0.1:11470/settings
  serverVersion: 4.20.8
  localAddonEnabled: false
  baseUrl: http://100.85.171.67:11470

GET http://127.0.0.1:11470/local-addon/manifest.json
  id: org.stremio.local
  resources: meta, stream
  stream types: movie, series
  idPrefixes: tt
```

The local addon stream route is reachable but returned no streams for initial probes:

```text
GET /local-addon/stream/movie/tt0078748.json
  {"streams":[]}

GET /local-addon/stream/movie/tt1254207.json
  {"streams":[]}
```

PocketStremio server includes this localhost-only local addon as a stream source by default. This does not expose Stremio Service to the Miyoo; the Miyoo still calls only:

```text
http://100.85.171.67:8755
```

If Stremio Service later exposes usable local streams, PocketStremio can normalize them through `/api/streams/...`.

Configured addons can also provide the Stremio `subtitles` resource. PocketStremio
normalizes those results through `/api/subtitles/...` and proxies the selected
subtitle through an opaque `/subtitle/{id}` route, keeping the upstream URL on
the gaming PC. Device rendering status is tracked in
[Subtitles and Continue Watching POC](subtitles-progress-poc.md).

Configure stream addon manifest URLs in:

```text
server/config/stream_addons.json
```

That file is ignored by git because configured addon URLs may contain private tokens.

Example shape:

```json
{
  "addons": [
    {
      "name": "My stream addon",
      "manifest_url": "https://example.com/manifest.json",
      "enabled": true
    }
  ]
}
```

Alternatively, set:

```text
POCKETSTREMIO_STREAM_ADDONS=https://addon-one/manifest.json,https://addon-two/manifest.json
```

## Built-In Test Stream

For safe end-to-end validation, the server exposes the known-compatible hosted test video only for Cinemeta ID `tt1254207`.

This is clearly labeled as:

```text
PocketStremio hosted test video
```

It is not a general movie stream resolver.

Because Cinemeta search did not return Big Buck Bunny for `big buck bunny` during testing, PocketStremio supplements that specific query family by fetching Cinemeta metadata for `tt1254207` and inserting it into the normalized search results. This is documented experimental behavior to enable a legal end-to-end playback test through the hosted PC test video.

Normal searches such as `alien` are returned directly from Cinemeta without this supplement.

## Series and Episode Mapping

PocketStremio searches both Cinemeta movie and series catalogs. Series metadata
normalizes Stremio `videos` into season and episode records, retaining each
video ID for `/api/streams/series/{video_id}`. The controller and playback path
is physically confirmed with a deterministic local two-season fixture; real
series streams remain dependent on configured addons.

Evidence: [Series and Episode Browsing](series-episode-browsing.md)

## Local Open-Media Addon

PocketStremio also starts a small, localhost-only Stremio addon at
`127.0.0.1:8756`. It currently resolves one public-domain direct HTTP stream for
*Night of the Living Dead* (1968), `tt0063350`. This keeps the media source
behind the same opaque `/api/streams` and `/api/play` contracts used by other
addons and does not expose another service to the Miyoo.

Implementation and current confirmation status are documented in
[Real Stream Resolution POC](real-stream-resolution.md).

## Assumptions

- Addons that return direct HTTP(S) `url` streams are playable candidates.
- Addons returning non-URL stream identifiers, external URLs, torrents, or debrid workflows are treated as not directly playable until a later resolver/transcoding milestone.

## Experimental Behavior

- `/play/{session}` proxies HTTP(S) streams through the PocketStremio server and forwards single Range requests where the upstream supports them.
- No stream URLs are persisted. Sessions are in memory and disappear when the server restarts.
- No account sync, library sync, external subtitle rendering, or transcoding is
  implemented. Subtitle discovery/proxy contracts exist, but the target FFplay
  build cannot render a separate SRT.
