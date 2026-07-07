"""Typed configuration schema.

Every tunable of the application lives in :class:`AppConfig`. The loader
builds instances of these dataclasses from YAML, applying defaults for any
missing keys so a partial user config is always valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DuplicatePolicy(str, Enum):
    """What to do when the destination file already exists."""

    RENAME = "rename"
    SKIP = "skip"
    REPLACE = "replace"
    KEEP_NEWEST = "keep_newest"
    KEEP_OLDEST = "keep_oldest"


@dataclass(frozen=True)
class FilenameRule:
    """Route files whose *name* matches a pattern to a destination folder.

    ``pattern`` is a case-insensitive glob (``fnmatch``) applied to the file
    name, e.g. ``"invoice*"`` or ``"Screenshot*.png"``.
    """

    pattern: str
    destination: str


@dataclass
class StabilityConfig:
    """Parameters for the download-completion detector."""

    #: File size/mtime must be unchanged for this many seconds before a
    #: file is considered fully downloaded.
    stable_seconds: float = 3.0
    #: How often pending files are re-checked.
    poll_interval: float = 1.0
    #: Give up on a file after this many seconds of instability.
    max_wait_seconds: float = 3600.0
    #: Extensions used by browsers/download managers for in-flight files.
    temp_extensions: tuple[str, ...] = (".crdownload", ".part", ".download", ".tmp", ".partial")


@dataclass
class NotificationConfig:
    enabled: bool = True
    #: Notification timeout in milliseconds (passed to notify-send).
    timeout_ms: int = 5000


@dataclass
class JournalConfig:
    """Move-history journal powering ``undo`` and ``stats``."""

    enabled: bool = True
    path: Path = field(
        default_factory=lambda: Path.home() / ".local" / "share" / "downloads-organizer" / "journal.jsonl"
    )


@dataclass
class LoggingConfig:
    #: ``None`` disables the file handler (console only).
    file: Path | None = None
    level: str = "INFO"
    max_bytes: int = 1_000_000
    backup_count: int = 5


@dataclass
class AppConfig:
    """Root configuration object."""

    watch_folder: Path = field(default_factory=lambda: Path.home() / "Downloads")
    #: Where categorized folders are created. Defaults to the watch folder.
    destination_root: Path | None = None
    #: Category name -> list of extensions (without dot, lowercase).
    categories: dict[str, list[str]] = field(default_factory=dict)
    #: Folder name for files no category matches.
    unknown_category: str = "Unknown"
    #: Filename rules, evaluated in order before extension mapping.
    filename_rules: list[FilenameRule] = field(default_factory=list)
    #: Source-URL rules, evaluated before filename rules. Patterns are globs
    #: matched against the download's origin URL (browser xattr).
    url_rules: list[FilenameRule] = field(default_factory=list)
    #: Classify extension-less/unknown files by magic bytes.
    content_detection: bool = True
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.RENAME
    #: Glob patterns of file names to leave untouched.
    ignore_patterns: list[str] = field(default_factory=lambda: ["*.tmp", "*.partial", ".*"])
    #: Organize files already present in the watch folder on startup.
    organize_existing_on_start: bool = True
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    journal: JournalConfig = field(default_factory=JournalConfig)
    #: Dotted paths of plugin classes to load, e.g.
    #: ``["my_pkg.plugins:OcrSorter"]``.
    plugins: list[str] = field(default_factory=list)
    #: When true, log intended actions without touching any file.
    dry_run: bool = False

    def resolved_destination_root(self) -> Path:
        return self.destination_root if self.destination_root is not None else self.watch_folder

    def category_folders(self) -> set[str]:
        """Top-level folder names the organizer itself creates/manages.

        Nested categories like ``Robotics/PointClouds`` contribute their
        first component so the whole subtree counts as managed.
        """
        destinations = set(self.categories) | {self.unknown_category}
        destinations.update(rule.destination for rule in self.filename_rules)
        destinations.update(rule.destination for rule in self.url_rules)
        return {Path(dest).parts[0] for dest in destinations if Path(dest).parts}


#: Built-in extension mapping used when the user config does not override it.
DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Documents": ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "odt", "rtf"],
    "Images": ["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "svg"],
    "Videos": ["mp4", "mkv", "avi", "mov", "webm"],
    "Audio": ["mp3", "wav", "flac", "aac", "ogg"],
    "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2", "xz"],
    "Programs": ["deb", "appimage", "run", "sh"],
    "Code": ["py", "cpp", "c", "h", "json", "yaml", "yml", "xml", "js", "ts", "html", "css"],
    "Datasets": ["csv", "parquet", "npy", "pkl"],
    "Robotics/PointClouds": ["pcd", "pcl", "ply"],
    "Robotics/Rosbags": ["bag", "db3", "mcap"],
    "Robotics/Models": ["urdf", "xacro", "sdf", "stl", "dae"],
    "Robotics/Maps": ["pgm"],
    "Robotics/Data": ["db", "sqlite", "sqlite3"],
}
