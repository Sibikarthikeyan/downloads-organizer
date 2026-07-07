"""Route downloads by their *origin URL*.

Chromium- and Firefox-based browsers on Linux stamp downloaded files with
the extended attribute ``user.xdg.origin.url``. That lets rules like
"anything from arxiv.org goes to Papers" work regardless of filename —
something plain organizers cannot do. Files without the xattr (wget, scp,
USB copies) simply fall through to the next classifier.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Sequence

from downloads_organizer.classifier.base import Classification, Classifier
from downloads_organizer.config.schema import FilenameRule
from downloads_organizer.utils.fsutils import read_origin_url


class UrlRuleClassifier(Classifier):
    def __init__(self, rules: Sequence[FilenameRule]) -> None:
        self._rules = list(rules)

    def classify(self, path: Path) -> Classification | None:
        if not self._rules:
            return None
        url = read_origin_url(path)
        if not url:
            return None
        lowered = url.lower()
        for rule in self._rules:
            if fnmatch.fnmatch(lowered, rule.pattern.lower()):
                return Classification(
                    category=rule.destination,
                    reason=f"downloaded from {url}",
                )
        return None
