# Install PocketCinema Server

PocketCinema Server runs on the computer that the Miyoo connects to. Install it
on the computer that can reach your media services and, when needed, your
Stremio account.

## Windows

1. Download the PocketCinema Server Windows release package.
2. Extract it to a folder you control, or run the provided installer if your
   release includes one.
3. Launch **PocketCinema Server**.
4. Continue with [Configure PocketCinema Server](configure-server.md).

The release package is intended to run without installing Python, cloning the
repository, or preparing PowerShell commands.

On Windows, allow PocketCinema Server through Windows Defender Firewall on your
trusted home network when Windows prompts. Windows normally uses a **Private**
network profile for a trusted home network. PCServer accepts local connections
on TCP **8755** and local discovery uses UDP **8754**. A policy that disables
inbound rules on **Public** networks can block PocketCinema even when the app
appears in Allowed Apps; switch the trusted network to the appropriate Private
profile or follow your administrator's policy instead of disabling the
firewall.

> [SCREENSHOT SHOT-01]
> **PocketCinema Server launched from the Windows release package.**
> The final image should show the normal end-user launch path without private
> usernames, paths, or account information.

## macOS

1. Open `PocketCinema Server.app` from the supplied macOS release package.
2. If macOS warns that the app is from an unidentified developer, open it
   through the normal Privacy & Security approval flow only if you trust the
   package.
3. Open the app and continue with [Configure PocketCinema Server](configure-server.md).

The v1 macOS app is a regular foreground application. Its red close button,
native Quit command, and Cmd+Q all cleanly stop the owned server and exit.
The app is ad-hoc signed, not Developer ID signed or notarized, so a clean Mac
may show the standard Gatekeeper warning.

Do not use the repository's source-development launcher as the normal user
installation path.
Windows may keep the application available through its system tray.

> [SCREENSHOT SHOT-02]
> **PocketCinema Server open on macOS.**
> Use the same main configuration image as the general setup section when the
> macOS and Windows interfaces are visually equivalent.
