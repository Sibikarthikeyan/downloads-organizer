"""Shared fixtures: a mock Downloads folder and a ready-made config."""

from __future__ import annotations

from pathlib import Path

import pytest

from downloads_organizer.config.schema import DEFAULT_CATEGORIES, AppConfig, FilenameRule, NotificationConfig


@pytest.fixture
def downloads(tmp_path: Path) -> Path:
    folder = tmp_path / "Downloads"
    folder.mkdir()
    return folder


@pytest.fixture
def config(downloads: Path, tmp_path: Path) -> AppConfig:
    cfg = AppConfig(
        watch_folder=downloads,
        categories={name: list(exts) for name, exts in DEFAULT_CATEGORIES.items()},
        filename_rules=[
            FilenameRule(pattern="invoice*", destination="Bills"),
            FilenameRule(pattern="screenshot*", destination="Screenshots"),
        ],
        notifications=NotificationConfig(enabled=False),
    )
    cfg.stability.stable_seconds = 0.2
    cfg.stability.poll_interval = 0.05
    cfg.journal.path = tmp_path / "journal.jsonl"  # never touch the real journal
    return cfg


def make_file(folder: Path, name: str, content: bytes = b"data") -> Path:
    path = folder / name
    path.write_bytes(content)
    return path
