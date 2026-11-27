# HANDOFF: AutoWirelessADB

Windows watcher that moves the Galaxy S25+ (serial RRCY1032Y6F, SM-S936B)
to TLS wireless ADB on allowed Wi-Fi. Repo: github.com/Horali/AutoWirelessADB
(private, `main`).

## Active tasks

(none)

## Current state

- v0.1.0 works. 41 unit tests pass (`py -3.12 -m pytest -q`).
- Live `status` against the real phone is correct (USB + TLS link seen).
- Allowlist (local config): "Pribadi", "Kos gk atas" (exact, case-sensitive).
- Notifications go to the phone (`notify_target = "phone"`), PC toast as fallback. Verified live.
- Startup shortcut installed and watcher running (log: `%LOCALAPPDATA%\AutoWirelessADB\watch.log`).
- USB enable flow worked live (log 2026-11-27 11:23).
- Logon watcher looked "silent" twice: cause found. The agent's tool shell sees
  a sandboxed copy of %APPDATA%/%LOCALAPPDATA%; the real config had an empty
  allowlist. Fixed in the real file via the user's terminal on 2026-11-27.

## Next steps

1. After the next logon, check (from the user's terminal) that `watch.log`
   has "watching" with both SSIDs, and the phone gets the notification.
2. Optional: single-instance guard so a manual `watch` does not run twice.
3. Optional: tray icon (needs `pystray` + `Pillow`), behind a flag.

## Decisions and lessons (keep)

- Over Wi-Fi, `adb get-serialno` returns `ip:port`. Use `getprop ro.serialno`.
- mDNS TLS name is `adb-<serial>-<random>`; match the serial prefix so other
  phones on the network are ignored.
- Security: fail closed. Both the Windows SSID and the phone SSID must be in
  the allowlist before `adb_wifi_enabled 1`. Legacy tcpip is opt-in only.
- Toasts use WinRT through PowerShell (no extra packages).
- Phone notifications: `cmd notification post`. Android drops posts from root,
  so post as uid 2000 (`su 2000 -c`). Samsung Game Booster may hide them in games.
- `status` must stay read-only.
- Agent tools (Bash/PowerShell/Write, even with the sandbox off) see a SANDBOX
  copy of AppData. Read or edit the real config/logs only through the user's
  terminal (run_in_terminal), or ask the user. Empty allowlist now warns.
- schtasks ONLOGON needs admin (Access is denied); use a Startup folder shortcut.
- Config and logs stay outside the repo (`%APPDATA%`, `%LOCALAPPDATA%`).

## Where to look

- `autowirelessadb/core.py`: the `tick()` state machine, enable flow, `off`.
- `autowirelessadb/adb.py`: adb calls and output parsers.
- `tests/fakes.py`: fake phone used by all tests.
