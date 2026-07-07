"""Filesystem helpers used across modules."""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Iterable

_UNSAFE_CHARS = re.compile(r'[\x00-\x1f/\\]')

#: Extended attribute browsers use to record where a download came from.
ORIGIN_URL_XATTR = "user.xdg.origin.url"


def read_origin_url(path: Path) -> str | None:
    """Origin URL a browser stamped on the download, or ``None``."""
    try:
        return os.getxattr(path, ORIGIN_URL_XATTR).decode("utf-8", "replace")
    except OSError:
        return None


def is_temp_download(path: Path, temp_extensions: Iterable[str]) -> bool:
    """True if ``path`` looks like an in-flight download artifact."""
    name = path.name.lower()
    return any(name.endswith(ext.lower()) for ext in temp_extensions)


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    """Case-insensitive glob match of ``name`` against ``patterns``."""
    return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns)


def sanitize_filename(name: str) -> str:
    """Strip characters that are invalid or dangerous in a file name."""
    cleaned = _UNSAFE_CHARS.sub("_", name).strip()
    return cleaned or "unnamed"


def unique_path(path: Path) -> Path:
    """Return ``path`` or the first free ``name (n).ext`` variant."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(1, 10_000):
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not find a free name for {path}")
