#!/usr/bin/env python3
"""Build the ad-hoc-signed macOS PocketCinema Server application bundle."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".tmp" / "macos-package"
SPEC = ROOT / "packaging" / "macos" / "PocketCinema.spec"
ICON_SOURCE = ROOT / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"
MEDIA_TOOLS = ("ffmpeg", "ffprobe")


def version():
    tree = ast.parse((ROOT / "server" / "pocketcinema_server.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SERVER_VERSION" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise RuntimeError("Canonical SERVER_VERSION was not found")


def clean_output():
    expected = (ROOT / ".tmp" / "macos-package").resolve()
    if OUTPUT.resolve() != expected or not OUTPUT.resolve().is_relative_to((ROOT / ".tmp").resolve()):
        raise RuntimeError("Refusing to remove a path outside the macOS packaging output")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)


def make_icon():
    if not ICON_SOURCE.is_file():
        raise RuntimeError(f"Missing canonical server icon: {ICON_SOURCE}")
    iconset = OUTPUT / "PocketCinema Server.iconset"
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            pixels = size * scale
            subprocess.run(
                ["sips", "-z", str(pixels), str(pixels), str(ICON_SOURCE),
                 "--out", str(iconset / f"icon_{size}x{size}{suffix}.png")],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            )
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(OUTPUT / "PocketCinema Server.icns")],
                   check=True)


def source_hash():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "server").rglob("*.py")) + [SPEC, ICON_SOURCE, Path(__file__)]:
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def _otool_dependencies(path):
    output = subprocess.check_output(["otool", "-L", str(path)], text=True)
    dependencies = []
    for line in output.splitlines()[1:]:
        value = line.strip().split(" ", 1)[0]
        if value.startswith("/") and not value.startswith(("/System/", "/usr/lib/")):
            dependencies.append((value, Path(value).resolve()))
    return dependencies


def bundle_media_tools(app):
    """Copy the known local Homebrew FFmpeg runtime and rewrite its dylibs."""
    if platform.machine() != "arm64":
        raise RuntimeError("The local macOS media-tool input is arm64-only")
    brew = shutil.which("brew")
    if not brew:
        raise RuntimeError("Homebrew is required to verify the approved FFmpeg input")
    inputs = {}
    for name in MEDIA_TOOLS:
        source = Path(shutil.which(name) or "").resolve()
        if not source.is_file() or not source.is_relative_to(Path("/opt/homebrew")):
            raise RuntimeError(f"Approved Homebrew {name} input was not found under /opt/homebrew")
        inputs[name] = source

    root = app / "Contents" / "Resources" / "media-tools"
    bindir, libdir = root / "bin", root / "lib"
    bindir.mkdir(parents=True)
    libdir.mkdir(parents=True)
    copied = {}
    pending = list(inputs.values())
    while pending:
        source = pending.pop()
        source = source.resolve()
        if source in copied:
            continue
        destination = libdir / source.name
        if source in inputs.values():
            destination = bindir / source.name
        shutil.copy2(source, destination)
        destination.chmod(0o755)
        # install_name_tool invalidates upstream signatures; remove them now
        # so the rewritten tools can execute before the final app re-sign.
        subprocess.run(["codesign", "--remove-signature", str(destination)],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        copied[source] = destination
        for _, dependency in _otool_dependencies(source):
            if dependency not in copied:
                pending.append(dependency)

    for source, destination in copied.items():
        is_binary = destination.parent == bindir
        for dependency_name, dependency in _otool_dependencies(source):
            replacement = "@loader_path/../lib/" + dependency.name if is_binary else "@loader_path/" + dependency.name
            subprocess.run(["install_name_tool", "-change", dependency_name, replacement, str(destination)], check=True)
        if not is_binary:
            subprocess.run(["install_name_tool", "-id", "@loader_path/" + destination.name, str(destination)], check=True)

    for destination in copied.values():
        subprocess.run(["codesign", "--force", "--sign", "-", str(destination)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for name, source in inputs.items():
        subprocess.run([str(bindir / source.name), "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    version_text = subprocess.check_output([str(bindir / inputs["ffmpeg"].name), "-version"], text=True, stderr=subprocess.STDOUT)
    brew_json = json.loads(subprocess.check_output([brew, "info", "--json=v2", "ffmpeg"], text=True))
    formula = brew_json["formulae"][0]
    notices = [
        "PocketCinema Server bundled media tools provenance",
        "",
        "Source input: local Homebrew arm64 bottle",
        f"Formula: {formula['full_name']}",
        f"Version: {formula['versions']['stable']}",
        f"License: {formula['license']}",
        f"Source URL: {formula['urls']['stable']['url']}",
        f"Source checksum: {formula['urls']['stable']['checksum']}",
        "",
        "This FFmpeg build is GPL-3.0-or-later because the Homebrew formula enables GPL codecs.",
        "Redistribution must preserve the applicable GPL notices and corresponding source-offer obligations.",
        "The app does not claim LGPL-only licensing for these binaries.",
        "",
        "Runtime dependencies copied into media-tools/lib are the Homebrew libraries reported by otool -L.",
        "Their respective license and source obligations must also be preserved for a public release.",
        "",
        version_text.strip(),
    ]
    (root / "MEDIA_TOOLS_NOTICES.txt").write_text("\n".join(notices) + "\n", encoding="utf-8")
    return {"ffmpeg": version_text.splitlines()[0], "ffprobe": formula["versions"]["stable"], "license": formula["license"],
            "bundled_files": len(copied)}


def main():
    if sys.platform != "darwin" or platform.machine() not in {"arm64", "x86_64"}:
        raise RuntimeError("Build on macOS arm64 or x86_64")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Use an isolated build environment with PyInstaller installed")
    clean_output()
    make_icon()
    env = dict(**__import__("os").environ, PYTHONHASHSEED="0", SOURCE_DATE_EPOCH="1666569600")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(OUTPUT / "dist"), "--workpath", str(OUTPUT / "work"),
                    str(SPEC)], cwd=ROOT, env=env, check=True)
    app = OUTPUT / "dist" / "PocketCinema Server.app"
    if not (app / "Contents" / "MacOS" / "PocketCinema Server").is_file():
        raise RuntimeError("PyInstaller did not create the expected .app executable")
    media_info = bundle_media_tools(app)
    info = {
        "product": "PocketCinema Server",
        "version": version(),
        "architecture": platform.machine(),
        "bundle_identifier": "com.quantumriftinteractive.pocketcinema.server",
        "signed": "adhoc",
        "source_inputs_sha256": source_hash(),
        "external_media_tools_bundled": True,
        "media_tools": media_info,
    }
    (app / "Contents" / "Resources" / "BUILD_INFO.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )
    # PyInstaller ad-hoc-signs the executable, but adding BUILD_INFO after the
    # bundle build changes the sealed resource set. Re-seal the finished app.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    print(json.dumps({"artifact": str(app.relative_to(ROOT)), "bundle_identifier": info["bundle_identifier"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
