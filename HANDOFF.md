# HANDOFF: AutoWirelessADB

Windows watcher that moves the Galaxy S25+ (serial RRCY1032Y6F, SM-S936B)
to TLS wireless ADB on allowed Wi-Fi. Repo: github.com/Horali/AutoWirelessADB
(private, `main`).

## Active tasks

(none)

## Current state

- v0.1.0 works. 31 unit tests pass (`py -3.12 -m pytest -q`).
- Live `status` against the real phone is correct (USB + TLS link seen).
- Allowlist (local config): "Pribadi", "Kos gk atas" (exact, case-sensitive).
- Live `connect` on Wi-Fi works and shows the toast.
- Startup shortcut installed and watcher running (log: `%LOCALAPPDATA%\AutoWirelessADB\watch.log`).
- Not yet run live: the USB enable flow (wireless debugging off + USB in).

## Next steps

1. Turn wireless debugging off, plug in USB; confirm the watcher enables it and toasts.
2. After the next logon, check `watch.log` shows a new "watching" line.
3. Optional: single-instance guard so a manual `watch` does not run twice.
4. Optional: tray icon (needs `pystray` + `Pillow`), behind a flag.

## Decisions and lessons (keep)

- Over Wi-Fi, `adb get-serialno` returns `ip:port`. Use `getprop ro.serialno`.
- mDNS TLS name is `adb-<serial>-<random>`; match the serial prefix so other
  phones on the network are ignored.
- Security: fail closed. Both the Windows SSID and the phone SSID must be in
  the allowlist before `adb_wifi_enabled 1`. Legacy tcpip is opt-in only.
- Toasts use WinRT through PowerShell (no extra packages).
- `status` must stay read-only.
- schtasks ONLOGON needs admin (Access is denied); use a Startup folder shortcut.
- Config and logs stay outside the repo (`%APPDATA%`, `%LOCALAPPDATA%`).

## Where to look

- `autowirelessadb/core.py`: the `tick()` state machine, enable flow, `off`.
- `autowirelessadb/adb.py`: adb calls and output parsers.
- `tests/fakes.py`: fake phone used by all tests.
