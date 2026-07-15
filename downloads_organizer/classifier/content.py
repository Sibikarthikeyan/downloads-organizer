"""Classify files by content (magic bytes) when the extension says nothing.

Runs after the extension classifier, so it only sees files with missing or
unrecognized extensions. Uses python-magic (libmagic) when installed;
otherwise falls back to a small built-in signature table, so the feature
works with zero extra dependencies.
"""

from __future__ import annotations

import logging
from pathlib import Path

from downloads_organizer.classifier.base import Classification, Classifier

log = logging.getLogger("downloads_organizer.classifier")

try:  # optional dependency
    import magic as _magic  # type: ignore[import-not-found]

    _MIME = _magic.Magic(mime=True)
except Exception:  # pragma: no cover - depends on host packages
    _MIME = None

#: MIME prefix/type -> category name (used only if the category is configured).
_MIME_CATEGORIES: list[tuple[str, str]] = [
    ("image/", "Images"),
    ("video/", "Videos"),
    ("audio/", "Audio"),
    ("application/pdf", "Documents"),
    ("application/zip", "Archives"),
    ("application/x-tar", "Archives"),
    ("application/gzip", "Archives"),
    ("application/x-7z-compressed", "Archives"),
    ("application/x-rar", "Archives"),
    ("application/x-executable", "Programs"),
    ("application/x-sharedlib", "Programs"),
    ("application/vnd.debian.binary-package", "Programs"),
    ("application/x-sqlite3", "Robotics/Data"),
    ("text/", "Documents"),
]

#: Fallback signatures when libmagic is unavailable: (offset, bytes, mime).
_SIGNATURES: list[tuple[int, bytes, str]] = [
    (0, b"%PDF", "application/pdf"),
    (0, b"\x89PNG\r\n\x1a\n", "image/png"),
    (0, b"\xff\xd8\xff", "image/jpeg"),
    (0, b"GIF8", "image/gif"),
    (0, b"PK\x03\x04", "application/zip"),
    (0, b"\x1f\x8b", "application/gzip"),
    (0, b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
    (0, b"Rar!", "application/x-rar"),
    (0, b"\x7fELF", "application/x-executable"),
    (0, b"SQLite format 3\x00", "application/x-sqlite3"),
    (0, b"ID3", "audio/mpeg"),
    (4, b"ftyp", "video/mp4"),
    (257, b"ustar", "application/x-tar"),
]


def _sniff_mime(path: Path) -> str | None:
    if _MIME is not None:
        try:
            return _MIME.from_file(str(path))
        except Exception as exc:
            log.debug("libmagic failed on %s: %s", path.name, exc)
    try:
        with path.open("rb") as fh:
            header = fh.read(512)
    except OSError:
        return None
    for offset, signature, mime in _SIGNATURES:
        if header[offset : offset + len(signature)] == signature:
            return mime
    return None


class ContentTypeClassifier(Classifier):
    def __init__(self, categories: dict[str, list[str]]) -> None:
        #: Only route to categories the user actually configured.
        self._known = set(categories)

    def classify(self, path: Path) -> Classification | None:
        mime = _sniff_mime(path)
        if mime is None:
            return None
        for prefix, category in _MIME_CATEGORIES:
            if mime.startswith(prefix) and category in self._known:
                return Classification(category=category, reason=f"content type {mime}")
        return None
