# Series and Episode Browsing

Goal: add controller-driven season and episode selection without making the
first device test depend on an Internet media source.

## Status

**Confirmed on the Miyoo Mini Plus from the OnionOS Apps context on August 13,
2026.**

The confirmed path is:

```text
Search
  -> PocketStremio Test Series
  -> Season 2
  -> S2E1 Return to OnionOS
  -> Play
  -> Offline episode A/V sync test
  -> FFplay
```

## Server Model

Normal search now interleaves normalized Cinemeta movie and series results.
Series metadata normalizes Stremio `videos` into compact `seasons` and
`episodes` arrays. Episode video IDs are passed unchanged to
`/api/streams/series/{video_id}`, preserving the identifier shape expected by
Stremio addons.

The deterministic fixture is available through the exact searches `test
series`, `pocketstremio test series`, and `offline test series`. It contains:

```text
PocketStremio Test Series
  Season 1: 3 episodes
  Season 2: 2 episodes
```

Its metadata, episodes, and stream mapping are local to PocketStremio server and
make no Cinemeta or stream-addon request. Each fixture episode maps to an opaque
stream backed by a generated local MP4. Raw media URLs remain absent from the
Miyoo-facing API.

Generate the ignored 30-second fixture with:

```powershell
.\experiments\ffplay\generate-series-av-sync-fixture.ps1
```

The fixture is H.264 High/AAC stereo, 640x360 at 30 fps, approximately 840 kb/s.
A short white flash and 880 Hz beep occur together once per second so startup
and continuing A/V synchronization can be judged without dialogue.

## Miyoo Client

The shell client adds two SDL selector loops between a series search result and
the existing media action flow:

```text
search results -> seasons -> episodes -> media action -> streams
```

D-pad and A use the existing selector. B from an episode list returns to its
season list; B from the season list returns to search results. The selected
series ID, season number, episode video ID, and episode number are written to
the app-local log. Movie behavior and the existing playback pipeline are
unchanged.

Episode progress uses `type=series` and the episode video ID, so Continue
Watching entries remain distinct per episode. A human-readable series, season,
episode, and title string is saved with the progress item.

## Confirmed Results

The deployed client reached server `0.7-series-browsing-poc` through the Miyoo
Tailscale HTTP proxy on its first attempt. An SSH-safe dry run parsed both
seasons and all three Season 1 episodes before the physical test.

The physical Apps-context run manually selected Season 2 and S2E1. The server
returned one confirmed opaque stream and FFplay reported:

```text
duration: 30 seconds
video: H.264 High, yuv420p, 640x360, 30 fps, 808 kb/s
audio: AAC, stereo, 44.1 kHz
total bitrate: 839 kb/s
video readiness: 1 second after FFplay launch
FFplay exit: rc=0
```

The user confirmed that the longer flash/beep fixture worked. No continuing
A/V synchronization problem was reported. The run counted 18 watched seconds,
excluded a four-second pause, saved episode progress, returned to the home menu,
and exited without stale FFplay, selector, loading-panel, or pause-monitor
processes. B/back on the new episode and season levels was also physically
confirmed.

The automated server suite contains 13 tests. It verifies that the local series
search, parent metadata, episode metadata, stream lookup, play-session creation,
and byte-range relay complete while any upstream metadata request is configured
to fail the test.

## Limits

- Real Cinemeta series search and metadata normalization are implemented and
  server-tested, but real-series playback has not been physically confirmed.
- A configured addon must return a direct HTTP(S) stream for the selected
  episode video ID; torrent and debrid resolution remain out of scope.
- The generated MP4 is a deterministic navigation and synchronization fixture,
  not episode content.
