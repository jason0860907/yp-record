"""Logging setup using loguru."""
from __future__ import annotations

import sys
from loguru import logger


def get_logger(name: str):
    """Return a logger bound with module name."""
    return logger.bind(module=name)


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[module]}</cyan> - {message}",
    )
