"""Configuration models and default constants for the Reformulator CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


DEFAULT_MODEL = "gpt-5-chat-latest"
DEFAULT_WORKERS = 5
DEFAULT_MAX_RETRIES = 5
DEFAULT_COLUMN = "moduledescription"
DEFAULT_DELIMITER = ";"
DEFAULT_REFRESH_INTERVAL = 1.0
DEFAULT_TARGET_LANGUAGE = "français"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


@dataclass(frozen=True, slots=True)
class DefaultsConfig:
    """Application defaults that may be reused across CLI helpers and orchestrators."""

    column: str = DEFAULT_COLUMN
    model: str = DEFAULT_MODEL
    workers: int = DEFAULT_WORKERS
    max_retries: int = DEFAULT_MAX_RETRIES
    delimiter: str = DEFAULT_DELIMITER
    dry_run: bool = False
    target_language: str = DEFAULT_TARGET_LANGUAGE


@dataclass(slots=True)
class RunConfig:
    """Concrete execution settings for a single Reformulator run."""

    input_path: str
    output_path: str
    column: str = DEFAULT_COLUMN
    model: str = DEFAULT_MODEL
    workers: int = DEFAULT_WORKERS
    max_retries: int = DEFAULT_MAX_RETRIES
    limit_rows: Optional[int] = None
    dry_run: bool = False
    delimiter: Optional[str] = None
    target_language: str = DEFAULT_TARGET_LANGUAGE


DEFAULTS = DefaultsConfig()


__all__ = [
    "DEFAULTS",
    "DefaultsConfig",
    "DEFAULT_COLUMN",
    "DEFAULT_DELIMITER",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MODEL",
    "DEFAULT_REFRESH_INTERVAL",
    "DEFAULT_TARGET_LANGUAGE",
    "DEFAULT_WORKERS",
    "OPENAI_API_KEY_ENV",
    "RunConfig",
]
