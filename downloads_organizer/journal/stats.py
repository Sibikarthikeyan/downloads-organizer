"""Aggregate the journal into a human-readable statistics report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from downloads_organizer.journal.journal import Journal, JournalEntry


def _fmt_size(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def _parse_ts(entry: JournalEntry) -> datetime | None:
    try:
        return datetime.fromisoformat(entry.timestamp)
    except ValueError:
        return None


def render_stats(journal: Journal) -> str:
    """Build the ``stats`` command output from the journal."""
    moves = [e for e in journal.read_all() if e.action == "move"]
    if not moves:
        return "No files organized yet. The journal is empty."

    now = datetime.now(timezone.utc)
    per_category: Counter[str] = Counter()
    bytes_per_category: Counter[str] = Counter()
    extensions: Counter[str] = Counter()
    last_day = last_week = 0

    for entry in moves:
        per_category[entry.category] += 1
        bytes_per_category[entry.category] += entry.size
        ext = Path(entry.destination).suffix.lower().lstrip(".") or "(none)"
        extensions[ext] += 1
        ts = _parse_ts(entry)
        if ts is not None:
            age = now - ts
            if age <= timedelta(days=1):
                last_day += 1
            if age <= timedelta(days=7):
                last_week += 1

    lines = [
        "Downloads Organizer — statistics",
        "=" * 40,
        f"Total files organized : {len(moves)}",
        f"Total data organized  : {_fmt_size(sum(e.size for e in moves))}",
        f"Last 24 hours         : {last_day}",
        f"Last 7 days           : {last_week}",
        "",
        "By category:",
    ]
    width = max(len(c) for c in per_category)
    for category, count in per_category.most_common():
        lines.append(f"  {category:<{width}}  {count:>5}  {_fmt_size(bytes_per_category[category]):>10}")

    lines += ["", "Top file types:"]
    for ext, count in extensions.most_common(10):
        lines.append(f"  .{ext:<10} {count:>5}")

    lines += ["", "Recent activity:"]
    for entry in moves[-10:][::-1]:
        name = Path(entry.destination).name
        lines.append(f"  {entry.timestamp}  {name} -> {entry.category}")
    return "\n".join(lines)
