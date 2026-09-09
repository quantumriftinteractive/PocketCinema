"""Focused desktop visibility, tray dispatch, and shutdown regression tests."""
import socket
import sys
import tempfile
import threading
import unittest
from unittest import mock

from server.desktop.config import DesktopSettings
from server.desktop.gui import PocketCinemaDesktop
from server.desktop.lifecycle import LifecycleStatus, PCServerLifecycle
from server.desktop.tray import menu_state, WindowsTray
from server.desktop.workers import DesktopWorkers


class Value:
    def __init__(self, value=""):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class TrayLifecycleTests(unittest.TestCase):
    def desktop(self):
        desktop = object.__new__(PocketCinemaDesktop)
        desktop.root = mock.Mock()
        data_root = tempfile.TemporaryDirectory()
        self.addCleanup(data_root.cleanup)
        desktop.data_root = data_root.name
        desktop.instance = None
        desktop.lifecycle = mock.Mock()
        desktop.lifecycle.status.return_value = LifecycleStatus("Stopped", "", None, "")
        desktop._closing = desktop._busy = desktop._tray_failed = False
        desktop._quit_error = None
        desktop._operation_lock = threading.Lock()
        desktop._effective_settings = None
        desktop.workers = mock.Mock()
        desktop.workers.start.side_effect = lambda target: target()
        desktop.workers.post.side_effect = lambda callback: callback()
        desktop.workers.idle.return_value = True
        desktop.tray = mock.Mock(available=True)
        desktop.server_state, desktop.server_detail = Value(), Value()
        desktop.start_button, desktop.stop_button, desktop.restart_button = mock.Mock(), mock.Mock(), mock.Mock()
        desktop.settings = mock.Mock(return_value=DesktopSettings())
        desktop.refresh_network_summary = mock.Mock()
        return desktop

    def test_x_hides_without_touching_child_then_restores_same_window(self):
        desktop = self.desktop()
        with mock.patch("server.desktop.gui.sys.platform", "win32"), mock.patch("server.desktop.gui.tk.Tk") as constructor:
            desktop.close()
            desktop.tray_action("open")
            desktop.tray_action("open")
        desktop.root.withdraw.assert_called_once()
        self.assertEqual(desktop.root.deiconify.call_count, 2)
        self.assertEqual(desktop.root.focus_force.call_count, 2)
        constructor.assert_not_called()
        desktop.root.destroy.assert_not_called()
        desktop.lifecycle.stop.assert_not_called()
        self.assertFalse(desktop._closing)

    def test_unavailable_tray_keeps_window_accessible(self):
        desktop = self.desktop()
        desktop.tray.available = False
        with mock.patch("server.desktop.gui.sys.platform", "win32"), mock.patch("server.desktop.gui.messagebox.showerror"):
            desktop.close()
        desktop.root.withdraw.assert_not_called()
        desktop.lifecycle.stop.assert_not_called()

    def test_macos_window_close_uses_canonical_shutdown(self):
        desktop = self.desktop()
        with mock.patch("server.desktop.gui.sys.platform", "darwin"):
            desktop.close()
        desktop.root.withdraw.assert_not_called()
        desktop.lifecycle.stop.assert_called_once()
        self.assertTrue(desktop._closing)

    def test_menu_follows_live_state_and_disables_transitions(self):
        desktop = self.desktop()
        for state, expected in [("Stopped", ("Start server", True, False)),
                                ("Running", ("Stop server", True, True)),
                                ("Error", ("Start server", True, False)),
                                ("Starting", ("Stop server", False, False)),
                                ("Stopping", ("Stop server", False, False))]:
            desktop.lifecycle.status.return_value = LifecycleStatus(state, "", None, "")
            self.assertEqual(desktop.tray_state(), expected)
            desktop.update_actions(state)
            self.assertEqual(desktop.restart_button.configure.call_args.kwargs["state"],
                             "normal" if expected[2] else "disabled")
        self.assertEqual(menu_state("Running", busy=True), ("Stop server", False, False))
        self.assertFalse(menu_state("Stopped", closing=True)[1])

    def test_tray_actions_use_same_gui_operations(self):
        desktop = self.desktop()
        desktop.start, desktop.stop, desktop.restart = mock.Mock(), mock.Mock(), mock.Mock()
        desktop.tray_action("toggle")
        desktop.start.assert_called_once()
        desktop.lifecycle.status.return_value = LifecycleStatus("Running", "", 12, "")
        desktop.tray_action("toggle")
        desktop.tray_action("restart")
        desktop.stop.assert_called_once()
        desktop.restart.assert_called_once()
        desktop._busy = True
        desktop.tray_action("toggle")
        desktop.stop.assert_called_once()

    def test_restart_stops_owned_child_before_starting_once(self):
        desktop = self.desktop()
        desktop.lifecycle.status.return_value = LifecycleStatus("Running", "", 12, "")
        calls = []
        desktop.lifecycle.stop.side_effect = lambda: calls.append("stop")
        desktop._start_with_settings = lambda settings: calls.append("start")
        desktop.restart()
        self.assertEqual(calls, ["stop", "start"])

    def test_start_persists_the_current_route_before_launching_the_child(self):
        desktop = self.desktop()
        current = DesktopSettings(
            listen_mode="custom",
            listen_address="100.82.23.65",
            advertised_mode="manual",
            advertised_address="100.82.23.65",
        )
        desktop.settings.return_value = current
        desktop.data_root = "/test-data"
        desktop._start_with_settings = mock.Mock()
        with mock.patch("server.desktop.gui.save_settings", return_value=current) as save:
            desktop.start()
        save.assert_called_once_with(current, "/test-data")
        desktop._start_with_settings.assert_called_once_with(current)

    def test_busy_blocks_duplicate_start_and_quit_prevents_late_start(self):
        desktop = self.desktop()
        tasks = []
        desktop.workers.start.side_effect = tasks.append
        desktop._start_with_settings = mock.Mock()
        desktop.start()
        desktop.start()
        desktop.restart()
        self.assertEqual(len(tasks), 1)
        desktop.quit()
        tasks[0]()
        tasks[1]()
        desktop._start_with_settings.assert_not_called()
        desktop.lifecycle.stop.assert_called_once()

    def test_quit_stops_owned_child_then_tray_and_waits_for_workers(self):
        desktop = self.desktop()
        calls = []
        desktop.lifecycle.stop.side_effect = lambda: calls.append("child")
        desktop.tray.stop.side_effect = lambda: calls.append("tray")
        desktop.tray_action("quit")
        desktop.quit()
        self.assertEqual(calls, ["child", "tray"])
        desktop.workers.idle.return_value = False
        desktop.pump_workers()
        desktop.root.destroy.assert_not_called()
        desktop.workers.idle.return_value = True
        desktop.pump_workers()
        desktop.root.destroy.assert_called_once()
        desktop.tray_action("open")
        desktop.root.deiconify.assert_not_called()

    def test_failed_quit_keeps_controller_open_for_retry(self):
        desktop = self.desktop()
        desktop.lifecycle.stop.side_effect = OSError("stop failed")
        desktop.poll = mock.Mock()
        desktop.quit()
        with mock.patch("server.desktop.gui.messagebox.showerror"):
            desktop.pump_workers()
        desktop.root.destroy.assert_not_called()
        desktop.root.deiconify.assert_called_once()
        self.assertFalse(desktop._closing)

    def test_worker_callbacks_run_only_when_main_thread_drains(self):
        workers = DesktopWorkers()
        callbacks = []
        workers.start(lambda: workers.post(lambda: callbacks.append(threading.get_ident())))
        workers.threads[0].join(2)
        self.assertFalse(callbacks)
        workers.drain()
        self.assertEqual(callbacks, [threading.get_ident()])
        self.assertTrue(workers.idle())

    @unittest.skipUnless(sys.platform == "win32", "Windows named instance handles")
    def test_second_launch_signals_existing_instance_and_releases_handles(self):
        from pathlib import Path
        from server.desktop.instance import WindowsInstance
        with tempfile.TemporaryDirectory() as directory:
            first = WindowsInstance(Path(directory))
            try:
                self.assertTrue(first.primary)
                second = WindowsInstance(Path(directory))
                try:
                    self.assertFalse(second.primary)
                    self.assertTrue(first.restore_requested())
                    self.assertFalse(first.restore_requested())
                finally:
                    second.close()
            finally:
                first.close()
            third = WindowsInstance(Path(directory))
            self.assertTrue(third.primary)
            third.close()

    def test_tray_adapter_builds_required_menu_and_stops_event_loop(self):
        api = mock.Mock()
        api.MenuItem.side_effect = lambda text, action, **kwargs: (text, action, kwargs)
        api.Menu.side_effect = lambda *items: items
        actions = []
        with mock.patch.dict(sys.modules, {"pystray": api, "PIL": mock.MagicMock()}), mock.patch("server.desktop.tray.threading.Thread"):
            tray = WindowsTray(actions.append, lambda: ("Start server", True, False))
        items = api.Icon.call_args.kwargs["menu"] if "menu" in api.Icon.call_args.kwargs else api.Icon.call_args.args[3]
        self.assertEqual([item[0] if isinstance(item[0], str) else item[0](None) for item in items],
                         ["Open PCServer", "Restart server", "Start server", "Quit"])
        for _, action, _ in items:
            action()
        self.assertEqual(actions, ["open", "restart", "toggle", "quit"])
        tray._ready.set()
        tray.update()
        tray.update()
        tray.icon.update_menu.assert_called_once()
        tray.thread.is_alive.return_value = False
        tray.stop()
        tray.icon.stop.assert_called_once()
        tray.thread.join.assert_called_once()

    def test_owned_child_exits_cleanly_without_terminate_or_kill(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as directory:
            lifecycle = PCServerLifecycle(directory)
            try:
                self.assertEqual(lifecycle.start(DesktopSettings(listen_port=port)).state, "Running")
                process = lifecycle._process
                with mock.patch.object(process, "terminate", wraps=process.terminate) as terminate, mock.patch.object(process, "kill", wraps=process.kill) as kill:
                    self.assertEqual(lifecycle.stop().state, "Stopped")
                    terminate.assert_not_called()
                    kill.assert_not_called()
                self.assertEqual(process.returncode, 0)
                self.assertIsNone(lifecycle._reader)
            finally:
                lifecycle.stop()


if __name__ == "__main__":
    unittest.main()
