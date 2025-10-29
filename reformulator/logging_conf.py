"""Centralised logging configuration."""

from __future__ import annotations

import logging
from typing import Optional


def configure_logging(level: int = logging.INFO, *, force: bool = False) -> None:
    """Configure root logging for the CLI."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        force=force,
    )


__all__ = ["configure_logging"]
