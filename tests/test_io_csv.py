from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from reformulator.io_csv import build_output_path, detect_delimiter, load_rows, save_rows


class BuildOutputPathTests(unittest.TestCase):
    def test_returns_provided_output_when_available(self) -> None:
        self.assertEqual(build_output_path("data.csv", "custom.csv"), "custom.csv")

    def test_appends_suffix_when_missing(self) -> None:
        self.assertEqual(build_output_path("data.csv", None), "data_rewritten.csv")

    def test_appends_extension_when_source_has_none(self) -> None:
        self.assertEqual(build_output_path("data", None), "data_rewritten.csv")


class CsvPersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self) -> None:
        rows = [
            {"moduledescription": "<p>Bienvenue</p>", "title": "Intro"},
            {"moduledescription": "<p>Suite</p>", "title": "Advanced"},
        ]
        headers = ["moduledescription", "title"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "dataset.csv"
            save_rows(str(csv_path), headers, rows)
            loaded_rows, loaded_headers, detected = load_rows(str(csv_path))
        self.assertEqual(loaded_headers, headers)
        self.assertEqual(loaded_rows, rows)
        self.assertEqual(detected, ";")

    def test_detects_comma_delimiter(self) -> None:
        rows = [
            {"moduledescription": "<p>A</p>", "title": "One"},
            {"moduledescription": "<p>B</p>", "title": "Two"},
        ]
        headers = ["moduledescription", "title"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "dataset.csv"
            with open(csv_path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=headers, delimiter=",", quotechar='"')
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            detected = detect_delimiter(str(csv_path))
            self.assertEqual(detected, ",")


if __name__ == "__main__":
    unittest.main()
