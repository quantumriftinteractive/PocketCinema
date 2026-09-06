#!/usr/bin/env python3
"""Export the allowlisted PocketCinema end-user documentation."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs/user/public-docs.json"
OUTPUT = ROOT / "public-docs/pocketcinema"


def load_manifest():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = data.get("files")
    if data.get("product") != "PocketCinema" or not isinstance(files, list):
        raise ValueError("invalid public-docs manifest")
    paths = []
    for name in files:
        if not isinstance(name, str):
            raise ValueError(f"unsafe manifest path: {name!r}")
        path = Path(name)
        if not name or path.is_absolute() or ".." in path.parts or path.suffix != ".md":
            raise ValueError(f"unsafe manifest path: {name!r}")
        source = ROOT / "docs/user" / path
        if not source.is_file():
            raise ValueError(f"missing public document: {name}")
        paths.append((path, source))
    if len({path for path, _ in paths}) != len(paths):
        raise ValueError("duplicate public document")
    return paths


def expected(files):
    return {path: source.read_bytes() for path, source in files}


def actual():
    if not OUTPUT.is_dir():
        return {}
    return {
        path.relative_to(OUTPUT): path.read_bytes()
        for path in OUTPUT.rglob("*")
        if path.is_file()
    }


def check(files):
    wanted = expected(files)
    present = actual()
    if present == wanted:
        return
    missing = sorted(str(path) for path in wanted.keys() - present.keys())
    stale = sorted(str(path) for path in present.keys() - wanted.keys())
    changed = sorted(str(path) for path in wanted.keys() & present.keys() if wanted[path] != present[path])
    details = []
    if missing:
        details.append("missing: " + ", ".join(missing))
    if stale:
        details.append("stale: " + ", ".join(stale))
    if changed:
        details.append("changed: " + ", ".join(changed))
    raise ValueError("public export is out of date (" + "; ".join(details) + ")")


def sync(files):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    wanted = expected(files)
    for path in sorted(OUTPUT.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    for path, content in wanted.items():
        destination = OUTPUT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    try:
        files = load_manifest()
        check(files) if args.check else sync(files)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"public-docs: {exc}", file=sys.stderr)
        return 1
    print(f"public-docs: {'checked' if args.check else 'exported'} {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
