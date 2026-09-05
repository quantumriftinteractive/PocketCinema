"""Owned PCServer subprocess lifecycle; it never searches for other processes."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from .capabilities import detect_tool
from .config import DesktopSettings, address_is_assigned, validate_settings
from .runtime import child_command, frozen, resource_root


LOG_LIMIT = 160
URL_PATTERN = re.compile(r"https?://[^\s'\"]+", re.IGNORECASE)


@dataclass(frozen=True)
class LifecycleStatus:
    state: str
    message: str
    pid: int | None
    endpoint: str
    listen_mode: str = ""


def sanitize_log_line(value):
    return URL_PATTERN.sub("<URL>", str(value).replace("\x00", ""))[:600]


class PCServerLifecycle:
    def __init__(self, data_root, python_executable=None, command_factory=None, tool_detector=detect_tool):
        self.data_root = Path(data_root)
        self.python_executable = python_executable or sys.executable
        self.command_factory = command_factory
        self.tool_detector = tool_detector
        self._process = None
        self._reader = None
        self._logs = deque(maxlen=LOG_LIMIT)
        self._lock = threading.Lock()
        self._status = LifecycleStatus("Stopped", "PCServer is stopped.", None, "")

    @property
    def logs(self):
        with self._lock:
            return list(self._logs)

    def status(self):
        with self._lock:
            process, status = self._process, self._status
        if process is not None and process.poll() is not None and status.state not in {"Stopped", "Error"}:
            self._set_status("Error", "PCServer exited unexpectedly.")
        return self._status

    def _set_status(self, state, message, pid=None, endpoint="", listen_mode=""):
        with self._lock:
            if pid is None and self._process is not None:
                pid = self._process.pid
            self._status = LifecycleStatus(state, message, pid, endpoint, listen_mode)

    def _append_log(self, line):
        line = sanitize_log_line(line.strip())
        if line:
            with self._lock:
                self._logs.append(line)

    def _read_output(self, process):
        if process.stdout is not None:
            for line in process.stdout:
                self._append_log(line)

    def _command(self, settings, device_hosts=()):
        addon_port = self._available_loopback_port()
        ffmpeg = self.tool_detector("ffmpeg", settings.ffmpeg_path)
        ffprobe = self.tool_detector("ffprobe", settings.ffprobe_path)
        command = child_command(self.python_executable) + [
            "--host", settings.listen_address,
            "--port", str(settings.listen_port),
            "--public-host", settings.advertised_address,
            "--server-name", settings.server_name,
            "--network-name", settings.network_name,
            "--stremio-service-url", settings.stremio_service_url,
            "--ffmpeg", ffmpeg.path if ffmpeg.available else "",
            "--ffprobe", ffprobe.path if ffprobe.available else "",
            "--data-dir", str(self.data_root / "data"),
            "--stremio-account-config", str(self.data_root / "credentials" / "stremio_account.json"),
            "--stream-addons", str(self.data_root / "config" / "stream_addons.json"),
            "--open-media-addon-port", str(addon_port),
            # The established desktop-independent managers enable the bounded
            # selectable-Matroska path by default.  Keep the owned desktop
            # child at that startup parity without changing the core default.
            "--enable-matroska-subtitles",
        ]
        if frozen():
            command.extend(("--media-dir", str(self.data_root / "media"),
                            "--fixture-dir", str(self.data_root / "fixtures")))
        seen = {settings.advertised_address}
        for host in device_hosts:
            host = str(host).strip()
            if host and host not in seen:
                seen.add(host)
                command.extend(("--device-host", host))
        return self.command_factory(settings, command) if self.command_factory else command

    @staticmethod
    def _available_loopback_port():
        """Use a private loopback helper port without claiming a user setting."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]
        finally:
            sock.close()

    def _release_process(self, process):
        if process.stdin is not None:
            process.stdin.close()
        if self._reader is not None:
            self._reader.join(timeout=2)
            self._reader = None
        if process.stdout is not None:
            process.stdout.close()
        with self._lock:
            if self._process is process:
                self._process = None

    @staticmethod
    def _health(endpoint, timeout=0.5):
        try:
            with urllib.request.urlopen(endpoint + "/api/status", timeout=timeout) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError, urllib.error.HTTPError):
            return False

    def start(self, settings, device_hosts=(), timeout=8):
        settings = validate_settings(settings)
        if self.status().state in {"Starting", "Running"}:
            raise RuntimeError("PCServer is already owned by this desktop application")
        if self._process is not None:
            if self._process.poll() is None:
                raise RuntimeError("PCServer is still owned by this desktop application")
            self._release_process(self._process)
        if not address_is_assigned(settings.listen_address):
            self._set_status("Error", "Selected listen address is no longer assigned to this machine.")
            return self.status()
        self.data_root.mkdir(parents=True, exist_ok=True)
        health_host = "127.0.0.1" if settings.listen_address == "0.0.0.0" else settings.listen_address
        endpoint = f"http://{health_host}:{settings.listen_port}"
        self._logs.clear()
        self._set_status("Starting", "Starting owned PCServer process…", endpoint=endpoint)
        try:
            process = subprocess.Popen(
                self._command(settings, device_hosts), cwd=str(resource_root()),
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", start_new_session=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as exc:
            self._set_status("Error", f"Could not start PCServer: {exc}", endpoint=endpoint)
            return self.status()
        with self._lock:
            self._process = process
        self._reader = threading.Thread(target=self._read_output, args=(process,), daemon=True)
        self._reader.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                self._set_status("Error", "PCServer could not start; see sanitized log below.", endpoint=endpoint)
                self._release_process(process)
                return self.status()
            if self._health(endpoint):
                self._set_status("Running", "PCServer is running.", endpoint=endpoint,
                                 listen_mode=settings.listen_mode)
                return self.status()
            time.sleep(0.1)
        self.stop()
        self._set_status("Error", "PCServer did not become healthy before the startup timeout.", endpoint=endpoint)
        return self.status()

    def stop(self, timeout=5):
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            if process is not None:
                self._release_process(process)
            self._set_status("Stopped", "PCServer is stopped.", pid=None)
            return self.status()
        self._set_status("Stopping", "Stopping owned PCServer process…")
        try:
            process.stdin.write("stop\n")
            process.stdin.flush()
        except (OSError, ValueError):
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        self._release_process(process)
        self._set_status("Stopped", "PCServer is stopped.", pid=None)
        return self.status()
