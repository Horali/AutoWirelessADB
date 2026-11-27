"""The watcher logic. One `tick()` checks state once and fixes what it can."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from . import notify as _notify
from . import wifi as _wifi
from .adb import Adb, is_network_serial, tls_endpoint_for
from .config import Config

log = logging.getLogger(__name__)

ENABLE_BACKOFF = 60.0  # seconds between enable attempts for one USB session


@dataclass
class Status:
    ssid: str | None = None
    ssid_allowed: bool = False
    usb: bool = False
    wireless: str | None = None  # connected network serial (ip:port)
    tls_endpoint: str | None = None  # what mDNS advertises right now
    actions: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        return [
            f"Windows SSID : {self.ssid or '(none / hidden)'}"
            f" ({'allowed' if self.ssid_allowed else 'NOT allowed'})",
            f"USB          : {'connected' if self.usb else 'not connected'}",
            f"mDNS TLS     : {self.tls_endpoint or '(not advertised)'}",
            f"Wireless ADB : {self.wireless or 'not connected'}",
        ]


class Controller:
    def __init__(
        self,
        cfg: Config,
        adb: Adb | None = None,
        get_ssid: Callable[[], str | None] | None = None,
        toast: Callable[[str, str], object] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cfg = cfg
        self.adb = adb or Adb(cfg.adb_path)
        self.get_ssid = get_ssid or _wifi.current_ssid
        self._toast = toast or _notify.toast
        self.sleep = sleep
        self.clock = clock
        self._serial_cache: dict[str, str | None] = {}
        self._last_enable: float | None = None
        self._announced: str | None = None
        self._was_allowed: bool | None = None

    # --- helpers ----------------------------------------------------------
    def notify(self, title: str, body: str) -> None:
        log.info("notify: %s - %s", title, body)
        if self.cfg.notifications:
            self._toast(title, body)

    def _owner(self, net_serial: str) -> str | None:
        if net_serial not in self._serial_cache:
            self._serial_cache[net_serial] = self.adb.get_serialno(net_serial)
        return self._serial_cache[net_serial]

    def find_wireless(self, devices: dict[str, str]) -> str | None:
        """Return the network serial that belongs to our phone, if any."""
        for serial, state in devices.items():
            if state == "device" and is_network_serial(serial):
                if self._owner(serial) == self.cfg.serial:
                    return serial
        return None

    def _forget(self, net_serial: str) -> None:
        self._serial_cache.pop(net_serial, None)
        if self._announced == net_serial:
            self._announced = None

    def _connect_verified(self, endpoint: str) -> bool:
        if not self.adb.connect(endpoint):
            log.info("connect %s failed", endpoint)
            return False
        self._serial_cache.pop(endpoint, None)
        if self._owner(endpoint) != self.cfg.serial or not self.adb.responds(endpoint):
            log.warning("%s connected but is not %s or does not respond", endpoint, self.cfg.serial)
            self.adb.disconnect(endpoint)
            self._forget(endpoint)
            return False
        return True

    def _announce(self, endpoint: str, usb: bool) -> None:
        if self._announced == endpoint:
            return
        self._announced = endpoint
        if usb:
            self.notify("Wireless ADB connected", f"Safe to unplug USB. ({endpoint})")
        else:
            self.notify("Wireless ADB connected", endpoint)

    # --- main step --------------------------------------------------------
    def tick(self) -> Status:
        st = Status()
        st.ssid = self.get_ssid()
        st.ssid_allowed = self.cfg.ssid_allowed(st.ssid)
        devices = self.adb.devices()
        st.usb = devices.get(self.cfg.serial) == "device"
        st.wireless = self.find_wireless(devices)

        if st.ssid_allowed != self._was_allowed:
            log.info("SSID %r allowed=%s", st.ssid, st.ssid_allowed)
            self._was_allowed = st.ssid_allowed
        if not st.usb:
            self._last_enable = None  # new USB plug-in gets a fresh attempt

        if not st.ssid_allowed:
            if st.wireless and self.cfg.disconnect_on_untrusted:
                self.adb.disconnect(st.wireless)
                self._forget(st.wireless)
                st.actions.append(f"disconnected {st.wireless} (untrusted Wi-Fi)")
                st.wireless = None
            return st

        st.tls_endpoint = tls_endpoint_for(self.adb.mdns_services(), self.cfg.serial)

        # adb's own mDNS auto-connect names the device "adb-<serial>-..."; that counts.
        auto_named = bool(st.wireless and st.wireless.startswith("adb-"))
        if st.tls_endpoint and st.wireless != st.tls_endpoint and not auto_named:
            # Not connected yet, or the IP / TLS port rotated.
            old = st.wireless
            if self._connect_verified(st.tls_endpoint):
                st.actions.append(f"connected {st.tls_endpoint}")
                if old and old != st.tls_endpoint and not old.endswith(":5555"):
                    self.adb.disconnect(old)
                    self._forget(old)
                    st.actions.append(f"dropped stale {old}")
                st.wireless = st.tls_endpoint
        elif not st.wireless and st.usb and self._may_enable():
            endpoint = self.enable_wireless()
            if endpoint:
                st.actions.append(f"enabled and connected {endpoint}")
                st.wireless = endpoint

        if st.wireless:
            self._announce(st.wireless, st.usb)
        return st

    def _may_enable(self) -> bool:
        now = self.clock()
        if self._last_enable is not None and now - self._last_enable < ENABLE_BACKOFF:
            return False
        self._last_enable = now
        return True

    # --- USB -> wireless --------------------------------------------------
    def enable_wireless(self) -> str | None:
        """Turn on Wireless debugging over USB, then connect over TLS.

        Returns the connected endpoint, or None.
        """
        serial = self.cfg.serial
        phone_ssid = self.adb.phone_ssid(serial)
        if not self.cfg.ssid_allowed(phone_ssid):
            log.warning("phone Wi-Fi %r is not allowed; not enabling", phone_ssid)
            return None

        log.info("enabling adb_wifi_enabled on %s", serial)
        if not self.adb.set_wifi_debugging(serial, True):
            log.warning("could not set adb_wifi_enabled")
            return None

        deadline = self.clock() + self.cfg.enable_timeout
        while self.clock() < deadline:
            endpoint = tls_endpoint_for(self.adb.mdns_services(), serial)
            if endpoint and self._connect_verified(endpoint):
                return endpoint
            self.sleep(2)

        if self.cfg.fallback_tcpip:
            return self._fallback_tcpip()
        log.warning("TLS endpoint did not come up in %ss", self.cfg.enable_timeout)
        return None

    def _fallback_tcpip(self) -> str | None:
        serial = self.cfg.serial
        ip = self.adb.wlan_ip(serial)
        if not ip:
            log.warning("fallback: no wlan0 IP")
            return None
        log.warning("fallback: legacy adb tcpip 5555 (plaintext)")
        if not self.adb.tcpip(serial, 5555):
            return None
        self.sleep(3)
        endpoint = f"{ip}:5555"
        return endpoint if self._connect_verified(endpoint) else None

    # --- off ----------------------------------------------------------------
    def turn_off(self) -> list[str]:
        """Disable Wireless debugging on the phone and drop PC connections."""
        done: list[str] = []
        devices = self.adb.devices()
        wireless = self.find_wireless(devices)
        # Prefer USB for the shell; fall back to the wireless link itself.
        target = self.cfg.serial if devices.get(self.cfg.serial) == "device" else wireless
        if target is None:
            done.append("phone not reachable over USB or Wi-Fi; nothing changed on the phone")
        else:
            if self.adb.set_wifi_debugging(target, False):
                done.append("adb_wifi_enabled = 0")
            if target == self.cfg.serial and self.adb.tcp_port(target):
                if self.adb.usb(target):
                    done.append("legacy tcpip mode off (adb usb)")
        if wireless:
            self.adb.disconnect(wireless)
            self._forget(wireless)
            done.append(f"disconnected {wireless}")
        return done

    def watch(self, stop: Callable[[], bool] = lambda: False) -> None:
        log.info("watching %s (allowed SSIDs: %s)", self.cfg.serial, self.cfg.allowed_ssids)
        while not stop():
            try:
                st = self.tick()
                for action in st.actions:
                    log.info(action)
            except Exception:  # keep the watcher alive
                log.exception("tick failed")
            self.sleep(self.cfg.poll_interval)
