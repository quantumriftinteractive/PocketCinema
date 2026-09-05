# Evaluated by PyInstaller from scripts/build-windows.py.
from pathlib import Path

root = Path(SPECPATH).resolve().parents[1]
assets = root / ".tmp" / "windows-package" / "assets"
a = Analysis(
    [str(root / "server" / "pocketcinema_desktop.py")],
    pathex=[str(root)],
    datas=[(str(root / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"), "UI_concept/Icons")],
    hiddenimports=["pystray._win32"],
    excludes=["unittest", "test", "pytest", "pip", "setuptools", "wheel",
              "pystray._darwin", "pystray._gtk", "pystray._appindicator", "pystray._xorg"],
    module_collection_mode={"pystray": "py"},
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="PocketCinema Server", console=False, debug=False, strip=False, upx=False,
    icon=str(assets / "PocketCinema Server.ico"),
    version=str(assets / "version.txt"),
    disable_windowed_traceback=True,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PocketCinema Server")
