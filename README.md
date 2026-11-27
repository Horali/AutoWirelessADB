# AutoWirelessADB

A small Windows background watcher. It moves an Android phone to TLS wireless
ADB on trusted Wi-Fi networks, so you can unplug the USB cable.

No extra Python packages. Python 3.12 and `adb.exe` only.

## How it works

Each check (every 5 s in `watch` mode):

1. Read the Windows SSID from `netsh wlan show interfaces`.
2. If the SSID is not in `allowed_ssids`, do nothing. If a wireless link is
   open, disconnect it on the PC (`disconnect_on_untrusted`).
3. If the phone advertises `_adb-tls-connect._tcp` over mDNS, and the mDNS
   name contains the phone serial, run `adb connect <ip:port>`. When the IP or
   the TLS port changes, connect to the new one and drop the old one.
4. If the phone is on USB and no wireless link exists, check the phone SSID
   (`cmd wifi status`). If that SSID is also allowed, run
   `settings put global adb_wifi_enabled 1`, wait for the TLS endpoint,
   connect, and verify with `shell echo`.
5. When the link works, post a notification on the phone through the new
   wireless link: "Safe to unplug USB." Set `notify_target` to `"phone"`
   (default), `"pc"` (Windows toast) or `"both"`. If the phone post fails,
   the watcher shows a PC toast instead.
6. When the link is lost (or Windows leaves an allowed network), show
   "Wireless ADB disconnected" with the reason. The phone gets it only over
   USB; with no USB it is a PC toast, because the phone is out of reach.

Every device command uses `adb -s <serial>`. An unknown or hidden SSID counts
as "not allowed".

## Set-up

1. Pair this PC with the phone one time (Developer options > Wireless
   debugging > Pair device). The phone must trust this PC over Wi-Fi.
2. Run `py -3.12 -m autowirelessadb status`. This creates the config file.
3. Add your home network: `py -3.12 -m autowirelessadb allow "MyHomeWifi"`.
   (Or edit the file that `config-path` shows.) Run this in your own
   terminal, not from a sandboxed tool, so the real config file changes.
4. Run `py -3.12 -m autowirelessadb connect` to test one pass.
5. Run `py -3.12 -m autowirelessadb install-startup` to start the watcher at
   logon. This adds `AutoWirelessADB.lnk` to your Startup folder (no admin
   rights, no console window).

## Commands

| Command | What it does |
| --- | --- |
| `watch` | Run the watcher loop. Logs go to `%LOCALAPPDATA%\AutoWirelessADB\watch.log`. |
| `connect` | Do one check now. |
| `status` | Show the state. Read-only: it changes nothing. |
| `off` | Set `adb_wifi_enabled 0`, reset legacy tcpip mode, disconnect. |
| `install-startup` / `uninstall-startup` | Add or remove the Startup folder shortcut. |
| `allow <SSID>` | Add a Wi-Fi network to the allowlist (exact name). |
| `config-path` | Print the config file path. |

Global flags: `--config <path>`, `-v`, `--fallback-tcpip`.

## Security notes

- `adb shell` on a rooted phone is root. Keep `allowed_ssids` short.
- `--fallback-tcpip` (or `fallback_tcpip = true`) uses `adb tcpip 5555`. That
  link is not encrypted. Keep it off unless TLS fails.
- On Windows 11 24H2 and later, `netsh` hides the SSID if location access is
  off for desktop apps. The watcher then sees no SSID and does nothing.
- The config and logs live in `%APPDATA%` and `%LOCALAPPDATA%`, not in the repo.

## Tests

```powershell
py -3.12 -m pytest -q
```

The tests use a fake phone, a fake `adb` and a fake `netsh`. They need no device.
