"""Tests for the gap-spec parser."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from gap_analysis.models import GapEntry
from gap_analysis.parser import parse_file, discover_files

_BASE = {
    "function_cluster": "FC-001",
    "failing_test_gap_identification": {
        "components": [{
            "name": "Auth",
            "test_entries": [{
                "scenario_name": "Login",
                "gap_specification": "Some gap.",
                "release": "v1.0",
                "baselines": ["prefix_261021_125411"],
            }]
        }]
    }
}


def _write(tmp: str, name: str, data: dict) -> Path:
    p = Path(tmp) / name
    p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return p


def _entry(**overrides) -> dict:
    base = {
        "scenario_name": "Login",
        "gap_specification": "Some gap.",
        "release": "v1.0",
        "baselines": ["prefix_261021_125411"],
    }
    base.update(overrides)
    return base


def _doc(entries) -> dict:
    import copy
    doc = copy.deepcopy(_BASE)
    doc["failing_test_gap_identification"]["components"][0]["test_entries"] = entries
    return doc


class TestParserValid(unittest.TestCase):

    def test_valid_entry_returns_gap_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _BASE)
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(errors), 0)
        self.assertIsInstance(entries[0], GapEntry)
        self.assertEqual(entries[0].scenario_name, "Login")
        self.assertEqual(entries[0].release, "v1.0")

    def test_optional_fields_default_to_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _BASE)
            entries, _ = parse_file(f)
        e = entries[0]
        self.assertIsNone(e.configuration_name)
        self.assertIsNone(e.machine_type)
        self.assertIsNone(e.test_case_name)
        self.assertIsNone(e.mitigations)

    def test_patch_ids_only_no_baselines(self):
        doc = _doc([_entry(baselines=[], patch_ids=["P1"])])
        del doc["failing_test_gap_identification"]["components"][0]["test_entries"][0]["baselines"]
        doc["failing_test_gap_identification"]["components"][0]["test_entries"][0]["patch_ids"] = ["P1"]
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", doc)
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(errors), 0)

    def test_baseline_range_stored_verbatim(self):
        doc = _doc([_entry(baselines=["range:prefix_261021_125411 - prefix_261101_101145"])])
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", doc)
            entries, _ = parse_file(f)
        self.assertTrue(entries[0].baselines[0].startswith("range:"))

    def test_function_cluster_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _BASE)
            entries, _ = parse_file(f)
        self.assertEqual(entries[0].function_cluster, "FC-001")

    def test_component_name_propagated(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _BASE)
            entries, _ = parse_file(f)
        self.assertEqual(entries[0].component, "Auth")

    def test_source_file_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _BASE)
            entries, _ = parse_file(f)
        self.assertEqual(entries[0].source_file, str(f))


class TestParserErrors(unittest.TestCase):

    def test_missing_scenario_name(self):
        te = _entry()
        del te["scenario_name"]
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _doc([te]))
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("scenario_name", errors[0].reason)

    def test_missing_release(self):
        te = _entry()
        del te["release"]
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _doc([te]))
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("release", errors[0].reason)

    def test_missing_gap_specification(self):
        te = _entry()
        del te["gap_specification"]
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _doc([te]))
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 0)
        self.assertIn("gap_specification", errors[0].reason)

    def test_missing_both_baselines_and_patch_ids(self):
        te = {
            "scenario_name": "Test",
            "gap_specification": "Gap.",
            "release": "v1.0",
        }
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", _doc([te]))
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("baselines", errors[0].reason)

    def test_invalid_yaml_produces_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "FC-002.yaml"
            f.write_text(": : invalid: yaml: {{{\n", encoding="utf-8")
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 0)
        self.assertEqual(len(errors), 1)

    def test_errors_do_not_abort_valid_entries(self):
        """One bad entry should not prevent parsing a good sibling entry."""
        good_te = _entry()
        bad_te = {"scenario_name": "Bad", "gap_specification": "g.", "release": "v1.0"}
        doc = _doc([good_te, bad_te])
        with tempfile.TemporaryDirectory() as tmp:
            f = _write(tmp, "FC-001.yaml", doc)
            entries, errors = parse_file(f)
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(errors), 1)


class TestDiscoverFiles(unittest.TestCase):

    def test_discovers_yaml_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "FC-001.yaml").touch()
            (Path(tmp) / "FC-002.yml").touch()
            (Path(tmp) / "FC-003.json").touch()
            (Path(tmp) / "ignored.txt").touch()
            (Path(tmp) / "README.md").touch()
            files = discover_files(Path(tmp))
        names = {f.name for f in files}
        self.assertIn("FC-001.yaml", names)
        self.assertIn("FC-002.yml", names)
        self.assertIn("FC-003.json", names)
        self.assertNotIn("ignored.txt", names)

    def test_nonexistent_dir_returns_empty(self):
        files = discover_files(Path("/nonexistent/path/xyz"))
        self.assertEqual(files, [])


class TestFixtureFile(unittest.TestCase):
    """Validates the bundled fixture produces the expected mix of entries and errors."""

    _FIXTURE = Path(__file__).parent / "fixtures" / "FC-001.yaml"

    def test_fixture_entries_and_errors(self):
        entries, errors = parse_file(self._FIXTURE)
        # 5 valid entries: LoginExact, Login*, PasswordReset, OAuthFlow (v1.0) + PaymentCapture (v2.0)
        self.assertEqual(len(entries), 5)
        # 1 syntax error: BrokenEntry is missing 'release'
        self.assertEqual(len(errors), 1)

    def test_fixture_scenario_names(self):
        entries, _ = parse_file(self._FIXTURE)
        names = {e.scenario_name for e in entries}
        self.assertIn("LoginExact", names)
        self.assertIn("Login*", names)
        self.assertIn("PasswordReset", names)
        self.assertIn("OAuthFlow", names)


if __name__ == "__main__":
    unittest.main()
