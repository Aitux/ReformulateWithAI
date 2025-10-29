"""CSV I/O helpers."""

from __future__ import annotations

import csv
import os
from typing import Dict, Iterable, List, Sequence, Tuple

from .config import DEFAULT_DELIMITER


PREFERRED_DELIMITERS: Sequence[str] = (";", ",", "\t", "|")


def detect_delimiter(path: str, *, fallback: str = DEFAULT_DELIMITER) -> str:
    """Attempt to infer the delimiter used by the CSV file."""
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            sample = handle.read(8192)
    except FileNotFoundError:
        raise
    except OSError:
        return fallback

    if not sample:
        return fallback

    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=PREFERRED_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        return fallback


def load_rows(path: str, delimiter: str | None = None) -> Tuple[List[Dict[str, str]], List[str], str]:
    """Load rows from a CSV file and return rows, headers, and the delimiter used."""
    actual_delimiter = delimiter or detect_delimiter(path)
    with open(path, "r", encoding="utf-8-sig", newline="") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=actual_delimiter, quotechar='"')
        rows = list(reader)
        headers = reader.fieldnames
    if headers is None:
        raise ValueError("Impossible de déterminer les colonnes du CSV.")
    return rows, headers, actual_delimiter


def save_rows(
    path: str,
    headers: Iterable[str],
    rows: Iterable[Dict[str, str]],
    *,
    delimiter: str = DEFAULT_DELIMITER,
) -> None:
    """Persist the given rows to disk."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=list(headers), delimiter=delimiter, quotechar='"')
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_output_path(input_path: str, provided_output: str | None) -> str:
    """Return the output file path based on the input path when none is provided."""
    if provided_output:
        return provided_output
    base, ext = os.path.splitext(input_path)
    ext = ext or ".csv"
    return f"{base}_rewritten{ext}"


__all__ = [
    "build_output_path",
    "detect_delimiter",
    "load_rows",
    "save_rows",
]
