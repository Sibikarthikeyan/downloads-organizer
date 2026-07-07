# Downloads Organizer

An intelligent, event-driven organizer for your Ubuntu `~/Downloads` folder.
It watches for new files in real time (inotify via [watchdog]), waits until
downloads are actually finished, then sorts files into categorized folders —
with **full undo**, **routing by the website a file came from**, content-type
detection, statistics, desktop notifications, and a plugin system.

Supported: Ubuntu 22.04+ · Python 3.10+

## Why another file organizer?

| | Downloads Organizer | organize-tool | Hazel | typical sorter scripts |
|---|---|---|---|---|
| Real-time (inotify, zero idle CPU) | ✅ | ❌ batch/cron | ✅ | ❌ polling |
| Waits for downloads to finish | ✅ | ❌ | ✅ | ❌ |
| **Undo any move** | ✅ journal + `undo` | ❌ | ❌ | ❌ |
| **Route by source website** | ✅ browser xattrs | ❌ | partially | ❌ |
| Content detection (magic bytes) | ✅ | ✅ | ✅ | ❌ |
| Linux-native, free, open source | ✅ | ✅ | ❌ macOS, paid | ✅ |
| Plugin API | ✅ | ❌ | ❌ | ❌ |

### Designed around the real pain points of auto-organizers

- *"Where did my file go?!"* — every move is journaled;
  `downloads-organizer undo` puts the last file(s) back. Nothing is ever
  deleted.
- *"It moved my file while it was still downloading"* — temp extensions are
  ignored and files must hold a stable size before being touched.
- *"It guessed wrong"* — try `once --dry-run` first; every move logs *why*
  (which rule, extension, origin URL, or content type matched); URL rules
  give precision no filename can (`*arxiv.org*` → `Papers/`).
- *"Yet another config format to learn"* — works with **zero configuration**;
  the YAML file is optional and every key has a sane default.
- *"I don't trust a daemon in my home folder"* — event-driven (no polling),
  memory-capped systemd unit, rotating logs, full audit trail in the journal.

## Features

- **Real-time monitoring** — inotify events, no polling at idle (zero CPU).
- **Safe download detection** — ignores `.crdownload`/`.part`/`.download`
  files and only moves a file after its size has been stable for a
  configurable period.
- **Undo & statistics** — `undo [N]` reverses recent moves; `stats` shows
  totals, per-category sizes, top file types, and recent activity.
- **Source-URL routing** — browsers on Linux stamp downloads with their
  origin URL (`user.xdg.origin.url` xattr); route `github.com` files to
  `Code/`, `arxiv.org` PDFs to `Papers/`, regardless of filename.
- **Smart classification** — URL rules → filename rules (`invoice*` →
  `Bills/`) → extension mapping (`.pdf` → `Documents/`) → magic-byte content
  detection; only then `Unknown/`.
- **Robotics-aware** — `.pcd`/`.ply` point clouds, rosbags (`.db3`, `.mcap`,
  `.bag`), URDF/SDF models, maps, and SQLite databases sort into a nested
  `Robotics/` tree out of the box.
- **Duplicate handling** — `rename`, `skip`, `replace`, `keep_newest`, or
  `keep_oldest`.
- **Crash-proof** — every file is processed in isolation; permission errors,
  vanished files, and broken plugins are logged, never fatal.
- **Reboot recovery** — files that arrived while the service was down are
  organized during the startup scan.
- **YAML configuration**, desktop notifications, rotating logs, dry-run mode.

## Architecture

```
inotify event ──> queue ──> StabilityTracker ──> OrganizerPipeline
 (watchdog)      (worker      "is the download      │
                  thread)      finished?"           ├─ ignore filter (globs, hidden, managed folders)
                                                    ├─ ClassifierChain
                                                    │    1. plugins (priority < 100)
                                                    │    2. UrlRuleClassifier        (rules/url.py)
                                                    │    3. FilenameRuleClassifier   (rules/filename.py)
                                                    │    4. plugins (100–199)
                                                    │    5. ExtensionClassifier      (classifier/)
                                                    │    6. ContentTypeClassifier    (magic bytes)
                                                    │    7. plugins (≥ 200), else Unknown
                                                    ├─ plugin before_move (veto point)
                                                    ├─ FileMover (duplicate policy)  (mover/)
                                                    └─ Journal + Notifier + logger, plugin after_move
```

Modules are loosely coupled through small interfaces: anything with a
`classify(path) -> Classification | None` method is a classifier; the
pipeline only knows the `Notifier` protocol; the watcher only calls
`pipeline.should_process()` / `pipeline.process()`. Each piece is
independently unit-tested.

```
downloads_organizer/
├── watcher/         # inotify observer, worker thread, download-completion detection
├── classifier/      # Classification protocol, extension classifier, chain
├── rules/           # user-defined filename rules
├── mover/           # safe moves + duplicate policies
├── journal/         # move history, undo, statistics
├── config/          # YAML schema, loader, annotated default config
├── notifications/   # notify-send integration (graceful fallback)
├── logger/          # console + rotating file logging
├── plugins/         # plugin base class + registry
├── core/            # the pipeline tying it all together
├── utils/           # filesystem helpers
├── app.py           # wiring + signal handling
└── main.py          # CLI
```

## Installation

```bash
git clone https://github.com/you/downloads-organizer
cd downloads-organizer
pipx install .          # or: pip install --user .
```

For development:

```bash
python3 -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -e ".[dev]"
pytest
```

Desktop notifications use `notify-send`, preinstalled on Ubuntu
(`sudo apt install libnotify-bin` otherwise).

## Usage

```bash
downloads-organizer init-config        # write ~/.config/downloads-organizer/config.yaml
downloads-organizer once --dry-run     # preview what would happen
downloads-organizer once               # organize existing files, then exit
downloads-organizer run                # watch continuously (foreground)
downloads-organizer undo               # put the last organized file back
downloads-organizer undo 5             # ...or the last five
downloads-organizer stats              # totals, categories, top types, recent moves
```

Useful flags: `--config PATH`, `--watch-folder PATH`, `--dry-run`.

### Run in the background (systemd user service)

```bash
mkdir -p ~/.config/systemd/user
cp packaging/downloads-organizer.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now downloads-organizer
journalctl --user -u downloads-organizer -f     # follow logs
```

An optional desktop autostart entry is provided in
`packaging/downloads-organizer.desktop` (copy to `~/.config/autostart/`).

## Configuration

Everything lives in `~/.config/downloads-organizer/config.yaml`; every key
is optional. The annotated default (see
`downloads_organizer/config/default_config.yaml`) covers:

| Key | Purpose |
|---|---|
| `watch_folder` / `destination_root` | what to watch, where category folders go |
| `categories` | folder → extension list mapping; names may nest (`Robotics/PointClouds`) |
| `filename_rules` | ordered glob rules, evaluated before extensions |
| `url_rules` | glob rules against the download's origin URL, highest priority |
| `content_detection` | classify unknown files by magic bytes (`true` by default) |
| `journal` | move-history location powering `undo` and `stats` |
| `duplicate_policy` | `rename` \| `skip` \| `replace` \| `keep_newest` \| `keep_oldest` |
| `ignore_patterns` | globs never touched (default: `*.tmp`, `*.partial`, `.*`) |
| `stability` | download-completion detection tuning |
| `notifications`, `logging` | desktop notifications, log level/file/rotation |
| `plugins` | dotted paths of plugin classes to load |

Example rules:

```yaml
filename_rules:
  - {pattern: "invoice*",    destination: Bills}
  - {pattern: "resume*",     destination: Career}
  - {pattern: "screenshot*", destination: Screenshots}
  - {pattern: "lecture*",    destination: Lectures}
  - {pattern: "ros2*",       destination: Robotics/Docs}

url_rules:
  - {pattern: "*arxiv.org*",  destination: Papers}
  - {pattern: "*github.com*", destination: Code}
```

## Writing a plugin

Subclass `OrganizerPlugin`, override any hook, list the class in the config:

```python
# my_plugins.py (anywhere on PYTHONPATH)
from downloads_organizer.plugins import OrganizerPlugin
from downloads_organizer.classifier import Classification

class TaxDocuments(OrganizerPlugin):
    name = "tax-documents"
    priority = 50  # run before built-in filename rules

    def classify(self, path):
        if "tax" in path.name.lower():
            return Classification("Taxes", "tax plugin")
        return None
```

```yaml
plugins: ["my_plugins:TaxDocuments"]
```

Hooks: `classify` (propose destination — AI/OCR classification),
`before_move` (return `False` to veto — virus scanning), `after_move`
(cloud backup, compression, statistics). A crashing plugin is logged and
skipped; it can never take down the organizer.

## Testing

```bash
pytest            # 65 unit + integration tests
```

The integration tests spin up a real watchdog observer on a temporary mock
Downloads folder and simulate a browser download
(`report.pdf.crdownload` → write → rename to `report.pdf`).

## License

MIT

[watchdog]: https://github.com/gorakhargosh/watchdog
