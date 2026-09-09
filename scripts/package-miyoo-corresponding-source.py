#!/usr/bin/env python3
"""Create a deterministic Miyoo v1 corresponding-source ZIP release asset."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args()
    root = args.archive_root.resolve()
    output = args.output.resolve()
    staging = args.staging.resolve()
    if output.exists() or staging.exists():
        raise SystemExit("refusing existing output or staging path")
    assembler = Path(__file__).with_name("assemble-miyoo-public-compliance.py")
    subprocess.run([sys.executable, str(assembler), "--archive-root", str(root), "--output", str(staging), "--include-archives"], check=True)
    forbidden = {"arm-gnu-toolchain.zip", "toolchain.tar.gz", "ffplay", "pocketcinema-selector", "PlusJakartaSans.ttf"}
    files = [p for p in staging.rglob("*") if p.is_file()]
    bad = [p for p in files if p.name in forbidden]
    if bad:
        shutil.rmtree(staging)
        raise SystemExit(f"forbidden release content: {bad}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files, key=lambda p: p.relative_to(staging).as_posix()):
            relative = Path("PocketCinema-Miyoo-v1.0.0-corresponding-source") / path.relative_to(staging)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    shutil.rmtree(staging)
    print(f"created {output} ({output.stat().st_size} bytes; {len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
