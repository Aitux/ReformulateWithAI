# Repository Guidelines

## Project Structure & Module Organization
Source code lives in `reformulator/`, with `reformulate_moduledescription.py` providing the production CLI and `main.py` reserved for quick experiments. `pyproject.toml` and `uv.lock` pin Python 3.12 dependencies for reproducible `uv` environments. Docker assets (`Dockerfile`, `docker-compose.yml`) stay in the repo root with `README.md`. Keep bulk CSV inputs outside version control.

## Build, Test, and Development Commands
- `uv sync` (from `reformulator/`): install the locked dependency set inside `.venv/`.
- `uv run python reformulate_moduledescription.py --input sample.csv --dry-run`: validate parsing and CSV wiring without hitting the API.
- `uv run python reformulate_moduledescription.py --interactive`: launch the guided wizard to populate environment variables and CLI flags step by step.
- `uv run python reformulate_moduledescription.py --input sample.csv --output sample_rewritten.csv --workers 8`: run the threaded rewrite against the OpenAI API.
- `docker compose run --rm reformulator`: execute the same flow in the container; override `INPUT_CSV`/`OUTPUT_CSV` inline as needed.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation and grouped imports. Continue using type hints and explicit `Optional`/`Tuple` usage. Module constants stay uppercase (`DEFAULT_MODEL`, `ASCII_LOGO`), functions remain snake_case, and CLI flags should mirror argument names. Extend argparse help strings and keep progress output human readable because the script often runs unattended.

## Testing Guidelines
There is no dedicated test suite yet; rely on `--dry-run` plus `--limit-rows 10` to exercise control flow without consuming tokens, then run a full pass on disposable data to confirm JSON shaping and retries. For complex helpers, add unit tests under `reformulator/tests/` and document `uv run pytest` once introduced.

## Commit & Pull Request Guidelines
Recent history uses capitalized type prefixes (`Feat:`, `Fix:`) followed by concise imperative summaries. Squash work to logical commits, reference issues when available, and share before/after snippets or representative CSV rows. Pull requests should outline the scenario, flag new environment variables, and list the exact `uv` or `docker compose` command reviewers can run.

## Security & Configuration Tips
Never commit real API keys or customer CSVs. Store secrets in `.env` (`OPENAI_API_KEY`, `INPUT_CSV`, `OUTPUT_CSV`) and use redacted examples. Rotate any leaked keys and document new permissions required by Docker or `uv` setups.
