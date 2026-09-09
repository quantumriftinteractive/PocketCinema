"""Developer-only frozen artifact smoke; no hooks are added to the product.

Uses temporary profiles, loopback ephemeral ports, and exact Popen ownership.
--gui needs an interactive desktop: native menu clicks briefly move the pointer
inside the test-owned menu, then restore it. Do not interact during that smoke.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import replace
import json
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from unittest import mock
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.desktop.capabilities import detect_tool
from server.desktop.config import DesktopSettings, load_settings, save_settings
from server.desktop.lifecycle import PCServerLifecycle


def until(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError("Timed out waiting for frozen runtime state")


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def status(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=.4) as response:
            return json.load(response)
    except OSError:
        return None


class NativeWindows:
    def __init__(self, pid):
        self.pid = pid
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.api.EnumWindows.argtypes = [self.callback, wintypes.LPARAM]
        self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.api.IsWindowVisible.argtypes = [wintypes.HWND]
        self.api.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.api.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.api.SendMessageW.restype = wintypes.LPARAM
        self.api.GetMenuItemRect.argtypes = [wintypes.HWND, wintypes.HMENU, wintypes.UINT, ctypes.POINTER(wintypes.RECT)]
        self.api.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self.api.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.api.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
        self.api.AllowSetForegroundWindow.argtypes = [wintypes.DWORD]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    def child_handles(self):
        # Read only exact parent/name matches; retain kernel handles so PID reuse
        # cannot affect later assertions. These handles are never used to kill.
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        command = (f"Get-CimInstance Win32_Process -Filter \"ParentProcessId = {self.pid} "
                   "AND Name = 'PocketCinema Server.exe'\" | Select-Object -ExpandProperty ProcessId")
        result = subprocess.check_output([str(powershell), "-NoProfile", "-Command", command],
                                         creationflags=subprocess.CREATE_NO_WINDOW, text=True, timeout=10)
        handles = []
        for value in result.split():
            handle = self.kernel.OpenProcess(0x100000, False, int(value))
            if handle:
                handles.append(handle)
        return handles

    def wait_children(self, handles):
        for handle in handles:
            try:
                assert self.kernel.WaitForSingleObject(handle, 15000) == 0, "Owned child did not exit"
            finally:
                self.kernel.CloseHandle(handle)

    def windows(self):
        found = []
        def visit(hwnd, unused):
            pid = wintypes.DWORD()
            self.api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == self.pid:
                name = ctypes.create_unicode_buffer(256)
                self.api.GetClassNameW(hwnd, name, 256)
                found.append((hwnd, name.value, bool(self.api.IsWindowVisible(hwnd))))
            return True
        self.api.EnumWindows(self.callback(visit), 0)
        return found

    def post(self, hwnd, message, key=0, detail=0):
        if not self.api.PostMessageW(hwnd, message, key, detail):
            raise ctypes.WinError(ctypes.get_last_error())

    def tray_action(self, index):
        time.sleep(1)  # production polling/notification loop must settle
        if index == 0:
            # The tray's native default action uses the same Open callback.
            for hwnd, name, visible in self.windows():
                if name.endswith("SystemTrayIcon"):
                    self.post(hwnd, 0x400 + 11, detail=0x202)
            return
        # A synthetic posted tray notification is not a physical shell click.
        # Grant foreground permission after injecting test input so Windows can
        # display the test-owned popup even after the GUI was hidden.
        self.api.mouse_event(1, 0, 0, 0, 0)
        self.api.AllowSetForegroundWindow(self.pid)
        # pystray's two hidden native windows share a class. Only its icon
        # window handles WM_NOTIFY; posting to both opens exactly one menu.
        for hwnd, name, visible in self.windows():
            if name.endswith("SystemTrayIcon"):
                self.post(hwnd, 0x400 + 11, detail=0x205)  # WM_NOTIFY / right-up
        menu = until(lambda: next((h for h, n, v in self.windows() if n == "#32768" and v), None))
        rect = wintypes.RECT()
        def geometry():
            handle = self.api.SendMessageW(menu, 0x1E1, 0, 0)  # MN_GETHMENU
            return handle and self.api.GetMenuItemRect(None, handle, index, ctypes.byref(rect))
        until(geometry, seconds=3)
        point = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        previous = wintypes.POINT()
        self.api.GetCursorPos(ctypes.byref(previous))
        try:
            self.api.SetCursorPos(point.x, point.y)
            time.sleep(.1)
            self.api.mouse_event(2, 0, 0, 0, 0)
            self.api.mouse_event(4, 0, 0, 0, 0)
            time.sleep(.1)
        finally:
            self.api.SetCursorPos(previous.x, previous.y)


def gui_smoke(exe, folder, settings, env, automatic_tools=False):
    profile = Path(env["APPDATA"]) / "PocketCinema"
    save_settings(settings, profile)
    expected = (profile / "config.json").read_bytes()
    process = subprocess.Popen([str(exe)], cwd=folder, env=env)
    native = NativeWindows(process.pid)
    try:
        window = until(lambda: next((h for h, n, v in native.windows() if n == "TkTopLevel" and v), None))
        until(lambda: len([1 for h, n, v in native.windows() if n.endswith("SystemTrayIcon")]) == 2)
        assert not any(n == "ConsoleWindowClass" for h, n, v in native.windows())
        native.tray_action(2)  # Start
        payload = until(lambda: status(settings.listen_port))
        assert payload["discovery"]["name"] == settings.server_name
        assert payload["media_preflight"] == bool(settings.ffprobe_path or automatic_tools)
        assert payload["transcodes"]["available"] == bool(settings.ffmpeg_path or automatic_tools)
        assert not payload["stremio_service"]["reachable"]
        native.post(window, 0x10)  # WM_CLOSE: production X handler
        until(lambda: not native.api.IsWindowVisible(window))
        assert status(settings.listen_port)
        native.tray_action(0)
        until(lambda: native.api.IsWindowVisible(window))
        duplicate = subprocess.Popen([str(exe)], cwd=folder, env=env)
        assert duplicate.wait(timeout=10) == 0
        assert len([1 for h, n, v in native.windows() if n == "TkTopLevel" and v]) == 1
        native.tray_action(2)  # Stop
        until(lambda: not status(settings.listen_port))
        time.sleep(1)  # next production menu-state poll
        native.tray_action(2)  # Start
        until(lambda: status(settings.listen_port))
        until(lambda: (status(settings.listen_port) or {}).get("uptime_seconds", 0) >= 3)
        old_children = native.child_handles()
        assert len(old_children) == 1
        time.sleep(1)  # allow the post-health Tk/menu state update to finish
        age = status(settings.listen_port)["uptime_seconds"]
        native.tray_action(1)  # Restart
        until(lambda: (value := status(settings.listen_port)) and value["uptime_seconds"] < age)
        native.wait_children(old_children)
        native.post(window, 0x10)
        until(lambda: not native.api.IsWindowVisible(window))
        owned = native.child_handles()
        assert len(owned) == 1
        native.tray_action(3)  # explicit production Quit
        assert process.wait(timeout=15) == 0
        native.wait_children(owned)
        assert not status(settings.listen_port)
        assert not native.windows()
        assert (profile / "config.json").read_bytes() == expected
    finally:
        if process.poll() is None:
            # Only this test-owned handle, never an image-name/process search.
            owned = native.child_handles()
            process.terminate()
            process.wait(timeout=10)
            native.wait_children(owned)
    # Restart application with the same per-user profile; no settings migration.
    again = subprocess.Popen([str(exe)], cwd=folder, env=env)
    native = NativeWindows(again.pid)
    try:
        until(lambda: any(n.endswith("SystemTrayIcon") for h, n, v in native.windows()))
        native.tray_action(3)
        assert again.wait(timeout=15) == 0
        assert (profile / "config.json").read_bytes() == expected
        assert load_settings(profile) == settings
    finally:
        if again.poll() is None:
            again.terminate()
            again.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=ROOT / ".tmp/windows-package-v1.0.0/dist/PocketCinema Server/PocketCinema Server.exe")
    parser.add_argument("--gui", action="store_true", help="Also exercise native GUI/tray on the interactive desktop")
    parser.add_argument("--archive", type=Path, help="Extract the built ZIP outside the repository and test that copy")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    exe = args.exe.resolve()
    tools = {name: detect_tool(name) for name in ("ffmpeg", "ffprobe")}
    with tempfile.TemporaryDirectory(prefix="PocketCinema packaged smoke ") as temporary:
        folder = Path(temporary)
        if args.archive:
            with zipfile.ZipFile(args.archive) as archive:
                for name in archive.namelist():
                    assert (folder / name).resolve().is_relative_to(folder.resolve())
                archive.extractall(folder)
            exe = folder / "PocketCinema Server" / "PocketCinema Server.exe"
        assert exe.is_file(), "Build the package first"
        unowned = subprocess.run([str(exe), "--server-child"], cwd=folder,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, timeout=10)
        assert unowned.returncode == 2, "A child without owning pipes was accepted"
        def artifact_hashes():
            return {p.relative_to(exe.parent).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in exe.parent.rglob("*") if p.is_file()}
        before = artifact_hashes()
        env = dict(os.environ)
        for key in list(env):
            if key.upper().startswith(("PYTHON", "POCKETCINEMA_", "POCKETSTREMIO_")):
                env.pop(key)
        system = Path(os.environ["SystemRoot"]) / "System32"
        env.update(PATH=os.pathsep.join((str(system), str(system / "WindowsPowerShell/v1.0"))),
                   LOCALAPPDATA=str(folder / "local"), APPDATA=str(folder / "roaming"))
        settings = DesktopSettings(server_name="Packaged smoke", listen_mode="custom", advertised_mode="manual",
                                   listen_port=free_port(), network_name="Smoke",
                                   stremio_service_url=f"http://127.0.0.1:{free_port()}")
        # Exercise the actual frozen role through the unchanged owning controller.
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys, "frozen", True, create=True):
            manager = PCServerLifecycle(folder / "owned", python_executable=str(exe))
            try:
                first = manager.start(settings, timeout=15)
                assert first.state == "Running", manager.logs
                payload = status(settings.listen_port)
                assert not payload["media_preflight"] and not payload["transcodes"]["available"]
                assert not payload["stremio_service"]["reachable"]
                child = manager._process
                assert not NativeWindows(child.pid).windows(), "Child created a GUI/console/tray"
                assert manager.logs, "Windowed child log pipe was lost"
                manager.stop()
                assert child.returncode == 0, "Stop used termination fallback instead of graceful pipe shutdown"
                assert not status(settings.listen_port)
                assert manager.start(settings, timeout=15).state == "Running"
                child = manager._process
                child.stdin.close()  # owner disappeared: EOF must cleanly stop
                assert child.wait(timeout=10) == 0
                assert manager.status().state == "Error"
                manager.stop()
                with socket.socket() as occupied:
                    occupied.bind(("127.0.0.1", 0))
                    result = manager.start(replace(settings, listen_port=occupied.getsockname()[1]), timeout=4)
                    assert result.state == "Error"
                    assert occupied.fileno() >= 0
                for name, tool in tools.items():
                    if not tool.available:
                        raise AssertionError(f"Available/manual {name} check needs an existing external installation")
                manual = replace(settings, ffmpeg_path=tools["ffmpeg"].path, ffprobe_path=tools["ffprobe"].path)
                assert manager.start(manual, timeout=15).state == "Running", manager.logs
                payload = status(settings.listen_port)
                assert payload["media_preflight"] and payload["transcodes"]["available"]
                child = manager._process
                manager.stop()
                assert child.returncode == 0
            finally:
                manager.stop()
        if args.gui:
            gui_smoke(exe, folder, settings, env)
            gui_smoke(exe, folder, manual, env)
            normal_env = dict(env, LOCALAPPDATA=os.environ.get("LOCALAPPDATA", ""))
            if all(tool.source == "Stremio runtime" for tool in tools.values()):
                gui_smoke(exe, folder, settings, normal_env, automatic_tools=True)
            else:
                # PATH fallback is explicit here, not an accidental dependence
                # on arbitrary developer PATH entries.
                normal_env["PATH"] += os.pathsep + os.pathsep.join(
                    sorted({str(Path(tool.path).parent) for tool in tools.values()}))
                gui_smoke(exe, folder, settings, normal_env, automatic_tools=True)
        assert artifact_hashes() == before, "Packaged runtime wrote inside its application directory"
    print("PASS: frozen child roles, log/shutdown pipes, EOF, restart, occupied port, external/manual/missing tools; "
          + ("native GUI/tray actions, same-window restore, duplicate launch, Quit and settings persistence" if args.gui else "GUI not requested"))


if __name__ == "__main__":
    main()
