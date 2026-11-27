"""Windowless launcher for the Startup shortcut: runs `autowirelessadb watch`.

pythonw has no console, so stdout/stderr are None and any crash or logging
error vanishes. Send them to a file so problems after logon leave a trace.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from autowirelessadb.config import log_dir  # noqa: E402

if sys.stderr is None or sys.stdout is None:
    d = log_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "watch.stderr.log"
    if path.exists() and path.stat().st_size > 256_000:
        path.replace(d / "watch.stderr.log.1")
    stream = open(path, "a", encoding="utf-8", buffering=1)
    sys.stderr = stream
    sys.stdout = stream
    os.environ["AWADB_NO_CONSOLE_LOG"] = "1"  # watch.log already has the log
    print(f"--- launcher start pid={os.getpid()}", file=stream)

from autowirelessadb.cli import main  # noqa: E402

sys.exit(main(["watch", "--startup-delay", "20"]))
