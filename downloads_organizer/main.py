"""Command-line interface.

Usage:
    downloads-organizer run            # watch continuously (foreground)
    downloads-organizer once           # organize existing files and exit
    downloads-organizer once --dry-run # preview without moving anything
    downloads-organizer undo [N]       # move the last N organized files back
    downloads-organizer stats          # statistics from the move journal
    downloads-organizer init-config    # write an annotated default config
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from downloads_organizer import __version__
from downloads_organizer.app import Application
from downloads_organizer.config.loader import DEFAULT_CONFIG_PATH, ConfigError, load_config, write_default_config
from downloads_organizer.journal.journal import Journal
from downloads_organizer.journal.stats import render_stats
from downloads_organizer.journal.undo import undo_last


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="downloads-organizer",
        description="Automatically organize your Downloads folder.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-c", "--config", type=Path, default=None,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Watch the Downloads folder continuously")
    once = sub.add_parser("once", help="Organize existing files once and exit")
    for p in (run, once):
        p.add_argument("--watch-folder", type=Path, default=None, help="Override the watched folder")
        p.add_argument("--dry-run", action="store_true", help="Log actions without moving files")

    undo = sub.add_parser("undo", help="Move the most recently organized file(s) back")
    undo.add_argument("count", nargs="?", type=int, default=1, help="How many moves to undo (default: 1)")

    sub.add_parser("stats", help="Show statistics built from the move journal")

    init = sub.add_parser("init-config", help="Write the annotated default config file")
    init.add_argument("--force", action="store_true", help="Overwrite an existing config")
    return parser


def _run_undo(config_path: Path | None, count: int) -> int:
    config = load_config(config_path)
    journal = Journal(config.journal.path)
    results = undo_last(journal, count)
    if not results:
        print("Nothing to undo.")
        return 0
    failures = 0
    for result in results:
        name = Path(result.entry.destination).name
        if result.restored:
            print(f"Restored {name} -> {result.entry.source}")
        else:
            failures += 1
            print(f"Could not restore {name}: {result.detail}")
    return 1 if failures and failures == len(results) else 0


def _run_stats(config_path: Path | None) -> int:
    config = load_config(config_path)
    print(render_stats(Journal(config.journal.path)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init-config":
            target = write_default_config(args.config, overwrite=args.force)
            print(f"Wrote default config to {target}")
            return 0
        if args.command == "undo":
            return _run_undo(args.config, args.count)
        if args.command == "stats":
            return _run_stats(args.config)

        app = Application.from_config_file(
            args.config,
            watch_folder=args.watch_folder,
            dry_run=True if args.dry_run else None,
        )
        if args.command == "once":
            app.run_once()
        else:
            app.run_forever()
        return 0
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
