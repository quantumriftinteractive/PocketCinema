# Miyoo installation

1. Connect the Miyoo to the development computer using the normal deployment workflow.
2. Deploy the tracked PocketCinema app files with `scripts/deploy-miyoo.ps1 -DeviceHost root@DEVICE_ADDRESS`.
3. Set `SERVER_BASE` in the app-local configuration to the PCServer URL. The live configuration is `/mnt/SDCARD/App/PocketCinema/config/pocketcinema.conf`.
4. Launch PocketCinema from OnionOS Apps.

Deployment preserves the existing live configuration. Do not replace it with a repository example if the device is already configured. A generic HTTP proxy can be configured when the network requires one; leave it empty for direct HTTP.

The app must remain under `/mnt/SDCARD/App/PocketCinema/`. Do not install files into OnionOS core directories.
