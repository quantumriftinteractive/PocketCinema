# macOS PocketCinema Server packaging

Status: **Physically accepted v1 baseline.** The packaged application is
`PocketCinema Server.app`, bundle version `1.0.0 (1)`, with normal foreground
application behavior.

The macOS release candidate is built with `scripts/build-macos.py` in an
isolated PyInstaller environment. The output is:

```text
.tmp/macos-package/dist/PocketCinema Server.app
```

The bundle identifier is
`com.quantumriftinteractive.pocketcinema.server`. The build embeds the
canonical PocketCinema Server icon and places persistent configuration/data in
the normal user-writable macOS application-support location; no runtime state
is written into the app bundle.

## Media tools

The build currently uses the known local arm64 Homebrew `ffmpeg` 9.0.1 input
and its `ffprobe` companion. It copies the executable pair and the non-system
dylib closure into `Contents/Resources/media-tools/`, rewrites those dylib
references to bundle-relative `@loader_path` paths, and ad-hoc-signs the copied
Mach-O files and finished bundle. Frozen macOS discovery checks this bundled
directory before the normal Stremio runtime/PATH discovery; source/dev and
Windows discovery are unchanged.

The exact build input recorded for this candidate is:

- source: FFmpeg 9.0.1 release tarball,
  <https://ffmpeg.org/releases/ffmpeg-9.0.1.tar.xz>
- source checksum:
  `cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635`
- Homebrew formula license: `GPL-3.0-or-later`
- reason: the selected Homebrew build enables GPL codecs, so this is not an
  LGPL-only FFmpeg distribution.

The app contains `Contents/Resources/media-tools/MEDIA_TOOLS_NOTICES.txt`
with the recorded formula/version and FFmpeg configuration. A public release
must preserve the GPL notices and applicable corresponding-source obligations,
and must also account for the licenses and source obligations of the bundled
runtime libraries reported by `otool -L`.

## macOS window behavior

The red close button performs canonical clean application shutdown, including
stopping the owned PCServer child. Native **Quit** and Cmd+Q use the same
shutdown path. The app is a regular foreground application: it has no custom
status item, menu-bar-only mode, or hide-to-background/Dock-reopen lifecycle.

Background or Dock-reopen behavior is deferred beyond v1. The existing Windows
tray implementation is unchanged.

The candidate is ad-hoc signed for local smoke testing. It is not Developer ID
signed or notarized; a clean Mac may require the user to approve or open it
through macOS security controls, and this artifact should not be described as
Gatekeeper-ready distribution.
