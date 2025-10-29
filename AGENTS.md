# Repository Guidelines

## Project Structure & Module Organization
Source code lives in `reformulator/`, now split across dedicated modules (`cli.py`, `core.py`, `io_csv.py`, `openai_client.py`, etc.). `pyproject.toml` and `uv.lock` in the repo root pin Python 3.12 dependencies for reproducible `uv` environments. Docker assets (`Dockerfile`, `docker-compose.yml`) stay in the repo root with `README.md`. Keep bulk CSV inputs outside version control.

## Build, Test, and Development Commands
- `uv sync` (run at repo root): install the locked dependency set inside `.venv/`.
- `uv run reformulator --input sample.csv --dry-run`: validate parsing and CSV wiring without hitting l'API.
- `uv run reformulator --interactive`: launch the guided wizard; the screen clears between questions and color cues separate guidance from required input.
- `uv run reformulator --input sample.csv --output sample_rewritten.csv --workers 8`: run the threaded rewrite against the OpenAI API.
- `docker compose run --rm reformulator`: execute the same flow in the container; override `INPUT_CSV`/`OUTPUT_CSV` inline as needed.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and grouped imports. Continue using type hints and explicit `Optional`/`Tuple` usage. Module constants stay uppercase (`DEFAULT_MODEL`, `ASCII_LOGO`), functions remain snake_case, and CLI flags should mirror argument names. Extend argparse help strings and keep progress output human readable because the script often runs unattended.

## Python Implementation Guidelines
- **Naming**: Default to PEP 8 naming; choose verbs for functions (`rewrite_batch`), nouns for classes (`BatchRunner`), and reserve caps for module constants. Treat private helpers as internal (`_derive_prompt`) so the module surface stays intentional.
- **Structure**: Keep modules import-safe—no network calls, file writes, or log spam at import time. Split logic into focused files and wire them together via `__init__.py` exports only when the public API needs it. Prefer dependency injection over globals so threaded workers stay testable.
- **Comments & Docstrings**: Use PEP 257 single-line summaries plus context on *why* the code exists; skip restating the signature. Let type hints carry type info and only mention edge cases or invariants the function enforces.
- **Tests**: Use pytest `test_*` functions with descriptive names (`test_merges_partial_batches`). Keep coverage high by isolating side effects behind mocks/fakes, especially for OpenAI and filesystem calls. Ensure tests stay deterministic—freeze time, seed RNGs, and avoid wall-clock sleeps.
- **Tooling**: Run `black`, `ruff`, and `isort` together via pre-commit so style stays automated; fail the hook instead of fixing by hand. Gate merges with `mypy` to ensure type hints are trusted, not decorative.

## Testing Guidelines
Run the unit suite with `python -m unittest discover -s tests -p 'test_*.py'`; it covers CSV round-trips, OpenAI stubs, threaded processing, and the interactive wizard. Use `--dry-run` plus `--limit-rows 10` for sanity checks against real CSVs, and add targeted tests under `tests/` for new helpers before expanding CI.

## Commit & Pull Request Guidelines
Recent history uses capitalized type prefixes (`Feat:`, `Fix:`) followed by concise imperative summaries. Squash work to logical commits, reference issues when available, and share before/after snippets or representative CSV rows. Pull requests should outline the scenario, flag new environment variables, and list the exact `uv` or `docker compose` command reviewers can run.

## Security & Configuration Tips
Never commit real API keys or customer CSVs. Store secrets in `.env` (`OPENAI_API_KEY`, `INPUT_CSV`, `OUTPUT_CSV`) and use redacted examples. Rotate any leaked keys and document new permissions required by Docker or `uv` setups. On color-limited terminals install `colorama` to render the wizard palette cleanly.
