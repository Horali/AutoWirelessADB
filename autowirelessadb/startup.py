"""Start the watcher at logon with a shortcut in the user's Startup folder.

A Task Scheduler ONLOGON task needs admin rights; a Startup shortcut does not.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import runner as _runner

SHORTCUT_NAME = "AutoWirelessADB.lnk"
LAUNCHER = Path(__file__).resolve().parent.parent / "awadb_watch.pyw"


def startup_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcut_path() -> Path:
    return startup_dir() / SHORTCUT_NAME


def pythonw_path(executable: str = sys.executable) -> str:
    exe = Path(executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def task_command(executable: str = sys.executable, launcher: Path = LAUNCHER) -> str:
    return f'"{pythonw_path(executable)}" "{launcher}"'


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def shortcut_script(
    lnk: Path, executable: str = sys.executable, launcher: Path = LAUNCHER
) -> str:
    return (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"{_ps_quote(str(lnk))}); "
        f"$s.TargetPath = {_ps_quote(pythonw_path(executable))}; "
        f"$s.Arguments = {_ps_quote(chr(34) + str(launcher) + chr(34))}; "
        f"$s.WorkingDirectory = {_ps_quote(str(launcher.parent))}; "
        "$s.Description = 'AutoWirelessADB watcher'; "
        "$s.Save()"
    )


def install(run: _runner.Runner = _runner.run, lnk: Path | None = None) -> _runner.Result:
    lnk = lnk or shortcut_path()
    lnk.parent.mkdir(parents=True, exist_ok=True)
    res = run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", shortcut_script(lnk)],
        30,
    )
    if res.ok:
        return _runner.Result(0, f"Startup shortcut created: {lnk}")
    return res


def uninstall(lnk: Path | None = None) -> _runner.Result:
    lnk = lnk or shortcut_path()
    if lnk.exists():
        lnk.unlink()
        return _runner.Result(0, f"Removed {lnk}")
    return _runner.Result(0, "No startup shortcut found")
