"""Logging setup for hn.fm."""

import logging
import sys
from typing import Optional


def setup_logger(level: str = "INFO", name: Optional[str] = None) -> logging.Logger:
    """Set up logging for the application.

    Args:
        level: Logging level
        name: Logger name

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name or __name__)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, level.upper()))
    return logger
