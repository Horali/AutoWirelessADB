"""Windows toast notifications with no extra packages (WinRT through PowerShell)."""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from . import runner as _runner

log = logging.getLogger(__name__)

# PowerShell's own AppUserModelID is registered on every Windows install.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_SCRIPT = """
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{title}</text><text>{body}</text></binding></visual></toast>')
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""


def build_script(title: str, body: str) -> str:
    def clean(s: str) -> str:
        # XML-escape, then double single quotes for the PowerShell string.
        return escape(s).replace("'", "''")

    return _SCRIPT.format(title=clean(title), body=clean(body), app_id=_APP_ID)


def toast(title: str, body: str, run: _runner.Runner = _runner.run) -> bool:
    res = run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", build_script(title, body)],
        15,
    )
    if not res.ok:
        log.warning("toast failed: %s", res.stderr.strip()[:200])
    return res.ok
