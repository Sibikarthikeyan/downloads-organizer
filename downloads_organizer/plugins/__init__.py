"""Plugin system: extend the organizer without modifying the core."""

from downloads_organizer.plugins.base import OrganizerPlugin
from downloads_organizer.plugins.registry import PluginRegistry

__all__ = ["OrganizerPlugin", "PluginRegistry"]
