"""Unit tests for filename-based routing rules."""

from pathlib import Path

from downloads_organizer.config.schema import FilenameRule
from downloads_organizer.rules.filename import FilenameRuleClassifier


def classify(rules: list[FilenameRule], name: str) -> str | None:
    result = FilenameRuleClassifier(rules).classify(Path(name))
    return result.category if result else None


def test_prompt_examples() -> None:
    rules = [
        FilenameRule("invoice*", "Bills"),
        FilenameRule("resume*", "Career"),
        FilenameRule("screenshot*", "Screenshots"),
        FilenameRule("lecture*", "Lectures"),
        FilenameRule("ros2*", "Robotics"),
    ]
    assert classify(rules, "Invoice_2026.pdf") == "Bills"
    assert classify(rules, "Resume.pdf") == "Career"
    assert classify(rules, "Screenshot_001.png") == "Screenshots"
    assert classify(rules, "Lecture_01.mp4") == "Lectures"
    assert classify(rules, "ROS2_Nav2.pdf") == "Robotics"
    assert classify(rules, "holiday.jpg") is None


def test_matching_is_case_insensitive() -> None:
    rules = [FilenameRule("INVOICE*", "Bills")]
    assert classify(rules, "invoice_final.pdf") == "Bills"


def test_plain_pattern_becomes_prefix_match() -> None:
    rules = [FilenameRule("invoice", "Bills")]
    assert classify(rules, "invoice_2026.pdf") == "Bills"


def test_first_matching_rule_wins() -> None:
    rules = [FilenameRule("invoice*", "Bills"), FilenameRule("invoice_2026*", "Archive2026")]
    assert classify(rules, "invoice_2026.pdf") == "Bills"
