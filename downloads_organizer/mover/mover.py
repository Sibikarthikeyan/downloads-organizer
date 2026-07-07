"""Move files into category folders, applying the duplicate policy.

Uses :func:`shutil.move` so moves work across filesystems (copy + delete
fallback). Destination folders are created on demand. The mover never
deletes a source file except under ``replace``/``keep_*`` policies where the
user explicitly opted in.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from downloads_organizer.config.schema import DuplicatePolicy
from downloads_organizer.utils.fsutils import sanitize_filename, unique_path

log = logging.getLogger("downloads_organizer.mover")


@dataclass(frozen=True)
class MoveResult:
    """Outcome of a move attempt."""

    moved: bool
    source: Path
    destination: Path | None
    detail: str


class FileMover:
    def __init__(
        self,
        destination_root: Path,
        duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME,
        dry_run: bool = False,
    ) -> None:
        self._root = destination_root
        self._policy = duplicate_policy
        self._dry_run = dry_run

    def move(self, source: Path, category: str) -> MoveResult:
        """Move ``source`` into ``<destination_root>/<category>/``."""
        target_dir = self._root / category
        target = target_dir / sanitize_filename(source.name)

        if target.exists():
            resolution = self._resolve_duplicate(source, target)
            if resolution is None:
                return MoveResult(False, source, None, f"skipped ({self._policy.value}): {target} exists")
            target = resolution

        if self._dry_run:
            return MoveResult(True, source, target, "dry run — not moved")

        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return MoveResult(True, source, target, f"moved to {target}")

    def _resolve_duplicate(self, source: Path, target: Path) -> Path | None:
        """Apply the duplicate policy. ``None`` means leave the source alone."""
        if self._policy is DuplicatePolicy.SKIP:
            return None
        if self._policy is DuplicatePolicy.RENAME:
            return unique_path(target)
        if self._policy is DuplicatePolicy.REPLACE:
            return target
        # keep_newest / keep_oldest: compare modification times.
        try:
            source_wins = source.stat().st_mtime > target.stat().st_mtime
        except OSError as exc:
            log.warning("Could not stat for duplicate comparison (%s); renaming instead", exc)
            return unique_path(target)
        if self._policy is DuplicatePolicy.KEEP_OLDEST:
            source_wins = not source_wins
        return target if source_wins else None
