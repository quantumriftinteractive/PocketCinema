"""Source/frozen process boundaries; no desktop widgets or network policy."""
import os
from pathlib import Path
import sys


_dll_directory = None


def frozen():
    return bool(getattr(sys, "frozen", False))


def child_command(executable):
    if frozen():
        return [executable, "--server-child"]
    return [executable, "-m", "server.desktop.server_child"]


def prepare_windows_runtime():
    """Keep bundled DLLs available to Python, not to external system tools."""
    global _dll_directory
    if frozen() and sys.platform == "win32":
        import ctypes
        _dll_directory = os.add_dll_directory(sys._MEIPASS)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())


def restore_child_pipes():
    """Windowed Python has no sys.std* objects; recover only parent-owned pipes.

    No console is allocated. A direct user invocation without the lifecycle
    pipe handles is rejected before the server can start.
    """
    if not frozen() or sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    handles = [kernel.GetStdHandle(value) for value in (-10, -11)]
    if any(not handle or kernel.GetFileType(handle) != 3 for handle in handles):
        raise RuntimeError("The server child requires its owning desktop's pipes.")
    stdin_fd = msvcrt.open_osfhandle(handles[0], os.O_RDONLY | os.O_BINARY)
    stdout_fd = msvcrt.open_osfhandle(handles[1], os.O_WRONLY | os.O_BINARY)
    sys.stdin = os.fdopen(stdin_fd, "r", encoding="utf-8", errors="replace")
    sys.stdout = os.fdopen(stdout_fd, "w", buffering=1, encoding="utf-8", errors="replace")
    sys.stderr = sys.stdout


def resource_root():
    return Path(__file__).resolve().parents[2]
