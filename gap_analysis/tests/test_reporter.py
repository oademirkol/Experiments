"""Tests for report generation."""
from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from gap_analysis.models import (
    FailingTestInput,
    GapEntry,
    GapSyntaxError,
    MatchResult,
    RunContext,
)
from gap_analysis.reporter import generate_reports


def _ctx() -> RunContext:
    return RunContext("v1.0", ["baseline_261021_125411"], ["PATCH-001"])


def _make_entry(**overrides) -> GapEntry:
    base = GapEntry(
        function_cluster="FC-001",
        component="AuthService",
        scenario_name="Login",
        configuration_name=None,
        machine_type=None,
        test_case_name=None,
        gap_specification="Login gap description.",
        mitigations="Mitigated by integration tests.",
        tags=["auth"],
        baselines=["baseline_261021_125411"],
        release="v1.0",
        patch_ids=["PATCH-001"],
        remarks="Tracked in JIRA.",
        output_dir=None,
        source_file="FC-001.yaml",
    )
    for k, v in overrides.items():
        object.__setattr__(base, k, v)
    return base


def _make_match(ambiguous: bool = False) -> MatchResult:
    entry = _make_entry()
    entries = [entry, dataclasses.replace(entry)] if ambiguous else [entry]
    return MatchResult(FailingTestInput("Login"), entries, 3, ambiguous)


class TestVersionCounter(unittest.TestCase):

    def test_first_run_version_ends_with_001(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            version = (out / ".version").read_text().strip()
        self.assertTrue(version.endswith(".001"), version)

    def test_second_run_increments_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            generate_reports([], [], [], _ctx(), out)
            version = (out / ".version").read_text().strip()
        self.assertTrue(version.endswith(".002"), version)

    def test_counter_increments_monotonically(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for expected in range(1, 6):
                generate_reports([], [], [], _ctx(), out)
                version = (out / ".version").read_text().strip()
                self.assertTrue(version.endswith(f".{expected:03d}"), version)


class TestJsonReport(unittest.TestCase):

    def _load(self, out: Path) -> dict:
        return json.loads((out / "report.json").read_text())

    def test_top_level_keys_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            data = self._load(out)
        for key in ("version", "generated_at", "run_context", "matched", "unmatched", "syntax_errors"):
            self.assertIn(key, data)

    def test_matched_entry_serialized(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([_make_match()], [], [], _ctx(), out)
            data = self._load(out)
        self.assertEqual(len(data["matched"]), 1)
        self.assertIn("matched_entries", data["matched"][0])

    def test_unmatched_entry_serialized(self):
        unmatched = [FailingTestInput("NoMatch", "cfg", "x86", "tc")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], unmatched, [], _ctx(), out)
            data = self._load(out)
        self.assertEqual(len(data["unmatched"]), 1)
        self.assertEqual(data["unmatched"][0]["scenario_name"], "NoMatch")

    def test_syntax_errors_serialized(self):
        errs = [GapSyntaxError("FC-001.yaml", 0, "Missing release")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], errs, _ctx(), out)
            data = self._load(out)
        self.assertEqual(len(data["syntax_errors"]), 1)

    def test_json_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([_make_match()], [FailingTestInput("X")], [], _ctx(), out)
            raw = (out / "report.json").read_text()
        parsed = json.loads(raw)  # must not raise
        self.assertIsInstance(parsed, dict)


class TestMarkdownReport(unittest.TestCase):

    def _read(self, out: Path) -> str:
        return (out / "report.md").read_text(encoding="utf-8")

    def test_header_fields_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            md = self._read(out)
        for field in ("Report Version", "Release", "Reference Baselines", "Patch IDs", "Generated at"):
            self.assertIn(field, md)

    def test_unmatched_table_has_required_columns(self):
        unmatched = [FailingTestInput("LoginFoo", "cfg", "x86", "test_foo")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], unmatched, [], _ctx(), out)
            md = self._read(out)
        for col in ("Scenario Name", "Configuration Name", "Machine Type", "Test Case Name"):
            self.assertIn(col, md)

    def test_unmatched_row_values_present(self):
        unmatched = [FailingTestInput("LoginFoo", "cfg", "x86", "test_foo")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], unmatched, [], _ctx(), out)
            md = self._read(out)
        self.assertIn("LoginFoo", md)
        self.assertIn("cfg", md)

    def test_ambiguous_warning_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([_make_match(ambiguous=True)], [], [], _ctx(), out)
            md = self._read(out)
        self.assertIn("Ambiguous", md)

    def test_matched_entry_function_cluster_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([_make_match()], [], [], _ctx(), out)
            md = self._read(out)
        self.assertIn("FC-001", md)


class TestHtmlReport(unittest.TestCase):

    def _read(self, out: Path) -> str:
        return (out / "report.html").read_text(encoding="utf-8")

    def test_html_contains_doctype(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            html = self._read(out)
        self.assertIn("<!DOCTYPE html>", html)

    def test_html_header_fields_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], [], [], _ctx(), out)
            html = self._read(out)
        for field in ("Report Version", "Release", "Reference Baselines", "Patch IDs"):
            self.assertIn(field, html)

    def test_html_unmatched_table_columns(self):
        unmatched = [FailingTestInput("Foo", "bar", "x86", "tc")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([], unmatched, [], _ctx(), out)
            html = self._read(out)
        for col in ("Scenario Name", "Configuration Name", "Machine Type", "Test Case Name"):
            self.assertIn(col, html)

    def test_html_escapes_special_chars(self):
        m = _make_match()
        # inject special chars into gap_specification
        entry = dataclasses.replace(
            m.matched_entries[0],
            gap_specification="Gap <with> &special chars",
        )
        result = dataclasses.replace(m, matched_entries=[entry])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            generate_reports([result], [], [], _ctx(), out)
            html = self._read(out)
        self.assertNotIn("<with>", html)
        self.assertIn("&lt;with&gt;", html)


if __name__ == "__main__":
    unittest.main()
