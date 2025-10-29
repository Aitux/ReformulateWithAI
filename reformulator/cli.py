"""Command line interface for the Reformulator application."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from typing import List, Optional

try:  # pragma: no cover - optional dependency
    from colorama import Fore, Style, init as colorama_init
except ImportError:  # pragma: no cover - optional dependency
    colorama_init = None
    Fore = None
    Style = None

from .config import DEFAULTS, OPENAI_API_KEY_ENV, RunConfig
from .core import run
from .io_csv import build_output_path
from .logging_conf import configure_logging
from .progress import clear_terminal, print_banner

STDOUT_IS_TTY = sys.stdout.isatty()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Réécrit la colonne moduledescription d'un CSV via l'API OpenAI en parallèle."
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Lance un assistant interactif pour configurer l'exécution.",
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Chemin vers le fichier CSV source.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Chemin du fichier CSV de sortie. Par défaut, ajoute '_rewritten' avant l'extension.",
    )
    parser.add_argument(
        "--column",
        "-c",
        default=DEFAULTS.column,
        help=f"Nom de la colonne à reformuler (défaut: {DEFAULTS.column}).",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULTS.model,
        help=f"Nom du modèle OpenAI à utiliser (défaut: {DEFAULTS.model}).",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=DEFAULTS.workers,
        help=f"Nombre de threads simultanés (défaut: {DEFAULTS.workers}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULTS.max_retries,
        help=f"Nombre maximum de tentatives par appel d'API (défaut: {DEFAULTS.max_retries}).",
    )
    parser.add_argument(
        "--limit-rows",
        "-n",
        type=int,
        help="Limite le traitement aux N premières lignes du CSV (teste l'API sur un petit échantillon).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ne contacte pas l'API. Utile pour tester les entrées/sorties.",
    )
    parser.add_argument(
        "--delimiter",
        help="Force le délimiteur utilisé pour lire/écrire le CSV (détection automatique sinon).",
    )
    return parser.parse_args(argv)


def mask_api_key(api_key: Optional[str]) -> str:
    """Return a masked representation of the API key."""
    if not api_key:
        return ""
    trimmed = api_key.strip()
    if not trimmed:
        return ""
    if len(trimmed) <= 4:
        return "*" * len(trimmed)
    if len(trimmed) <= 8:
        return trimmed[0] + "*" * (len(trimmed) - 2) + trimmed[-1]
    return f"{trimmed[:4]}...{trimmed[-2:]}"


def _interactive_configure(args: argparse.Namespace) -> RunConfig:
    """Interactive wizard returning a RunConfig."""
    current_key = os.getenv(OPENAI_API_KEY_ENV)

    if STDOUT_IS_TTY:
        if colorama_init and Fore is not None and Style is not None:
            colorama_init()
            color_reset = Style.RESET_ALL
            color_context = Fore.CYAN
            color_action = Fore.YELLOW
            color_error = Fore.RED
            color_success = Fore.GREEN
        else:
            color_reset = "\033[0m"
            color_context = "\033[36m"
            color_action = "\033[33m"
            color_error = "\033[31m"
            color_success = "\033[32m"
    else:
        color_reset = ""
        color_context = ""
        color_action = ""
        color_error = ""
        color_success = ""

    def colorize(text: str, color: str) -> str:
        if not color:
            return text
        return f"{color}{text}{color_reset}"

    def style_context(text: str) -> str:
        return colorize(text, color_context)

    def style_action(text: str) -> str:
        return colorize(text, color_action)

    def style_error(text: str) -> str:
        return colorize(text, color_error)

    def style_success(text: str) -> str:
        return colorize(text, color_success)

    def render_step(context_lines: List[str], error: Optional[str] = None) -> None:
        clear_terminal()
        print_banner()
        for line in context_lines:
            if line:
                print(style_context(line))
        if error:
            print(style_error(error))
        print()

    def render_summary(lines: List[str], error: Optional[str] = None) -> None:
        clear_terminal()
        print_banner()
        print(style_success("Récapitulatif de l'exécution:"))
        for line in lines:
            print(style_context(f"  - {line}"))
        if error:
            print(style_error(error))
        print()

    def confirm_settings(lines: List[str]) -> bool:
        while True:
            render_summary(lines)
            entered = input(style_action("Confirmer et lancer ? [O/n]: ")).strip().lower()
            if entered in {"", "o", "oui", "y", "yes"}:
                return True
            if entered in {"n", "non", "no"}:
                return False
            print(style_error("Réponse non reconnue. Répondez par O ou N."))

    def ask_api_key(initial_key: Optional[str]) -> str:
        error: Optional[str] = None
        current = initial_key
        while True:
            context_lines = [
                "Configurez la clé OpenAI utilisée pour authentifier les requêtes.",
                f"Clé détectée: {mask_api_key(current) or 'Aucune'}",
            ]
            render_step(context_lines, error)
            prompt = f"{OPENAI_API_KEY_ENV} (laisser vide pour conserver): "
            entered = getpass.getpass(style_action(prompt)).strip()
            if entered:
                os.environ[OPENAI_API_KEY_ENV] = entered
                return entered
            if current:
                return current
            error = "Une clé API est requise pour poursuivre."

    def ask_input_path(default: Optional[str]) -> str:
        error: Optional[str] = None
        while True:
            context_lines = [
                "Sélectionnez le fichier CSV d'entrée contenant la colonne à reformuler.",
                f"Valeur par défaut: {default}" if default else "Aucun chemin par défaut détecté.",
            ]
            render_step(context_lines, error)
            suffix = f" [{default}]" if default else ""
            entered = input(style_action(f"Chemin du CSV d'entrée{suffix}: ")).strip()
            candidate = entered or (default or "")
            if not candidate:
                error = "Un chemin de fichier est requis."
                continue
            if os.path.isfile(candidate):
                return candidate
            error = f"Fichier introuvable: {candidate}"

    def ask_output_path(input_path: str, provided_output: Optional[str]) -> str:
        default = provided_output or build_output_path(input_path, None)
        error: Optional[str] = None
        while True:
            context_lines = [
                "Indiquez le fichier de sortie qui recevra les descriptions reformulées.",
                f"Chemin suggéré: {default}",
            ]
            render_step(context_lines, error)
            suffix = f" [{default}]" if default else ""
            entered = input(style_action(f"Chemin du CSV de sortie{suffix}: ")).strip()
            candidate = entered or default
            if not candidate:
                error = "Un chemin de sortie est requis."
                continue
            parent = os.path.dirname(candidate) or "."
            if os.path.isdir(parent):
                return candidate
            error = f"Répertoire introuvable: {parent}"

    def ask_column(default: Optional[str]) -> str:
        fallback = default or DEFAULTS.column
        error: Optional[str] = None
        while True:
            context_lines = [
                "Saisissez le nom exact de la colonne à reformuler.",
                f"Valeur par défaut: {fallback}",
            ]
            render_step(context_lines, error)
            entered = input(style_action(f"Colonne à reformuler [{fallback}]: ")).strip()
            if entered:
                return entered
            if fallback:
                return fallback
            error = "Veuillez fournir le nom d'une colonne."

    def ask_model(default: Optional[str]) -> str:
        fallback = default or DEFAULTS.model
        context_lines = [
            "Choisissez le modèle OpenAI utilisé pour les réécritures.",
            f"Valeur par défaut: {fallback}",
        ]
        render_step(context_lines)
        entered = input(style_action(f"Modèle OpenAI [{fallback}]: ")).strip()
        return entered or fallback

    def ask_workers(default: int) -> int:
        error: Optional[str] = None
        while True:
            context_lines = [
                "Définissez le nombre de workers pour paralléliser les appels.",
                f"Valeur par défaut: {default}",
            ]
            render_step(context_lines, error)
            entered = input(style_action(f"Nombre de workers [{default}]: ")).strip()
            if not entered:
                return default
            try:
                value = int(entered)
            except ValueError:
                error = "Veuillez entrer un entier."
                continue
            if value < 1:
                error = "Veuillez entrer un entier supérieur ou égal à 1."
                continue
            return value

    def ask_max_retries(default: int) -> int:
        error: Optional[str] = None
        while True:
            context_lines = [
                "Fixez le nombre maximum de tentatives en cas d'erreur transitoire.",
                f"Valeur par défaut: {default}",
            ]
            render_step(context_lines, error)
            entered = input(style_action(f"Nombre maximum de tentatives [{default}]: ")).strip()
            if not entered:
                return default
            try:
                value = int(entered)
            except ValueError:
                error = "Veuillez entrer un entier."
                continue
            if value < 0:
                error = "Veuillez entrer un entier supérieur ou égal à 0."
                continue
            return value

    def ask_limit_rows(default: Optional[int]) -> Optional[int]:
        context_lines = [
            "Limitez éventuellement le nombre de lignes traitées pour un test rapide.",
            f"Valeur actuelle: {default}" if default else "Aucune limite spécifiée.",
        ]
        render_step(context_lines)
        entered = input(style_action("Nombre de lignes à traiter (laisser vide pour aucune): ")).strip()
        if not entered:
            return default
        try:
            value = int(entered)
        except ValueError:
            print(style_error("Veuillez entrer un entier valide."))  # simple message, ne relance pas tout
            return ask_limit_rows(default)
        if value < 1:
            print(style_error("La valeur doit être supérieure ou égale à 1."))
            return ask_limit_rows(default)
        return value

    def ask_dry_run(default: bool) -> bool:
        context_lines = [
            "Activez le mode dry-run pour éviter les appels API.",
            f"Valeur par défaut: {'oui' if default else 'non'}",
        ]
        render_step(context_lines)
        entered = input(style_action("Activer le dry-run ? [o/N]: ")).strip().lower()
        if not entered:
            return default
        return entered in {"o", "oui", "y", "yes"}

    api_key = ask_api_key(current_key)
    input_path = ask_input_path(args.input)
    output_path = ask_output_path(input_path, args.output)
    column = ask_column(args.column)
    model = ask_model(args.model)
    workers = ask_workers(args.workers or DEFAULTS.workers)
    max_retries = ask_max_retries(args.max_retries or DEFAULTS.max_retries)
    limit_rows = ask_limit_rows(args.limit_rows)
    dry_run = ask_dry_run(args.dry_run)

    summary_lines = [
        f"Fichier d'entrée : {input_path}",
        f"Fichier de sortie : {output_path}",
        f"Colonne : {column}",
        f"Modèle : {model}",
        f"Workers : {workers}",
        f"Max retries : {max_retries}",
        f"Limit rows : {limit_rows if limit_rows is not None else 'aucune'}",
        f"Dry-run : {'oui' if dry_run else 'non'}",
        f"Clé API : {mask_api_key(api_key)}",
    ]

    if not confirm_settings(summary_lines):
        raise SystemExit("Exécution annulée par l'utilisateur.")
    return RunConfig(
        input_path=input_path,
        output_path=output_path,
        column=column,
        model=model,
        workers=workers,
        max_retries=max_retries,
        limit_rows=limit_rows,
        dry_run=dry_run,
    )


def args_to_config(args: argparse.Namespace) -> RunConfig:
    """Convert CLI args into a RunConfig."""
    if not args.input:
        raise SystemExit("Option --input requise (ou utilisez --interactive pour l'assistant).")
    output_path = build_output_path(args.input, args.output)
    return RunConfig(
        input_path=args.input,
        output_path=output_path,
        column=args.column,
        model=args.model,
        workers=args.workers,
        max_retries=args.max_retries,
        limit_rows=args.limit_rows,
        dry_run=args.dry_run,
        delimiter=args.delimiter,
    )


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the CLI."""
    configure_logging()
    args = parse_args(argv)
    clear_terminal()
    print_banner()

    if args.interactive:
        config = _interactive_configure(args)
    else:
        config = args_to_config(args)
    if config.delimiter is None:
        config.delimiter = args.delimiter
    run(config)


__all__ = ["main", "parse_args", "args_to_config"]
