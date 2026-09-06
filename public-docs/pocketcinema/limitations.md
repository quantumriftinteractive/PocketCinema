# Known limitations and v1 notes

- PocketCinema is a focused Miyoo client, not the full Stremio interface.
- Availability depends on the linked account, installed addons, PCServer configuration, and the source returned by an addon.
- Device playback supports a measured compatibility envelope. PCServer can convert some sources, but unsupported or unsuitable media can still fail.
- Live streams can be less seekable and less stable than on-demand media.
- Subtitle behavior depends on the source and playback path.
- Very large selector lists are bounded by the device build and available resources.
- Remote access uses the standalone Tailscale companion; public port forwarding is not a PocketCinema setup.
- Library, Next Episode, and broader UI polish are not part of this v1 guide.

PocketCinema does not bundle or hard-code a particular TV addon or channel list.
