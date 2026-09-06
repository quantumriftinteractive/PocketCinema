# Local network connection

For local use, connect the Miyoo and the PCServer host to the same trusted network. Set the Miyoo `SERVER_BASE` to the host address and configured PCServer port, for example `http://HOST_ADDRESS:8755`.

Do not use `127.0.0.1` on the Miyoo: that address refers to the Miyoo itself. It is the normal default only when Stremio Service runs locally on the PCServer host.

If the connection fails, check the host firewall, the PCServer process, the configured port, and whether a proxy setting is required by the network.
