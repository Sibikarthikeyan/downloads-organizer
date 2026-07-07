"""Unit tests for the YAML config loader."""

from pathlib import Path

import pytest

from downloads_organizer.config.loader import ConfigError, load_config, write_default_config
from downloads_organizer.config.schema import DuplicatePolicy


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.yaml")
    assert config.watch_folder == Path.home() / "Downloads"
    assert config.duplicate_policy is DuplicatePolicy.RENAME
    assert "Documents" in config.categories


def test_partial_config_merges_with_defaults(tmp_path: Path) -> None:
    path = write(tmp_path, "watch_folder: /data/dl\nduplicate_policy: keep_newest\n")
    config = load_config(path)
    assert config.watch_folder == Path("/data/dl")
    assert config.duplicate_policy is DuplicatePolicy.KEEP_NEWEST
    assert config.categories  # defaults kept


def test_filename_rules_and_categories_parse(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
categories:
  Docs: [PDF, .txt]
filename_rules:
  - {pattern: "invoice*", destination: Bills}
stability:
  stable_seconds: 9
  temp_extensions: [crdownload, .part]
""",
    )
    config = load_config(path)
    assert config.categories == {"Docs": ["pdf", "txt"]}
    assert config.filename_rules[0].destination == "Bills"
    assert config.stability.stable_seconds == 9
    assert config.stability.temp_extensions == (".crdownload", ".part")


@pytest.mark.parametrize(
    "text",
    [
        "duplicate_policy: explode",
        "filename_rules: [{pattern: x}]",
        "categories: [not, a, mapping]",
        "- top level list",
    ],
)
def test_invalid_configs_raise(tmp_path: Path, text: str) -> None:
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, text))


def test_v02_sections_parse(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        """
url_rules:
  - {pattern: "*arxiv.org*", destination: Papers}
content_detection: false
journal:
  enabled: false
  path: ~/custom/journal.jsonl
""",
    )
    config = load_config(path)
    assert config.url_rules[0].destination == "Papers"
    assert config.content_detection is False
    assert config.journal.enabled is False
    assert config.journal.path == Path.home() / "custom" / "journal.jsonl"


def test_nested_categories_manage_top_level_folder(tmp_path: Path) -> None:
    config = load_config(tmp_path / "nope.yaml")
    assert "Robotics" in config.category_folders()
    assert "Robotics/PointClouds" not in config.category_folders()


def test_write_default_config_roundtrips(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "config.yaml"
    write_default_config(target)
    config = load_config(target)
    assert config.filename_rules  # bundled default has example rules
    with pytest.raises(ConfigError):
        write_default_config(target)  # refuses to overwrite
