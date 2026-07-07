"""Run classifiers in priority order; first answer wins."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from downloads_organizer.classifier.base import Classification, Classifier

log = logging.getLogger("downloads_organizer.classifier")


class ClassifierChain(Classifier):
    """Try each classifier in order and fall back to ``fallback_category``.

    A crashing classifier is logged and skipped so one bad plugin can never
    stop files from being organized.
    """

    def __init__(self, classifiers: Sequence[Classifier], fallback_category: str) -> None:
        self._classifiers = list(classifiers)
        self._fallback = fallback_category

    def classify(self, path: Path) -> Classification:
        for classifier in self._classifiers:
            try:
                result = classifier.classify(path)
            except Exception:
                log.exception("Classifier %s failed on %s", type(classifier).__name__, path.name)
                continue
            if result is not None:
                return result
        return Classification(category=self._fallback, reason="no rule or extension matched")
