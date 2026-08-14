# Long-Running Live Playback Resilience

## Status

Milestone 17 is in progress. Automated bridge hardening and progressive-media
regressions are confirmed. The required 30-minute OnionOS Apps-context playback,
physical audio/video assessment, FFplay memory measurement, and Menu cleanup
check remain pending.

## Deterministic Bridge Coverage

The server test fixture publishes a rotating MPEG-TS media playlist with three
overlapping segments. Its media sequence advances from 100 through 102 before
ending. The bridge produced sequences 100, 101, 102, 103, and 104 exactly once,
confirming playlist refresh and deduplication across the sliding window.

Bounded recovery tests confirm:

- one HTTP 503 while refreshing the media playlist is retried and playback
  continues without a missing or duplicate segment;
- one HTTP 503 while opening a segment is retried before any bytes from that
  segment are sent downstream;
- a persistently failing media playlist receives exactly three attempts and
  returns HTTP 502 with the generic `hls_bridge_failed` response;
- network exception details and upstream addresses do not enter the client
  response;
- retry responses are closed, with the recovery tests passing while Python
  treats `ResourceWarning` as an error;
- closing an endless live response after its first segment terminates the
  server request thread within the three-second test bound and returns the
  thread-safe `/api/status` `live_bridges.active` diagnostic from one to zero.

Retries apply only to connection failures, timeouts, HTTP 408, HTTP 429, and
HTTP 5xx. Invalid, encrypted, fragmented-MP4, byte-range, or otherwise
unsupported playlists still fail immediately. A segment can be retried only
before its validated 564-byte MPEG-TS prefix is written downstream; a later
partial read is never replayed.

## Progressive Playback Regressions

The managed gaming-PC server was exercised while an ERT News bridge handler was
active on August 14, 2026. Both existing progressive sources retained normal
byte-range behavior:

```text
Big Buck Bunny hosted fixture
HTTP status:       206
Content-Range:     bytes 0-65535/1137884
Bytes read:        65,536
MP4 marker:        ftyp

The Beverly Hillbillies S1E1
HTTP status:       206
Content-Range:     bytes 0-65535/108342026
Bytes read:        65,536
MP4 marker:        ftyp
```

The full account and server regression suite contains 43 tests and passes after
the bridge changes.

## Headless Transport Observation

A Miyoo curl process consumed an opaque ERT News play session through the
configured userspace HTTP proxy for 694 continuous seconds. The observation was
stopped intentionally with signal exit code 143 while wrapping up development;
it was not an upstream timeout or bridge failure. Twelve one-minute samples
recorded these ranges:

```text
MemAvailable:       32,908-69,792 kB
SwapFree:          121,740-126,764 kB
tailscaled RSS:     22,984-59,304 kB
```

No matching curl process remained afterward. The managed server returned from
five threads during the active relay to its four-thread idle baseline and used
33,556 kB RSS after disconnect. This confirms sustained transport and headless
disconnect cleanup, but it does not substitute for FFplay or physical
audio/video evidence.

After deploying server version `0.14-live-resilience`, a second short ERT relay
reported `live_bridges.active` as one while connected and zero after the client
closed. The consumer thread also terminated normally.

## Pending Physical Evidence

The milestone remains incomplete until an OnionOS Apps-menu run confirms all of
the following on the Miyoo Mini Plus:

- ERT News remains visibly smooth and audibly correct for 30 continuous
  minutes;
- FFplay, tailscaled, available-memory, and swap measurements remain viable;
- Menu exits promptly and closes the gaming-PC bridge handler;
- no FFplay, selector, pause monitor, info panel, or playback temporary state
  remains;
- one movie and one real episode still start correctly after the hardening.
