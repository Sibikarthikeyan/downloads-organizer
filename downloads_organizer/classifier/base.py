"""Classifier protocol shared by built-in classifiers and plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Classification:
    """Result of classifying a file.

    ``category`` is the destination folder name (relative to the destination
    root); ``reason`` is a human-readable explanation used in logs and
    notifications.
    """

    category: str
    reason: str


@runtime_checkable
class Classifier(Protocol):
    """Anything that can propose a destination for a file.

    Returning ``None`` means "no opinion" — the next classifier in the chain
    gets a chance.
    """

    def classify(self, path: Path) -> Classification | None:
        ...
