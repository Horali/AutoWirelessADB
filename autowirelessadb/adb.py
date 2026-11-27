"""adb calls. Every device command passes `-s <serial>`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import runner as _runner

TLS_SERVICE = "_adb-tls-connect._tcp"
_ENDPOINT_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}:\d+$")
_INET_RE = re.compile(r"inet (\d{1,3}(?:\.\d{1,3}){3})/")
_PHONE_SSID_RE = re.compile(r'Wifi is connected to "(.*?)"')


@dataclass(frozen=True)
class MdnsService:
    name: str
    service: str
    endpoint: str  # "ip:port"


def is_network_serial(serial: str) -> bool:
    return bool(_ENDPOINT_RE.match(serial)) or serial.startswith("adb-")


def parse_devices(text: str) -> dict[str, str]:
    """`adb devices` output -> {serial: state}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def parse_mdns(text: str) -> list[MdnsService]:
    """`adb mdns services` output -> list of services."""
    out: list[MdnsService] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1].startswith("_adb") and _ENDPOINT_RE.match(parts[2]):
            out.append(MdnsService(parts[0], parts[1].rstrip("."), parts[2]))
    return out


def tls_endpoint_for(services: list[MdnsService], serial: str) -> str | None:
    """Pick the TLS endpoint whose mDNS name belongs to this serial.

    Android names it "adb-<serial>-<random>". Matching on the serial stops us
    from connecting to some other phone on the same network.
    """
    prefix = f"adb-{serial}-"
    for svc in services:
        if svc.service == TLS_SERVICE and svc.name.startswith(prefix):
            return svc.endpoint
    return None


class Adb:
    def __init__(self, path: str, run: _runner.Runner = _runner.run):
        self.path = path
        self._run = run

    def _call(self, *args: str, timeout: float = 15.0) -> _runner.Result:
        return self._run([self.path, *args], timeout)

    # --- host-level -------------------------------------------------------
    def devices(self) -> dict[str, str]:
        res = self._call("devices")
        return parse_devices(res.stdout) if res.ok else {}

    def mdns_services(self) -> list[MdnsService]:
        res = self._call("mdns", "services")
        return parse_mdns(res.stdout) if res.ok else []

    def connect(self, endpoint: str) -> bool:
        res = self._call("connect", endpoint, timeout=20)
        text = res.stdout.lower()
        return res.ok and ("connected to" in text) and "failed" not in text

    def disconnect(self, endpoint: str) -> None:
        self._call("disconnect", endpoint)

    # --- device-level (always -s) ----------------------------------------
    def shell(self, serial: str, *cmd: str, timeout: float = 15.0) -> _runner.Result:
        return self._call("-s", serial, "shell", *cmd, timeout=timeout)

    def get_serialno(self, serial: str) -> str | None:
        """Hardware serial. `adb get-serialno` returns ip:port over Wi-Fi, so ask the phone."""
        res = self.shell(serial, "getprop", "ro.serialno", timeout=10)
        value = res.stdout.strip()
        return value if res.ok and value and value != "unknown" else None

    def responds(self, serial: str) -> bool:
        res = self.shell(serial, "echo", "awadb-ok", timeout=10)
        return res.ok and "awadb-ok" in res.stdout

    def set_wifi_debugging(self, serial: str, enabled: bool) -> bool:
        value = "1" if enabled else "0"
        res = self.shell(serial, "settings", "put", "global", "adb_wifi_enabled", value)
        return res.ok

    def wifi_debugging_enabled(self, serial: str) -> bool | None:
        res = self.shell(serial, "settings", "get", "global", "adb_wifi_enabled")
        if not res.ok:
            return None
        return res.stdout.strip() == "1"

    def phone_ssid(self, serial: str) -> str | None:
        """SSID the phone itself is on (from `cmd wifi status`)."""
        res = self.shell(serial, "cmd", "wifi", "status")
        match = _PHONE_SSID_RE.search(res.stdout) if res.ok else None
        return match.group(1) if match else None

    def tcp_port(self, serial: str) -> str | None:
        res = self.shell(serial, "getprop", "service.adb.tcp.port")
        value = res.stdout.strip()
        return value if res.ok and value and value not in ("-1", "0") else None

    def wlan_ip(self, serial: str) -> str | None:
        res = self.shell(serial, "ip", "-f", "inet", "addr", "show", "wlan0")
        match = _INET_RE.search(res.stdout) if res.ok else None
        return match.group(1) if match else None

    def tcpip(self, serial: str, port: int = 5555) -> bool:
        return self._call("-s", serial, "tcpip", str(port)).ok

    def usb(self, serial: str) -> bool:
        """Restart adbd in USB-only mode (turns legacy tcpip off)."""
        return self._call("-s", serial, "usb").ok
