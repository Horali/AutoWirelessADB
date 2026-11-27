"""Read the current Windows Wi-Fi SSID from `netsh wlan show interfaces`."""

from __future__ import annotations

import re

from . import runner as _runner

_SSID_RE = re.compile(r"^\s*SSID\s*:\s*(.*?)\s*$", re.MULTILINE)
_STATE_RE = re.compile(r"^\s*State\s*:\s*(.*?)\s*$", re.MULTILINE)


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


def current_ssid(run: _runner.Runner = _runner.run) -> str | None:
    res = run(["netsh", "wlan", "show", "interfaces"], 10)
    if not res.ok:
        return None
    return parse_ssid(res.stdout)
