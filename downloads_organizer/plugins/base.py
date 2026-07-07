"""Plugin base class.

A plugin subclasses :class:`OrganizerPlugin` and overrides any subset of the
hooks. Hooks cover the whole lifecycle of a file, which is enough to build
the envisioned extensions without core changes:

* ``classify`` — propose a destination (AI image classification, OCR sorting).
* ``before_move`` — veto or delay a move (virus scanning; return ``False`` to veto).
* ``after_move`` — react to a completed move (cloud backup, compression, stats).
"""

from __future__ import annotations

from pathlib import Path

from downloads_organizer.classifier.base import Classification


class OrganizerPlugin:
    """Base class for plugins. All hooks are optional no-ops."""

    #: Lower runs earlier; built-in filename rules use 100, extensions 200.
    priority: int = 150

    name: str = "plugin"

    def classify(self, path: Path) -> Classification | None:
        """Return a Classification to claim the file, or None to pass."""
        return None

    def before_move(self, path: Path, classification: Classification) -> bool:
        """Return False to prevent the move (file stays in the watch folder)."""
        return True

    def after_move(self, source: Path, destination: Path, classification: Classification) -> None:
        """Called after a successful move."""
