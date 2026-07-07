"""Filename-pattern classifier (runs before extension mapping).

Rules come from the ``filename_rules`` config section. Patterns are
case-insensitive globs; a pattern without a wildcard is treated as a prefix
match so ``pattern: invoice`` behaves like ``invoice*``.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Sequence

from downloads_organizer.classifier.base import Classification, Classifier
from downloads_organizer.config.schema import FilenameRule


class FilenameRuleClassifier(Classifier):
    def __init__(self, rules: Sequence[FilenameRule]) -> None:
        self._rules = [
            FilenameRule(pattern=self._normalize(rule.pattern), destination=rule.destination)
            for rule in rules
        ]

    @staticmethod
    def _normalize(pattern: str) -> str:
        lowered = pattern.lower()
        if not any(ch in lowered for ch in "*?["):
            lowered += "*"
        return lowered

    def classify(self, path: Path) -> Classification | None:
        name = path.name.lower()
        for rule in self._rules:
            if fnmatch.fnmatch(name, rule.pattern):
                return Classification(
                    category=rule.destination,
                    reason=f"filename rule '{rule.pattern}'",
                )
        return None
