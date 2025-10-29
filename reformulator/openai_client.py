"""OpenAI client helpers."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, Iterable, List, Tuple

try:
    import openai
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit("Le paquet 'openai' est requis. Installez-le avec 'pip install openai'.") from exc

from .config import OPENAI_API_KEY_ENV


STRUCTURED_RESPONSE_FORMAT: Dict[str, Any] = {
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


def create_client() -> OpenAI:
    """Instantiate an OpenAI client using the configured API key."""
    api_key = os.getenv(OPENAI_API_KEY_ENV)
    if not api_key:
        raise EnvironmentError(f"La variable d'environnement {OPENAI_API_KEY_ENV} doit être définie.")
    return OpenAI(api_key=api_key)


def make_prompt(content: str) -> str:
    """Build the user prompt for the API call."""
    return (
        "Réécris le texte HTML suivant en français en conservant toutes les balises et le sens global. "
        "Varie la formulation pour éviter le contenu dupliqué, mais ne supprime aucune information utile.\n\n"
        f"Texte d'origine:\n{content}"
    )


def extract_rewritten_html(response: Any) -> str:
    """Extract the rewritten HTML from the OpenAI response object."""
    outputs = getattr(response, "output", None)
    if not outputs:
        raise ValueError("Réponse sans contenu exploitable.")

    for block in outputs:
        contents: Iterable[Any] = getattr(block, "content", None) or []
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
    *,
    max_retries: int = 5,
    backoff_base: float = 2.0,
) -> str:
    """Call the OpenAI Responses API until a payload is received or retries exhausted."""
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


__all__ = [
    "RETRYABLE_EXCEPTIONS",
    "STRUCTURED_RESPONSE_FORMAT",
    "call_openai",
    "create_client",
    "extract_rewritten_html",
    "make_prompt",
]
