"""Thin wrapper around subprocess so tests can swap in a fake."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable, Sequence

# Hide console windows when run from pythonw / Task Scheduler.
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0


Runner = Callable[[Sequence[str], float], Result]


def run(args: Sequence[str], timeout: float = 15.0) -> Result:
    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return Result(124, "", "timeout")
    except OSError as exc:
        return Result(127, "", str(exc))
    return Result(proc.returncode, proc.stdout or "", proc.stderr or "")
