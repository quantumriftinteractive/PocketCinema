import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from server.desktop.capabilities import (
    ServiceStatus,
    ToolStatus,
    device_endpoints,
    detect_tool,
    host_interface_addresses,
    preferred_local_address,
    probe_stremio_service,
)
from server.desktop.gui import PocketCinemaDesktop, connection_summary
from server.desktop.config import (
    ConfigurationError,
    DeviceEndpoint,
    DesktopSettings,
    derive_device_endpoints,
    load_settings,
    pocketcinema_url,
    resolve_network_settings,
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
        expected_windows_root = str(Path("C:/Users/Test/AppData/Roaming") / "PocketCinema")
        self.assertEqual(
            str(user_data_root("win32", {"APPDATA": "C:/Users/Test/AppData/Roaming"})),
            expected_windows_root,
        )

    def test_settings_are_atomic_and_persisted(self):
        with tempfile.TemporaryDirectory() as temporary:
            saved = save_settings(DesktopSettings(server_name="Living Room PCServer"), temporary)
            self.assertEqual(saved.server_name, "Living Room PCServer")
            self.assertEqual(load_settings(temporary).server_name, "Living Room PCServer")
            self.assertEqual(json.loads((Path(temporary) / "config.json").read_text())["schema_version"], 2)

    def test_new_profile_automatically_derives_a_local_network_address(self):
        effective = resolve_network_settings(DesktopSettings(), "192.0.2.44")
        self.assertEqual(effective.listen_mode, "automatic")
        self.assertEqual(effective.listen_address, "192.0.2.44")
        self.assertEqual(effective.advertised_address, "192.0.2.44")
        self.assertEqual(pocketcinema_url(effective.advertised_address, 8755), "http://192.0.2.44:8755")

    def test_all_interfaces_keeps_a_device_facing_address(self):
        effective = resolve_network_settings(
            DesktopSettings(listen_mode="all_interfaces"), "192.0.2.44"
        )
        self.assertEqual(effective.listen_address, "0.0.0.0")
        self.assertEqual(effective.advertised_address, "192.0.2.44")

    def test_all_interfaces_exposes_local_and_remote_routes(self):
        endpoints = derive_device_endpoints(
            DesktopSettings(listen_mode="all_interfaces"),
            (
                DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
                DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun4"),
            ),
        )
        self.assertEqual(
            [endpoint.address for endpoint in endpoints], ["192.0.2.44", "100.64.10.20"]
        )

    def test_automatic_uses_only_local_routes_when_remote_is_available(self):
        effective = resolve_network_settings(DesktopSettings(), "192.0.2.44")
        self.assertEqual(effective.listen_address, "192.0.2.44")
        self.assertEqual(effective.network_name, "Local network")
        endpoints = derive_device_endpoints(
            effective,
            (
                DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
                DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun4"),
            ),
        )
        self.assertEqual([endpoint.address for endpoint in endpoints], ["192.0.2.44"])

    def test_all_interfaces_omits_remote_when_no_remote_route_exists(self):
        endpoints = derive_device_endpoints(
            DesktopSettings(listen_mode="all_interfaces"),
            (DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),),
        )
        self.assertEqual([endpoint.address for endpoint in endpoints], ["192.0.2.44"])

    def test_specific_bind_exposes_only_its_matching_route(self):
        settings = DesktopSettings(listen_mode="automatic", listen_address="192.0.2.44")
        endpoints = derive_device_endpoints(
            settings,
            (
                DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
                DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun4"),
            ),
        )
        self.assertEqual([endpoint.address for endpoint in endpoints], ["192.0.2.44"])

    def test_manual_address_override_remains_single_compatible_route(self):
        settings = DesktopSettings(advertised_mode="manual", advertised_address="remote.example")
        endpoints = derive_device_endpoints(settings, (DeviceEndpoint("Local", "192.0.2.44"),))
        self.assertEqual(endpoints, (DeviceEndpoint("Custom", "remote.example", "manual"),))

    def test_custom_mode_uses_its_explicit_bind_address(self):
        settings = DesktopSettings(listen_mode="custom", listen_address="192.0.2.45")
        endpoints = derive_device_endpoints(
            settings,
            (DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),),
        )
        self.assertEqual(endpoints, (DeviceEndpoint("Custom", "192.0.2.45", "manual"),))

    def test_route_urls_refresh_for_port_and_custom_address_changes(self):
        records = (
            DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
            DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun4"),
        )
        automatic = resolve_network_settings(DesktopSettings(listen_port=8755), "192.0.2.44")
        self.assertEqual(
            [pocketcinema_url(endpoint.address, automatic.listen_port) for endpoint in derive_device_endpoints(automatic, records)],
            ["http://192.0.2.44:8755"],
        )
        all_interfaces = DesktopSettings(listen_mode="all_interfaces", listen_port=8757)
        self.assertEqual(
            [pocketcinema_url(endpoint.address, all_interfaces.listen_port) for endpoint in derive_device_endpoints(all_interfaces, records)],
            ["http://192.0.2.44:8757", "http://100.64.10.20:8757"],
        )
        custom = DesktopSettings(listen_mode="custom", listen_address="192.0.2.45", listen_port=8760)
        self.assertEqual(
            [pocketcinema_url(endpoint.address, custom.listen_port) for endpoint in derive_device_endpoints(custom, records)],
            ["http://192.0.2.45:8760"],
        )

    def test_detected_routes_filter_loopback_link_local_and_wildcard(self):
        endpoints = derive_device_endpoints(
            DesktopSettings(listen_mode="all_interfaces"),
            (
                DeviceEndpoint("Loopback", "127.0.0.1", "local", "lo0"),
                DeviceEndpoint("Link local", "169.254.1.2", "local", "en0"),
                DeviceEndpoint("Wildcard", "0.0.0.0", "local"),
                DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
            ),
        )
        self.assertEqual([endpoint.address for endpoint in endpoints], ["192.0.2.44"])

    def test_custom_and_manual_address_remain_available(self):
        settings = DesktopSettings(
            listen_mode="custom",
            listen_address="192.0.2.45",
            advertised_mode="manual",
            advertised_address="example.test",
            network_name="Remote network",
        )
        effective = resolve_network_settings(settings, "192.0.2.44")
        self.assertEqual(effective.listen_address, "192.0.2.45")
        self.assertEqual(effective.advertised_address, "example.test")
        self.assertEqual(effective.network_name, "Remote network")

    def test_version_one_settings_remain_manual(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "config.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "server_name": "Existing PCServer",
                        "listen_address": "192.0.2.45",
                        "listen_port": 8757,
                        "advertised_address": "192.0.2.46",
                        "network_name": "Existing network",
                        "stremio_service_url": "http://127.0.0.1:11470",
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_settings(temporary)
        self.assertEqual(loaded.listen_mode, "custom")
        self.assertEqual(loaded.advertised_mode, "manual")
        self.assertEqual(loaded.listen_address, "192.0.2.45")

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
    def test_macos_interface_records_keep_local_and_tailnet_routes_distinct(self):
        records = host_interface_addresses(
            "darwin",
            """en0: flags=8863<UP,BROADCAST,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tinet 192.0.2.44 netmask 0xffffff00 broadcast 192.0.2.255
\tstatus: active
utun4: flags=8051<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1280
\tinet 100.64.10.20 --> 100.64.10.20 netmask 0xffffffff
utun5: flags=8010<POINTOPOINT,MULTICAST> mtu 1280
\tinet 100.90.1.2 --> 100.90.1.2 netmask 0xffffffff
""",
        )
        self.assertEqual(records, (("en0", "192.0.2.44"), ("utun4", "100.64.10.20")))
        endpoints = device_endpoints(records)
        self.assertEqual([(item.label, item.address) for item in endpoints], [
            ("Local network", "192.0.2.44"),
            ("Tailscale / Remote", "100.64.10.20"),
        ])

    def test_tailscale_route_is_absent_without_a_detected_tunnel(self):
        endpoints = device_endpoints((("en0", "192.0.2.44"),))
        self.assertEqual(
            [(item.label, item.address) for item in endpoints], [("Local network", "192.0.2.44")]
        )

    def test_windows_records_keep_lan_and_tailnet_routes_distinct(self):
        records = host_interface_addresses(
            "win32",
            windows_output='''[
                {"interface":"Tailscale","address":"100.85.171.67","virtual":true,"hardware":false},
                {"interface":"Gaming Ethernet","address":"192.168.0.185","virtual":false,"hardware":true},
                {"interface":"vEthernet (WSL)","address":"172.29.80.1","virtual":true,"hardware":false},
                {"interface":"Tailscale","address":"fd7a:115c:a1e0:d201::ab43","virtual":true,"hardware":false}
            ]''',
        )
        self.assertEqual(records, (
            ("Tailscale", "100.85.171.67"),
            ("Gaming Ethernet", "192.168.0.185"),
            ("Tailscale", "fd7a:115c:a1e0:d201::ab43"),
        ))
        endpoints = device_endpoints(records)
        self.assertEqual([(item.label, item.address) for item in endpoints], [
            ("Tailscale / Remote", "100.85.171.67"),
            ("Local network", "192.168.0.185"),
            ("Tailscale / Remote", "fd7a:115c:a1e0:d201::ab43"),
        ])

    def test_preferred_local_address_skips_loopback(self):
        self.assertEqual(
            preferred_local_address(
                [
                    ("Loopback", "127.0.0.1"),
                    ("Link-local", "fe80::1"),
                    ("Host", "192.0.2.44"),
                ]
            ),
            "192.0.2.44",
        )
    def test_tool_detection_for_manual_missing_path(self):
        status = detect_tool("definitely-not-pocketcinema-tool", "/missing/tool")
        self.assertFalse(status.available)
        self.assertEqual(status.source, "manual")

    def test_windows_tool_detection_uses_installed_stremio_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "Programs" / "LNV" / "Stremio-4"
            runtime.mkdir(parents=True)
            tool = runtime / "ffprobe.exe"
            tool.write_bytes(b"test")
            tool.chmod(0o700)
            status = detect_tool(
                "ffprobe", platform="win32", environ={"LOCALAPPDATA": temporary}
            )
        self.assertTrue(status.available)
        self.assertEqual(status.path, str(tool))
        self.assertEqual(status.source, "Stremio runtime")

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


class DesktopServiceCheckTests(unittest.TestCase):
    def test_connection_summary_is_concise(self):
        self.assertEqual(connection_summary(0), "None available")
        self.assertEqual(connection_summary(1), "1 available")
        self.assertEqual(connection_summary(2), "2 available")

    def test_stopped_desktop_refreshes_rows_for_mode_port_and_custom_address(self):
        class Root:
            @staticmethod
            def after(_delay, callback):
                callback()

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        class Value:
            def __init__(self, value=""):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        routes = (
            DeviceEndpoint("Local network", "192.0.2.44", "local", "en0"),
            DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun4"),
        )
        desktop = object.__new__(PocketCinemaDesktop)
        desktop.values = {
            key: Value(str(value))
            for key, value in vars(DesktopSettings()).items()
            if key != "schema_version"
        }
        desktop.listen_choice = Value("Automatic / Local network")
        desktop.device_url = Value()
        desktop.listen_detail = Value()
        desktop.root = Root()
        desktop.workers = mock.Mock()
        desktop.workers.start.side_effect = lambda target: target()
        desktop.workers.post.side_effect = lambda callback: callback()
        desktop._effective_settings = None
        desktop._render_connections = mock.Mock()
        with mock.patch("server.desktop.gui.device_endpoints", return_value=routes), mock.patch(
            "server.desktop.gui.threading.Thread", ImmediateThread
        ):
            desktop.refresh_network_summary()
            self.assertEqual(
                desktop._render_connections.call_args.args[0],
                [("Local network", "http://192.0.2.44:8755")],
            )
            self.assertEqual(desktop.device_url.get(), "1 available")

            desktop.listen_choice.set("All interfaces")
            desktop.refresh_network_summary()
            self.assertEqual(
                desktop._render_connections.call_args.args[0],
                [
                    ("Local network", "http://192.0.2.44:8755"),
                    ("Tailscale / Remote", "http://100.64.10.20:8755"),
                ],
            )

            desktop.listen_choice.set("Custom address")
            desktop.values["listen_address"].set("192.0.2.45")
            desktop.values["listen_port"].set("8760")
            desktop._on_route_setting_changed()
            self.assertEqual(
                desktop._render_connections.call_args.args[0],
                [("Custom", "http://192.0.2.45:8760")],
            )

    def test_explicit_service_check_shows_current_unreachable_result(self):
        class Value:
            def __init__(self, value=""):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        class Root:
            @staticmethod
            def after(_delay, callback):
                callback()

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        desktop = object.__new__(PocketCinemaDesktop)
        desktop.values = {"stremio_service_url": Value("http://192.0.2.55:11470")}
        desktop.service_state = Value()
        desktop.root = Root()
        desktop.workers = mock.Mock()
        desktop.workers.start.side_effect = lambda target: target()
        desktop.workers.post.side_effect = lambda callback: callback()
        unavailable = ServiceStatus(
            True, False, "Configured Stremio Service is currently unreachable from this machine."
        )
        with mock.patch("server.desktop.gui.probe_stremio_service", return_value=unavailable), mock.patch(
            "server.desktop.gui.threading.Thread", ImmediateThread
        ):
            desktop.check_service()
        self.assertEqual(desktop.service_state.get(), "Unreachable")


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
            self.assertEqual(started.listen_mode, settings.listen_mode)
            stopped = manager.stop()
            self.assertEqual(stopped.state, "Stopped")
            self.assertEqual(stopped.listen_mode, "")

    def test_child_receives_all_approved_device_hosts(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = PCServerLifecycle(
                temporary,
                python_executable=sys.executable,
                tool_detector=lambda name, manual: ToolStatus(
                    f"C:/Stremio/{name}.exe", True, "Stremio runtime"
                ),
            )
            command = manager._command(
                DesktopSettings(listen_port=self.free_port(), advertised_address="192.0.2.44"),
                ("192.0.2.44", "100.64.10.20"),
            )
        self.assertIn("--enable-matroska-subtitles", command)
        self.assertEqual(command[command.index("--ffmpeg") + 1], "C:/Stremio/ffmpeg.exe")
        self.assertEqual(command[command.index("--ffprobe") + 1], "C:/Stremio/ffprobe.exe")
        self.assertEqual(command.count("--device-host"), 1)
        self.assertEqual(command[command.index("--device-host") + 1], "100.64.10.20")

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
