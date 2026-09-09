"""Stage verified corresponding source without compiling or touching recovery inputs."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    metadata = root / "release-sources/miyoo/ffmpeg-2.4.14-pocketcinema"
    if not (metadata / "manifest.json").is_file():
        # The staged source set also carries this script beside its metadata.
        metadata = Path(__file__).resolve().parent / "ffmpeg-2.4.14-pocketcinema"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New directory; existing paths are always refused")
    args = parser.parse_args()
    manifest = json.loads((metadata / "manifest.json").read_text())
    if sha256(args.archive) != manifest["archive_sha256"]:
        raise SystemExit("Pristine archive hash mismatch")
    for relative, expected in manifest["metadata_sha256"].items():
        if sha256(metadata / relative) != expected:
            raise SystemExit(f"Metadata hash mismatch: {relative}")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists; refusing to overwrite")
    # Check every member before creating output; reject links and special files.
    with tarfile.open(args.archive) as archive:
        members = archive.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or
                    "\\" in member.name or ":" in member.name or
                    not name.parts or name.parts[0] != "ffmpeg-2.4.14" or
                    not (member.isdir() or member.isfile())):
                raise SystemExit(f"Unexpected archive member: {member.name}")
        output.mkdir(parents=True)
        source = output / "source"
        source.mkdir()
        pristine_hashes = {}
        for member in members:
            relative = PurePosixPath(member.name).relative_to("ffmpeg-2.4.14")
            target = source / str(relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(member.mode & 0o777)
                pristine_hashes[relative.as_posix()] = sha256(target)
    # Preserve pristine archive as well as the resulting patched source.
    shutil.copyfile(args.archive, output / args.archive.name)
    subprocess.run(["git", "-c", "core.autocrlf=false", "apply", "--no-index", "--whitespace=nowarn",
                    str(metadata / "final.patch")], cwd=source, check=True)
    changed = []
    for relative, original_hash in pristine_hashes.items():
        actual = sha256(source / relative)
        expected = manifest["modified_source_sha256"].get(relative, original_hash)
        if actual != expected:
            raise SystemExit(f"Patched source mismatch: {relative}")
        if actual != original_hash:
            changed.append(relative)
    if set(changed) != set(manifest["modified_source_sha256"]):
        raise SystemExit("Unexpected modified-file set")
    actual_files = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    if actual_files != set(pristine_hashes):
        raise SystemExit("Unexpected added or missing source files")
    provenance = output / "provenance"
    shutil.copytree(metadata, provenance / metadata.name)
    for path in metadata.parent.iterdir():
        if path.is_file() and path.suffix in {".md", ".json"}:
            shutil.copyfile(path, provenance / path.name)
    shutil.copyfile(Path(__file__), provenance / Path(__file__).name)
    shutil.copyfile(metadata / "configuration/pkg-config-arm.sh", source / "pkg-config-arm.sh")
    result = {"archive_sha256": manifest["archive_sha256"],
              "patch_sha256": manifest["metadata_sha256"]["final.patch"],
              "pristine_regular_files": len(pristine_hashes),
              "modified_source_sha256": manifest["modified_source_sha256"],
              "verification": "Every archive member verified; only two source files changed",
              "compiled": False}
    (output / "VERIFICATION.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
