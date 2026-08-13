# Real Episode Resume and Reliability

Milestone 13 validates Continue Watching against the real public-domain series
episode introduced in Milestone 12. Both playback paths were run from the
OnionOS Apps context on August 13, 2026.

## Saved Entry

The first real-episode playback left this server-side progress record:

```text
title:    The Beverly Hillbillies - S1E1 The Clampetts Strike Oil
id:       tt0055662:1:1
position: 44 seconds
duration: 1492 seconds
```

The device rendered the Continue Watching row as:

```text
The Beverly Hillbillies - S1E1 The Clampetts Strike Oil (1962) - 0m 44s
```

This preserves the series title, season and episode number, episode title,
release year, and saved position in a single controller-selectable row.

## Resume Run

The user selected the episode and first pressed B on its action menu. The SDL
selector returned `rc=1` with no selected value, and PocketStremio returned to
its home screen without exiting or freezing.

The episode was then selected again through Continue Watching. The device log
confirmed:

```text
selected=Resume at 0m 44s
resume_seconds=44
startup_seconds=49
watched_seconds=25
progress saved position_seconds=69 duration_seconds=1492 completed=false
```

The user confirmed that playback visibly started partway into the episode and
that video and audio were correct. The 25 seconds measured after video readiness
advanced the saved position from 44 to 69 seconds. The 49-second remote-media
startup interval did not advance progress.

## Play From Start Run

The next Continue Watching row displayed the updated `1m 9s` position. The user
selected Play from Start and the same Internet Archive stream. The log
confirmed:

```text
selected=Play from Start
resume_seconds=0
startup_seconds=33
watched_seconds=3
progress saved position_seconds=3 duration_seconds=1492 completed=false
```

The user confirmed that the episode opening was displayed. The old 69-second
position was replaced by 3 seconds of valid playback only after video readiness;
the 33-second startup interval was excluded. A failed startup therefore would
not have erased the prior saved position.

## Controls and Cleanup

Both runs used the existing controller and player behavior:

- B returned from the pre-playback action selector;
- A selected Continue Watching actions and the stream;
- Menu exited FFplay;
- FFplay returned `rc=0` after both playback runs;
- pause tracking remained valid and reported no paused interval;
- OnionOS `MainUI` was active after each app exit;
- no PocketStremio UI, selector, FFplay, or infoPanel process remained;
- `/tmp/stay_awake` and `/tmp/dismiss_info_panel` were absent;
- the configured userspace networking provider continued running independently.

Post-run memory showed 10.8 MB free RAM and 1.3 MB swap in use. This was sampled
after playback, not during active decoding.

## Result

The real episode can be identified in Continue Watching, resumed near its saved
position, restarted from the beginning, and exited cleanly. Progress replacement
is consistent with the chosen playback action and excludes measured startup
time. Resume remains approximate because this FFplay build does not expose a
machine-readable playback clock.
