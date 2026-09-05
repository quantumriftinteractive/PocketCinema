#!/usr/bin/env python3
"""Source and packaged entry point, with an explicit owned-server child role."""
from pathlib import Path
import sys


# Direct script execution sets sys.path to ``server/``. Add the checkout root so
# the ``server`` package imports exactly as it does in a bundled entry point.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

def main():
    from server.desktop.runtime import prepare_windows_runtime, restore_child_pipes
    prepare_windows_runtime()
    if sys.argv[1:2] == ["--server-child"]:
        del sys.argv[1]
        try:
            restore_child_pipes()
        except RuntimeError:
            return 2
        from server.desktop.server_child import run
        run()
        return 0
    from server.desktop.gui import main as desktop_main
    desktop_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
