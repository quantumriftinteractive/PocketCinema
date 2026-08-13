#!/bin/sh
set -eu

VERSION="${TAILSCALE_VERSION:-1.102.2}"
ARCH="${TAILSCALE_ARCH:-arm}"
BASE_DIR="${TAILSCALE_INSTALL_DIR:-/mnt/SDCARD/App/Tailscale}"
URL="${TAILSCALE_URL:-https://pkgs.tailscale.com/stable/tailscale_${VERSION}_${ARCH}.tgz}"
TGZ="${1:-}"
WORK_DIR="${TMPDIR:-/tmp}/onion-tailscale-install"

mkdir -p "$BASE_DIR/bin" "$BASE_DIR/state" "$BASE_DIR/logs" "$BASE_DIR/scripts" "$WORK_DIR"

if [ -z "$TGZ" ]; then
  TGZ="$WORK_DIR/tailscale_${VERSION}_${ARCH}.tgz"
  if command -v curl >/dev/null 2>&1; then
    curl -fL "$URL" -o "$TGZ"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$TGZ" "$URL"
  else
    echo "No curl or wget found."
    echo "Download on a PC instead: $URL"
    echo "Then copy the .tgz to the Miyoo and run: $0 /path/to/tailscale_${VERSION}_${ARCH}.tgz"
    exit 1
  fi
fi

rm -rf "$WORK_DIR/extract"
mkdir -p "$WORK_DIR/extract"
tar -xzf "$TGZ" -C "$WORK_DIR/extract"

SRC_DIR="$WORK_DIR/extract/tailscale_${VERSION}_${ARCH}"
if [ ! -x "$SRC_DIR/tailscale" ] || [ ! -x "$SRC_DIR/tailscaled" ]; then
  echo "Archive did not contain expected tailscale and tailscaled executables."
  exit 1
fi

cp "$SRC_DIR/tailscale" "$BASE_DIR/bin/tailscale"
cp "$SRC_DIR/tailscaled" "$BASE_DIR/bin/tailscaled"
chmod +x "$BASE_DIR/bin/tailscale" "$BASE_DIR/bin/tailscaled"

echo "Installed Tailscale $VERSION ($ARCH) into $BASE_DIR/bin"
echo "Next: cd $BASE_DIR/scripts && ./start.sh"
