"""Focused X notification and active-listen-mode hover acceptance checks."""
import unittest
from unittest import mock

from server import test_desktop_tray
from server.desktop.config import DesktopSettings
from server.desktop.lifecycle import LifecycleStatus
from server.desktop.tray import WindowsTray


class NotificationModeTests(unittest.TestCase):
    def desktop(self):
        desktop = test_desktop_tray.TrayLifecycleTests().desktop()
        api = mock.Mock()
        with mock.patch.dict("sys.modules", {"pystray": api, "PIL": mock.MagicMock()}), mock.patch(
            "server.desktop.tray.threading.Thread"
        ):
            desktop.tray = WindowsTray(desktop.tray_action, desktop.tray_state, desktop.tray_title)
        desktop.tray._ready.set()
        desktop.tray.icon.title = api.Icon.call_args.args[2]

        def started(settings):
            status = LifecycleStatus("Running", "", 123, "", settings.listen_mode)
            desktop.lifecycle.status.return_value = status
            desktop.show_lifecycle(status)

        def stopped():
            status = LifecycleStatus("Stopped", "", None, "")
            desktop.lifecycle.status.return_value = status
            return status

        desktop._start_with_settings = started
        desktop.lifecycle.stop.side_effect = stopped
        return desktop, api

    def test_x_sends_one_native_notification_without_changing_server_state(self):
        desktop, api = self.desktop()
        desktop.start()
        before = desktop.lifecycle.status()
        with mock.patch("server.desktop.gui.sys.platform", "win32"):
            desktop.close()
        desktop.root.withdraw.assert_called_once()
        desktop.tray.icon.notify.assert_called_once_with(
            "PocketCinema Server is still running in the system tray.", "PocketCinema Server"
        )
        self.assertEqual(desktop.lifecycle.status(), before)
        desktop.lifecycle.stop.assert_not_called()
        api.Icon.assert_called_once()

    def test_startup_non_x_hide_restore_actions_and_quit_never_notify(self):
        desktop, api = self.desktop()
        desktop.tray.stop = mock.Mock()
        desktop.root.withdraw()  # Startup/programmatic hide bypasses X handling.
        desktop.show()
        desktop.tray_action("open")
        desktop.tray_action("toggle")
        desktop.tray_action("restart")
        desktop.tray_action("toggle")
        desktop.tray_action("quit")
        desktop.close()  # Closing callback during shutdown must also be silent.
        desktop.tray.icon.notify.assert_not_called()
        api.Icon.assert_called_once()

    def test_notification_failure_does_not_break_hide_or_tray(self):
        desktop, _ = self.desktop()
        desktop.tray.icon.notify.side_effect = OSError("notification unavailable")
        with mock.patch("server.desktop.gui.sys.platform", "win32"):
            desktop.close()
        desktop.root.withdraw.assert_called_once()
        self.assertFalse(desktop.tray.error)
        desktop.lifecycle.stop.assert_not_called()
        desktop.show()
        desktop.root.deiconify.assert_called_once()

    def test_unsupported_notifications_do_not_invoke_native_api(self):
        desktop, _ = self.desktop()
        desktop.tray.icon.HAS_NOTIFICATION = False
        self.assertFalse(desktop.tray.notify_hidden())
        desktop.tray.icon.notify.assert_not_called()

    def test_running_labels_use_started_mode_and_stopped_remains_simple(self):
        for mode, label in (("automatic", "Automatic / Local network"),
                            ("all_interfaces", "All interfaces"), ("custom", "Custom")):
            with self.subTest(mode=mode):
                desktop, api = self.desktop()
                desktop.settings.return_value = DesktopSettings(listen_mode=mode)
                desktop.tray.update()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
                desktop.start()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started - " + label)
                desktop.settings.return_value = DesktopSettings(listen_mode="all_interfaces")
                desktop._effective_settings = None  # Saving draft settings cannot relabel the live child.
                desktop.tray.update()
                desktop.show()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started - " + label)
                desktop.stop()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")
                api.Icon.assert_called_once()

    def test_restart_adopts_new_active_mode_for_gui_and_tray_actions(self):
        for source in ("gui", "tray"):
            with self.subTest(source=source):
                desktop, api = self.desktop()
                desktop.start() if source == "gui" else desktop.tray_action("toggle")
                desktop.settings.return_value = DesktopSettings(listen_mode="all_interfaces")
                desktop.restart() if source == "gui" else desktop.tray_action("restart")
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Started - All interfaces")
                desktop.tray.icon.notify.assert_not_called()
                api.Icon.assert_called_once()

    def test_failed_start_and_restart_report_stopped_without_stale_mode(self):
        for restart in (False, True):
            with self.subTest(restart=restart):
                desktop, _ = self.desktop()
                if restart:
                    desktop.start()

                def fail(settings):
                    status = LifecycleStatus("Error", "failed", None, "")
                    desktop.lifecycle.status.return_value = status
                    desktop.show_lifecycle(status)

                desktop._start_with_settings = fail
                desktop.restart() if restart else desktop.start()
                self.assertEqual(desktop.tray.icon.title, "PocketCinema Server - Stopped")


if __name__ == "__main__":
    unittest.main()
