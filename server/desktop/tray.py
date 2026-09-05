"""Windows tray adapter. Callbacks enqueue commands; they never touch Tk."""
from pathlib import Path
import threading


SERVER_ICON = Path(__file__).resolve().parents[2] / "UI_concept" / "Icons" / "PocketCinema_Server_icon.png"


def menu_state(state, busy=False, closing=False):
    running = state in {"Starting", "Running", "Stopping"}
    enabled = not busy and not closing and state not in {"Starting", "Stopping"}
    return ("Stop server" if running else "Start server", enabled,
            enabled and state == "Running")


def tray_title(state, mode_label=""):
    title = "PocketCinema Server - " + ("Started" if state == "Running" else "Stopped")
    return title + " - " + mode_label if state == "Running" and mode_label else title


class WindowsTray:
    def __init__(self, dispatch, status, title=lambda: tray_title("Stopped")):
        import pystray
        from PIL import Image

        self._status = status
        self._title = title
        self._ready = threading.Event()
        self._stopping = threading.Event()
        self._signature = None
        self.error = False
        with Image.open(SERVER_ICON) as source:
            artwork = source.convert("RGBA")
        self.icon = pystray.Icon(
            "PocketCinemaServer", artwork, self._title(),
            pystray.Menu(
                pystray.MenuItem("Open PCServer", lambda: dispatch("open"), default=True),
                pystray.MenuItem("Restart server", lambda: dispatch("restart"),
                                 enabled=lambda item: self._status()[2]),
                pystray.MenuItem(lambda item: self._status()[0], lambda: dispatch("toggle"),
                                 enabled=lambda item: self._status()[1]),
                pystray.MenuItem("Quit", lambda: dispatch("quit")),
            ),
        )
        self.thread = threading.Thread(target=self._run, name="PocketCinema tray", daemon=False)
        self.thread.start()

    def _setup(self, icon):
        try:
            if not self._stopping.is_set():
                icon.visible = True
        except Exception:
            self.error = True
        finally:
            self._ready.set()

    def _run(self):
        try:
            self.icon.run(setup=self._setup)
        except Exception:
            self.error = True
        finally:
            self._ready.set()

    @property
    def available(self):
        return self._ready.is_set() and self.thread.is_alive() and not self.error

    def update(self):
        title = self._title()
        signature = (self._status(), title)
        if self.available and signature != self._signature:
            try:
                self.icon.update_menu()
                self.icon.title = title
                self._signature = signature
            except Exception:
                self.error = True

    def notify_hidden(self):
        """Notify on the existing native icon without changing lifecycle state."""
        if not self.available or not self.icon.HAS_NOTIFICATION:
            return False
        try:
            self.icon.notify(
                "PocketCinema Server is still running in the system tray.",
                "PocketCinema Server",
            )
            return True
        except Exception:
            # A notification failure must never break hide/restore or Quit.
            return False

    def stop(self):
        self._stopping.set()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Tray startup has not finished; retry Quit.")
        self.icon.stop()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("Tray shutdown has not finished; retry Quit.")
