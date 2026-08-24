# Unified PocketStremio UI Plan

## Purpose and scope

This document plans a gradual, app-local replacement for PocketStremio's
mixed OnionOS helper and selector screens. It does not authorize implementation
and does not change the PocketStremio server (PSS), playback, FFplay, subtitle,
progress, account, network, Tailscale, or deployment behavior.

The visual source is
[PocketstremioUI.svg](../UI_concept/PocketstremioUI.svg). Its two-pane frame is
retained, but the right pane is contextual rather than permanently reserved for
Settings:

```text
left pane                         right pane
current navigation or list       details, state, help, or actions
```

The redesign remains outside the active release milestone. Existing UI paths
must remain usable until each replacement has passed an OnionOS Apps-context
test on the Miyoo Mini Plus.

## 1. Current UI architecture

The production path is currently:

```text
app/launch.sh
  -> client/miyoo/pocketstremio-ui.sh
       -> curl + jq                       PSS API and JSON normalization
       -> pocketstremio-selector          lists and account QR
       -> kbinput                         search and manual server entry
       -> infoPanel                       messages and blocking progress
       -> discovery/helper processes      bounded, task-specific work
       -> FFplay                          playback
```

`pocketstremio-ui.sh` is a BusyBox `/bin/sh` state machine. It owns app-local
configuration, HTTP/proxy setup, API calls, temporary TSV/JSON files, navigation
loops, error classification, FFplay launch, readiness-based progress, pause
tracking, logging, and cleanup. It already implements Search, Live TV, Quick
Resume, Continue Watching, Stremio Account, Settings, movies, series, seasons,
episodes, stream/source filtering, verified audio-track selection, subtitles,
and playback fallback.

The normal list UI is already an app-local SDL 1.2 selector, not OnionOS
`shellect`. `shellect.sh` is retained only as a missing-selector fallback. The
selector:

- opens one 640x480, 32-bit software surface per selection screen;
- applies the confirmed 180-degree framebuffer correction in its rectangle
  primitive;
- contains a compile-time 5x7 bitmap font and uppercases lowercase input;
- reads up to 64 newline-delimited items of at most 255 bytes from stdin;
- shows eight one-line rows or four multiline rows;
- implements D-pad Up/Down, A/select, and B/back;
- emits only the selected display value on stdout and logs diagnostics
  separately;
- renders the account QR from a value received through stdin; and
- can poll an app-local file every 200 ms to update the home screen's first
  server-status row.

The shell's existing server monitor starts the home menu immediately, uses a
3-second connect timeout and 5-second total timeout for `/api/status`, and
updates every 10 seconds by default. It writes `Connecting`, `Connected`, or
`Offline` to a temporary file. It is stopped and its files are removed when the
client exits.

This architecture is intentionally disposable around playback: a selector has
exited before the shell launches FFplay. That property is more valuable than a
nominally cleaner all-in-one process and must be preserved.

## 2. SVG concept analysis

### Authored geometry

The SVG has a `viewBox` of exactly `0 0 640 480`, matching the Miyoo
framebuffer. Coordinates below are calculated from the SVG's transforms rather
than estimated from its rendered preview.

| Region | Authored bounds or baseline |
| --- | --- |
| Screen | `x=0`, `y=0`, `w=640`, `h=480` |
| Header outer path | `x=13.223`, `y=14.104`, `w=613.462`, `h=62.147` |
| Header inner edge | approximately `x=19.473..620.435`, `y=20.354..70.001` |
| Main panel | `x=16.349`, `y=81.960`, `w=607.301`, `h=316.084` |
| Pane-title divider | `x=16.349`, `y=114.988`, `w=607.300`, `h=15.908` |
| Center divider | `x=312.046`, `y=88.248`, `w=15.908`, `h=309.793` |
| Left pane before divider | approximately 296 px wide |
| Right pane after divider | approximately 296 px wide |
| Footer outer path | `x=13.269`, `y=408.938`, `w=613.462`, `h=62.147` |
| Footer inner edge | approximately `x=19.519..620.481`, `y=415.188..464.835` |

The header-to-main gap is about 5.7 px; the main-to-footer gap is about 10.9
px. Body content starts below the horizontal divider at about `y=131` and ends
at `y=398`. Text begins about 20 px inside each pane: the first authored left
item starts at `x=36.349`, and the first right item at `x=347.954`.

### Authored visual hierarchy

- Header: `PocketStremio - version#`, centered, Arial Regular, 25 px, with a
  baseline near `y=54.131`.
- Pane headings: `Main Menu` and `Settings Menu`, centered, Arial Italic; SVG
  transforms produce an effective size of about 28 px and baseline
  `y=111.636`.
- List text: Avenir Book, 20.833 px, with authored baselines approximately
  29.167 px apart.
- Footer: `Server Name - IP - Status`, centered, Arial Regular, 20.833 px, with
  baseline near `y=447.473`.
- Containers: large rounded black outlines, inset black edge detail, gray fill,
  a strong center divider, and a separate footer status capsule.
- Palette: the SVG explicitly uses black geometry and
  `rgb(116,116,116)` at 65% opacity. It does not define the compositing
  background, so the final opaque device color cannot be inferred reliably.
- Menu organization shown by the concept: Search, History, Continue Watching,
  and Exit on the left; Preferences, Volume Override, Server, Account, and an
  explicit placeholder for more settings on the right.
- Icon treatment: the SVG contains text placeholders for Search, History, and
  pause/play icons. It does not contain final icon artwork.

### Details the SVG does not specify

The SVG has no selected, focused, disabled, scrolling, empty, error, offline,
or pane-focus state. It also does not define controller behavior, wrapping,
truncation, button hints, actual icons, final opaque colors, or responsive
behavior. Those are interaction requirements, not visual facts, and should not
be reverse-engineered from the static concept.

The decorative edge paths contain dense repeated/scalloped geometry. Runtime
SVG parsing is inappropriate for the device. The first implementation should
preserve the authored proportions, nested rounded containers, grayscale
language, and strong dividers with simple SDL primitives. A solid two- or
three-pixel approximation of the micro-edge treatment is justified if the
literal pattern aliases on the Miyoo LCD; the choice must be made from a
640x480 Apps-context comparison.

## 3. Contextual dual-pane design specification

Use fixed logical 640x480 coordinates. The stable screen skeleton is:

```text
+--------------------------------------------------------------+
| PocketStremio [optional client version]      current section |
+-----------------------------+--------------------------------+
| left heading                | contextual heading             |
+-----------------------------+--------------------------------+
| current navigation/list     | selected-item details          |
|                             | state, help, or actions         |
|                             |                                |
+-----------------------------+--------------------------------+
| configured PSS identity/address | connection state           |
+--------------------------------------------------------------+
```

The header, main panel, divider, pane-title band, and footer use the SVG's
principal bounds. Content uses layout tokens rather than scattered coordinates.
The left pane owns the list. Merely moving the left selection redraws the right
pane; it must not trigger a network request.

The right pane is read-only when it contains description and hints. If a screen
has a real contextual action group, D-pad Right transfers focus to it, D-pad
Left returns focus to the list, and both panes retain their last selection.
Header and footer never receive focus. Dual-pane mode should not be forced onto
the keyboard, QR, blocking progress, or small confirmation dialogs.

## 4. Proposed visual system

Start with an opaque grayscale palette derived from the SVG rather than alpha
blending every frame:

- one opaque background color selected by physical comparison;
- the authored mid-gray as the panel family;
- black borders and primary text where contrast permits;
- light text on the selected black row;
- a shape or text label in addition to any status color.

Do not rely on red/green or small hue changes for connection and compatibility
states. `CONNECTED`, `OFFLINE`, `DIRECT`, and similar words remain visible.

The initial focus treatment should combine three cues: a solid filled row, an
inverted text color, and a left-side pointer or 3-pixel focus bar. A focused
right-pane action uses the same treatment. Disabled rows remain focusable so
the right pane can explain why they are unavailable, but A does nothing except
show a concise notice. This is preferable to silently skipping an item.

Rounded frames should be drawn with small filled-rectangle helpers or a tiny
precomputed corner mask. Avoid per-pixel antialiasing and general path code.
Progress bars are two filled rectangles plus a border. Badges are bordered text
capsules; they need no texture.

## 5. Proposed interaction model

The baseline controller contract is:

| Control | List/detail screens | Keyboard | FFplay |
| --- | --- | --- | --- |
| Up/Down | move within focused pane | move between key rows | unchanged |
| Left/Right | enter/leave action pane or move within a control | move between keys | unchanged |
| A | select/confirm | enter highlighted key | unchanged |
| B | right focus: return left; left focus: back | backspace | not an exit control |
| Start | screen-specific primary action, only when labeled | submit/search | unchanged |
| Menu | proposed app-level cancel/exit | cancel keyboard | confirmed playback exit |

Only Up `273`, Down `274`, A `32`, and B `306` are currently documented for
the selector. Start, Menu, X, Y, Left, and Right must be captured with the
existing app-local button diagnostic before their SDL mappings are coded. Menu
behavior outside FFplay is therefore a recommendation, not a confirmed fact.

Preserve the current selector's wraparound Up/Down behavior during initial
parity work. Reconsider it only after a physical large-list test. B always pops
one application level; it must not exit several levels or terminate playback.
Every Start shortcut must also be visibly available through A navigation.

The shell currently waits one second before opening each selector to debounce
input. Preserve that guard during parity work. Phase C may replace it with an
SDL event drain plus a confirmed button-release gate if Apps-context testing
shows that doing so improves transitions without accepting the previous A/B
press on the next screen.

## 6. Main-menu behavior

The production home menu should expose only current behavior:

1. Search
2. Live TV
3. Quick Resume
4. Continue Watching
5. Stremio Account
6. Settings
7. Exit

The current dedicated server row moves into the footer. Offline and
unconfigured users can still open Settings, so removing that row does not hide
recovery. Quick Resume may be shown disabled when `last-play.json` is absent or
belongs to another configured PSS.

Suggested right-pane summaries use data already available locally or from the
last completed status response:

| Highlight | Right pane |
| --- | --- |
| Search | Search movies and series; last/default query if appropriate; `A Open`, optional `Start Search` |
| Live TV | Account-backed live channels; account availability if known |
| Quick Resume | Saved title and approximate position from app-local `last-play.json`; no stream URL |
| Continue Watching | Count from `/api/status`; most recent item only if already cached |
| Stremio Account | linked/unlinked/unchecked state and cached addon count |
| Settings | configured PSS address, audio gain, and available settings count |
| Exit | concise exit description; A confirms or opens a small confirmation dialog |

Home must draw before any network result. It initially displays the configured
address plus `CONNECTING`, `UNCONFIGURED`, or the last status observed during
the current app process.

## 7. Contextual right-pane behavior

Each list record should supply a stable opaque value plus display-only fields:
primary label, optional secondary label, optional badge, detail heading,
wrapped detail lines, and action hints. The shell continues to sanitize and
normalize server JSON with `jq`; the SDL process does not parse arbitrary
upstream JSON.

The right pane updates entirely from the in-memory records given at screen
startup. Slow enrichment should finish before the screen opens or update
through a bounded app-local state file; selection movement must never start
`curl`, `jq`, or `ffprobe` work.

Default behavior:

- wrap description text at word boundaries;
- cap lines and show an ellipsis when content does not fit;
- show unknown values as `Not available`, not `?` where that could look like an
  error;
- place the primary action hint at the bottom of the pane;
- retain the left selection while action focus is active; and
- never display addon transports, auth material, upstream media/subtitle URLs,
  or private file paths.

## 8. Settings navigation model

Settings is another contextual list, not a permanent home pane. Its first
shipping version should contain only implemented categories:

| Category | Current action/detail |
| --- | --- |
| Server | configured PSS URL, status, Scan for PSS, Enter Manually, connectivity test |
| Audio gain | current `AUDIO_GAIN`; existing bounded values |
| Stremio Account | current linked state and existing account flow |
| Back | return home |

Add categories only when their underlying roadmap work exists:

- ordered audio languages: Milestone 21;
- ordered subtitle languages: Milestone 21 and its bounded resolver changes;
- compatibility preference: Milestone 21;
- individual Continue Watching removal: Milestone 21;
- selectable-Matroska status: the Milestone 22 capability is confirmed, but an
  editable device setting belongs here only if Milestone 21 and the release
  configuration explicitly make it user-facing.

`Preferences` should not be an empty container. `Volume Override` maps to the
existing, more accurate `Audio gain` label. `More Settings [if available]` is
an SVG placeholder and must not ship.

Server editing must continue to update the authoritative
`config/pocketstremio.conf` atomically and preserve unrelated keys and the
environment-override warning. The optional `PROXY` remains generic HTTP proxy
configuration. A future editor may display/edit it under Server, but must not
identify, inspect, start, stop, or authenticate Tailscale. The UI should repeat
the existing warning that PSS has no public-facing login and belongs on a
trusted network or authenticated gateway.

## 9. Search-results model

The left pane shows normalized title, year, and a compact movie/series marker.
The right pane shows title, year, type, and the bounded description already
returned by `/api/search`. A displays the existing media or series path. B
returns to the query screen.

Do not download or cache `poster` fields during this migration. Search-result
progress requires a safe join with Continue Watching state and should be omitted
until it can be populated without a request on every highlight.

Long titles use a static ellipsis in the left pane and wrap in the right pane.
There is no automatic marquee in the first implementation: it creates redraw
work, timing state, and unstable reading on a small display. A manually tested
marquee can remain optional polish.

## 10. Continue Watching model

The left pane shows the saved title and `position / duration` when duration is
known. The right pane shows title, movie or episode identity, year, an integer
progress bar, saved position, and actions.

Initial actions reuse current behavior:

- Resume;
- Play from Start; and
- Back.

`Remove` must remain visibly absent until Milestone 21 adds a specific bounded
server operation. Posting a fabricated completion would misuse progress logic
and could affect the wrong meaning of state. Continue Watching is ordered by
the server's existing `updated_at` value and completed items are removed, so it
is not watch history.

## 11. Season and episode model

Season lists use `Season N` as the primary label and the existing episode count
as secondary context. The right pane shows the parent series title, season
number, and episode count.

Episode lists show `E<N> <title>` on the left. The right pane uses existing
normalized data: episode title, season/episode number, release/year, and
description. Duration is often unavailable until a stream is resolved and
preflighted, so the UI must not promise it at this level. Saved progress can be
shown only when it is already available from Continue Watching state.

B from episodes returns to seasons; B from seasons returns to search results,
preserving the current navigation loops.

## 12. Stream-selection model

The stream list is the highest-risk list migration and should be last. The left
pane uses source/release text plus a text badge:

- `DIRECT`: PSS classified the source for direct playback;
- `CONVERT`: PSS will use its bounded conversion path;
- `CHECK`: uninspected candidate requiring play-time preflight; and
- `UNSUPPORTED`: explanatory/disabled state only if a future API returns it.

The current API normally omits cached unsupported and otherwise unplayable
items, so the UI must not invent disabled `UNSUPPORTED` rows.

The right pane may show only public normalized fields already returned by
`/api/streams`: source label, release label, resolution, container, video
codec, audio codec, verified audio languages/tracks, duration when known,
compatibility message, and playback mode. Subtitle availability is discovered
separately and should read `Checked during playback setup` unless it has
actually been fetched. Technical fields with no decision value stay hidden
behind a `More details` action, if one is later justified.

Source and verified-audio filters remain explicit list screens at first. The
selected stream still passes through the existing details confirmation,
audio-track picker, subtitle behavior, `/api/play`, and fallback logic. The new
UI changes presentation only.

## 13. Server-status integration

Reuse the current shell monitor during the home phase; do not add a daemon or
an HTTP stack to the SDL binary. The footer reads a bounded app-local status
record and redraws only when its contents change.

Recommended footer content is:

```text
<discovery name or PSS> | <configured host:port> | CONNECTED
```

The configured address is available immediately. `discovery.name`, network
label, server version, Continue Watching count, and sanitized account state can
come from a successful `/api/status`. If the name is absent, use `PSS`; do not
infer a machine or Tailscale identity.

Use the current 10-second refresh interval, 3-second connect timeout, and
5-second total timeout as the first baseline. Show `CONNECTING` immediately and
never persist `CONNECTED` across app launches, because a stale success is more
misleading than a fast neutral state. Cache successful details only for the
current client process so they survive transitions between one-shot UI screens.

Required text states are `UNCONFIGURED`, `CONNECTING`, `CONNECTED`, and
`OFFLINE`. `PROXY UNAVAILABLE` should be used only if the existing curl error
evidence can distinguish it safely from an unreachable PSS; otherwise use the
sanitized offline detail already established by the client. Account status
belongs in the Account context unless header/footer measurements show enough
space.

## 14. Custom QWERTY keyboard plan

The keyboard is a full-width modal screen, not a forced dual-pane layout. It
uses a text-entry field, the staggered QWERTY rows, and a small control-hint
band in the same visual system:

```text
Q W E R T Y U I O P
 A S D F G H J K L
  Z X C V B N M
```

Recommended controls, pending physical key mapping, are:

- D-pad: nearest-key movement across staggered rows;
- A: type key;
- B: backspace, including repeated deletion through bounded key repeat;
- Y: space;
- X: toggle letters and a bounded numbers/symbol page;
- Start: submit;
- Menu: cancel without returning partial text.

B should not cancel from an empty field; this avoids accidental loss while
editing. Menu is the explicit cancel. The keyboard must accept an initial value
for the default query and manual PSS address, cap output length, show the cursor,
and emit one newline-terminated result only on submit. Secrets are not entered
on the Miyoo.

First ship it behind an opt-in mode. A failure exit code falls back to
`kbinput` with the original initial value. Retire `kbinput` only after search,
manual server entry, repeated characters, space, backspace, symbols, cancel,
multiple consecutive searches, memory, and cleanup all pass physically.

## 15. Custom list-selector plan

Build one reusable component with:

- current item and viewport indices;
- one to 64 bounded records initially, matching the proven selector limit;
- one-line and primary-plus-secondary row styles;
- static ellipsis in the left pane and wrapped detail text on the right;
- selected, normal, disabled, and empty states;
- optional text badge and secondary label;
- scroll position or `N / total` feedback;
- stable opaque return values rather than duplicate-prone display labels;
- A/select, B/back, and optional right-pane action focus; and
- exact stdout/log separation.

Use a small, documented stdin record format produced by the shell, for example
bounded tab-separated display fields plus an opaque action ID. Newlines and
tabs must be normalized before invocation. The record must never include raw
URLs, tokens, addon transports, or file paths. Do not add a general JSON parser
to C merely to move the existing `jq` boundary.

Start with the Settings list, then migrate Search Results, Live TV, Seasons,
Episodes, Continue Watching, audio/subtitle choices, filters, and Streams. The
stream picker comes last because it combines multiline release data, filters,
compatibility, and playback consequences.

## 16. Custom dialog plan

Use a centered bounded panel over the standard background for info, warning,
error, retry, and confirmation. The dialog API needs title, wrapped sanitized
body, severity label, and at most three actions. Focus and button hints follow
the normal selected-state rules.

There are two distinct cases:

1. Non-blocking modal messages can be replaced by a one-shot SDL dialog.
2. A network/preflight operation currently blocks the shell while a persistent
   `infoPanel` process owns the display. Its replacement must be a temporary
   app-local SDL progress process with an owned PID and explicit dismissal, not
   a resident service.

Keep `infoPanel` until both cases are physically accepted. Loading screens can
be static; animation is unnecessary. A later cancelable operation needs a
specific IPC/cancellation design and must not kill unrelated curl, PSS, or
FFmpeg work.

The existing app-local QR renderer is already secure and lightweight. It
should be visually reskinned only after the core dialog layer exists, while
continuing to receive one-time links through stdin and emitting only `refresh`.

## 17. Recommended code architecture

Do not turn the current selector into the sole fallback and experimental UI at
the same time. Add a separate opt-in ARMv7 binary, tentatively
`pocketstremio-native-ui`, composed of small in-tree C modules:

```text
ui_layout.c/.h       fixed 640x480 regions and clipping
ui_draw.c/.h         fills, borders, corners, bars, text
ui_font.c/.h         compile-time bitmap glyphs and measurement
ui_input.c/.h        normalized controller events and repeat
ui_list.c/.h         viewport, rows, focus, contextual pane
ui_screens.c/.h      home, keyboard, dialog, progress, QR adapters
native_ui_main.c     stdin/stdout mode contract and lifecycle
```

These may compile as ordinary objects into one executable; a runtime shared
library adds packaging complexity with no demonstrated memory benefit. The
current `pocketstremio-selector` and its binary remain untouched during the
migration.

The shell chooses native or legacy mode per screen. A future refactor may build
the legacy selector from shared drawing code after the native path is stable,
but it is not required to achieve a coherent UI.

## 18. Existing code that can be reused

Reuse or adapt these proven pieces:

- SDL 1.2 initialization, cursor hiding, 640x480 software surface, and
  `SDL_Flip` lifecycle from `sdl_selector.c`;
- the corrected `rect()` coordinate transform for the 180-degree framebuffer;
- bitmap-glyph drawing and text measurement as the dependency-free starting
  point;
- key repeat and event wait/poll patterns;
- strict duplicated-result-fd handling that prevents vendor SDL diagnostics
  from corrupting stdout;
- app-local selector logging and QR encoder integration;
- current shell API/proxy functions, `jq` normalization, error messages,
  loading ownership, server monitor, config writers, and cleanup traps;
- all existing navigation and playback functions below the presentation call;
- existing resource monitor and Apps-context validation procedures; and
- reproducible ARMv7 compiler/sysroot flags, including
  `-Wall -Wextra -Werror -O2`, SDL 1.2, and `libts`.

The current font supports only a small bitmap set and uppercases text. Reuse its
mechanism, not necessarily its limited glyph coverage or metrics.

## 19. Process-boundary recommendation

Retain shell orchestration for the foreseeable redesign:

```text
launch.sh
  -> BusyBox shell state/navigation/API orchestration
       -> one-shot native SDL screen
       -> existing curl/jq/helper operations
       -> UI process fully exits
       -> existing FFplay handoff
```

This is the smallest evolution because it leaves proven HTTP, JSON, config,
fallback, progress, and playback code in place. A C rewrite would need an HTTP
client, JSON parser, URL encoding, proxy rules, atomic config editing, error
classification, subprocess supervision, and playback cleanup before it could
match current behavior. That is a large regression surface with no established
RAM advantage.

One-shot SDL screens may show a small transition as surfaces reopen, but they
give simple crash isolation and guarantee memory release. Measure that
transition before considering a persistent UI process. A shell/UI IPC session
host is not part of the initial plan.

## 20. Memory and resource strategy

The best current selector measurement while waiting on the account/home UI is
3,452 kB RSS, 9,528 kB virtual size, and zero process swap. At that point the
system reported 5,220 kB free and 69,200 kB available. Playback measurements
vary by path: normal/live FFplay has reached roughly 19-28 MB RSS, while the
latest app-local converted run recorded 1,168-17,048 kB player RSS, at least
36,704 kB `MemAvailable`, and zero player swap. Other evidence records only a
few MB of `MemFree`, so a new resident UI is unacceptable.

The native UI should:

- allocate one 640x480 software surface and no full-screen duplicate;
- use opaque fills and redraw only after input or status change;
- precompute colors and layout, with no allocation in the normal draw loop;
- keep glyphs in compile-time data and avoid SDL_ttf, SDL_image, SVG, and
  general animation dependencies;
- cap item counts and field lengths before allocation;
- load no posters or large textures;
- stop its status polling/redraw before returning; and
- call `SDL_Quit` and exit before FFplay starts.

Measure these states on the device with consistent commands and fixture:

1. current legacy home idle;
2. native home idle while Connecting and Connected;
3. native home after 10 status cycles;
4. custom keyboard with a long input;
5. one-item, maximum visible, and 64-item lists;
6. repeated transitions between ten screens;
7. immediately after native UI exit;
8. FFplay startup and steady playback after native selection; and
9. post-Menu return and cleanup.

Record process RSS/virtual/swap, `MemFree`, `MemAvailable`, `SwapFree`, startup
time, and stale processes. Use 5 MiB RSS and zero swap as an initial stop/review
ceiling for the one-shot native UI, not as proof of safety; any regression of
more than about 1.5 MiB over the measured selector needs explanation and a
repeat playback comparison. Playback must remain inside its prior resource and
readiness envelope with no native UI process present.

## 21. Asset workflow

Treat the Affinity SVG as editable design source and reference, not a runtime
asset:

```text
Affinity Designer
  -> UI_concept/PocketstremioUI.svg
  -> measured layout constants and SDL primitives
  -> optional tiny offline-exported bitmap icons
```

The current SVG contains placeholders rather than usable icons, so Phase A and
Phase B should be text-first. If final icons are later supplied, export at the
exact device size, compare 1-bit/opaque BMP or compiled bitmap data, and load no
more than the icons needed by the active screen. SDL 1.2 can load BMP without
SDL_image. Do not export full-screen backgrounds, parse SVG on the Miyoo, or
ship Affinity-only font dependencies.

## 22. Layout and coordinate strategy

Use a single `UiLayout` initialized from named constants such as:

```text
SCREEN               0,0,640,480
HEADER               13,14,614,62
MAIN                 16,82,608,316
PANE_TITLE_DIVIDER   16,115,608,16
CENTER_DIVIDER       312,88,16,310
FOOTER               13,409,614,62
BODY_TOP             131
BODY_BOTTOM          398
PANE_TEXT_INSET      20
```

Integer rounding is deliberate and should be documented once. Derive pane
content rectangles, centers, clipping, row positions, and action regions from
those constants. Percentages and a responsive layout engine add no value on a
fixed framebuffer. Pure functions for centering, wrapping, ellipsis, visible
row calculation, and nearest keyboard key keep individual screens free of
magic coordinates.

## 23. Typography strategy

The SVG names Avenir and Arial, neither of which is committed as an app UI font.
The only production UI font is the selector's compile-time 5x7 bitmap. The
experimental FFplay bundle references DejaVu Sans plus fontconfig/FreeType, but
that playback dependency should not become an idle UI dependency.

Preserve hierarchy rather than claiming exact font-family parity:

- app/header: approximately 24-25 px;
- pane headings: approximately 26-28 px, with weight or spacing rather than a
  required italic raster font;
- primary rows: approximately 20-21 px;
- secondary/detail text: approximately 14-16 px;
- footer and button hints: approximately 14-16 px unless the physical footer
  test supports the SVG's 20.833 px size.

The first technical spike should compare the current font at integer scales
with a slightly wider compile-time 6x8 or 8x8 bitmap set. It must measure text
width without allocating rendered surfaces. Decode UTF-8 safely even if the
initial glyph set falls back visibly for unsupported characters. Full Unicode,
Latin-1/Greek coverage, exact italic headings, and localization are open design
decisions; silently corrupting bytes is not acceptable.

Left labels are single-line ellipsized. Secondary labels are single-line.
Right descriptions wrap to a fixed line budget. Stream release names may use
two left-pane lines only in the dedicated stream row style.

## 24. Fallback strategy

Introduce a documented future setting or environment override such as
`UI_MODE=legacy|native`, defaulting to legacy until the native home has passed
physical testing. The config parser must explicitly recognize it when
implemented; do not rely on an unknown key.

Use distinct result codes:

- `0`: confirmed selection/value on stdout;
- `1`: user back/cancel, no stdout; and
- `2+`: initialization, input, or rendering failure, no stdout.

Only `2+` triggers a fallback. Treating B as a crash would reopen a screen the
user deliberately left.

Per-screen fallbacks are:

```text
native home failure       -> legacy home selector
native list failure       -> pocketstremio-selector, then shellect if absent
native keyboard failure   -> kbinput
native dialog/progress    -> infoPanel
native QR failure         -> current selector QR mode
```

Keep the old binary and helpers in deployment. A replacement can retire only
after its functional, memory, failure, repeated-use, cleanup, and Apps-context
tests pass, and after one release/rollback cycle if it is release-facing.

## 25. Migration phases

### Phase A - UI foundation

Add the opt-in binary, layout/drawing/font/input modules, host-side pure-layout
tests, framebuffer correction, logging/stdout contract, and a static concept
comparison screen. Do not call PSS or change application behavior.

### Phase B - Native home

Render the contextual dual-pane home and footer. Feed existing action IDs back
to the unchanged shell functions. Reuse the current asynchronous status
monitor. All deeper screens remain legacy.

### Phase C - Reusable list migration

Pilot Settings, then migrate Search Results, Live TV, Seasons, Episodes,
Continue Watching, source/audio filters, track/subtitle lists, and Streams in
that order. Keep a per-screen legacy branch. No API or playback semantics
change.

### Phase D - QWERTY keyboard

Add search and manual-PSS modes, then physically validate before changing the
default. Keep `kbinput` installed and callable.

### Phase E - Dialog, progress, and QR unification

Replace non-blocking messages first, then blocking progress ownership, and
finally reskin the already app-local QR flow. Keep `infoPanel` and QR fallback
until cleanup and failure tests pass.

### Phase F - Optional polish

Only after measurements: tiny icons, smoother focus redraw, richer typography,
and limited progress visualization. Poster grids, full-screen textures,
animation systems, and image caches need separate roadmap scope and evidence.

## 26. Physical acceptance tests

Every phase requires an Apps-context test; SSH cannot confirm framebuffer,
audio, or controller behavior.

### Foundation and home

- compare the rendered 640x480 screenshot to the SVG regions;
- verify no clipping, correct 180-degree orientation, header/title/footer
  alignment, and obvious focus on the actual LCD;
- move through every home item and confirm right-pane updates;
- confirm offline/unconfigured home opens immediately and Settings remains
  reachable;
- confirm status changes without blocking navigation;
- test A, B, Start if enabled, and Menu after its mapping is confirmed;
- measure idle and ten-cycle memory; and
- exit to MainUI with no stale UI/status process or temporary file.

### List component

- test empty, one, five, one-screen maximum, and 64 items;
- test long ASCII and UTF-8 titles, secondary labels, badges, and descriptions;
- test disabled items, top/bottom wrap, scrolling, pane focus, A, and B;
- verify stable return IDs when two labels are identical; and
- repeat screen entry/exit at least ten times without RSS growth.

### Keyboard

- reach every QWERTY key and every staggered-row edge;
- enter repeated letters, spaces, deletion, numbers/symbols, and a maximum
  length value;
- submit and cancel without stdout contamination;
- run several consecutive searches and manual PSS entry; and
- force native failure and confirm `kbinput` fallback with no leaked process.

### Feature screens

- Search: movie and series selection, long title, no results, and B;
- Seasons/Episodes: one and many seasons, long episode title, nested back;
- Continue Watching: position/duration/progress, Resume, Play from Start, and
  later Remove only when Milestone 21 exists;
- Settings: current values, server scan/manual entry, audio gain, persistence,
  and environment-override warning;
- Account: unlinked/link/waiting/connected/expired/error without secret data;
- Streams: DIRECT/CONVERT/CHECK, unknown fields, multiple tracks, filters,
  details confirmation, retry, and no raw upstream information;
- Dialogs: info, warning, error, confirm, retry, offline, and progress dismissal.

### Playback handoff regression

- confirm the native UI and progress panel have exited before FFplay;
- play the deterministic direct fixture and one normal movie/episode path;
- exercise the current converted subtitle path and the confirmed
  selectable-track path if it is enabled in that build;
- confirm video, audio, readiness timing, pause tracking, progress, aspect
  ratio, Menu exit, and fallback are unchanged;
- record FFplay RSS/swap and system memory; and
- verify no UI, selector, FFplay, infoPanel, helper, marker, or temporary
  subtitle state remains.

## 27. Risks

- A persistent UI would compete with the tight playback memory envelope.
- The SVG's alpha and detailed edge geometry may render differently or alias on
  the Miyoo LCD.
- A 296 px pane cannot fit long stream releases without aggressive hierarchy
  and truncation.
- The current bitmap font has limited glyphs and no authored Avenir/Arial
  parity.
- Unconfirmed Start/Menu/X/Y/Left/Right mappings could conflict with OnionOS or
  FFplay behavior.
- One-shot SDL screens may flicker between shell operations.
- A richer status record introduces file-update races unless writes remain
  atomic and bounded.
- A background custom progress process can leak or dismiss the wrong UI if PID
  ownership is weaker than the current cleanup.
- Display labels are not unique; returning them instead of opaque IDs can
  select the wrong record.
- Right-pane details can accidentally expose server-only data if the shell
  passes raw provider records rather than an explicit public field set.
- Stream and episode duration/subtitle data is not always available at browse
  time; speculative labels would be misleading.
- Adding planned Settings entries before their underlying milestones would
  create nonfunctional UI and expand scope.
- A full client rewrite would couple UI progress to playback/network parity and
  threaten the confirmed release path.

## 28. Open design questions

1. Which opaque background/panel grays best reproduce the SVG on the physical
   LCD, given the source's undefined alpha-compositing background?
2. Does the decorative/scalloped inner border survive at 640x480, or should the
   physically tested solid nested border become the technical approximation?
3. Should pane headings retain an italic bitmap treatment, or use weight/case
   hierarchy because no matching font is deployed?
4. What is the canonical client release version for the header? The current
   `/api/status.version` is the PSS version and should not masquerade as a
   device-app version.
5. What SDL key codes do Left, Right, X, Y, Start, and Menu produce in the Apps
   context, and should Menu globally exit or open a confirmation outside
   playback?
6. Should right-pane actions be focusable on every action screen, or should the
   earliest release keep the pane read-only and open the existing action list
   with A?
7. Which compiled glyph coverage is required for real catalog titles and
   planned Greek language labels without adding a font runtime?
8. Is a static ellipsis sufficient for all left-pane lists, or is a
   focus-delayed, measured marquee worth its redraw cost on stream titles?
9. Should Quick Resume remain a separate home item when Continue Watching is
   nonempty, or be a shortcut inside that context?
10. Should account state ever appear in the header/footer, or remain in the
    right pane to protect scarce space?
11. When discovery is disabled, should the footer prefer the configured
    host:port or the generic `PSS` label when both cannot fit?
12. What bounded symbol page is necessary for manual URLs while keeping every
    key reachable and readable?
13. What should a future History feature mean: completed plays, all attempts,
    or account-synchronized history? Current state cannot answer this.

## Roadmap and release interaction

Milestone 21 remains the sole `Next` milestone, Milestone 22 is Confirmed, and
the unified UI remains deferred as Milestone 25 behind the planned Milestone 23
desktop distribution and Milestone 24 Offline Downloads.
This plan is Milestone 25 with `Deferred` status, after the planned Milestone 24
Offline Downloads milestone, and does not promote any UI slice into v1. The
release-readiness document already treats a full UI as deferrable; if v1 ships
first, its prerequisites must continue to list the legacy selector, `kbinput`,
and `infoPanel` actually used by that release.

Milestone 21 owns preference semantics, Continue Watching removal, and
compatibility preferences. Milestone 25 may present those features after they
exist, but must not reimplement or silently absorb their scope. History,
posters, image caching, and catalog additions remain separate feature work
rather than visual-refresh tasks.

## History interpretation

There is no current history endpoint or history database. Continue Watching
contains only incomplete progress and deletes completed items. `last-play.json`
stores one recent opaque selection for Quick Resume and is neither complete nor
stable history. Therefore History must not appear as an enabled home item and
must not be derived from either source.

The SVG's History row is a future visual placeholder. Watch history remains a
separate deferred feature requiring its own semantics, privacy/storage bounds,
server contract, and physical acceptance criteria.

## Account UI and security

The Account list can show only the current public states: not linked, checking,
linked, unavailable, addon count, and usable stream-addon count. Actions reuse
Connect, Refresh, View status, and Back as supported by the existing flow. A
linked account cannot be replaced or removed through the remote API.

The official temporary approval flow remains server-mediated. The one-time
approval link goes to the QR renderer through stdin; auth keys, addon transport
URLs, manifests, and stream URLs remain on PSS and out of UI records, process
arguments, device logs, and screenshots.

## 29. Recommended first implementation milestone

When the active release sequence explicitly permits UI work, start with
**Native UI Foundation and Home**, not the keyboard or stream picker.

Scope:

- add the separate opt-in SDL binary and reusable layout/draw/font/input core;
- reproduce the SVG header, equal panes, title band, dividers, and footer with
  fixed 640x480 coordinates;
- implement the current seven home actions with a read-only contextual right
  pane;
- reuse the shell's current status monitor and existing action functions;
- preserve the legacy home and every deeper legacy screen; and
- guarantee native SDL teardown before the selected action and FFplay.

Acceptance criterion:

> From OnionOS Apps, the native home appears immediately at 640x480, all current
> home actions are readable and controller-selectable, the right pane follows
> the highlight, PSS state updates without blocking, offline Settings recovery
> works, RSS/swap stays within the agreed one-shot UI envelope, legacy deeper
> screens and playback behave unchanged, and forced native failure returns to
> the legacy home without stale processes or files.

This slice proves the visual language, process boundary, memory strategy, and
fallback before the migration touches high-value selection or text-entry paths.
