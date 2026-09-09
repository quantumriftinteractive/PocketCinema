"""Verify externally archived Miyoo release inputs without modifying anything."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="Recovery or archival root containing manifest paths")
    parser.add_argument("--manifest", type=Path,
                        default=Path("release-sources/miyoo/archival-manifest.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    failures = []
    for item in manifest["items"]:
        path = args.root / Path(item.get("archive_path", item["path"]))
        if not path.is_file():
            if item.get("required", True):
                failures.append(f"MISSING required {item['id']}: {path}")
            else:
                print(f"SKIP optional {item['id']}: {path}")
            continue
        actual = digest(path)
        if actual.lower() != item["sha256"].lower():
            failures.append(f"HASH {item['id']}: {actual} != {item['sha256']}")
        else:
            print(f"PASS {item['id']}: {actual}")
    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit(1)
    print("All present manifest items match; no files were modified.")


if __name__ == "__main__":
    main()
