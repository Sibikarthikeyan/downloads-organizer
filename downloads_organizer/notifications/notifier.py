"""Desktop notifications via ``notify-send``.

``notify-send`` (libnotify-bin) ships with stock Ubuntu, so no extra Python
dependency is needed. Failures are logged and swallowed — a broken
notification daemon must never stop file organization.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Protocol

from downloads_organizer.config.schema import NotificationConfig

log = logging.getLogger("downloads_organizer.notifications")


class Notifier(Protocol):
    def notify(self, title: str, body: str) -> None:
        ...


class NullNotifier:
    """Used when notifications are disabled or notify-send is unavailable."""

    def notify(self, title: str, body: str) -> None:  # noqa: D102
        pass


class DesktopNotifier:
    def __init__(self, timeout_ms: int = 5000) -> None:
        self._timeout_ms = timeout_ms

    def notify(self, title: str, body: str) -> None:
        try:
            subprocess.run(
                [
                    "notify-send",
                    "--app-name=Downloads Organizer",
                    f"--expire-time={self._timeout_ms}",
                    "--icon=folder-download",
                    title,
                    body,
                ],
                check=False,
                timeout=5,
                capture_output=True,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.debug("Notification failed: %s", exc)


def build_notifier(config: NotificationConfig) -> Notifier:
    if not config.enabled:
        return NullNotifier()
    if shutil.which("notify-send") is None:
        log.warning("notify-send not found; desktop notifications disabled")
        return NullNotifier()
    return DesktopNotifier(timeout_ms=config.timeout_ms)
