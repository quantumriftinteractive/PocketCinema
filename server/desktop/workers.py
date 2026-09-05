"""Background work with callbacks delivered exclusively by the Tk thread."""
from queue import Empty, Queue
import threading


class DesktopWorkers:
    def __init__(self):
        self.callbacks = Queue()
        self.threads = []

    def post(self, callback):
        self.callbacks.put(callback)

    def start(self, target):
        thread = threading.Thread(target=target, daemon=False)
        self.threads.append(thread)
        thread.start()

    def drain(self):
        for _ in range(100):
            try:
                callback = self.callbacks.get_nowait()
            except Empty:
                break
            callback()

    def idle(self):
        self.threads = [thread for thread in self.threads if thread.is_alive()]
        return not self.threads

    def discard(self):
        while True:
            try:
                self.callbacks.get_nowait()
            except Empty:
                return
