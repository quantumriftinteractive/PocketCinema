"""Focused tests for the running-state configuration lock."""
import unittest
from unittest import mock

from server.desktop.gui import PocketCinemaDesktop
from server.desktop.lifecycle import LifecycleStatus


class SettingsLockTests(unittest.TestCase):
    def desktop(self):
        desktop = object.__new__(PocketCinemaDesktop)
        desktop._busy = False
        desktop._closing = False
        desktop._advanced_dialog = None
        desktop.lifecycle = mock.Mock()
        desktop.tray = None
        desktop._close_advanced = mock.Mock()
        desktop.start_button = mock.Mock()
        desktop.stop_button = mock.Mock()
        desktop.restart_button = mock.Mock()
        desktop.server_name_entry = mock.Mock()
        desktop.listen_selector = mock.Mock()
        desktop.custom_listen_entry = mock.Mock()
        desktop.listen_port_entry = mock.Mock()
        desktop.stremio_service_url_entry = mock.Mock()
        desktop.advanced_button = mock.Mock()
        desktop.save_button = mock.Mock()
        desktop.running_notice = mock.Mock()
        return desktop

    def test_stopped_state_unlocks_configuration_and_hides_notice(self):
        desktop = self.desktop()
        desktop.update_actions("Stopped")
        for widget in (desktop.server_name_entry, desktop.custom_listen_entry,
                       desktop.listen_port_entry, desktop.stremio_service_url_entry,
                       desktop.advanced_button, desktop.save_button):
            self.assertEqual(widget.configure.call_args.kwargs["state"], "normal")
        self.assertEqual(desktop.listen_selector.configure.call_args.kwargs["state"], "readonly")
        desktop.running_notice.grid_remove.assert_called_once_with()
        desktop._close_advanced.assert_not_called()

    def test_running_state_locks_runtime_configuration_but_keeps_actions(self):
        desktop = self.desktop()
        desktop.update_actions("Running")
        for widget in (desktop.server_name_entry, desktop.listen_selector,
                       desktop.custom_listen_entry, desktop.listen_port_entry,
                       desktop.stremio_service_url_entry, desktop.advanced_button,
                       desktop.save_button):
            self.assertEqual(widget.configure.call_args.kwargs["state"], "disabled")
        self.assertEqual(desktop.stop_button.configure.call_args.kwargs["state"], "normal")
        self.assertEqual(desktop.restart_button.configure.call_args.kwargs["state"], "normal")
        desktop.running_notice.grid.assert_called_once_with()
        desktop._close_advanced.assert_called_once_with()

    def test_failed_or_unexpected_exit_hides_running_message(self):
        desktop = self.desktop()
        desktop.server_state = mock.Mock()
        desktop.server_detail = mock.Mock()
        desktop.refresh_network_summary = mock.Mock()
        desktop.update_actions = mock.Mock()
        desktop._restore_editable_settings = mock.Mock()
        desktop.show_lifecycle(LifecycleStatus("Error", "child exited", None, ""))
        desktop._restore_editable_settings.assert_called_once_with()
        desktop.update_actions.assert_called_once_with("Error")


if __name__ == "__main__":
    unittest.main()
