# Configure PocketCinema Server

Open PocketCinema Server before launching the Miyoo client.

## Main settings

- **Server name** helps identify this computer when more than one PCServer is
  available.
- **Listen on** controls which computer network interfaces PCServer uses.
- **Port** is the port used by PocketCinema. Keep the default unless you have a
  reason to change it.
- **Stremio Service endpoint** tells PCServer where its Stremio Service is
  running. The usual local value is `http://127.0.0.1:11470`.
- **FFmpeg** and **FFprobe** show whether the media tools needed for checking or
  preparing some sources are available.

The app displays the usable **PocketCinema connections** that the Miyoo can
use. This is the address to enter or select on the Miyoo. It may differ from a
listen address when the computer has more than one network interface.

Do not enter the Stremio Service address on the Miyoo. The Miyoo connects only
to PocketCinema Server.

## Start the server

1. Review the displayed PocketCinema connection address.
2. Select **Save settings** if you changed anything.
3. Select **Start server**.
4. Wait for the server status to show **Running** and the connection status to
   be available.
5. Use [Connect PocketCinema](connect.md) to configure the Miyoo with the
   displayed PocketCinema address.

When PCServer is running, its configuration controls are locked. Stop the
server before changing them. Use **Restart** after saving a change that should
be applied immediately.

> [SCREENSHOT SHOT-03]
> **PocketCinema Server running with a usable Miyoo connection address.**
> The final image should show the Running status and connection information;
> hide private IP addresses before publication.

For account-backed browsing, link the Stremio account through the PocketCinema
account flow:

1. On the Miyoo, open **Stremio Account** and choose **Connect Account**.
2. Scan the displayed QR code with a phone or open its temporary approval link
   in a browser.
3. Complete the official Stremio approval in that browser.
4. Return to PocketCinema and choose the refresh/check action until the account
   shows as connected.

This step is optional for basic title search. It is required for My Library,
account-backed addons, Live TV, and watched/current account state. PocketCinema
does not require your Stremio password, and account credentials and addon
configuration remain on the computer.
