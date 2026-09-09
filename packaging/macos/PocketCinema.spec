# PyInstaller recipe for the macOS PocketCinema Server .app.
from pathlib import Path

root = Path(SPECPATH).resolve().parents[1]

a = Analysis(
    [str(root / "server" / "pocketcinema_desktop.py")],
    pathex=[str(root)],
    datas=[(str(root / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"),
           "UI_concept/Icons")],
    excludes=["pystray", "PIL", "server.test_", "pytest", "pip", "setuptools", "wheel"],
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="PocketCinema Server",
    console=False,
    debug=False,
    strip=False,
    upx=False,
    disable_windowed_traceback=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PocketCinema Server")
app = BUNDLE(
    coll,
    name="PocketCinema Server.app",
    icon=str(root / ".tmp" / "macos-package" / "PocketCinema Server.icns"),
    bundle_identifier="com.quantumriftinteractive.pocketcinema.server",
    info_plist={
        "CFBundleDisplayName": "PocketCinema Server",
        "CFBundleName": "PocketCinema Server",
        "CFBundleIdentifier": "com.quantumriftinteractive.pocketcinema.server",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
    },
)
