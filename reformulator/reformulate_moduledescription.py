# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "openai>=1.55.0",
# ]
# ///
"""Reformulates the moduledescription column of a CSV file using the OpenAI API.

Usage example:
    python reformulate_moduledescription.py --input gesform_export_formation_prod_20250925.csv

This script expects the environment variable OPENAI_API_KEY to be set before execution
and forces the OpenAI response into a structured JSON payload to réduire la variabilité.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import os
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional, Tuple

try:
    import openai
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit("Le paquet 'openai' est requis. Installez-le avec 'pip install openai'.") from exc

try:  # pragma: no cover - optional dependency
    from colorama import Fore, Style, init as colorama_init
except ImportError:  # pragma: no cover - optional dependency
    colorama_init = None
    Fore = None
    Style = None


DEFAULT_MODEL = "gpt-5-chat-latest"
DEFAULT_WORKERS = 5

ASCII_LOGO = (
    "                                                                                                                  %%%%%%%%%                                               \n"
    "                                                                                                                 %%%%%%%%%%%%                                             \n"
    "                                                                                                                %%%%%%%%%%%%%%                                            \n"
    "                                                                                                               %%%%%%%%% %%%%%%                                           \n"
    "                                                                                                              %%%%%%%%%   %%%%%%                                          \n"
    "                                              @@@        @@@         @@         @@@        @@@       @@@     %%%%%% %%%   %%%%%%                                          \n"
    "                                            @@@@@@@    @@@@@@@     @@@@@@@    @@@@@@@    @@@@@@@   @@@@@@@   %%%%%  %%%   %%%%%%                                          \n"
    "                                           @@@@@@@@@  @@@@@@@@@   @@@@@@@@@  @@@@@@@@@  @@@@@@@@@ @@@@@@@@@  %%%%%%%%%%     %%%%%                                         \n"
    "                                          @@@@   @@@  @@@   @@@@ @@@@   @@@ @@@@   @@@@@@@@   @@@@@@@   @@@ %%%%%%%%%%%      %%%%                                         \n"
    "                                          @@@     @@@@@@     @@@ @@@     @@ @@@     @@@@@@@       @@@       %%%%%%%%%%%     %%%%%                                         \n"
    "                                          @@      @@@@@@        @@@         @@@@@@@@@@@ @@@@@@@   @@@@@@@@  %%%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@      @@@@@@        @@@         @@@@@@@@@@@  @@@@@@@   @@@@@@@@ %%%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@@     @@@@@@     @@@ @@@     @@ @@@              @@@@      @@@@  %%%%%  %%%   %%%%%%%                                         \n"
    "                                          @@@@  @@@@@ @@@   @@@@ @@@@   @@@ @@@@   @@@  @@    @@@ @@    @@@  %%%%%  %%%   %%%%%%                                          \n"
    "                                           @@@@@@@@@@ @@@@@@@@@   @@@@@@@@@  @@@@@@@@@ @@@@@@@@@@@@@@@@@@@@  %%%%%  %%%   %%%%%%                                          \n"
    "                                            @@@@@@@@@  @@@@@@@    @@@@@@@@    @@@@@@@   @@@@@@@@  @@@@@@@@    %%%%%%%%%%%%%%%%%                                           \n"
    "                                              @@@  @     @@@        @@@        @@@@       @@@@      @@@@       %%%%%%%%%%%%%%%%                                           \n"
    "                                                                                                                %%%%%%%%%%%%%%                                            \n"
    "                                                                                                                 %%%%%%%%%%%%                                             \n"
    "                                                                                                                  %%%%%%%%%                                               "
)
CURRENT_YEAR = time.strftime("%Y")
BANNER_TEXT = f"{ASCII_LOGO}\n\n"
ASCII_LOGO_LINES = ASCII_LOGO.splitlines()
ASCII_LOGO_TOTAL_CHARS = sum(len(line) for line in ASCII_LOGO_LINES)

STDOUT_IS_TTY = sys.stdout.isatty()


def clear_terminal() -> None:
    if not STDOUT_IS_TTY:
        return
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()



def print_banner(*, flush: bool = True) -> None:
    print(BANNER_TEXT, end="", flush=flush)



def build_logo_progress(ratio: float) -> str:
    """Return an ASCII logo partially revealed according to the provided ratio."""
    if ASCII_LOGO_TOTAL_CHARS <= 0 or not ASCII_LOGO_LINES:
        return ""
    clamped_ratio = max(0.0, min(1.0, ratio))
    visible_chars = int(ASCII_LOGO_TOTAL_CHARS * clamped_ratio)
    if clamped_ratio > 0.0 and visible_chars == 0:
        visible_chars = 1
    visible_chars = min(ASCII_LOGO_TOTAL_CHARS, visible_chars)
    remaining = visible_chars
    rendered_lines: List[str] = []
    for line in ASCII_LOGO_LINES:
        line_length = len(line)
        if remaining <= 0:
            rendered_lines.append(" " * line_length)
            continue
        if remaining >= line_length:
            rendered_lines.append(line)
            remaining -= line_length
            continue
        rendered_lines.append(line[:remaining] + " " * (line_length - remaining))
        remaining = 0
    return "\n".join(rendered_lines)


def refresh_progress_display(progress_line: str) -> None:
    if not STDOUT_IS_TTY:
        print(progress_line, flush=True)
        return
    clear_terminal()
    print(progress_line, flush=True)


STRUCTURED_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "module_description_rewrite",
    "schema": {
        "type": "object",
        "properties": {
            "rewritten_html": {
                "type": "string",
                "description": "Version reformulee du contenu HTML d'origine.",
            }
        },
        "required": ["rewritten_html"],
        "additionalProperties": False,
    },
    "strict": True,
}
USE_RESPONSE_FORMAT = True
RESPONSE_FORMAT_LOCK = threading.Lock()

_RETRY_ERROR_CANDIDATES = [
    "RateLimitError",
    "ServiceUnavailableError",
    "APIError",
    "Timeout",
    "APITimeoutError",
]
_retryable: List[type] = []
for _name in _RETRY_ERROR_CANDIDATES:
    _exc = getattr(openai, _name, None)
    if _exc is None:
        _exc = getattr(getattr(openai, "error", object()), _name, None)
    if isinstance(_exc, type) and issubclass(_exc, Exception):
        _retryable.append(_exc)
RETRYABLE_EXCEPTIONS = tuple(_retryable) or (Exception,)


def parse_args() -> argparse.Namespace:
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
        default="moduledescription",
        help="Nom de la colonne à reformuler.",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=f"Nom du modèle OpenAI à utiliser (défaut: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Nombre de threads simultanés (défaut: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Nombre maximum de tentatives par appel d'API en cas d'erreur transitoire.",
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
    return parser.parse_args()


def build_output_path(input_path: str, provided_output: Optional[str]) -> str:
    if provided_output:
        return provided_output
    base, ext = os.path.splitext(input_path)
    ext = ext or ".csv"
    return f"{base}_rewritten{ext}"


def load_rows(path: str, delimiter: str = ";") -> Tuple[List[Dict[str, str]], List[str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=delimiter, quotechar='"')
        rows = list(reader)
        headers = reader.fieldnames
    if headers is None:
        raise ValueError("Impossible de déterminer les colonnes du CSV.")
    return rows, headers


def save_rows(path: str, headers: List[str], rows: List[Dict[str, str]], delimiter: str = ";") -> None:
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers, delimiter=delimiter, quotechar='"')
        writer.writeheader()
        writer.writerows(rows)


def mask_api_key(api_key: Optional[str]) -> str:
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


def interactive_configure(args: argparse.Namespace) -> argparse.Namespace:
    current_key = os.getenv("OPENAI_API_KEY")

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

    def ask_api_key(initial_key: Optional[str]) -> str:
        error: Optional[str] = None
        current = initial_key
        while True:
            context_lines = [
                "Configurez la clé OpenAI utilisée pour authentifier les requêtes.",
                f"Clé détectée: {mask_api_key(current) or 'Aucune'}",
            ]
            render_step(context_lines, error)
            prompt = "OPENAI_API_KEY (laisser vide pour conserver): "
            entered = getpass.getpass(style_action(prompt)).strip()
            if entered:
                os.environ["OPENAI_API_KEY"] = entered
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
        fallback = default or "moduledescription"
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
        fallback = default or DEFAULT_MODEL
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
        error: Optional[str] = None
        default_label = str(default) if default is not None else "aucune"
        while True:
            context_lines = [
                "Optionnel: limitez le nombre de lignes traitées pour les tests.",
                f"Valeur par défaut: {default_label}",
            ]
            render_step(context_lines, error)
            hint = f"[{default}]" if default is not None else "[laisser vide]"
            entered = input(style_action(f"Limite de lignes {hint}: ")).strip()
            if not entered:
                return default
            try:
                value = int(entered)
            except ValueError:
                error = "Veuillez entrer un entier ou laisser vide."
                continue
            if value < 1:
                error = "Veuillez entrer un entier supérieur ou égal à 1."
                continue
            return value

    def ask_dry_run(default: bool) -> bool:
        error: Optional[str] = None
        while True:
            context_lines = [
                "Activez le mode dry-run pour vérifier le flux sans appeler l'API.",
                f"Valeur actuelle: {'activé' if default else 'désactivé'}",
            ]
            render_step(context_lines, error)
            hint = "Y/n" if default else "y/N"
            choice = input(style_action(f"Activer le mode dry-run [{hint}]: ")).strip().lower()
            if not choice:
                return default
            if choice in {"y", "yes", "o", "oui"}:
                return True
            if choice in {"n", "no", "non"}:
                return False
            error = "Répondez par 'y' ou 'n'."

    def confirm_settings(lines: List[str]) -> bool:
        error: Optional[str] = None
        while True:
            render_summary(lines, error)
            choice = input(style_action("Lancer la reformulation ? [Y/n]: ")).strip().lower()
            if not choice:
                return True
            if choice in {"y", "yes", "o", "oui"}:
                return True
            if choice in {"n", "no", "non"}:
                return False
            error = "Répondez par 'y' ou 'n'."

    current_key = ask_api_key(current_key)
    args.input = ask_input_path(args.input)
    args.output = ask_output_path(args.input, args.output)
    args.column = ask_column(args.column)
    args.model = ask_model(args.model)
    args.workers = ask_workers(args.workers or DEFAULT_WORKERS)
    retries_default = args.max_retries if args.max_retries is not None else 5
    args.max_retries = ask_max_retries(retries_default)
    args.limit_rows = ask_limit_rows(args.limit_rows)
    args.dry_run = ask_dry_run(args.dry_run)

    summary_lines = [
        f"Input CSV : {args.input}",
        f"Output CSV : {args.output}",
        f"Colonne : {args.column}",
        f"Modèle : {args.model}",
        f"Workers : {args.workers}",
        f"Max retries : {args.max_retries}",
        f"Limit rows : {args.limit_rows if args.limit_rows is not None else 'aucune'}",
        f"Dry-run : {'oui' if args.dry_run else 'non'}",
    ]

    if not confirm_settings(summary_lines):
        raise SystemExit("Exécution annulée par l'utilisateur.")

    return args


def create_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("La variable d'environnement OPENAI_API_KEY doit être définie.")
    return OpenAI(api_key=api_key)


def make_prompt(content: str) -> str:
    return (
        "Réécris le texte HTML suivant en français en conservant toutes les balises et le sens global. "
        "Varie la formulation pour éviter le contenu dupliqué, mais ne supprime aucune information utile.\n\n"
        f"Texte d'origine:\n{content}"
    )


def extract_rewritten_html(response: Any) -> str:
    outputs = getattr(response, "output", None)
    if not outputs:
        raise ValueError("Réponse sans contenu exploitable.")

    for block in outputs:
        contents = getattr(block, "content", None) or []
        for content in contents:
            json_payload = getattr(content, "json", None)
            if isinstance(json_payload, dict):
                candidate = json_payload.get("rewritten_html")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
            text_payload = getattr(content, "text", None)
            if isinstance(text_payload, str) and text_payload.strip():
                try:
                    parsed = json.loads(text_payload)
                except json.JSONDecodeError:
                    continue
                candidate = parsed.get("rewritten_html")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()

    raise ValueError("Impossible d'extraire le champ 'rewritten_html' de la réponse.")


def call_openai(
    client: OpenAI,
    model: str,
    content: str,
    max_retries: int = 5,
    backoff_base: float = 2.0,
) -> str:
    global USE_RESPONSE_FORMAT
    attempt = 0
    while True:
        attempt += 1
        try:
            with RESPONSE_FORMAT_LOCK:
                use_structured_output = USE_RESPONSE_FORMAT
            request_kwargs: Dict[str, Any] = {}
            if use_structured_output:
                request_kwargs["text"] = {"format": STRUCTURED_RESPONSE_FORMAT}

            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Tu es un assistant qui reformule du contenu HTML en français. "
                                    "Tu conserves toutes les balises et la structure, tout en modifiant "
                                    "les phrases pour éviter le contenu dupliqué. "
                                    "Respecte strictement le format de sortie JSON contenant une seule "
                                    "clé 'rewritten_html'."
                                ),
                            }
                        ],
                    },
                    {"role": "user", "content": [{"type": "input_text", "text": make_prompt(content)}]},
                ],
                **request_kwargs,
            )
            rewritten = extract_rewritten_html(response)
            return rewritten
        except TypeError as err:
            message = str(err)
            if (
                use_structured_output
                and "unexpected keyword argument" in message
                and ("text" in message or "response_format" in message)
            ):
                with RESPONSE_FORMAT_LOCK:
                    if USE_RESPONSE_FORMAT:
                        USE_RESPONSE_FORMAT = False
                        print(
                            "[WARN] Le SDK OpenAI installé ne supporte pas le parametre 'text.format'. "
                            "Bascule vers un mode JSON assisté."
                        )
                continue
            raise
        except RETRYABLE_EXCEPTIONS as err:
            if attempt > max_retries:
                raise RuntimeError(f"Échec après {max_retries} tentatives: {err}") from err
            sleep_for = backoff_base ** attempt + (0.1 * attempt)
            print(f"[WARN] Tentative {attempt}/{max_retries} échouée ({err}). Nouvelle tentative dans {sleep_for:.1f}s.")
            time.sleep(sleep_for)
        except Exception:
            raise


def reformulate_rows(
    rows: List[Dict[str, str]],
    column: str,
    client: Optional[OpenAI],
    model: str,
    workers: int,
    max_retries: int,
    dry_run: bool = False,
) -> None:
    total = len(rows)
    completed = 0
    progress_interval = 1.0

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

    with ThreadPoolExecutor(max_workers=workers) as executor:
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


def main() -> None:
    args = parse_args()

    if args.interactive:
        args = interactive_configure(args)

    if not args.input:
        raise SystemExit("Option --input requise (ou utilisez --interactive pour l'assistant).")

    clear_terminal()
    print_banner()

    input_path = args.input
    output_path = build_output_path(input_path, args.output)

    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Fichier introuvable: {input_path}")

    rows, headers = load_rows(input_path)
    total_rows = len(rows)
    if args.column not in headers:
        raise ValueError(
            f"La colonne '{args.column}' n'existe pas dans le fichier. Colonnes disponibles: {', '.join(headers)}"
        )
    if args.limit_rows is not None:
        if args.limit_rows < 1:
            raise ValueError("--limit-rows doit être supérieur ou égal à 1.")
        if args.limit_rows < total_rows:
            rows = rows[: args.limit_rows]
        print(f"[INFO] Limite active: {len(rows)} premières lignes traitées (sur {total_rows}).")

    print(f"[INFO] {len(rows)} lignes chargées depuis {input_path}.")
    print(f"[INFO] Colonne ciblée: {args.column}")
    if args.dry_run:
        print("[INFO] Mode dry-run activé: aucun appel API ne sera effectué.")

    client = create_client() if not args.dry_run else None

    try:
        reformulate_rows(
            rows=rows,
            column=args.column,
            client=client,
            model=args.model,
            workers=max(1, args.workers),
            max_retries=args.max_retries,
            dry_run=args.dry_run,
        )
    except Exception as err:
        raise SystemExit(f"Erreur pendant la reformulation: {err}") from err

    save_rows(output_path, headers, rows)
    print(f"[INFO] Fichier reformulé enregistré dans: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Interruption utilisateur. Aucun fichier n'a été généré.", file=sys.stderr)
        sys.exit(130)
