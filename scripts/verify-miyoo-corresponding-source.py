#!/usr/bin/env python3
"""Verify the packaged Miyoo corresponding-source ZIP without extracting it."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        root = next(name for name in names if name.endswith("/SOURCE-MANIFEST.json")).rsplit("/", 1)[0]
        manifest = json.loads(archive.read(f"{root}/SOURCE-MANIFEST.json"))
        components = manifest["components"]
        assert len(components) == 17
        assert sum(len(item.get("patches", [])) for item in components) == 19
        for required in ("README.md", "THIRD_PARTY_NOTICES.md", "ffmpeg/final.patch", "ffmpeg/configure-command.txt", "licenses/COPYING.LGPLv2.1", "licenses/PlusJakartaSans-2.6-OFL.txt"):
            assert f"{root}/{required}" in names, required
        configure = archive.read(f"{root}/ffmpeg/configure-command.txt").decode()
        assert "--enable-gpl" not in configure and "--enable-nonfree" not in configure
        assert sha256(archive.read(f"{root}/ffmpeg/final.patch")) == "18d917d32cb0279acc7804849560d33bd7355602c5caa78d001552320b3f5747"
        for item in components:
            if item["component"] == "Plus Jakarta Sans":
                continue
            path = f"{root}/{item['public_source']}"
            assert path in names, path
            assert sha256(archive.read(path)) == item["sha256"], item["source_archive"]
        forbidden = ("arm-gnu-toolchain.zip", "toolchain.tar.gz", "/ffplay", "pocketcinema-selector", "PlusJakartaSans.ttf")
        assert not [name for name in names if any(token in name for token in forbidden)]
        print(f"PASS corresponding-source ZIP: {len(names)} files; 16 source archives; 19 patches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
