"""M23 route presentation, quiet helper processes, and actual-state hover text."""
import json
import subprocess
import sys
import unittest
from unittest import mock

from server.desktop import capabilities
from server.desktop.config import (
    DesktopSettings, DeviceEndpoint, derive_device_endpoints,
    presented_device_endpoints, resolve_network_settings,
)
from server.desktop.lifecycle import LifecycleStatus
from server.desktop.tray import WindowsTray, tray_title
from server import test_desktop_tray, transcoding


class RoutePresentationTests(unittest.TestCase):
    def routes(self):
        return capabilities.device_endpoints(capabilities.host_interface_addresses(
            "win32", windows_output=json.dumps([
                {"interface": "Ethernet", "address": "192.0.2.44", "hardware": True},
                {"interface": "Tailscale", "address": "fd7a:115c:a1e0::1234", "virtual": True},
                {"interface": "Tailscale", "address": "100.64.10.20", "virtual": True},
                {"interface": "vEthernet (WSL)", "address": "172.29.1.1", "virtual": True},
                {"interface": "Ethernet", "address": "0.0.0.0", "hardware": True},
            ]),
        ))

    def test_dual_stack_display_prefers_same_interface_ipv4_without_changing_routes(self):
        routes = self.routes()
        selected = derive_device_endpoints(DesktopSettings(listen_mode="all_interfaces"), routes)
        self.assertEqual([(row.address, row.kind) for row in presented_device_endpoints(selected)],
                         [("192.0.2.44", "local"), ("100.64.10.20", "remote")])
        self.assertEqual(len(selected), 3)  # The child still approves both Remote families.
        self.assertEqual(capabilities.preferred_local_address(routes), "192.0.2.44")
        effective = resolve_network_settings(DesktopSettings(listen_mode="all_interfaces"),
                                             capabilities.preferred_local_address(routes))
        self.assertEqual(effective.listen_address, "0.0.0.0")
        self.assertEqual(effective.advertised_address, "192.0.2.44")  # Discovery stays Local.

    def test_ipv6_only_and_different_interface_remote_are_retained(self):
        ipv6 = DeviceEndpoint("Tailscale / Remote", "fd7a:115c:a1e0::1234", "remote", "utun4")
        ipv4 = DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote", "utun5")
        self.assertEqual(presented_device_endpoints((ipv6,)), (ipv6,))
        self.assertEqual(presented_device_endpoints((ipv6, ipv4)), (ipv6, ipv4))

    def test_local_ipv6_custom_and_missing_identity_are_not_suppressed(self):
        routes = (
            DeviceEndpoint("Local network", "2001:db8::44", "local", "Ethernet"),
            DeviceEndpoint("Local network", "192.0.2.44", "local", "Ethernet"),
            DeviceEndpoint("Custom", "fd7a:115c:a1e0::1234", "manual"),
            DeviceEndpoint("Tailscale / Remote", "fd7a:115c:a1e0::2345", "remote"),
            DeviceEndpoint("Tailscale / Remote", "100.64.10.20", "remote"),
        )
        self.assertEqual(presented_device_endpoints(routes), routes)

    def test_unusable_ipv4_does_not_hide_ipv6_and_automatic_stays_local(self):
        ipv6 = DeviceEndpoint("Tailscale / Remote", "fd7a:115c:a1e0::1234", "remote", "Tailscale")
        wildcard = DeviceEndpoint("Tailscale / Remote", "0.0.0.0", "remote", "Tailscale")
        selected = derive_device_endpoints(DesktopSettings(listen_mode="all_interfaces"), (wildcard, ipv6))
        self.assertEqual(presented_device_endpoints(selected), (ipv6,))
        automatic = derive_device_endpoints(DesktopSettings(), self.routes())
        self.assertEqual([(row.address, row.kind) for row in presented_device_endpoints(automatic)],
                         [("192.0.2.44", "local")])


class QuietProcessTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows helper creation flags")
    def test_windows_interface_enumeration_is_no_console_with_output_capture(self):
        with mock.patch("server.desktop.capabilities.subprocess.run", return_value=mock.Mock(stdout="[]")) as run:
            self.assertEqual(capabilities._read_windows_interface_addresses(), "[]")
        self.assertEqual(run.call_args.args[0][0], "powershell.exe")
        self.assertEqual(run.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertFalse(run.call_args.kwargs["check"])

    @unittest.skipUnless(sys.platform == "win32", "Windows capability probe flags")
    def test_startup_ffmpeg_probe_is_no_console_with_both_streams_captured(self):
        with mock.patch("server.transcoding.subprocess.run", return_value=mock.Mock(returncode=0, stdout=b" ... subtitles filter")) as run:
            self.assertTrue(transcoding.supports_subtitle_burn_in("ffmpeg.exe"))
        self.assertEqual(run.call_args.args[0], ["ffmpeg.exe", "-hide_banner", "-filters"])
        self.assertEqual(run.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)
        self.assertEqual(run.call_args.kwargs["stdout"], subprocess.PIPE)
        self.assertEqual(run.call_args.kwargs["stderr"], subprocess.PIPE)
        self.assertEqual(run.call_args.kwargs["timeout"], 10)

    def test_non_windows_probe_keeps_default_creation_flags_and_failure_result(self):
        with mock.patch("server.transcoding.sys.platform", "darwin"), mock.patch(
            "server.transcoding.subprocess.run", return_value=mock.Mock(returncode=1, stdout=b"", stderr=b"failure")
        ) as run:
            self.assertFalse(transcoding.supports_subtitle_burn_in("ffmpeg"))
        self.assertEqual(run.call_args.kwargs["creationflags"], 0)


class TrayTooltipTests(unittest.TestCase):
    def desktop(self):
        desktop = test_desktop_tray.TrayLifecycleTests().desktop()
        api = mock.Mock()
        with mock.patch.dict(sys.modules, {"pystray": api, "PIL": mock.MagicMock()}), mock.patch(
            "server.desktop.tray.threading.Thread"
        ):
            desktop.tray = WindowsTray(lambda action: desktop.tray_action(action), desktop.tray_state,
                                      lambda: tray_title(desktop.lifecycle.status().state))
        desktop.tray._ready.set()
        desktop.tray.icon.title = api.Icon.call_args.args[2]
        desktop._start_with_settings = lambda settings: self.set_state(desktop, "Running")
        desktop.lifecycle.stop.side_effect = lambda: self.set_state(desktop, "Stopped")
        return desktop, api

    def set_state(self, desktop, state):
        status = LifecycleStatus(state, "", 123 if state == "Running" else None, "")
        desktop.lifecycle.status.return_value = status
        desktop.show_lifecycle(status)
        return status

    def test_only_actual_running_reports_started(self):
        self.assertEqual(tray_title("Running"), "PocketCinema Server - Started")
        for state in ("Stopped", "Error", "Starting", "Stopping"):
            self.assertEqual(tray_title(state), "PocketCinema Server - Stopped")

    def test_gui_and_tray_start_stop_restart_and_failed_restart_update_one_icon(self):
        for source in ("gui", "tray"):
            with self.subTest(source=source):
                desktop, api = self.desktop()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
                desktop.start() if source == "gui" else desktop.tray_action("toggle")
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started")
                desktop.stop() if source == "gui" else desktop.tray_action("toggle")
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
                desktop.start() if source == "gui" else desktop.tray_action("toggle")
                desktop.restart() if source == "gui" else desktop.tray_action("restart")
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started")
                desktop._start_with_settings = lambda settings: self.set_state(desktop, "Error")
                desktop.restart() if source == "gui" else desktop.tray_action("restart")
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
                api.Icon.assert_called_once()

    def test_tooltip_is_independent_of_last_action_and_survives_hide_restore(self):
        desktop, api = self.desktop()
        self.set_state(desktop, "Running")
        with mock.patch("server.desktop.gui.sys.platform", "win32"):
            desktop.close()
            desktop.tray_action("open")
        self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started")
        desktop.lifecycle.status.return_value = LifecycleStatus("Error", "exited", None, "")
        desktop.tray.update()
        self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
        desktop.server_state.set("Starting")  # A request cannot claim a live child.
        desktop.tray.update()
        self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
        api.Icon.assert_called_once()

    def test_busy_restart_poll_still_updates_tooltip_from_child_state(self):
        desktop, _ = self.desktop()
        desktop._busy = True
        desktop.lifecycle.logs = ()
        desktop._last_logs = ()
        for state, title in (("Starting", "Stopped"), ("Running", "Started"), ("Error", "Stopped")):
            desktop.lifecycle.status.return_value = LifecycleStatus(state, "", None, "")
            desktop.poll()
            self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - " + title)


if __name__ == "__main__":
    unittest.main()
