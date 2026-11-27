"""User config. Lives in %APPDATA%\\AutoWirelessADB\\config.toml, outside the repo."""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "AutoWirelessADB"
DEFAULT_ADB = r"C:\Users\child\AppData\Local\Android\Sdk\platform-tools\adb.exe"
DEFAULT_SERIAL = "RRCY1032Y6F"


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def default_config_path() -> Path:
    return app_dir() / "config.toml"


DEFAULT_TOML = f"""\
# AutoWirelessADB config. This file is local only; never commit it.

# USB serial of the phone (adb -s <serial>).
serial = "{DEFAULT_SERIAL}"

# Full path to adb.exe.
adb_path = '{DEFAULT_ADB}'

# Wireless ADB is only used on these Windows Wi-Fi networks (exact SSID match).
# Empty list = never use wireless ADB. Add your home network, for example:
# allowed_ssids = ["MyHomeWifi"]
allowed_ssids = []

# Seconds between checks in `watch` mode.
poll_interval = 5

# Seconds to wait for the TLS endpoint after enabling wireless debugging.
enable_timeout = 30

# Legacy `adb tcpip 5555` fallback. Plaintext, weaker. Keep false unless needed.
fallback_tcpip = false

# Disconnect wireless ADB on the PC side when Windows leaves an allowed network.
disconnect_on_untrusted = true

# Show notifications when wireless ADB connects.
notifications = true

# Where to show them: "phone", "pc" or "both".
# "phone" falls back to a PC toast if the phone post fails.
notify_target = "phone"
"""


@dataclass
class Config:
    serial: str = DEFAULT_SERIAL
    adb_path: str = DEFAULT_ADB
    allowed_ssids: list[str] = field(default_factory=list)
    poll_interval: float = 5.0
    enable_timeout: float = 30.0
    fallback_tcpip: bool = False
    disconnect_on_untrusted: bool = True
    notifications: bool = True
    notify_target: str = "phone"  # "phone" | "pc" | "both"

    def ssid_allowed(self, ssid: str | None) -> bool:
        # Fail closed: unknown SSID is never allowed.
        return bool(ssid) and ssid in self.allowed_ssids


_ALLOWED_LINE = re.compile(r"(?m)^allowed_ssids\s*=.*$")


def add_ssid(ssid: str, path: Path | None = None) -> list[str]:
    """Add one SSID to allowed_ssids in config.toml. Returns the new list."""
    path = path or default_config_path()
    cfg = load(path)
    if ssid not in cfg.allowed_ssids:
        cfg.allowed_ssids.append(ssid)
    # json.dumps gives valid TOML basic strings (quotes and backslashes escaped).
    line = "allowed_ssids = [" + ", ".join(json.dumps(s) for s in cfg.allowed_ssids) + "]"
    text = path.read_text(encoding="utf-8")
    if _ALLOWED_LINE.search(text):
        text = _ALLOWED_LINE.sub(lambda _: line, text, count=1)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    path.write_text(text, encoding="utf-8")
    return cfg.allowed_ssids


def load(path: Path | None = None, create: bool = True) -> Config:
    path = path or default_config_path()
    if not path.exists():
        if not create:
            return Config()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_TOML, encoding="utf-8")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    cfg = Config()
    for key in cfg.__dataclass_fields__:
        if key in data:
            setattr(cfg, key, data[key])
    cfg.allowed_ssids = [str(s) for s in cfg.allowed_ssids]
    return cfg
