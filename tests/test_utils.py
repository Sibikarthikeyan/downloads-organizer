"""Unit tests for filesystem helpers."""

from pathlib import Path

from downloads_organizer.utils.fsutils import is_temp_download, matches_any, sanitize_filename, unique_path


def test_is_temp_download() -> None:
    exts = (".crdownload", ".part")
    assert is_temp_download(Path("a.pdf.crdownload"), exts)
    assert is_temp_download(Path("A.PDF.CRDOWNLOAD"), exts)
    assert not is_temp_download(Path("a.pdf"), exts)


def test_matches_any_is_case_insensitive() -> None:
    assert matches_any("FILE.TMP", ["*.tmp"])
    assert matches_any(".hidden", [".*"])
    assert not matches_any("file.txt", ["*.tmp", ".*"])


def test_sanitize_filename() -> None:
    assert sanitize_filename("bad\x00name.txt") == "bad_name.txt"
    assert sanitize_filename("a/b.txt") == "a_b.txt"
    assert sanitize_filename("   ") == "unnamed"
    assert sanitize_filename("fine.pdf") == "fine.pdf"


def test_unique_path(tmp_path: Path) -> None:
    target = tmp_path / "a.pdf"
    assert unique_path(target) == target
    target.touch()
    assert unique_path(target) == tmp_path / "a (1).pdf"
    (tmp_path / "a (1).pdf").touch()
    assert unique_path(target) == tmp_path / "a (2).pdf"
