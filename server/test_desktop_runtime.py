"""Focused source/frozen role and writable-path contract tests."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from server.desktop import runtime
from server.desktop.capabilities import ToolStatus
from server.desktop.config import DesktopSettings
from server.desktop.lifecycle import PCServerLifecycle
from server import pocketcinema_desktop


class RuntimeTests(unittest.TestCase):
    def test_source_command_retains_module_entry(self):
        with mock.patch.object(sys, "frozen", False, create=True):
            self.assertEqual(runtime.child_command("python"),
                             ["python", "-m", "server.desktop.server_child"])

    def test_frozen_command_preserves_config_and_private_writable_paths(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.object(sys, "frozen", True, create=True):
            manager = PCServerLifecycle(folder, python_executable="PocketCinema Server.exe",
                tool_detector=lambda name, manual: ToolStatus("", False, "missing"))
            command = manager._command(DesktopSettings(), ("192.0.2.5",))
            self.assertEqual(command[:2], ["PocketCinema Server.exe", "--server-child"])
            for flag, suffix in (("--media-dir", "media"), ("--fixture-dir", "fixtures"),
                                 ("--data-dir", "data")):
                self.assertEqual(Path(command[command.index(flag) + 1]), Path(folder) / suffix)
            self.assertIn("--enable-matroska-subtitles", command)
            self.assertIn("--device-host", command)
            self.assertEqual(command[command.index("--stremio-service-url") + 1], "http://127.0.0.1:11470")

    def test_child_dispatch_precedes_gui_and_removes_only_role_argument(self):
        with mock.patch.object(sys, "argv", ["app", "--server-child", "--port", "9876"]), \
             mock.patch.object(runtime, "prepare_windows_runtime"), \
             mock.patch.object(runtime, "restore_child_pipes") as pipes, \
             mock.patch("server.desktop.server_child.run") as child, \
             mock.patch("server.desktop.gui.main") as gui:
            self.assertEqual(pocketcinema_desktop.main(), 0)
            self.assertEqual(sys.argv, ["app", "--port", "9876"])
            pipes.assert_called_once_with()
            child.assert_called_once_with()
            gui.assert_not_called()

    def test_unowned_frozen_child_does_not_start(self):
        with mock.patch.object(sys, "argv", ["app", "--server-child"]), \
             mock.patch.object(runtime, "prepare_windows_runtime"), \
             mock.patch.object(runtime, "restore_child_pipes", side_effect=RuntimeError("No pipes")), \
             mock.patch("server.desktop.server_child.run") as child:
            self.assertEqual(pocketcinema_desktop.main(), 2)
            child.assert_not_called()

    def test_default_role_opens_existing_desktop_path(self):
        with mock.patch.object(sys, "argv", ["app"]), \
             mock.patch.object(runtime, "prepare_windows_runtime"), \
             mock.patch("server.desktop.gui.main") as gui:
            self.assertEqual(pocketcinema_desktop.main(), 0)
            gui.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
