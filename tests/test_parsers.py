from autowirelessadb import adb, config, notify, startup, wifi
from autowirelessadb.runner import Result


NETSH_REAL = """
There is 1 interface on the system:

    Name                   : Wi-Fi
    Description            : Intel(R) Wi-Fi 6E AX211 160MHz
    State                  : connected
    SSID                   : Pribadi
    AP BSSID               : ec:e7:a2:43:5f:48
    Band                   : 2.4 GHz
    Profile                : Pribadi
"""


def test_parse_ssid_ignores_bssid():
    assert wifi.parse_ssid(NETSH_REAL) == "Pribadi"


def test_parse_ssid_disconnected():
    text = NETSH_REAL.replace("State                  : connected", "State                  : disconnected")
    assert wifi.parse_ssid(text) is None


def test_parse_ssid_hidden_by_location_privacy():
    text = "Network shell commands need location permission to access WLAN information."
    assert wifi.parse_ssid(text) is None
    assert wifi.location_blocked(text)


def test_current_ssid_netsh_failure():
    assert wifi.current_ssid(lambda a, t: Result(1, "")) is None


def test_no_ssid_reason_logged_once(caplog):
    wifi._last_problem = None
    text = "Network shell commands need location permission to access WLAN information."
    with caplog.at_level("WARNING"):
        for _ in range(3):
            assert wifi.current_ssid(lambda a, t: Result(0, text)) is None
    msgs = [r.getMessage() for r in caplog.records if "no SSID" in r.getMessage()]
    assert msgs == ["no SSID: netsh hides the SSID: location access is off for desktop apps"]
    wifi.current_ssid(lambda a, t: Result(0, NETSH_REAL))
    assert wifi._last_problem is None


def test_explain_netsh_failure():
    assert "exit 1" in wifi.explain(Result(1, "", "The Wireless AutoConfig Service (wlansvc) is not running."))


def test_ssid_with_spaces():
    text = NETSH_REAL.replace("SSID                   : Pribadi", "SSID                   : My Home 5G")
    assert wifi.parse_ssid(text) == "My Home 5G"


def test_parse_devices():
    text = (
        "List of devices attached\n"
        "RRCY1032Y6F\tdevice\n"
        "192.168.1.6:38605\tdevice\n"
        "emulator-5554\toffline\n"
    )
    assert adb.parse_devices(text) == {
        "RRCY1032Y6F": "device",
        "192.168.1.6:38605": "device",
        "emulator-5554": "offline",
    }


def test_parse_mdns_and_pick_own_serial():
    text = (
        "List of discovered mdns services\n"
        "adb-OTHER-abc\t_adb-tls-connect._tcp\t192.168.1.9:41111\n"
        "adb-RRCY1032Y6F-Wj1Car\t_adb._tcp\t192.168.1.6:5555\n"
        "adb-RRCY1032Y6F-Wj1Car\t_adb-tls-connect._tcp\t192.168.1.6:38605\n"
    )
    services = adb.parse_mdns(text)
    assert len(services) == 3
    assert adb.tls_endpoint_for(services, "RRCY1032Y6F") == "192.168.1.6:38605"
    assert adb.tls_endpoint_for(services, "NOPE") is None


def test_is_network_serial():
    assert adb.is_network_serial("192.168.1.6:38605")
    assert adb.is_network_serial("adb-RRCY1032Y6F-Wj1Car._adb-tls-connect._tcp")
    assert not adb.is_network_serial("RRCY1032Y6F")


def test_device_commands_always_pass_serial():
    calls = []

    def run(args, timeout):
        calls.append(list(args))
        return Result(0, "")

    a = adb.Adb("adb.exe", run)
    a.set_wifi_debugging("RRCY1032Y6F", True)
    a.responds("RRCY1032Y6F")
    a.phone_ssid("RRCY1032Y6F")
    a.tcpip("RRCY1032Y6F")
    for c in calls:
        assert c[1:3] == ["-s", "RRCY1032Y6F"], c
    assert calls[0][3:] == ["shell", "settings", "put", "global", "adb_wifi_enabled", "1"]


def test_connect_failure_text_is_not_success():
    a = adb.Adb("adb.exe", lambda args, t: Result(0, "failed to connect to 1.2.3.4:5\n"))
    assert not a.connect("1.2.3.4:5")


def test_config_defaults_and_allowlist(tmp_path):
    p = tmp_path / "config.toml"
    cfg = config.load(p)
    assert p.exists()
    assert cfg.allowed_ssids == []
    assert cfg.fallback_tcpip is False
    assert not cfg.ssid_allowed("Anything")
    assert not cfg.ssid_allowed(None)
    p.write_text('allowed_ssids = ["HomeNet"]\nserial = "X1"\n', encoding="utf-8")
    cfg = config.load(p)
    assert cfg.serial == "X1"
    assert cfg.ssid_allowed("HomeNet")
    assert not cfg.ssid_allowed("homenet")  # exact match only


def test_toast_script_escapes():
    s = notify.build_script("A & B", "it's <ok>")
    assert "A &amp; B" in s
    assert "it''s &lt;ok&gt;" in s


def test_startup_command(tmp_path):
    exe = tmp_path / "python.exe"
    exe.write_text("")
    (tmp_path / "pythonw.exe").write_text("")
    cmd = startup.task_command(str(exe), tmp_path / "awadb_watch.pyw")
    assert "pythonw.exe" in cmd and "awadb_watch.pyw" in cmd


def test_startup_install_writes_shortcut(tmp_path):
    calls = []
    lnk = tmp_path / "Startup" / "AutoWirelessADB.lnk"
    res = startup.install(lambda a, t: calls.append(list(a)) or Result(0, ""), lnk=lnk)
    assert res.ok
    script = calls[0][-1]
    assert calls[0][0] == "powershell.exe"
    assert "CreateShortcut" in script and str(lnk) in script
    assert "awadb_watch.pyw" in script


def test_startup_uninstall(tmp_path):
    lnk = tmp_path / "x.lnk"
    lnk.write_text("")
    assert startup.uninstall(lnk).ok
    assert not lnk.exists()
    assert startup.uninstall(lnk).ok  # second call is harmless


def test_post_notification_quotes_text():
    calls = []

    def run(args, timeout):
        calls.append(list(args))
        return Result(0, "posting for user 0:")

    a = adb.Adb("adb.exe", run)
    assert a.post_notification("RRCY1032Y6F", "It's on", "Safe; unplug $USB")
    script = calls[0][-1]
    assert calls[0][1:4] == ["-s", "RRCY1032Y6F", "shell"]
    # Text must stay inert in the phone shell: no bare $ or ; outside quotes.
    import shlex
    inner = list(shlex.shlex(script, posix=True, punctuation_chars=True))
    assert "Safe; unplug $USB" in shlex.split(inner[inner.index("-c") + 1])
