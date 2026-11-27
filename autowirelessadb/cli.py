"""Command line: watch, connect, off, status, install-startup, uninstall-startup."""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path

from . import config as _config
from . import startup as _startup
from .core import Controller


def setup_logging(verbose: bool, to_file: bool) -> None:
    handlers: list[logging.Handler] = []
    # pythonw has no console; the launcher sends stderr to a file and sets this flag.
    if sys.stderr is not None and not os.environ.get("AWADB_NO_CONSOLE_LOG"):
        handlers.append(logging.StreamHandler())
    if to_file:
        d = _config.log_dir()
        d.mkdir(parents=True, exist_ok=True)
        handlers.append(
            logging.handlers.RotatingFileHandler(
                d / "watch.log", maxBytes=512_000, backupCount=2, encoding="utf-8"
            )
        )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="autowirelessadb", description=__doc__)
    p.add_argument("--config", type=Path, help="config.toml path (default: %%APPDATA%%)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--fallback-tcpip",
        action="store_true",
        help="allow legacy `adb tcpip 5555` if TLS fails (plaintext; off by default)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch", help="run the background watcher")
    w.add_argument(
        "--startup-delay", type=float, default=0,
        help="seconds to wait before the first check (lets Wi-Fi come up at logon)",
    )
    sub.add_parser("connect", help="one pass: connect now (enable over USB if needed)")
    sub.add_parser("off", help="set adb_wifi_enabled 0 and disconnect")
    sub.add_parser("status", help="show SSID, USB, mDNS and wireless state")
    sub.add_parser("install-startup", help="run `watch` at logon (Startup folder shortcut)")
    sub.add_parser("uninstall-startup", help="remove the Startup folder shortcut")
    sub.add_parser("config-path", help="print the config file path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose, to_file=args.cmd == "watch")
    cfg_path = args.config or _config.default_config_path()

    if args.cmd == "config-path":
        print(cfg_path)
        return 0
    if args.cmd == "install-startup":
        res = _startup.install()
        print(res.stdout.strip() or res.stderr.strip())
        return res.returncode
    if args.cmd == "uninstall-startup":
        res = _startup.uninstall()
        print(res.stdout.strip() or res.stderr.strip())
        return res.returncode

    cfg = _config.load(cfg_path)
    if args.fallback_tcpip:
        cfg.fallback_tcpip = True
    if not cfg.allowed_ssids and args.cmd in ("watch", "connect"):
        print(f"No allowed_ssids set. Edit {cfg_path} first.", file=sys.stderr)
        if args.cmd == "connect":
            return 2
    ctl = Controller(cfg)

    if args.cmd == "status":
        # status is read-only: it never connects, enables or disconnects.
        print("\n".join(_read_only_status(ctl)))
        return 0
    if args.cmd == "off":
        for line in ctl.turn_off():
            print(line)
        return 0
    if args.cmd == "connect":
        st = ctl.tick()
        for line in st.lines() + st.actions:
            print(line)
        return 0 if st.wireless else 1
    if args.cmd == "watch":
        try:
            if args.startup_delay > 0:
                logging.info("startup delay %ss", args.startup_delay)
                time.sleep(args.startup_delay)
            ctl.watch()
        except KeyboardInterrupt:
            pass
        return 0
    return 1


def _read_only_status(ctl: Controller) -> list[str]:
    from .adb import tls_endpoint_for
    from .core import Status

    cfg = ctl.cfg
    st = Status()
    st.ssid = ctl.get_ssid()
    st.ssid_allowed = cfg.ssid_allowed(st.ssid)
    devices = ctl.adb.devices()
    st.usb = devices.get(cfg.serial) == "device"
    st.wireless = ctl.find_wireless(devices)
    st.tls_endpoint = tls_endpoint_for(ctl.adb.mdns_services(), cfg.serial)
    lines = st.lines()
    reach = cfg.serial if st.usb else st.wireless
    if reach:
        enabled = ctl.adb.wifi_debugging_enabled(reach)
        lines.append(f"adb_wifi_enabled: {enabled}")
        lines.append(f"Phone SSID   : {ctl.adb.phone_ssid(reach)}")
        port = ctl.adb.tcp_port(reach)
        if port:
            lines.append(f"WARNING      : legacy plaintext tcpip mode is on (port {port}); `off` resets it")
    return lines
