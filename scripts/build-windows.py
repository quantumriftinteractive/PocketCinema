"""Rebuild a pinned Windows one-directory candidate entirely under ignored .tmp."""
from __future__ import annotations

import ast
import hashlib
from importlib import metadata
import json
import marshal
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tkinter
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".tmp" / "windows-package-v1.0.0"
CONFIG = ROOT / "packaging" / "windows"
PYTHON_VERSION = "3.11.0"
TCL_VERSION = "8.6.12"
MEDIA_INPUT = Path(os.environ.get(
    "POCKETCINEMA_WINDOWS_FFMPEG_INPUT",
    str(Path.home() / "PocketCinema-Windows-v1.0.0-release-inputs" / "ffmpeg"),
))
MEDIA_TOOLS = {
    "ffmpeg.exe": "72A489ECCD008C2EC2C0A5856C5C75BC3D8BBFA90166C4566865C246445E6AA3",
    "ffprobe.exe": "19202B23C0043F15AD1B7BCE2344F406FD52BD6EFD8F995CE02E7392A1CEC52F",
}


def repository_version():
    tree = ast.parse((ROOT / "server" / "pocketcinema_server.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SERVER_VERSION" for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError("Canonical SERVER_VERSION was not found")


def clean_output(path):
    # Resolve and check every recursive removal against the fixed build root.
    path = path.resolve()
    expected = OUTPUT.resolve()
    if path != expected or not path.is_relative_to((ROOT / ".tmp").resolve()):
        raise RuntimeError("Refusing to remove a path outside the packaging output")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def check_environment():
    if sys.platform != "win32" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Build on 64-bit Windows using the documented isolated build environment")
    if platform.python_version() != PYTHON_VERSION:
        raise RuntimeError(f"This candidate recipe requires Python {PYTHON_VERSION}; see packaging documentation")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Use an isolated venv with packaging/windows/requirements-build.txt")
    versions = {}
    for path in (CONFIG / "requirements-build.txt", ROOT / "server" / "requirements-desktop.txt"):
        for line in path.read_text().splitlines():
            if "==" not in line or line.lstrip().startswith("#"):
                continue
            name, version = line.split(";", 1)[0].strip().split("==")
            actual = metadata.version(name)
            if actual != version:
                raise RuntimeError(f"{name} requires {version}; install the pinned build requirements")
            versions[name] = actual
    tcl = tkinter.Tcl().eval("info patchlevel")
    if tcl != TCL_VERSION:
        raise RuntimeError(f"This candidate requires Tcl/Tk {TCL_VERSION}")
    return versions


def prepare_assets(version):
    from PIL import Image
    assets = OUTPUT / "assets"
    assets.mkdir()
    with Image.open(ROOT / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png") as source:
        source.save(assets / "PocketCinema Server.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    numbers = tuple(int(n) for n in version.split("-", 1)[0].split(".")) + (0,)
    (assets / "version.txt").write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(numbers) + ", prodvers=" + repr(numbers)
        + ", mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('040904B0', ["
        "StringStruct('CompanyName','Quantum Rift Interactive'),"
        "StringStruct('FileDescription','PocketCinema Server'),"
        "StringStruct('ProductName','PocketCinema Server'),"
        "StringStruct('OriginalFilename','PocketCinema Server.exe'),"
        "StringStruct('FileVersion'," + repr(version) + "),"
        "StringStruct('ProductVersion'," + repr(version) + ")])]),"
        "VarFileInfo([VarStruct('Translation',[1033,1200])])])", encoding="utf-8",
    )
    media = assets / "media-tools" / "bin"
    media.mkdir(parents=True)
    for name, expected in MEDIA_TOOLS.items():
        source = MEDIA_INPUT / "runtime-input" / name
        if not source.is_file():
            raise RuntimeError(f"Approved bundled media tool is missing: {source}")
        actual = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        if actual != expected:
            raise RuntimeError(f"Approved hash mismatch for {name}: {actual}")
        shutil.copyfile(source, media / name)


def copy_notices(destination):
    for name in ("README.txt", "THIRD_PARTY_NOTICES.txt"):
        shutil.copyfile(CONFIG / name, destination / name)
    licenses = destination / "THIRD_PARTY"
    licenses.mkdir()
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    shutil.copyfile(Path(sys.base_prefix) / "tcl" / "tk8.6" / "license.terms", licenses / "Tk-license.terms")
    shutil.copyfile(CONFIG / "Tcl-license.terms", licenses / "Tcl-license.terms")
    for name in ("pystray", "Pillow", "six", "PyInstaller", "pyinstaller-hooks-contrib"):
        dist = metadata.distribution(name)
        for entry in dist.files:
            if entry.name.lower().startswith(("license", "copying", "notice")):
                folder = licenses / name
                folder.mkdir(exist_ok=True)
                shutil.copyfile(dist.locate_file(entry), folder / entry.name)
    ffmpeg = destination / "THIRD_PARTY" / "FFmpeg"
    ffmpeg.mkdir(parents=True)
    for source_name, destination_name in (
        ("LICENSES/FFmpeg-LICENSE", "LICENSE"),
        ("BUILD_INFO.txt", "BUILD_INFO.txt"),
        ("ORIGIN.txt", "ORIGIN.txt"),
        ("SOURCE_REFERENCE.txt", "SOURCE_REFERENCE.txt"),
        ("COMPLIANCE-PLAN.txt", "COMPLIANCE-PLAN.txt"),
        ("SHA256SUMS", "INPUT-SHA256SUMS.txt"),
        ("extracted/ffmpeg-9.0.1-essentials_build/README.txt", "Gyan-build-README.txt"),
    ):
        shutil.copyfile(MEDIA_INPUT / source_name, ffmpeg / destination_name)
    source_dir = ffmpeg / "SOURCE"
    source_dir.mkdir()
    for name in ("ffmpeg-9.0.1.tar.xz", "ffmpeg-9.0.1.tar.xz.asc"):
        shutil.copyfile(MEDIA_INPUT / name, source_dir / name)


def audit(destination):
    import pefile
    from PyInstaller.archive.readers import CArchiveReader
    forbidden = {".git", "credentials", "logs", "fixtures", "__pycache__", "tests"}
    paths = sorted(path for path in destination.rglob("*") if path.is_file())
    markers = (str(ROOT).encode(), str(ROOT).replace("\\", "/").encode(),
               str(Path.home()).encode(), str(Path.home()).encode("utf-16le"))
    def check_paths(payload, label):
        for marker in markers:
            if marker.lower() in payload.lower():
                raise RuntimeError("Local build path leaked into artifact: " + label)
    for path in paths:
        relative = path.relative_to(destination)
        expected_media = {
            Path("_internal") / "media-tools" / "bin" / name
            for name in MEDIA_TOOLS
        }
        if forbidden.intersection(relative.parts) or (
            path.name.lower() in {"ffmpeg.exe", "ffprobe.exe"} and relative not in expected_media
        ) or path.name.lower() in {
            "tailscale.exe", "tailscaled.exe", "stremio.exe",
            "stremio_account.json", "stream_addons.json", "config.json",
        } or path.suffix.lower() in {".log", ".pdb"}:
            raise RuntimeError("Unexpected development/runtime content in artifact: " + str(relative))
        check_paths(path.read_bytes(), str(relative))
    media_hashes = {}
    for name, expected in MEDIA_TOOLS.items():
        path = destination / "_internal" / "media-tools" / "bin" / name
        if not path.is_file():
            raise RuntimeError("Required bundled media tool is missing: " + name)
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual != expected:
            raise RuntimeError(f"Bundled media tool hash mismatch for {name}: {actual}")
        media_hashes[name] = actual
    for required in (
        destination / "THIRD_PARTY" / "FFmpeg" / "LICENSE",
        destination / "THIRD_PARTY" / "FFmpeg" / "SOURCE_REFERENCE.txt",
        destination / "THIRD_PARTY" / "FFmpeg" / "SOURCE" / "ffmpeg-9.0.1.tar.xz",
    ):
        if not required.is_file():
            raise RuntimeError("Required FFmpeg compliance file is missing: " + str(required.relative_to(destination)))
    exe = destination / "PocketCinema Server.exe"
    pe = pefile.PE(str(exe))
    if pe.OPTIONAL_HEADER.Subsystem != 2:
        raise RuntimeError("Executable is not a Windows GUI subsystem image")
    pe.close()
    archive = CArchiveReader(str(exe))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    modules = sorted(pyz.toc)
    for name in modules:
        check_paths(marshal.dumps(pyz.extract(name)), name)
    if any(name.startswith(("server.test_", "pytest", "pip.", "setuptools.", "unittest")) for name in modules):
        raise RuntimeError("Unexpected test/build packages in frozen archive")
    if "server.desktop.server_child" not in modules or "server.desktop.gui" not in modules:
        raise RuntimeError("A required frozen role was not collected")
    if not (destination / "_internal" / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png").is_file():
        raise RuntimeError("Canonical icon missing")
    if not (destination / "_internal" / "pystray" / "_win32.py").is_file():
        raise RuntimeError("Replaceable Win32 tray source missing")
    return {"file_count": len(paths), "frozen_module_count": len(modules), "gui_subsystem": True,
            "external_media_tools_bundled": True, "media_tools": media_hashes,
            "local_path_scan": "PASS"}


def main():
    versions = check_environment()
    version = repository_version()
    clean_output(OUTPUT)
    prepare_assets(version)
    env = dict(os.environ, PYTHONHASHSEED="0", SOURCE_DATE_EPOCH="1666569600")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(OUTPUT / "dist"), "--workpath", str(OUTPUT / "work"),
                    str(CONFIG / "PocketCinema.spec")], cwd=ROOT, env=env, check=True)
    destination = OUTPUT / "dist" / "PocketCinema Server"
    copy_notices(destination)
    result = audit(destination)
    source_files = sorted((ROOT / "server").rglob("*.py")) + sorted(CONFIG.glob("*")) + [
        Path(__file__), ROOT / "server/requirements-desktop.txt",
        ROOT / "UI_concept/Icons/PocketCinema_Server_icon.png"]
    source_hash = hashlib.sha256()
    for path in source_files:
        if path.is_file():
            source_hash.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    source_hash.update(b"approved-media-tools\0")
    for name, expected in MEDIA_TOOLS.items():
        source_hash.update(name.encode() + b"\0" + expected.encode() + b"\0")
    info = {"product": "PocketCinema Server", "version": version, "python": PYTHON_VERSION,
            "tcl_tk": TCL_VERSION, "architecture": "Windows x64", "packages": versions,
            "source_inputs_sha256": source_hash.hexdigest(), "audit": result,
            "signed": False, "clean_machine_accepted": False}
    (destination / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    hashes = []
    for path in sorted(destination.rglob("*")):
        if path.is_file():
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(destination).as_posix())
    (destination / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")
    archive = OUTPUT / f"PocketCinema-Server-{version}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                entry = zipfile.ZipInfo("PocketCinema Server/" + path.relative_to(destination).as_posix(),
                                        date_time=(2022, 10, 24, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                handle.writestr(entry, path.read_bytes())
    print(json.dumps({"artifact": str(archive.relative_to(ROOT)), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                      "audit": result}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, metadata.PackageNotFoundError) as exc:
        raise SystemExit(str(exc))
