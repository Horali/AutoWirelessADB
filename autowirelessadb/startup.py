"""Register the watcher as a Task Scheduler job that runs at logon."""

from __future__ import annotations

import sys
from pathlib import Path

from . import runner as _runner

TASK_NAME = "AutoWirelessADB"
LAUNCHER = Path(__file__).resolve().parent.parent / "awadb_watch.pyw"


def pythonw_path(executable: str = sys.executable) -> str:
    exe = Path(executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def task_command(executable: str = sys.executable, launcher: Path = LAUNCHER) -> str:
    return f'"{pythonw_path(executable)}" "{launcher}"'


def install(run: _runner.Runner = _runner.run) -> _runner.Result:
    return run(
        [
            "schtasks", "/Create", "/F",
            "/TN", TASK_NAME,
            "/SC", "ONLOGON",
            "/RL", "LIMITED",
            "/TR", task_command(),
        ],
        30,
    )


def uninstall(run: _runner.Runner = _runner.run) -> _runner.Result:
    return run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], 30)
