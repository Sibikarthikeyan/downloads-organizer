"""Classify files by extension using the configured category map."""

from __future__ import annotations

from pathlib import Path

from downloads_organizer.classifier.base import Classification, Classifier


class ExtensionClassifier(Classifier):
    """Map file extensions to category folders.

    Compound archive extensions like ``.tar.gz`` are matched against their
    final component (``gz``), which the default config routes to Archives.
    """

    def __init__(self, categories: dict[str, list[str]]) -> None:
        self._by_extension: dict[str, str] = {}
        for category, extensions in categories.items():
            for ext in extensions:
                self._by_extension[ext.lower().lstrip(".")] = category

    def classify(self, path: Path) -> Classification | None:
        extension = path.suffix.lower().lstrip(".")
        if not extension:
            return None
        category = self._by_extension.get(extension)
        if category is None:
            return None
        return Classification(category=category, reason=f"extension .{extension}")
