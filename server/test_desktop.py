import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

from server.desktop.capabilities import detect_tool, probe_stremio_service
from server.desktop.config import (
    ConfigurationError,
    DesktopSettings,
    load_settings,
    save_settings,
    user_data_root,
    validate_settings,
)
from server.desktop.lifecycle import PCServerLifecycle, sanitize_log_line


class SettingsTests(unittest.TestCase):
    def test_defaults_and_platform_roots(self):
        self.assertEqual(DesktopSettings().listen_port, 8755)
        self.assertEqual(DesktopSettings().stremio_service_url, "http://127.0.0.1:11470")
        self.assertEqual(str(user_data_root("darwin", {})), str(Path.home() / "Library" / "Application Support" / "PocketCinema"))
        self.assertEqual(str(user_data_root("win32", {"APPDATA": "C:/Users/Test/AppData/Roaming"})), "C:/Users/Test/AppData/Roaming/PocketCinema")

    def test_settings_are_atomic_and_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            saved = save_settings(DesktopSettings(server_name="Living Room PCServer"), temporary)
            self.assertEqual(saved.server_name, "Living Room PCServer")
            self.assertEqual(load_settings(temporary).server_name, "Living Room PCServer")
            self.assertEqual(json.loads((Path(temporary) / "config.json").read_text())["schema_version"], 1)

    def test_invalid_settings_are_rejected(self):
        for kwargs in (
            {"listen_port": 0},
            {"listen_port": 8754},
            {"listen_address": "not an address"},
            {"advertised_address": "0.0.0.0"},
            {"stremio_service_url": "https://example.test"},
            {"stremio_service_url": "http://user:password@example.test:11470"},
            {"stremio_service_url": "http://example.test:99999"},
            {"ffmpeg_path": "/missing/ffmpeg"},
        ):
            with self.assertRaises(ConfigurationError, msg=str(kwargs)):
                validate_settings(DesktopSettings(**kwargs))


class StremioHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/settings":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")
            return
        self.send_error(404)

    def log_message(self, format, *args):
        pass


class CapabilityTests(unittest.TestCase):
    def test_tool_detection_for_manual_missing_path(self):
        status = detect_tool("definitely-not-pocketcinema-tool", "/missing/tool")
        self.assertFalse(status.available)
        self.assertEqual(status.source, "manual")

    def test_stremio_reachable_and_unreachable_status(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), StremioHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status = probe_stremio_service(f"http://127.0.0.1:{server.server_port}")
            self.assertTrue(status.reachable)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        status = probe_stremio_service("http://127.0.0.1:1", timeout=0.1)
        self.assertTrue(status.configured)
        self.assertFalse(status.reachable)
        self.assertIn("currently unreachable", status.message)


class LifecycleTests(unittest.TestCase):
    def free_port(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def test_owned_server_starts_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = DesktopSettings(listen_port=self.free_port())
            manager = PCServerLifecycle(temporary, python_executable=sys.executable)
            started = manager.start(settings)
            self.assertEqual(started.state, "Running", manager.logs)
            self.assertIsNotNone(started.pid)
            stopped = manager.stop()
            self.assertEqual(stopped.state, "Stopped")

    def test_unexpected_owned_child_exit_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = PCServerLifecycle(
                temporary,
                command_factory=lambda settings, command: [sys.executable, "-c", "import sys; sys.exit(3)"],
            )
            result = manager.start(DesktopSettings(listen_port=self.free_port()), timeout=1)
            self.assertEqual(result.state, "Error")
            self.assertIn("could not start", result.message)
            self.assertEqual(manager.stop().state, "Stopped")

    def test_occupied_port_is_not_taken_over(self):
        occupied = socket.socket()
        occupied.bind(("127.0.0.1", 0))
        try:
            with tempfile.TemporaryDirectory() as temporary:
                manager = PCServerLifecycle(temporary, python_executable=sys.executable)
                result = manager.start(DesktopSettings(listen_port=occupied.getsockname()[1]), timeout=2)
                self.assertEqual(result.state, "Error")
                self.assertTrue(occupied.fileno() >= 0)
        finally:
            occupied.close()

    def test_log_sanitization_does_not_expose_url(self):
        self.assertEqual(sanitize_log_line("failure https://user:secret@example.test/path?token=abc"), "failure <URL>")


if __name__ == "__main__":
    unittest.main()
