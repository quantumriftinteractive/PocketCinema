#!/usr/bin/env python3
"""Assemble the small public Miyoo compliance bundle from verified inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

LIBRARIES = {
    "sdl": ("SDL 1.2.15", "LGPL-2.1+", "libSDL-1.2.so.0"),
    "libass": ("libass 0.15.2", "ISC", "libass.so.9"),
    "bzip2": ("bzip2 1.0.8", "bzip2 license", "libbz2.so.1.0"),
    "libzlib": ("zlib 1.2.11", "zlib license", "libz.so.1"),
    "fontconfig": ("Fontconfig 2.13.1", "Fontconfig license", "libfontconfig.so.1"),
    "freetype": ("FreeType 2.10.4", "FTL/GPL-2.0+", "libfreetype.so.6"),
    "libfribidi": ("FriBidi 1.0.10", "LGPL-2.1+", "libfribidi.so.0"),
    "harfbuzz": ("HarfBuzz 3.0.0", "MIT, ISC", "libharfbuzz.so.0"),
    "libglib2": ("GLib 2.68.4", "LGPL-2.1+", "libglib-2.0.so.0"),
    "pcre": ("PCRE 8.45", "BSD-3-Clause", "libpcre.so.1"),
    "expat": ("Expat 2.4.1", "MIT", "libexpat.so.1"),
    "libpng": ("libpng 1.6.37", "libpng license", "libpng16.so.16"),
    "libffi": ("libffi 3.4.2", "MIT", "libffi.so.8"),
    "util-linux": ("libuuid 2.37.2", "BSD-3-Clause", "libuuid.so.1"),
    "tslib": ("tslib 1.22", "GPL-2.0+ programs; LGPL-2.1+ libraries", "libts.so.0"),
}
PATCH_DIRS = {"libglib2": "glib"}
SOURCE_DIRS = {"libzlib": "zlib", "libfribidi": "fribidi", "libglib2": "glib"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_verified(source: Path, destination: Path, expected: str | None = None) -> None:
    if not source.is_file():
        raise SystemExit(f"missing required input: {source}")
    actual = sha256(source)
    if expected and actual != expected:
        raise SystemExit(f"SHA-256 mismatch for {source}: {actual} != {expected}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-archives", action="store_true")
    args = parser.parse_args()
    root = args.archive_root.resolve()
    out = args.output.resolve()
    if not (root / "source-info/dependency-source-recovery.json").is_file():
        raise SystemExit("archive root is not the verified Miyoo input archive")
    if out == root or root in out.parents:
        raise SystemExit("output must not be inside the archival input directory")
    if out.exists():
        shutil.rmtree(out)
    (out / "licenses").mkdir(parents=True)
    (out / "ffmpeg").mkdir()
    (out / "dependencies").mkdir()
    (out / "font").mkdir()

    recovery = json.loads((root / "source-info/dependency-source-recovery.json").read_text(encoding="utf-8"))
    manifest = {"format": 1, "generated_from": "verified external archival input set", "components": []}

    ffmpeg_archive = root / "upstream/ffmpeg/ffmpeg-2.4.14.tar.xz"
    ffmpeg = {
        "component": "FFmpeg/FFplay",
        "version": "2.4.14",
        "license": "LGPL-2.1+ (configuration evidence shows no --enable-gpl or --enable-nonfree)",
        "source_archive": "ffmpeg-2.4.14.tar.xz",
        "sha256": sha256(ffmpeg_archive),
        "patch": "ffmpeg/final.patch",
        "runtime": "runtime/ffplay",
        "public_source": "corresponding-source/ffmpeg/ffmpeg-2.4.14.tar.xz",
    }
    manifest["components"].append(ffmpeg)
    for relative in ("PROVENANCE.md", "BUILD-PROVENANCE.md", "final.patch", "manifest.json", "configuration/configure-command.txt", "configuration/config.h", "configuration/config.mak", "configuration/pkg-config-arm.sh"):
        source = Path(__file__).parent.parent / "release-sources/miyoo/ffmpeg-2.4.14-pocketcinema" / relative
        if source.is_file():
            copy_verified(source, out / "ffmpeg" / Path(relative).name)
    with tarfile.open(ffmpeg_archive, "r:xz") as archive:
        for member in archive.getmembers():
            if member.name in {"ffmpeg-2.4.14/LICENSE.md", "ffmpeg-2.4.14/COPYING.LGPLv2.1", "ffmpeg-2.4.14/COPYING.GPLv2"}:
                target = out / "licenses" / Path(member.name).name
                target.write_bytes(archive.extractfile(member).read())
    if args.include_archives:
        copy_verified(ffmpeg_archive, out / "corresponding-source/ffmpeg" / ffmpeg_archive.name, ffmpeg["sha256"])

    for item in recovery["packages"]:
        package = item["package"]
        label, license_name, runtime = LIBRARIES[package]
        source_dir = SOURCE_DIRS.get(package, package)
        archive = root / "dependency-sources" / source_dir / item["source_archive"]
        record = {"component": label, "version": label.rsplit(" ", 1)[1], "license": license_name,
                  "source_archive": item["source_archive"], "sha256": item["source_sha256"],
                  "patches": item["buildroot_patch_files"], "runtime": runtime,
                  "public_source": f"corresponding-source/dependencies/{item['source_archive']}"}
        if sha256(archive) != item["source_sha256"]:
            raise SystemExit(f"SHA-256 mismatch for {archive}")
        manifest["components"].append(record)
        patch_dir = PATCH_DIRS.get(package, package)
        for patch in item["buildroot_patch_files"]:
            source = root / "dependency-patches" / patch_dir / patch
            copy_verified(source, out / "dependencies" / package / patch)
        for license_file in item["license_files_recovered"]:
            source = root / "licenses/dependencies" / package / license_file
            copy_verified(source, out / "licenses/dependencies" / package / Path(license_file).name)
        if args.include_archives:
            copy_verified(archive, out / "corresponding-source/dependencies" / item["source_archive"], item["source_sha256"])

    font = root / "font/PlusJakartaSans.ttf"
    manifest["components"].append({"component": "Plus Jakarta Sans", "version": "2.006", "license": "SIL OFL 1.1",
                                    "sha256": sha256(font), "runtime": "font/PlusJakartaSans.ttf",
                                    "stremio_web_commit": "1748dc1a3e95f0eb0d171f78aedb536e7df7cd61",
                                    "git_path": "assets/fonts/PlusJakartaSans.ttf", "git_blob_sha1": "b88589a39657e0103d0911c6ced782fce08e757c",
                                    "public_source": "font/PlusJakartaSans.ttf"})
    copy_verified(root / "licenses/PlusJakartaSans-2.6-OFL.txt", out / "licenses/PlusJakartaSans-2.6-OFL.txt")
    (out / "SOURCE-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_note = "The corresponding-source archives are included under `corresponding-source/`." if args.include_archives else "The corresponding-source archives are separate release assets named and hash-pinned in `SOURCE-MANIFEST.json`."
    (out / "README.md").write_text(f"""# PocketCinema Miyoo v1 public compliance bundle\n\nThis bundle accompanies the Miyoo runtime. {source_note} The large private archival input directory is not this bundle. The candidate player sets `LD_LIBRARY_PATH` to `experiments/ffplay/lib` before launching FFplay, so the listed shared libraries are replaceable compatible runtime files. Use the supplied corresponding sources and patches for LGPL modifications.\n\nThis bundle does not contain the compiler, SDK/sysroot, recovered runtime binaries, selector, account configuration, logs, or device state.\n""", encoding="utf-8")
    notices = ["# PocketCinema Miyoo v1 third-party notices", "", "PocketCinema ships FFplay and the shared libraries listed below. Corresponding source archives, patches, and hashes are identified in `SOURCE-MANIFEST.json`. LGPL components are dynamically linked; users may replace compatible shared libraries, subject to normal ABI compatibility. No technical restriction is intentionally added to prevent replacement or debugging of LGPL modifications.", ""]
    for component in manifest["components"]:
        notices += [f"## {component['component']} {component['version']}", f"- License: {component['license']}", "- Copyright/attribution: preserved in the accompanying authoritative license text for this component.", f"- Runtime: {component.get('runtime', 'font asset')}", f"- Corresponding source: `{component['public_source']}`", ""]
    notices += ["Plus Jakarta Sans attribution: Copyright 2020 The Plus Jakarta Sans Project Authors; Tokotype; Gumpita Rahayu. The exact unmodified font is distributed under SIL OFL 1.1.", ""]
    (out / "THIRD_PARTY_NOTICES.md").write_text("\n".join(notices), encoding="utf-8")
    print(f"assembled {sum(1 for _ in out.rglob('*') if _.is_file())} files at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
