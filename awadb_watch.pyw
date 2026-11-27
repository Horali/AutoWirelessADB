"""Windowless launcher for Task Scheduler: runs `autowirelessadb watch`."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from autowirelessadb.cli import main  # noqa: E402

sys.exit(main(["watch"]))
