# ReformulateWithAI

Batch rewrite of HTML descriptions stored in a CSV file using the OpenAI API with multithreaded processing. This repository lives at [github.com/Aitux/ReformulateWithAI](https://github.com/Aitux/ReformulateWithAI.git) and provides the Python script, Docker packaging, and step by step automation instructions.

---

## Key Features
- Rewrites the `moduledescription` column (or any chosen column) to reduce duplicate content while preserving HTML structure.
- Parallel OpenAI calls with transient error handling and exponential backoff.
- Structured JSON output (`rewritten_html`) for consistent LLM responses.
- Docker and Docker Compose support for reproducible execution.
- `--dry-run` mode to validate the workflow without consuming API credits.

---

## Prerequisites

### Local execution (outside Docker)
- Python 3.12 or newer (uv can download and manage it automatically).
- [`uv`](https://docs.astral.sh/uv/) for dependency and virtual-env management.
- OpenAI API access with the key stored in `OPENAI_API_KEY`.

### Docker and Docker Compose
- Docker 20.10 or newer.
- Docker Compose (plugin or built in `docker compose`).
- Source CSV reachable from the host (default `gesform_export_formation_prod_20250925.csv` in repo root).

---

## Installation

### Clone the repository
```bash
git clone https://github.com/Aitux/ReformulateWithAI.git
cd ReformulateWithAI
```

### Local installation (uv)
1. Ensure `uv` is installed (see [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/)).
2. From the repository root (where `pyproject.toml` lives), sync dependencies (this creates `.venv/` pinned by `uv.lock`):
   ```bash
   uv sync
   ```
3. Optionally activate the virtual environment created by uv:
   ```bash
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   # macOS / Linux
   source .venv/bin/activate
   ```
   Activation is not required when using `uv run`, but it can be handy for interactive sessions.

### Docker installation
Docker Compose builds the image automatically. If you want to build up front:
```bash
docker compose build
```
The included `Dockerfile` now uses Python 3.12 slim and installs the locked dependencies with `uv`.

---

## Configuration

### Environment variables
- `OPENAI_API_KEY` (required): OpenAI API key.
- `INPUT_CSV` (optional): CSV input path (default `/workspace/gesform_export_formation_prod_20250925.csv` in Docker, or the value passed to `--input` locally).
- `OUTPUT_CSV` (optional): CSV output path (default appends `_rewritten`).
- `COLUMN_NAME` (optional): Column to rewrite (`moduledescription` by default).
- `MODEL` (optional): OpenAI model (`gpt-5-chat-latest` by default).
- `WORKERS` (optional): Number of worker threads (default 5).
- `MAX_RETRIES` (optional): Maximum retry attempts per request (default 5).

Sample `.env` file for Docker:
```env
OPENAI_API_KEY=sk-...
INPUT_CSV=/workspace/mes_donnees.csv
OUTPUT_CSV=/workspace/mes_donnees_rewritten.csv
COLUMN_NAME=moduledescription
WORKERS=8
```

---

## Usage

### Local run
Run the CLI from the repository root:
```bash
export OPENAI_API_KEY=sk-...    # macOS / Linux
setx OPENAI_API_KEY "sk-..."    # Windows PowerShell (persistent)
uv run reformulator --input path/to/input.csv
```

Common arguments:
```bash
uv run reformulator --input input.csv \
    --output rewritten.csv \
    --column moduledescription \
    --model gpt-5-chat-latest \
    --workers 8 \
    --max-retries 6 \
    --limit-rows 10 \
    --dry-run
```
- `--dry-run` copies the CSV without calling the API.
- `--limit-rows` processes only the first *N* rows (handy to validate prompts/models on a cheap sample).

### Docker Compose run
1. Optionally create a `.env` file in the repo root.
2. Place your CSV inside the repository (or adjust `INPUT_CSV` and `OUTPUT_CSV`).
3. Execute:
   ```bash
   docker compose run --rm reformulator
   ```
   Override variables inline when needed:
   ```bash
   INPUT_CSV=/workspace/my_input.csv \
   OUTPUT_CSV=/workspace/my_output.csv \
   docker compose run --rm reformulator
   ```

Service `reformulator` mounts the project at `/workspace`, injects `OPENAI_API_KEY`, and forwards every script option via environment-driven `docker-compose.yml` values.

### Example workflow
1. Export `gesform_export_formation_prod_20250925.csv`.
2. Set `OPENAI_API_KEY`.
3. Run `docker compose run --rm reformulator`.
4. Collect the generated `gesform_export_formation_prod_20250925_rewritten.csv`.

### Interactive mode
Launch a guided setup when you prefer to supply parameters step by step:
```bash
uv run reformulator --interactive
```
The wizard clears the screen between questions, reprints the ASCII banner, and uses colored cues so you can distinguish context (cyan) from actionable prompts (yellow). It masks your existing `OPENAI_API_KEY`, validates file paths, and walks you through column, model, workers, retry policy, optional row limits, and the dry-run toggle before summarizing the run.

---

## Project structure
```
ReformulateWithAI/
|-- reformulator/
|   |-- __init__.py
|   |-- __main__.py              # permet `python -m reformulator`
|   |-- cli.py                   # argparse + assistant interactif
|   |-- config.py                # modèles de configuration + valeurs par défaut
|   |-- core.py                  # orchestration principale
|   |-- io_csv.py                # lecture/écriture CSV + détection délimiteur
|   |-- logging_conf.py          # configuration logging
|   |-- openai_client.py         # client OpenAI + parsing de réponse
|   |-- progress.py              # affichage ASCII & progression
|-- Dockerfile                         # Python 3.12 slim image installing deps with uv
|-- docker-compose.yml                 # Compose service definition
|-- pyproject.toml                     # Dépendances + console_scripts
|-- README.md                          # Documentation (this file)
|-- tests/                             # Suite de tests unitaires
|-- uv.lock                            # Dépendances verrouillées pour uv
```

---

## Troubleshooting
- **"OPENAI_API_KEY must be set"**: ensure the variable is configured in your shell or `.env`.
- **Missing column errors**: verify the column passed with `--column` exists in the CSV header.
- **Slow processing or quota limits**: adjust `--workers` as needed for your API quota and CSV size.
- **Empty responses**: transient errors are retried up to `MAX_RETRIES`; beyond that the script stops and shows the error message.
- **Special characters**: CSV read/write uses UTF-8 (with BOM on read) to preserve French characters; ensure your editor handles UTF-8 correctly.

---

## Contributing
1. Fork the project.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Commit your changes: `git commit -am "Describe changes"`.
4. Push the branch: `git push origin feature/my-feature`.
5. Open a Pull Request on GitHub.

Open an issue to discuss new ideas (batch modes, additional CSV formats, advanced prompts, etc.).

---

## License
MIT
---

## Acknowledgements
- OpenAI for the language models.
- Python community for standard tooling (threading, concurrent.futures).

For questions or support open an issue on [github.com/Aitux/ReformulateWithAI](https://github.com/Aitux/ReformulateWithAI.git).
