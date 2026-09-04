#!/usr/bin/env python3
"""Development entry point for the PocketCinema Server desktop shell."""
from pathlib import Path
import sys


# Direct script execution sets sys.path to ``server/``. Add the checkout root so
# the ``server`` package imports exactly as it does in a bundled entry point.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.desktop.gui import main


if __name__ == "__main__":
    main()
