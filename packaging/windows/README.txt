PocketCinema Server - Windows standalone candidate

Extract the complete ZIP to a folder, then open PocketCinema Server.exe.
Keep _internal beside the executable. No Python, repository, build tools,
environment variables, or PowerShell launch script are needed by the user.

Existing desktop settings are reused under %APPDATA%\PocketCinema. Settings,
credentials and runtime data stay there when the application directory moves.
No credentials or media are included in this distribution.

Start the server in the GUI. X hides the window to the existing tray icon;
Open PCServer restores it. Use tray Quit to stop the owned server and exit.
This app does not install a Windows Service or start automatically at login.

This v1.0.0 package includes the approved static FFmpeg 9.0.1 essentials build
as app-local `media-tools/bin/ffmpeg.exe` and `ffprobe.exe`. Normal packaged
execution uses these copies and does not require a separate FFmpeg/FFprobe
installation, PATH changes, or a Stremio installation. Source/development
launches may still use the existing Stremio-runtime, PATH, or manual-tool
fallbacks.
Stremio Service is also external; the normal endpoint is http://127.0.0.1:11470.
An unreachable service does not prevent the controller from opening.
Tailscale is independent and is not installed or managed by this application.

This v1.0.0 candidate is unsigned. Developer-machine packaged physical
acceptance and clean-Windows acceptance are separate gates. This archive is
not a claim of completed M23/public release readiness. See BUILD_INFO.json for
exact build versions and SHA256SUMS.txt for artifact contents.

Licenses and provenance are in THIRD_PARTY_NOTICES.txt and THIRD_PARTY/,
including the bundled FFmpeg GPLv3 license, build metadata, hashes, provider
attribution, and corresponding FFmpeg source archive/signature.
The unmodified LGPL pystray package is provided as replaceable Python source
under _internal/pystray. It may be modified/replaced under its license without
rebuilding the executable. Keep the public API compatible when replacing it.
