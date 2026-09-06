# Privacy and security

PocketCinema is designed for a trusted LAN or private network. PCServer is the only service the Miyoo contacts; Stremio account credentials, addon settings, and upstream media URLs remain on the PCServer host. Device-facing APIs return opaque identifiers instead of those private values.

Use an access-controlled network and host firewall. Do not expose PCServer or a local Stremio Service directly to the public internet, and do not use public port forwarding as a remote-access setup.

Only safe direct HTTP(S) media results are eligible. P2P sources, credential-bearing URLs, local/private-address sources, and external-player results are not passed to the Miyoo. The independent Tailscale companion has its own identity and state; PocketCinema does not administer it.
