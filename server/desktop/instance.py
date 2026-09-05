"""Per-user Windows controller instance and restore signal; no process scanning."""
import ctypes
from ctypes import wintypes
import hashlib


class WindowsInstance:
    def __init__(self, data_root):
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateEventW.restype = wintypes.HANDLE
        kernel.SetEvent.argtypes = [wintypes.HANDLE]
        kernel.SetEvent.restype = wintypes.BOOL
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        self.kernel = kernel
        key = hashlib.sha256(str(data_root.resolve()).casefold().encode()).hexdigest()[:24]
        name = "Local\\PocketCinemaServer-" + key
        self.event = kernel.CreateEventW(None, False, False, name + "-open")
        if not self.event:
            raise ctypes.WinError(ctypes.get_last_error())
        self.mutex = kernel.CreateMutexW(None, False, name)
        error = ctypes.get_last_error()
        if not self.mutex:
            kernel.CloseHandle(self.event)
            raise ctypes.WinError(error)
        self.primary = error != 183  # ERROR_ALREADY_EXISTS
        if not self.primary:
            kernel.SetEvent(self.event)

    def restore_requested(self):
        return self.kernel.WaitForSingleObject(self.event, 0) == 0

    def close(self):
        for handle in (self.event, self.mutex):
            self.kernel.CloseHandle(handle)
