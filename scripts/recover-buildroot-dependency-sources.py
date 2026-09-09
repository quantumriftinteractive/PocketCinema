"""Verify and archive Buildroot 2021.11 dependency sources and package patches."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


PACKAGE_DIRS = {
    "sdl": "sdl", "libass": "libass", "bzip2": "bzip2", "libzlib": "zlib",
    "fontconfig": "fontconfig", "freetype": "freetype", "libfribidi": "fribidi",
    "harfbuzz": "harfbuzz", "libglib2": "glib", "pcre": "pcre", "expat": "expat",
    "libpng": "libpng", "libffi": "libffi", "util-linux": "util-linux", "tslib": "tslib",
}

LICENSE_FILES = {
    "sdl": ["COPYING"], "libass": ["COPYING"], "bzip2": ["LICENSE"],
    "libzlib": ["README"], "fontconfig": ["COPYING"],
    "freetype": ["docs/LICENSE.TXT", "docs/FTL.TXT", "docs/GPLv2.TXT"],
    "libfribidi": ["COPYING"], "harfbuzz": ["COPYING"], "libglib2": ["COPYING"],
    "pcre": ["LICENCE"], "expat": ["COPYING"], "libpng": ["LICENSE"],
    "libffi": ["LICENSE"], "util-linux": ["README.licensing",
        "Documentation/licenses/COPYING.BSD-3-Clause",
        "Documentation/licenses/COPYING.BSD-4-Clause-UC",
        "Documentation/licenses/COPYING.GPL-2.0-or-later",
        "Documentation/licenses/COPYING.ISC",
        "Documentation/licenses/COPYING.LGPL-2.1-or-later"], "tslib": ["COPYING"]
}


def digest(data, algorithm="sha256"):
    return getattr(hashlib, algorithm)(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args()
    metadata = args.repo / "release-sources/miyoo"
    buildroot = args.repo / "release-sources/miyoo/inputs/buildroot-2021.11.tar.gz"
    index = json.loads((metadata / "buildroot-package-index.json").read_text())
    index_by_name = {item["package"]: item for item in index}
    patch_root = args.archive_root / "dependency-patches"
    package_root = args.archive_root / "dependency-metadata"
    license_root = args.archive_root / "licenses/dependencies"
    records = []
    with tarfile.open(buildroot) as source:
        members = {member.name: member for member in source.getmembers()}
        for package, package_dir in PACKAGE_DIRS.items():
            prefix = f"buildroot-2021.11/package/{package}/"
            files = [member for name, member in members.items()
                     if name.startswith(prefix) and member.isfile()]
            makefile = next(member for member in files if member.name.endswith(f"/{package}.mk"))
            hashfile = next((member for member in files if member.name.endswith(".hash")), None)
            target_dir = package_root / package_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / PurePosixPath(makefile.name).name).write_bytes(source.extractfile(makefile).read())
            if hashfile:
                (target_dir / PurePosixPath(hashfile.name).name).write_bytes(source.extractfile(hashfile).read())
            patches = []
            for member in files:
                if member.name.endswith(".patch"):
                    name = PurePosixPath(member.name).name
                    destination = patch_root / package_dir / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.extractfile(member).read())
                    patches.append(name)
            item = index_by_name[package]
            archive = next((path for path in (args.archive_root / "dependency-sources" / package_dir).iterdir()
                            if path.is_file()), None)
            if archive is None:
                raise SystemExit(f"Missing downloaded source archive for {package}")
            expected = None
            algorithm = "sha256"
            for line in item.get("upstream_hash_entries", []):
                fields = line.split()
                if len(fields) >= 3 and fields[-1] == archive.name:
                    algorithm, expected = fields[0], fields[1]
            if expected is None:
                raise SystemExit(f"No Buildroot source hash for {package}")
            data = archive.read_bytes()
            actual = digest(data, algorithm)
            if actual != expected:
                raise SystemExit(f"Source hash mismatch for {package}: {actual} != {expected}")
            licenses = []
            with tarfile.open(archive) as dependency:
                members_by_suffix = {member.name: member for member in dependency.getmembers()
                                     if member.isfile()}
                for relative in LICENSE_FILES[package]:
                    member = next((candidate for name, candidate in members_by_suffix.items()
                                   if name.endswith("/" + relative) or PurePosixPath(name).name == relative), None)
                    if member is None:
                        raise SystemExit(f"License file missing in {package}: {relative}")
                    destination = args.archive_root / "licenses/dependencies" / package / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(dependency.extractfile(member).read())
                    licenses.append(relative)
            records.append({
                "package": package,
                "source_archive": archive.name,
                "source_hash_algorithm": algorithm,
                "source_sha256": digest(data),
                "buildroot_patch_files": sorted(patches),
                "license_files_recovered": licenses,
                "provenance_class": "A",
                "note": "Exact Buildroot 2021.11 source hash and complete package patch directory preserved; this does not prove the recovered SDK applied this package set."
            })
    result = {"buildroot": "2021.11", "packages": records}
    (args.archive_root / "dependency-source-recovery.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.repo / "release-sources/miyoo/dependency-source-recovery.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
