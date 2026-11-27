"""Allow ``python -m agenthalt``."""

from __future__ import annotations

import sys

from agenthalt.cli import main

if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    sys.exit(main())
