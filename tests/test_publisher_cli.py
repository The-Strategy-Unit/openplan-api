import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"

# Pytest's storage guard does not cross process boundaries. Install the same
# guard in the child before executing the real CLI entry point and SystemExit.
CLI_SCRIPT = """
import runpy
from unittest.mock import patch
from openplan.api.v1 import data

with patch.object(data, 'BlobServiceClient', side_effect=AssertionError('No live storage in CLI tests')) as storage:
    try:
        runpy.run_module('openplan.api.v1.discovery.validate', run_name='__main__')
    finally:
        storage.assert_not_called()
"""


class PublisherValidationCLITests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(TemporaryDirectory()))

    def run_validator(self, *args):
        return subprocess.run(
            [sys.executable, "-c", CLI_SCRIPT, *map(str, args)],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )

    def assert_invalid_file(self, kind, path):
        result = self.run_validator(kind, path)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(f"Invalid {kind}:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_valid_examples_exit_successfully(self):
        for kind in ("index", "manifest"):
            with self.subTest(kind=kind):
                path = EXAMPLES / f"dataset-{kind}.json"
                result = self.run_validator(kind, path)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, f"Valid {kind}: {path}\n")
                self.assertEqual(result.stderr, "")

    def test_malformed_json_exits_with_a_validation_failure(self):
        path = self.directory / "malformed.json"
        path.write_text('{"schema_version":', encoding="utf-8")
        for kind in ("index", "manifest"):
            with self.subTest(kind=kind):
                self.assert_invalid_file(kind, path)

    def test_invalid_schema_exits_with_a_validation_failure(self):
        path = self.directory / "invalid.json"
        for kind in ("index", "manifest"):
            with self.subTest(kind=kind):
                document = json.loads((EXAMPLES / f"dataset-{kind}.json").read_text())
                document["schema_version"] = 99
                path.write_text(json.dumps(document), encoding="utf-8")
                self.assert_invalid_file(kind, path)

    def test_missing_files_exit_with_a_file_error(self):
        for kind in ("index", "manifest"):
            with self.subTest(kind=kind):
                self.assert_invalid_file(kind, self.directory / "missing.json")

    def test_document_kind_selects_the_correct_schema(self):
        for kind, other in (("index", "manifest"), ("manifest", "index")):
            with self.subTest(kind=kind):
                self.assert_invalid_file(kind, EXAMPLES / f"dataset-{other}.json")

    def test_invalid_arguments_exit_with_a_usage_error(self):
        for args in ((), ("release", EXAMPLES / "dataset-index.json")):
            with self.subTest(args=args):
                result = self.run_validator(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertIn("usage:", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
