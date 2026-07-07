"""Load and validate the YAML configuration file.

Missing keys fall back to defaults from :mod:`downloads_organizer.config.schema`,
so an empty (or absent) config file yields a fully working setup.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from downloads_organizer.config.schema import (
    DEFAULT_CATEGORIES,
    AppConfig,
    DuplicatePolicy,
    FilenameRule,
    JournalConfig,
    LoggingConfig,
    NotificationConfig,
    StabilityConfig,
)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "downloads-organizer" / "config.yaml"
_BUNDLED_DEFAULT = Path(__file__).with_name("default_config.yaml")


class ConfigError(Exception):
    """Raised when the configuration file is invalid."""


def load_config(path: Path | None = None) -> AppConfig:
    """Build an :class:`AppConfig` from ``path`` (or the default location).

    A missing file is not an error: defaults are used.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    raw: dict[str, Any] = {}
    if config_path.is_file():
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc
        if loaded is not None and not isinstance(loaded, dict):
            raise ConfigError(f"{config_path} must contain a YAML mapping at the top level")
        raw = loaded or {}
    return _build(raw)


def write_default_config(path: Path | None = None, overwrite: bool = False) -> Path:
    """Copy the annotated default config to ``path`` and return it."""
    target = path or DEFAULT_CONFIG_PATH
    if target.exists() and not overwrite:
        raise ConfigError(f"Refusing to overwrite existing config at {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_BUNDLED_DEFAULT, target)
    return target


def _build(raw: dict[str, Any]) -> AppConfig:
    config = AppConfig()

    if "watch_folder" in raw:
        config.watch_folder = Path(str(raw["watch_folder"])).expanduser()
    if raw.get("destination_root"):
        config.destination_root = Path(str(raw["destination_root"])).expanduser()

    config.categories = _parse_categories(raw.get("categories"))
    config.unknown_category = str(raw.get("unknown_category", config.unknown_category))
    config.filename_rules = _parse_rules(raw.get("filename_rules"), "filename_rules")
    config.url_rules = _parse_rules(raw.get("url_rules"), "url_rules")
    config.duplicate_policy = _parse_duplicate_policy(raw.get("duplicate_policy"))
    if "content_detection" in raw:
        config.content_detection = bool(raw["content_detection"])

    if "ignore_patterns" in raw:
        config.ignore_patterns = [str(p) for p in _require_list(raw["ignore_patterns"], "ignore_patterns")]
    if "organize_existing_on_start" in raw:
        config.organize_existing_on_start = bool(raw["organize_existing_on_start"])
    if "dry_run" in raw:
        config.dry_run = bool(raw["dry_run"])
    config.plugins = [str(p) for p in _require_list(raw.get("plugins", []), "plugins")]

    config.stability = _parse_section(raw.get("stability"), StabilityConfig, "stability")
    config.notifications = _parse_section(raw.get("notifications"), NotificationConfig, "notifications")
    config.logging = _parse_logging(raw.get("logging"))
    config.journal = _parse_journal(raw.get("journal"))
    return config


def _parse_categories(raw: Any) -> dict[str, list[str]]:
    if raw is None:
        return {name: list(exts) for name, exts in DEFAULT_CATEGORIES.items()}
    if not isinstance(raw, dict):
        raise ConfigError("'categories' must be a mapping of folder name -> extension list")
    categories: dict[str, list[str]] = {}
    for name, exts in raw.items():
        categories[str(name)] = [str(e).lower().lstrip(".") for e in _require_list(exts, f"categories.{name}")]
    return categories


def _parse_rules(raw: Any, name: str) -> list[FilenameRule]:
    if raw is None:
        return []
    rules: list[FilenameRule] = []
    for i, entry in enumerate(_require_list(raw, name)):
        if not isinstance(entry, dict) or "pattern" not in entry or "destination" not in entry:
            raise ConfigError(
                f"{name}[{i}] must be a mapping with 'pattern' and 'destination' keys"
            )
        rules.append(FilenameRule(pattern=str(entry["pattern"]), destination=str(entry["destination"])))
    return rules


def _parse_duplicate_policy(raw: Any) -> DuplicatePolicy:
    if raw is None:
        return DuplicatePolicy.RENAME
    try:
        return DuplicatePolicy(str(raw).lower())
    except ValueError as exc:
        valid = ", ".join(p.value for p in DuplicatePolicy)
        raise ConfigError(f"Unknown duplicate_policy '{raw}'. Valid values: {valid}") from exc


def _parse_section(raw: Any, cls: type, name: str) -> Any:
    """Instantiate dataclass ``cls`` from a mapping, ignoring unknown keys."""
    section = cls()
    if raw is None:
        return section
    if not isinstance(raw, dict):
        raise ConfigError(f"'{name}' must be a mapping")
    for key, value in raw.items():
        if key == "temp_extensions":
            value = tuple(str(v) if str(v).startswith(".") else f".{v}" for v in _require_list(value, key))
        if hasattr(section, str(key)):
            setattr(section, str(key), value)
    return section


def _parse_logging(raw: Any) -> LoggingConfig:
    section: LoggingConfig = _parse_section(raw, LoggingConfig, "logging")
    if section.file is not None:
        section.file = Path(str(section.file)).expanduser()
    return section


def _parse_journal(raw: Any) -> JournalConfig:
    section: JournalConfig = _parse_section(raw, JournalConfig, "journal")
    section.path = Path(str(section.path)).expanduser()
    return section


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"'{name}' must be a list")
    return value
