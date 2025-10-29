"""Core orchestration and concurrency helpers."""

from __future__ import annotations

import logging
import os
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Dict, List, Optional, Tuple

from .config import DEFAULT_REFRESH_INTERVAL, RunConfig
from .io_csv import build_output_path, load_rows, save_rows
from .openai_client import OpenAI, call_openai, create_client
from .progress import build_logo_progress, refresh_progress_display

LOGGER = logging.getLogger(__name__)


def reformulate_rows(
    *,
    rows: List[Dict[str, str]],
    column: str,
    client: Optional[OpenAI],
    model: str,
    workers: int,
    max_retries: int,
    dry_run: bool = False,
    progress_interval: float = DEFAULT_REFRESH_INTERVAL,
) -> None:
    """Reformulate a specific column for the given rows in place."""
    total = len(rows)
    completed = 0

    def render_progress(current: int, maximum: int) -> str:
        ratio = 1.0 if maximum <= 0 else max(0.0, min(1.0, current / maximum))
        percent = ratio * 100
        logo_block = build_logo_progress(ratio)
        progress_text = f"[PROGRESS] {percent:6.2f}% ({current}/{maximum})"
        if not logo_block:
            return progress_text
        return f"{logo_block}\n{progress_text}"

    def process(index: int, text: str) -> Tuple[int, str]:
        if dry_run or not text.strip():
            return index, text
        if client is None:
            raise RuntimeError("Client OpenAI non initialisé.")
        rewritten = call_openai(client, model, text, max_retries=max_retries)
        return index, rewritten

    if total == 0:
        refresh_progress_display(render_progress(completed, total))
        return

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures: List[Future[Tuple[int, str]]] = []
        for idx, row in enumerate(rows):
            original = row.get(column, "")
            futures.append(executor.submit(process, idx, original))

        pending = set(futures)
        refresh_progress_display(render_progress(completed, total))

        while pending:
            done, pending = wait(pending, timeout=progress_interval, return_when=FIRST_COMPLETED)
            if not done:
                refresh_progress_display(render_progress(completed, total))
                continue

            for future in done:
                index, rewritten_text = future.result()
                rows[index][column] = rewritten_text
                completed += 1

            refresh_progress_display(render_progress(completed, total))


def run_with_args(
    *,
    input_path: str,
    output_path: Optional[str],
    column: str,
    model: str,
    workers: int,
    max_retries: int,
    limit_rows: Optional[int],
    dry_run: bool,
    delimiter: Optional[str],
) -> None:
    """Helper to build a RunConfig from primitives. Deprecated in favour of RunConfig directly."""
    run(
        RunConfig(
            input_path=input_path,
            output_path=build_output_path(input_path, output_path),
            column=column,
            model=model,
            workers=workers,
            max_retries=max_retries,
            limit_rows=limit_rows,
            dry_run=dry_run,
            delimiter=delimiter,
        )
    )


def run(config: RunConfig) -> None:
    """Execute the full CSV reformulation flow based on the provided configuration."""
    if not config.input_path:
        raise SystemExit("Option --input requise (ou utilisez --interactive pour l'assistant).")

    if not os.path.isfile(config.input_path):
        raise FileNotFoundError(f"Fichier introuvable: {config.input_path}")

    rows, headers, detected_delimiter = load_rows(config.input_path, config.delimiter)
    total_rows = len(rows)
    if config.column not in headers:
        raise ValueError(
            f"La colonne '{config.column}' n'existe pas dans le fichier. Colonnes disponibles: {', '.join(headers)}"
        )

    target_rows = rows
    if config.limit_rows is not None:
        if config.limit_rows < 1:
            raise ValueError("--limit-rows doit être supérieur ou égal à 1.")
        if config.limit_rows < total_rows:
            target_rows = rows[: config.limit_rows]
            LOGGER.info(
                "[INFO] Limite active: %s premières lignes traitées (sur %s).",
                len(target_rows),
                total_rows,
            )
        else:
            LOGGER.info("[INFO] Limite %s >= nombre de lignes (%s). Tout sera traité.", config.limit_rows, total_rows)

    LOGGER.info("[INFO] %s lignes chargées depuis %s.", len(target_rows), config.input_path)
    LOGGER.info("[INFO] Colonne ciblée: %s", config.column)
    if config.dry_run:
        LOGGER.info("[INFO] Mode dry-run activé: aucun appel API ne sera effectué.")

    client = None if config.dry_run else create_client()

    try:
        reformulate_rows(
            rows=target_rows,
            column=config.column,
            client=client,
            model=config.model,
            workers=max(1, config.workers),
            max_retries=config.max_retries,
            dry_run=config.dry_run,
        )
    except Exception as err:
        raise SystemExit(f"Erreur pendant la reformulation: {err}") from err

    delimiter_to_use = config.delimiter or detected_delimiter
    save_rows(config.output_path, headers, target_rows, delimiter=delimiter_to_use)
    LOGGER.info("[INFO] Fichier reformulé enregistré dans: %s", config.output_path)


__all__ = [
    "run",
    "run_with_args",
    "reformulate_rows",
]
