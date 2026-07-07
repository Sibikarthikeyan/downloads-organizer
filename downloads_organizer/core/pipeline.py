"""The organizer pipeline: ignore-filter -> classify -> move -> notify.

This is the single entry point the watcher (or a one-shot scan) feeds files
into. Every step is wrapped so an error with one file is logged and never
propagates — requirement: the application must not crash because of a
single file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from downloads_organizer.classifier.base import Classification
from downloads_organizer.classifier.chain import ClassifierChain
from downloads_organizer.classifier.content import ContentTypeClassifier
from downloads_organizer.classifier.extension import ExtensionClassifier
from downloads_organizer.config.schema import AppConfig
from downloads_organizer.journal.journal import Journal, JournalEntry
from downloads_organizer.mover.mover import FileMover, MoveResult
from downloads_organizer.notifications.notifier import Notifier, NullNotifier, build_notifier
from downloads_organizer.plugins.registry import PluginRegistry
from downloads_organizer.rules.filename import FilenameRuleClassifier
from downloads_organizer.rules.url import UrlRuleClassifier
from downloads_organizer.utils.fsutils import matches_any

log = logging.getLogger("downloads_organizer.pipeline")


class _PluginClassifier:
    """Adapts a plugin's classify hook to the Classifier protocol."""

    def __init__(self, plugin) -> None:  # noqa: ANN001 - OrganizerPlugin
        self._plugin = plugin

    def classify(self, path: Path) -> Classification | None:
        return self._plugin.classify(path)


class OrganizerPipeline:
    def __init__(
        self,
        config: AppConfig,
        registry: PluginRegistry | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self._config = config
        self._registry = registry or PluginRegistry()
        self._notifier = notifier if notifier is not None else build_notifier(config.notifications)

        classifiers: list = [_PluginClassifier(p) for p in self._registry.plugins if p.priority < 100]
        classifiers.append(UrlRuleClassifier(config.url_rules))
        classifiers.append(FilenameRuleClassifier(config.filename_rules))
        classifiers.extend(_PluginClassifier(p) for p in self._registry.plugins if 100 <= p.priority < 200)
        classifiers.append(ExtensionClassifier(config.categories))
        if config.content_detection:
            classifiers.append(ContentTypeClassifier(config.categories))
        classifiers.extend(_PluginClassifier(p) for p in self._registry.plugins if p.priority >= 200)
        self._chain = ClassifierChain(classifiers, fallback_category=config.unknown_category)

        self._mover = FileMover(
            destination_root=config.resolved_destination_root(),
            duplicate_policy=config.duplicate_policy,
            dry_run=config.dry_run,
        )
        self._journal = Journal(config.journal.path, enabled=config.journal.enabled and not config.dry_run)
        #: Top-level folders the organizer manages; files anywhere inside
        #: them (including nested categories) are never re-processed.
        self._managed_folders = config.category_folders()

    def should_process(self, path: Path) -> bool:
        """Filter out ignored, hidden, and already-organized files."""
        if not path.is_file():
            return False
        if matches_any(path.name, self._config.ignore_patterns):
            return False
        root = self._config.resolved_destination_root()
        try:
            relative = path.relative_to(root)
        except ValueError:
            return True
        return not (len(relative.parts) > 1 and relative.parts[0] in self._managed_folders)

    def process(self, path: Path) -> MoveResult | None:
        """Classify and move one file. Never raises."""
        try:
            if not self.should_process(path):
                log.debug("Ignoring %s", path)
                return None
            classification = self._chain.classify(path)
            for plugin in self._registry.plugins:
                try:
                    if not plugin.before_move(path, classification):
                        log.info("Plugin %s vetoed move of %s", plugin.name, path.name)
                        return None
                except Exception:
                    log.exception("Plugin %s before_move failed; continuing", plugin.name)

            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            result = self._mover.move(path, classification.category)
            self._report(result, classification)
            if result.moved and result.destination is not None and not self._config.dry_run:
                self._journal.record(
                    JournalEntry.move(path, result.destination, classification.category, classification.reason, size)
                )
                for plugin in self._registry.plugins:
                    try:
                        plugin.after_move(path, result.destination, classification)
                    except Exception:
                        log.exception("Plugin %s after_move failed", plugin.name)
            return result
        except PermissionError as exc:
            log.error("Permission denied for %s: %s", path, exc)
        except FileNotFoundError:
            log.warning("File vanished before it could be moved: %s", path)
        except OSError as exc:
            log.error("Filesystem error for %s: %s", path, exc)
        except Exception:
            log.exception("Unexpected error processing %s", path)
        return None

    def scan_existing(self) -> int:
        """Organize files already in the watch folder (startup / --once)."""
        count = 0
        try:
            entries = sorted(self._config.watch_folder.iterdir())
        except OSError as exc:
            log.error("Cannot read watch folder %s: %s", self._config.watch_folder, exc)
            return 0
        for entry in entries:
            result = self.process(entry)
            if result is not None and result.moved:
                count += 1
        return count

    def _report(self, result: MoveResult, classification: Classification) -> None:
        if result.moved and result.destination is not None:
            log.info(
                "%s -> %s (%s)%s",
                result.source,
                result.destination,
                classification.reason,
                " [dry run]" if self._config.dry_run else "",
            )
            self._notifier.notify(
                "Downloads Organizer",
                f"Moved {result.source.name} → {classification.category}",
            )
        else:
            log.info("Not moved: %s — %s", result.source.name, result.detail)
