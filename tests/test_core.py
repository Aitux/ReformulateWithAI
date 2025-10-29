from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import types

fake_openai = types.ModuleType("openai")


class DummyOpenAI:
    def __init__(self, *args, **kwargs) -> None:
        self.responses = None


fake_openai.OpenAI = DummyOpenAI
fake_openai.error = types.SimpleNamespace()
sys.modules.setdefault("openai", fake_openai)

from reformulator.config import RunConfig
from reformulator.core import reformulate_rows, run
from reformulator.io_csv import load_rows, save_rows


class ReformulateRowsTests(unittest.TestCase):
    def test_updates_rows_with_call_openai_results(self) -> None:
        rows = [
            {"moduledescription": "<p>Alpha</p>"},
            {"moduledescription": "<p>Beta</p>"},
        ]
        with patch("reformulator.core.call_openai", side_effect=lambda client, model, text, max_retries: f"{text}-rewritten") as mocked_call, patch(
            "reformulator.core.refresh_progress_display", new=MagicMock()
        ), patch(
            "reformulator.core.build_logo_progress", return_value=""
        ):
            reformulate_rows(
                rows=rows,
                column="moduledescription",
                client=object(),
                model="gpt",
                workers=2,
                max_retries=1,
                dry_run=False,
            )

        self.assertEqual(rows[0]["moduledescription"], "<p>Alpha</p>-rewritten")
        self.assertEqual(rows[1]["moduledescription"], "<p>Beta</p>-rewritten")
        self.assertEqual(mocked_call.call_count, 2)

    def test_dry_run_leaves_rows_unchanged(self) -> None:
        rows = [{"moduledescription": "<p>Gamma</p>"}]
        with patch("reformulator.core.refresh_progress_display", new=MagicMock()), patch(
            "reformulator.core.build_logo_progress", return_value=""
        ):
            reformulate_rows(
                rows=rows,
                column="moduledescription",
                client=None,
                model="gpt",
                workers=2,
                max_retries=1,
                dry_run=True,
            )
        self.assertEqual(rows[0]["moduledescription"], "<p>Gamma</p>")


class RunFlowTests(unittest.TestCase):
    def test_run_dry_run_generates_output_file(self) -> None:
        rows = [
            {"moduledescription": "<p>Intro</p>", "title": "One"},
            {"moduledescription": "<p>Outro</p>", "title": "Two"},
        ]
        headers = ["moduledescription", "title"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.csv"
            output_path = tmp_path / "output.csv"
            save_rows(str(input_path), headers, rows)

            config = RunConfig(
                input_path=str(input_path),
                output_path=str(output_path),
                column="moduledescription",
                model="gpt",
                workers=1,
                max_retries=1,
                dry_run=True,
            )

            with patch("reformulator.core.refresh_progress_display", new=MagicMock()), patch(
                "reformulator.core.build_logo_progress", return_value=""
            ):
                run(config)

            generated_rows, generated_headers, _ = load_rows(str(output_path))

        self.assertEqual(generated_headers, headers)
        self.assertEqual(generated_rows, rows)


if __name__ == "__main__":
    unittest.main()
