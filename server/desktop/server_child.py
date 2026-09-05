"""Stable child-process entry point for source and later frozen desktop builds."""
from server.pocketcinema_server import main
import sys
import threading


def run():
    """Only the owning parent's anonymous stdin pipe can request shutdown."""
    shutdown = threading.Event()

    def control():
        for command in sys.stdin:
            if command.strip() == "stop":
                break
        shutdown.set()  # Parent exit/pipe EOF also releases this child.

    threading.Thread(target=control, daemon=True).start()
    main(shutdown_event=shutdown)


if __name__ == "__main__":
    run()
