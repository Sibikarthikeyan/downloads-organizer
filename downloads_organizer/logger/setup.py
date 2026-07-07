"""Configure application-wide logging with optional rotating file output."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from downloads_organizer.config.schema import LoggingConfig

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Set up the ``downloads_organizer`` logger tree and return its root."""
    logger = logging.getLogger("downloads_organizer")
    logger.setLevel(config.level.upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if config.file is not None:
        config.file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
