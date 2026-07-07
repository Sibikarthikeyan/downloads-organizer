"""Load plugins from dotted paths listed in the config.

A plugin spec is ``"package.module:ClassName"``. Import or instantiation
errors are logged and the plugin is skipped — a bad plugin never prevents
startup.
"""

from __future__ import annotations

import importlib
import logging
from typing import Iterable

from downloads_organizer.plugins.base import OrganizerPlugin

log = logging.getLogger("downloads_organizer.plugins")


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[OrganizerPlugin] = []

    @property
    def plugins(self) -> list[OrganizerPlugin]:
        return list(self._plugins)

    def register(self, plugin: OrganizerPlugin) -> None:
        self._plugins.append(plugin)
        self._plugins.sort(key=lambda p: p.priority)

    def load_from_specs(self, specs: Iterable[str]) -> None:
        for spec in specs:
            try:
                module_name, _, class_name = spec.partition(":")
                if not class_name:
                    raise ValueError("plugin spec must look like 'package.module:ClassName'")
                module = importlib.import_module(module_name)
                plugin_cls = getattr(module, class_name)
                if not issubclass(plugin_cls, OrganizerPlugin):
                    raise TypeError(f"{spec} is not an OrganizerPlugin subclass")
                self.register(plugin_cls())
                log.info("Loaded plugin %s", spec)
            except Exception:
                log.exception("Failed to load plugin '%s'; skipping", spec)
