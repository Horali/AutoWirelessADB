"""Read the current Windows Wi-Fi SSID from `netsh wlan show interfaces`."""

from __future__ import annotations

import logging
import re

from . import runner as _runner

log = logging.getLogger(__name__)

_SSID_RE = re.compile(r"^\s*SSID\s*:\s*(.*?)\s*$", re.MULTILINE)
_STATE_RE = re.compile(r"^\s*State\s*:\s*(.*?)\s*$", re.MULTILINE)

_last_problem: str | None = None


def parse_ssid(text: str) -> str | None:
    """Return the SSID of the first connected interface, or None.

    The regex anchors on "SSID" at line start, so "AP BSSID" never matches.
    """
    state = _STATE_RE.search(text)
    if state and state.group(1).lower() != "connected":
        return None
    match = _SSID_RE.search(text)
    if not match or not match.group(1):
        return None
    return match.group(1)


def location_blocked(text: str) -> bool:
    """Windows 11 24H2+ hides the SSID unless location access is on."""
    return "location" in text.lower() and "permission" in text.lower()


def explain(res: _runner.Result) -> str:
    """Short reason why no SSID came back (for the log)."""
    text = res.stdout + res.stderr
    if not res.ok:
        return f"netsh exit {res.returncode}: {' '.join(text.split())[:160]}"
    if location_blocked(text):
        return "netsh hides the SSID: location access is off for desktop apps"
    state = _STATE_RE.search(text)
    if state:
        return f"Wi-Fi state is {state.group(1)!r}"
    return f"no Wi-Fi interface in netsh output: {' '.join(text.split())[:160]}"


def current_ssid(run: _runner.Runner = _runner.run) -> str | None:
    global _last_problem
    res = run(["netsh", "wlan", "show", "interfaces"], 10)
    ssid = parse_ssid(res.stdout) if res.ok else None
    problem = None if ssid else explain(res)
    if problem != _last_problem:  # log each new problem once, not every 5 s
        if problem:
            log.warning("no SSID: %s", problem)
        _last_problem = problem
    return ssid
