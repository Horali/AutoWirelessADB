import pytest

from autowirelessadb import wifi
from autowirelessadb.adb import Adb
from autowirelessadb.config import Config
from autowirelessadb.core import Controller

from .fakes import ADB, SERIAL, Clock, FakePhone


def make(phone: FakePhone, **cfg_kw):
    cfg_kw.setdefault("notify_target", "pc")
    cfg = Config(serial=SERIAL, adb_path=ADB, allowed_ssids=["HomeNet"], enable_timeout=10, **cfg_kw)
    clock = Clock()
    toasts = []
    ctl = Controller(
        cfg,
        adb=Adb(ADB, phone),
        get_ssid=lambda: wifi.current_ssid(phone),
        toast=lambda t, b: toasts.append((t, b)),
        sleep=clock.sleep,
        clock=clock,
    )
    return ctl, toasts, clock


def enabled_writes(phone):
    return [c for c in phone.adb_calls() if "adb_wifi_enabled" in c and "put" in c]


def test_unlisted_wifi_never_enables():
    phone = FakePhone(pc_ssid="CoffeeShop")
    ctl, toasts, _ = make(phone)
    st = ctl.tick()
    assert not st.ssid_allowed
    assert enabled_writes(phone) == []
    assert not any(c[0] == "connect" for c in phone.adb_calls())
    assert toasts == []


def test_no_wifi_fails_closed():
    phone = FakePhone(pc_ssid=None)
    ctl, _, _ = make(phone)
    ctl.tick()
    assert enabled_writes(phone) == []


def test_usb_on_allowed_wifi_enables_connects_and_toasts():
    phone = FakePhone()
    ctl, toasts, _ = make(phone)
    st = ctl.tick()
    assert phone.wifi_enabled
    assert st.wireless == phone.endpoint
    assert phone.endpoint in phone.connected
    # It verified the link with a shell echo over the wireless serial.
    assert ["-s", phone.endpoint, "shell", "echo", "awadb-ok"] in phone.adb_calls()
    assert toasts == [("Wireless ADB connected", f"Safe to unplug USB. ({phone.endpoint})")]
    # Second tick: nothing new, no second toast.
    ctl.tick()
    assert len(toasts) == 1


def test_phone_on_other_wifi_is_not_enabled():
    phone = FakePhone(phone_ssid="Neighbour")
    ctl, _, _ = make(phone)
    ctl.tick()
    assert enabled_writes(phone) == []


def test_already_advertising_connects_without_usb():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, toasts, _ = make(phone)
    st = ctl.tick()
    assert st.wireless == phone.endpoint
    assert enabled_writes(phone) == []
    assert toasts == [("Wireless ADB connected", phone.endpoint)]


def test_ignores_other_phones_on_mdns():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, _, _ = make(phone)
    ctl.tick()
    assert ["connect", "192.168.1.50:40000"] not in phone.adb_calls()


def test_reconnects_when_port_rotates():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, _, _ = make(phone)
    ctl.tick()
    old = phone.endpoint
    phone.tls_port = 41234  # phone rotated its TLS port
    st = ctl.tick()
    assert st.wireless == phone.endpoint
    assert ["disconnect", old] in phone.adb_calls()
    assert old not in phone.connected


def test_reconnects_when_ip_changes():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, toasts, _ = make(phone)
    ctl.tick()
    phone.ip = "192.168.1.77"
    st = ctl.tick()
    assert st.wireless == "192.168.1.77:38605"
    assert len(toasts) == 2


def test_leaving_allowed_wifi_disconnects():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, _, _ = make(phone)
    ctl.tick()
    phone.pc_ssid = "Airport"
    st = ctl.tick()
    assert st.wireless is None
    assert phone.connected == set()


def test_tls_timeout_no_fallback_by_default():
    phone = FakePhone(advertise_after_enable=False)
    ctl, toasts, clock = make(phone)
    st = ctl.tick()
    assert st.wireless is None
    assert clock.t >= 10
    assert not any(c[-2:] == ["tcpip", "5555"] for c in phone.adb_calls())
    assert toasts == []


def test_tls_timeout_with_fallback_uses_tcpip():
    phone = FakePhone(advertise_after_enable=False)
    ctl, toasts, _ = make(phone, fallback_tcpip=True)
    st = ctl.tick()
    assert ["-s", SERIAL, "tcpip", "5555"] in phone.adb_calls()
    assert st.wireless == "192.168.1.6:5555"
    assert toasts


def test_enable_backoff_per_usb_session():
    phone = FakePhone(advertise_after_enable=False)
    ctl, _, clock = make(phone)
    ctl.tick()
    ctl.tick()  # within backoff window: no second attempt
    assert len(enabled_writes(phone)) == 1
    clock.t += 61
    ctl.tick()
    assert len(enabled_writes(phone)) == 2


def test_off_disables_and_resets_tcpip():
    phone = FakePhone(wifi_enabled=True, tcp_port="5555")
    ctl, _, _ = make(phone)
    ctl.tick()
    done = ctl.turn_off()
    assert not phone.wifi_enabled
    assert phone.tcp_port == ""
    assert phone.connected == set()
    assert "adb_wifi_enabled = 0" in done


def test_off_over_wireless_only():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, _, _ = make(phone)
    ctl.tick()
    ctl.turn_off()
    assert not phone.wifi_enabled
    assert ["-s", "192.168.1.6:38605", "shell", "settings", "put", "global", "adb_wifi_enabled", "0"] in phone.adb_calls()


def test_watch_survives_errors():
    phone = FakePhone()
    ctl, _, _ = make(phone)
    n = {"i": 0}

    def boom():
        n["i"] += 1
        raise RuntimeError("x")

    ctl.get_ssid = boom
    ctl.watch(stop=lambda: n["i"] >= 3)
    assert n["i"] == 3


@pytest.mark.parametrize("cmd", ["status", "off"])
def test_cli_parser(cmd):
    from autowirelessadb.cli import build_parser

    assert build_parser().parse_args([cmd]).cmd == cmd


def test_phone_notification_goes_over_wireless_link():
    phone = FakePhone()
    ctl, toasts, _ = make(phone, notify_target="phone")
    ctl.tick()
    assert toasts == []
    assert len(phone.notifications) == 1
    via, script = phone.notifications[0]
    assert via == phone.endpoint  # posted through the wireless link, not USB
    assert "su 2000 -c" in script and "cmd notification post" in script
    assert "Safe to unplug USB." in script


def test_phone_notification_failure_falls_back_to_pc():
    phone = FakePhone(notif_ok=False)
    ctl, toasts, _ = make(phone, notify_target="phone")
    ctl.tick()
    assert len(toasts) == 1


def test_notify_both():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, toasts, _ = make(phone, notify_target="both")
    ctl.tick()
    assert len(toasts) == 1 and len(phone.notifications) == 1


def test_notifications_off():
    phone = FakePhone(usb=False, wifi_enabled=True)
    ctl, toasts, _ = make(phone, notify_target="both", notifications=False)
    ctl.tick()
    assert toasts == [] and phone.notifications == []
