# Miyoo Client POC

`json-client.sh` is a lightweight OnionOS shell client for the first structured JSON proof.

It uses the existing Tailscale userspace HTTP proxy:

```sh
HTTP_PROXY=http://127.0.0.1:1055/
```

Run on the Miyoo after `tailscaled` is authenticated:

```sh
cd /mnt/SDCARD/App/PocketStremio/client
chmod +x json-client.sh
./json-client.sh
```

The client writes parsed values to:

```text
/mnt/SDCARD/App/PocketStremio/client/logs/json-client.log
```
