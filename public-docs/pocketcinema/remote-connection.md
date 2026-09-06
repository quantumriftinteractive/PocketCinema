# Remote connection with the Tailscale companion

Remote use can be provided by the independent standalone Tailscale companion for OnionOS. It supplies the network path; PocketCinema does not start, stop, inspect, or authenticate Tailscale.

Install and sign in to the companion using its own documented workflow, then configure PocketCinema with the PCServer address reachable through that private network. Keep the PocketCinema app’s optional generic HTTP proxy setting empty unless your network specifically needs it.

Do not use public port forwarding. Keep PCServer on a private, access-controlled network and preserve the companion’s own state independently of PocketCinema.
