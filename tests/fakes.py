"""A fake phone + adb + netsh, driven by plain state, for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from autowirelessadb.runner import Result

ADB = "adb.exe"
SERIAL = "RRCY1032Y6F"

NETSH_TEMPLATE = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    State                  : {state}
    SSID                   : {ssid}
    AP BSSID               : ec:e7:a2:43:5f:48
    Profile                : {ssid}
"""


@dataclass
class FakePhone:
    usb: bool = True
    ip: str = "192.168.1.6"
    tls_port: int = 38605
    wifi_enabled: bool = False
    phone_ssid: str = "HomeNet"
    advertise_after_enable: bool = True
    tcp_port: str = ""
    connected: set[str] = field(default_factory=set)
    connect_ok: bool = True
    pc_ssid: str | None = "HomeNet"
    calls: list[list[str]] = field(default_factory=list)

    @property
    def tls_up(self) -> bool:
        return self.wifi_enabled and self.advertise_after_enable

    @property
    def endpoint(self) -> str:
        return f"{self.ip}:{self.tls_port}"

    # The Runner signature: (args, timeout) -> Result
    def __call__(self, args, timeout=15.0) -> Result:
        args = list(args)
        self.calls.append(args)
        if args[0] == "netsh":
            if self.pc_ssid is None:
                return Result(0, NETSH_TEMPLATE.format(state="disconnected", ssid=""))
            return Result(0, NETSH_TEMPLATE.format(state="connected", ssid=self.pc_ssid))
        assert args[0] == ADB, args
        a = args[1:]
        if a == ["devices"]:
            lines = ["List of devices attached"]
            if self.usb:
                lines.append(f"{SERIAL}\tdevice")
            lines += [f"{c}\tdevice" for c in sorted(self.connected)]
            return Result(0, "\n".join(lines) + "\n")
        if a == ["mdns", "services"]:
            out = "List of discovered mdns services\n"
            if self.tls_up:
                out += f"adb-{SERIAL}-Wj1Car\t_adb-tls-connect._tcp\t{self.endpoint}\n"
            out += "adb-OTHER123-zz\t_adb-tls-connect._tcp\t192.168.1.50:40000\n"
            return Result(0, out)
        if a[0] == "connect":
            ep = a[1]
            live = {self.endpoint} if self.tls_up else set()
            if self.tcp_port:
                live.add(f"{self.ip}:{self.tcp_port}")
            if self.connect_ok and ep in live:
                self.connected.add(ep)
                return Result(0, f"connected to {ep}\n")
            return Result(1, f"failed to connect to {ep}\n")
        if a[0] == "disconnect":
            self.connected.discard(a[1])
            return Result(0, f"disconnected {a[1]}\n")
        if a[0] == "-s":
            target, rest = a[1], a[2:]
            if target == SERIAL and not self.usb:
                return Result(1, "", "device not found")
            if target != SERIAL and target not in self.connected:
                return Result(1, "", "device not found")
            return self._device(target, rest)
        return Result(1, "", f"unknown {a}")

    def _device(self, target: str, rest: list[str]) -> Result:
        if rest == ["get-serialno"]:  # real adb returns the transport name
            return Result(0, target + "\n")
        if rest == ["shell", "getprop", "ro.serialno"]:
            return Result(0, SERIAL + "\n")
        if rest == ["tcpip", "5555"]:
            self.tcp_port = "5555"
            return Result(0, "restarting in TCP mode port: 5555\n")
        if rest == ["usb"]:
            self.tcp_port = ""
            return Result(0, "restarting in USB mode\n")
        if rest[0] != "shell":
            return Result(1, "", "bad")
        cmd = rest[1:]
        if cmd == ["echo", "awadb-ok"]:
            return Result(0, "awadb-ok\n")
        if cmd[:3] == ["settings", "put", "global"] and cmd[3] == "adb_wifi_enabled":
            self.wifi_enabled = cmd[4] == "1"
            return Result(0, "")
        if cmd == ["settings", "get", "global", "adb_wifi_enabled"]:
            return Result(0, "1\n" if self.wifi_enabled else "0\n")
        if cmd == ["cmd", "wifi", "status"]:
            return Result(0, f'Wifi is enabled\nWifi is connected to "{self.phone_ssid}"\n')
        if cmd == ["getprop", "service.adb.tcp.port"]:
            return Result(0, self.tcp_port + "\n")
        if cmd[:2] == ["ip", "-f"]:
            return Result(0, f"    inet {self.ip}/24 brd 192.168.1.255 scope global wlan0\n")
        return Result(1, "", f"unknown shell {cmd}")

    def adb_calls(self) -> list[list[str]]:
        return [c[1:] for c in self.calls if c[0] == ADB]


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += s
