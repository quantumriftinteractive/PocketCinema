#!/usr/bin/env python3
"""Verify the tracked public Miyoo compliance bundle against archival inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    archive = args.archive_root.resolve()
    manifest = json.loads((bundle / "SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
    components = manifest["components"]
    assert len(components) == 17, "expected FFmpeg, 15 dependencies, and font"
    assert sum(len(item.get("patches", [])) for item in components) == 19
    required = [bundle / "README.md", bundle / "THIRD_PARTY_NOTICES.md"]
    required += [bundle / "ffmpeg/final.patch", bundle / "ffmpeg/configure-command.txt", bundle / "licenses/PlusJakartaSans-2.6-OFL.txt"]
    for path in required:
        assert path.is_file(), f"missing {path}"
    configure = (bundle / "ffmpeg/configure-command.txt").read_text(encoding="utf-8")
    assert "--enable-gpl" not in configure and "--enable-nonfree" not in configure
    for item in components:
        if item["component"] == "Plus Jakarta Sans":
            assert digest(archive / "font/PlusJakartaSans.ttf") == item["sha256"]
            continue
        archive_path = archive / ("upstream/ffmpeg/" if item["component"] == "FFmpeg/FFplay" else "dependency-sources/")
        if item["component"] != "FFmpeg/FFplay":
            # Locate by immutable filename without depending on Buildroot's package directory alias.
            matches = list((archive / "dependency-sources").glob(f"*/{item['source_archive']}"))
            assert len(matches) == 1, item["source_archive"]
            archive_path = matches[0]
        else:
            archive_path = archive_path / item["source_archive"]
        assert digest(archive_path) == item["sha256"], item["source_archive"]
    forbidden = {"arm-gnu-toolchain.zip", "toolchain.tar.gz", "ffplay", "pocketcinema-selector"}
    present = {path.name for path in bundle.rglob("*") if path.is_file()}
    assert not forbidden.intersection(present), forbidden.intersection(present)
    print(f"PASS public bundle: {sum(1 for p in bundle.rglob('*') if p.is_file())} files; 17 components; 19 patches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
