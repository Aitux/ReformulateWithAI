from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import types

fake_openai = types.ModuleType("openai")


class DummyOpenAI:
    def __init__(self, *args, **kwargs) -> None:
        self.responses = None


fake_openai.OpenAI = DummyOpenAI
fake_openai.error = types.SimpleNamespace()
sys.modules.setdefault("openai", fake_openai)

import reformulator.reformulate_moduledescription as module


class BuildOutputPathTests(unittest.TestCase):
    def test_returns_provided_output_when_available(self) -> None:
        self.assertEqual(module.build_output_path("data.csv", "custom.csv"), "custom.csv")

    def test_appends_suffix_when_missing(self) -> None:
        self.assertEqual(module.build_output_path("data.csv", None), "data_rewritten.csv")

    def test_appends_extension_when_source_has_none(self) -> None:
        self.assertEqual(module.build_output_path("data", None), "data_rewritten.csv")


class CsvPersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        rows = [
            {"moduledescription": "<p>Bienvenue</p>", "title": "Intro"},
            {"moduledescription": "<p>Suite</p>", "title": "Advanced"},
        ]
        headers = ["moduledescription", "title"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "dataset.csv"
            module.save_rows(str(csv_path), headers, rows)
            loaded_rows, loaded_headers = module.load_rows(str(csv_path))
        self.assertEqual(loaded_headers, headers)
        self.assertEqual(loaded_rows, rows)


class ExtractRewrittenHtmlTests(unittest.TestCase):
    def test_prefers_structured_json_payload(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json={"rewritten_html": "<p>OK</p>"}, text=None)
                    ]
                )
            ]
        )
        self.assertEqual(module.extract_rewritten_html(response), "<p>OK</p>")

    def test_parses_json_string_when_needed(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json=None, text='{"rewritten_html": "<div>Alt</div>"}')
                    ]
                )
            ]
        )
        self.assertEqual(module.extract_rewritten_html(response), "<div>Alt</div>")


class StubResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):  # type: ignore[override]
        self.calls.append(kwargs)
        return SimpleNamespace(
            output=[
                SimpleNamespace(
                    content=[
                        SimpleNamespace(json={"rewritten_html": "<p>Réécrit</p>"}, text=None)
                    ]
                )
            ]
        )


class StubClient:
    def __init__(self) -> None:
        self.responses = StubResponses()


class CallOpenAITests(unittest.TestCase):
    def test_returns_rewritten_result(self) -> None:
        client = StubClient()
        previous = module.USE_RESPONSE_FORMAT
        try:
            module.USE_RESPONSE_FORMAT = True
            result = module.call_openai(client, "gpt-test", "<p>Source</p>", max_retries=1)
        finally:
            module.USE_RESPONSE_FORMAT = previous
        self.assertEqual(result, "<p>Réécrit</p>")
        self.assertEqual(client.responses.calls[0]["model"], "gpt-test")
        self.assertIn("input", client.responses.calls[0])


class ReformulateRowsTests(unittest.TestCase):
    def test_updates_rows_with_call_openai_results(self) -> None:
        rows = [
            {"moduledescription": "<p>Alpha</p>"},
            {"moduledescription": "<p>Beta</p>"},
        ]
        with patch.object(
            module,
            "call_openai",
            side_effect=lambda client, model, text, max_retries: f"{text}-rewritten",
        ) as mocked_call, patch.object(
            module, "refresh_progress_display", new=MagicMock()
        ), patch.object(
            module, "build_logo_progress", return_value=""
        ):
            module.reformulate_rows(
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
        with patch.object(module, "refresh_progress_display", new=MagicMock()), patch.object(
            module, "build_logo_progress", return_value=""
        ):
            module.reformulate_rows(
                rows=rows,
                column="moduledescription",
                client=None,
                model="gpt",
                workers=2,
                max_retries=1,
                dry_run=True,
            )
        self.assertEqual(rows[0]["moduledescription"], "<p>Gamma</p>")


class MainFlowTests(unittest.TestCase):
    def test_main_dry_run_generates_output_file(self) -> None:
        rows = [
            {"moduledescription": "<p>Intro</p>", "title": "One"},
            {"moduledescription": "<p>Outro</p>", "title": "Two"},
        ]
        headers = ["moduledescription", "title"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.csv"
            output_path = tmp_path / "output.csv"
            module.save_rows(str(input_path), headers, rows)

            args = [
                "reformulate_moduledescription.py",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--dry-run",
            ]

            with patch.object(sys, "argv", args), patch.object(
                module, "clear_terminal", new=lambda: None
            ), patch.object(
                module, "print_banner", new=lambda: None
            ), patch.object(
                module, "refresh_progress_display", new=lambda *_, **__: None
            ), patch.object(
                module, "build_logo_progress", return_value=""
            ):
                module.main()

            generated_rows, generated_headers = module.load_rows(str(output_path))

        self.assertEqual(generated_headers, headers)
        self.assertEqual(generated_rows, rows)


class InteractiveModeTests(unittest.TestCase):
    def test_main_interactive_flow(self) -> None:
        rows = [
            {"moduledescription": "<p>Interactive</p>", "title": "One"},
            {"moduledescription": "<p>Session</p>", "title": "Two"},
        ]
        headers = ["moduledescription", "title"]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.csv"
            module.save_rows(str(input_path), headers, rows)
            expected_output = module.build_output_path(str(input_path), None)

            previous_key = os.environ.get("OPENAI_API_KEY")

            inputs = [
                str(input_path),  # input path
                "",  # output path (default)
                "",  # column
                "",  # model
                "",  # workers
                "",  # max retries
                "",  # limit rows
                "y",  # dry-run
                "y",  # confirm
            ]

            configured_key = None

            try:
                with patch.object(
                    sys,
                    "argv",
                    ["reformulate_moduledescription.py", "--interactive"],
                ), patch(
                    "builtins.input",
                    side_effect=inputs,
                ), patch.object(
                    module.getpass,
                    "getpass",
                    return_value="sk-test-key",
                ), patch.object(
                    module,
                    "clear_terminal",
                    new=lambda: None,
                ), patch.object(
                    module,
                    "print_banner",
                    new=lambda: None,
                ), patch.object(
                    module,
                    "refresh_progress_display",
                    new=lambda *_, **__: None,
                ), patch.object(
                    module,
                    "build_logo_progress",
                    return_value="",
                ):
                    module.main()
                    configured_key = os.environ.get("OPENAI_API_KEY")
            finally:
                if previous_key is None:
                    os.environ.pop("OPENAI_API_KEY", None)
                else:
                    os.environ["OPENAI_API_KEY"] = previous_key

            generated_rows, generated_headers = module.load_rows(expected_output)

        self.assertEqual(generated_headers, headers)
        self.assertEqual(generated_rows, rows)
        self.assertEqual(configured_key, "sk-test-key")
        self.assertEqual(os.environ.get("OPENAI_API_KEY"), previous_key)

if __name__ == "__main__":
    unittest.main()
