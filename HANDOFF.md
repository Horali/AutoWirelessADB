# HANDOFF: AutoWirelessADB

Windows watcher that moves the Galaxy S25+ (serial RRCY1032Y6F, SM-S936B)
to TLS wireless ADB on allowed Wi-Fi. Repo: github.com/Horali/AutoWirelessADB
(private, `main`).

## Active tasks

(none)

## Current state

- v0.1.0 works. 31 unit tests pass (`py -3.12 -m pytest -q`).
- Live `status` against the real phone is correct (USB + TLS link seen).
- Not yet run live: `connect` / `watch` enable flow, toast, `install-startup`.
  Reason: `allowed_ssids` is empty until the user adds their network.

## Next steps

1. User adds their home SSID to `%APPDATA%\AutoWirelessADB\config.toml`.
2. Run `connect` with USB plugged in; confirm the toast shows.
3. Run `install-startup`; log off and on; check `watch.log`.
4. Optional: tray icon (needs `pystray` + `Pillow`), behind a flag.

## Decisions and lessons (keep)

- Over Wi-Fi, `adb get-serialno` returns `ip:port`. Use `getprop ro.serialno`.
- mDNS TLS name is `adb-<serial>-<random>`; match the serial prefix so other
  phones on the network are ignored.
- Security: fail closed. Both the Windows SSID and the phone SSID must be in
  the allowlist before `adb_wifi_enabled 1`. Legacy tcpip is opt-in only.
- Toasts use WinRT through PowerShell (no extra packages).
- `status` must stay read-only.
- Config and logs stay outside the repo (`%APPDATA%`, `%LOCALAPPDATA%`).

## Where to look

- `autowirelessadb/core.py`: the `tick()` state machine, enable flow, `off`.
- `autowirelessadb/adb.py`: adb calls and output parsers.
- `tests/fakes.py`: fake phone used by all tests.
