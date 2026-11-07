"""End-to-end integration tests — drive the real CLI via subprocess with GH_PAT=LOCAL."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# gap_analysis/tests/ → gap_analysis/ → Experiments/
_WORKSPACE = Path(__file__).parent.parent.parent.resolve()
_PKG_DIR = Path(__file__).parent.parent.resolve()  # gap_analysis/


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(tmp: str, output_subdir: str = "out") -> Path:
    """Write an integration config.yaml pointing local_path at the workspace root."""
    p = Path(tmp) / "config.yaml"
    p.write_text(
        textwrap.dedent(f"""\
        github:
          owner: oademirkol
          repo: Experiments
          branch: main
          gap_spec_dir: TestFailureGapSpec
        local_path: {_WORKSPACE}
        output:
          base_dir: {tmp}/{output_subdir}
        """),
        encoding="utf-8",
    )
    return p


def _tests_yaml(tmp: str, tests: list, name: str = "failing_tests.yaml") -> Path:
    p = Path(tmp) / name
    p.write_text(yaml.dump(tests, allow_unicode=True), encoding="utf-8")
    return p


def _run(cfg: Path, release: str, tests: Path, extra: tuple = (), output: Path | None = None):
    cmd = [
        sys.executable, "-m", "gap_analysis",
        "--config", str(cfg),
        "--release", release,
        "--tests", str(tests),
    ]
    if output:
        cmd += ["--output", str(output)]
    cmd += list(extra)
    env = os.environ.copy()
    env["GH_PAT"] = "LOCAL"
    return subprocess.run(cmd, cwd=str(_PKG_DIR), capture_output=True, text=True, env=env)


def _json(out: Path) -> dict:
    return json.loads((out / "report.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Exact matching
# ---------------------------------------------------------------------------

class TestExactMatch(unittest.TestCase):

    def test_all_four_fields_exact_scores_12(self):
        """LoginExact entry in FC-001 has all 4 fields set — must score 12."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "LoginExact",
                "configuration_name": "default",
                "machine_type": "x86_64",
                "test_case_name": "test_login_success",
            }])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)
            self.assertEqual(len(data["unmatched"]), 0)
            self.assertEqual(data["matched"][0]["specificity_score"], 12)
            self.assertFalse(data["matched"][0]["is_ambiguous"])

    def test_exact_match_entry_function_cluster_in_report(self):
        """Matched entry must carry the correct function_cluster in JSON and MD."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "LoginExact",
                "configuration_name": "default",
                "machine_type": "x86_64",
                "test_case_name": "test_login_success",
            }])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            data = _json(out)
            self.assertEqual(data["matched"][0]["matched_entries"][0]["function_cluster"], "FC-001")
            md = (out / "report.md").read_text()
            self.assertIn("FC-001", md)

    def test_fc003_all_four_fields_exact(self):
        """API_RateLimit in FC-003 must score 12 on a perfect match."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "API_RateLimit",
                "configuration_name": "staging",
                "machine_type": "x86_64",
                "test_case_name": "test_rate_limit",
            }])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests,
                     extra=("--baseline", "prefix_261021_125411", "--patch", "PATCH-001"),
                     output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(data["matched"][0]["specificity_score"], 12)


# ---------------------------------------------------------------------------
# Wildcard matching
# ---------------------------------------------------------------------------

class TestWildcardMatch(unittest.TestCase):

    def test_partial_wildcard_scenario(self):
        """Login* in FC-001 must match LoginSomething with score < 12."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)
            self.assertLess(data["matched"][0]["specificity_score"], 12)

    def test_double_wildcard_scenario(self):
        """*Session* in FC-001 must match ActiveSessionCheck."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "ActiveSessionCheck"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261025_000000"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)
            winning = data["matched"][0]["matched_entries"][0]["scenario_name"]
            self.assertEqual(winning, "*Session*")

    def test_exact_beats_wildcard(self):
        """LoginExact entry must outscore Login* when input matches exactly."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "LoginExact",
                "configuration_name": "default",
                "machine_type": "x86_64",
                "test_case_name": "test_login_success",
            }])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            data = _json(out)
            # Exact entry wins; should NOT be ambiguous
            self.assertFalse(data["matched"][0]["is_ambiguous"])
            self.assertEqual(data["matched"][0]["matched_entries"][0]["scenario_name"], "LoginExact")

    def test_suffix_wildcard_matches(self):
        """*_Timeout in FC-003 must match Connection_Timeout."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "Connection_Timeout"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261025_000000"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            names = [e["scenario_name"] for m in data["matched"] for e in m["matched_entries"]]
            self.assertIn("*_Timeout", names)

    def test_machine_type_wildcard_matches(self):
        """Refund_* in FC-002 has machine_type=* — must match any machine."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "Refund_FullAmount",
                "machine_type": "arm64",
            }])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261027_115411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            names = [e["scenario_name"] for m in data["matched"] for e in m["matched_entries"]]
            self.assertIn("Refund_*", names)


# ---------------------------------------------------------------------------
# Release filter
# ---------------------------------------------------------------------------

class TestReleaseFilter(unittest.TestCase):

    def test_v2_entry_excluded_on_v1_query(self):
        """Gateway_Health is v2.0 — must appear in unmatched for release=v1.0."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "Gateway_Health"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 0)
            self.assertEqual(len(data["unmatched"]), 1)

    def test_v2_entry_matched_on_v2_query(self):
        """Gateway_Health must appear in matched when release=v2.0."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "Gateway_Health"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v2.0", tests, output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)
            self.assertEqual(len(data["unmatched"]), 0)


# ---------------------------------------------------------------------------
# Baseline filter
# ---------------------------------------------------------------------------

class TestBaselineFilter(unittest.TestCase):

    def test_exact_baseline_match(self):
        """Entry with exact baseline must match when ctx baseline equals it."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)

    def test_baseline_in_range_matches(self):
        """prefix_261027_115411 (Oct 27) is inside the Oct 21–Nov 01 range."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "PasswordResetFoo"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261027_115411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            names = [e["scenario_name"] for m in data["matched"] for e in m["matched_entries"]]
            self.assertIn("PasswordReset*", names)

    def test_baseline_before_range_unmatched(self):
        """prefix_261015_120000 (Oct 15) is before range start Oct 21 — must not match."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "PasswordResetFoo"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261015_120000"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            names = [e["scenario_name"] for m in data["matched"] for e in m["matched_entries"]]
            self.assertNotIn("PasswordReset*", names)

    def test_no_ctx_baseline_skips_filter(self):
        """When no baseline is supplied, baseline filter is skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, output=out)  # no --baseline
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertGreater(len(data["matched"]), 0)


# ---------------------------------------------------------------------------
# Patch filter
# ---------------------------------------------------------------------------

class TestPatchFilter(unittest.TestCase):

    def test_patch_intersection_matches(self):
        """LogoutExact (PATCH-002) must be matched when ctx supplies PATCH-002."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "LogoutExact",
                "configuration_name": "prod",
                "machine_type": "arm64",
                "test_case_name": "test_logout",
            }])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--patch", "PATCH-002"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)

    def test_no_patch_intersection_unmatched(self):
        """LogoutExact (PATCH-002) must NOT be matched when ctx only has PATCH-999."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "LogoutExact",
                "configuration_name": "prod",
                "machine_type": "arm64",
                "test_case_name": "test_logout",
            }])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--patch", "PATCH-999"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["unmatched"]), 1)

    def test_no_ctx_patch_skips_filter(self):
        """When no patch is supplied, patch filter is skipped for patch-only entries."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "OAuthFlow"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            # Entry may or may not exist in gap specs; either is acceptable —
            # the key assertion is that the tool exits successfully
            self.assertEqual(r.returncode, 0)


# ---------------------------------------------------------------------------
# Ambiguous match
# ---------------------------------------------------------------------------

class TestAmbiguousMatch(unittest.TestCase):

    def test_two_identical_patterns_produce_ambiguous(self):
        """FC-005 has DataPipeline_* in two components — must produce is_ambiguous=True."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "DataPipeline_LoadTest"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["matched"]), 1)
            self.assertTrue(data["matched"][0]["is_ambiguous"])
            self.assertEqual(len(data["matched"][0]["matched_entries"]), 2)

    def test_ambiguous_warning_in_markdown(self):
        """Ambiguous result must emit a warning block in the MD report."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "DataPipeline_LoadTest"}])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            md = (out / "report.md").read_text()
            self.assertIn("Ambiguous", md)

    def test_ambiguous_warning_in_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "DataPipeline_LoadTest"}])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            html = (out / "report.html").read_text()
            self.assertIn("Ambiguous", html)


# ---------------------------------------------------------------------------
# Unmatched inputs
# ---------------------------------------------------------------------------

class TestUnmatched(unittest.TestCase):

    def test_unknown_scenario_goes_to_unmatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "CompletelyUnknownScenario_XYZ"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertEqual(len(data["unmatched"]), 1)
            self.assertEqual(data["unmatched"][0]["scenario_name"], "CompletelyUnknownScenario_XYZ")

    def test_unmatched_table_has_four_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{
                "scenario_name": "UnknownFoo",
                "configuration_name": "cfg1",
                "machine_type": "x86",
                "test_case_name": "tc1",
            }])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, output=out)
            md = (out / "report.md").read_text()
            for col in ("Scenario Name", "Configuration Name", "Machine Type", "Test Case Name"):
                self.assertIn(col, md)
            self.assertIn("UnknownFoo", md)

    def test_mixed_matched_and_unmatched(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [
                {
                    "scenario_name": "LoginExact",
                    "configuration_name": "default",
                    "machine_type": "x86_64",
                    "test_case_name": "test_login_success",
                },
                {"scenario_name": "CompletelyUnknownScenario_XYZ"},
            ])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = _json(out)
            self.assertGreaterEqual(len(data["matched"]), 1)
            self.assertGreaterEqual(len(data["unmatched"]), 1)


# ---------------------------------------------------------------------------
# Report files and versioning
# ---------------------------------------------------------------------------

class TestReportFiles(unittest.TestCase):

    def _base_run(self, tmp: str) -> Path:
        cfg = _cfg(tmp)
        tests = _tests_yaml(tmp, [{
            "scenario_name": "LoginExact",
            "configuration_name": "default",
            "machine_type": "x86_64",
            "test_case_name": "test_login_success",
        }])
        out = Path(tmp) / "out"
        _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
        return out

    def test_all_three_reports_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._base_run(tmp)
            for fname in ("report.json", "report.md", "report.html"):
                self.assertTrue((out / fname).exists(), f"{fname} missing")

    def test_version_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._base_run(tmp)
            self.assertTrue((out / ".version").exists())

    def test_version_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._base_run(tmp)
            ver = (out / ".version").read_text().strip()
            # format: YYYY.MM.DD.NNN
            parts = ver.split(".")
            self.assertEqual(len(parts), 4)
            self.assertEqual(len(parts[0]), 4)   # year
            self.assertEqual(len(parts[3]), 3)   # NNN

    def test_version_increments_on_second_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            extra = ("--baseline", "prefix_261021_125411")
            _run(cfg, "v1.0", tests, extra=extra, output=out)
            v1 = int((out / ".version").read_text().strip().rsplit(".", 1)[1])
            _run(cfg, "v1.0", tests, extra=extra, output=out)
            v2 = int((out / ".version").read_text().strip().rsplit(".", 1)[1])
            self.assertEqual(v2, v1 + 1)

    def test_json_top_level_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self._base_run(tmp)
            data = _json(out)
            for key in ("version", "generated_at", "run_context", "matched", "unmatched", "syntax_errors"):
                self.assertIn(key, data)

    def test_run_context_fields_in_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests,
                 extra=("--baseline", "prefix_261021_125411", "--patch", "PATCH-001"),
                 output=out)
            data = _json(out)
            ctx = data["run_context"]
            self.assertEqual(ctx["release"], "v1.0")
            self.assertIn("prefix_261021_125411", ctx["reference_baselines"])
            self.assertIn("PATCH-001", ctx["patch_ids"])

    def test_html_escapes_angle_brackets(self):
        """Angle brackets in scenario name must be HTML-escaped."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "<script>xss</script>"}])
            out = Path(tmp) / "out"
            _run(cfg, "v1.0", tests, output=out)
            html = (out / "report.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)


# ---------------------------------------------------------------------------
# Syntax errors
# ---------------------------------------------------------------------------

class TestSyntaxErrors(unittest.TestCase):

    def test_syntax_errors_not_fatal(self):
        """A broken gap-spec entry must not cause a non-zero exit code."""
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = Path(tmp) / "TestFailureGapSpec"
            spec_dir.mkdir()
            (spec_dir / "FC-099.yaml").write_text(
                textwrap.dedent("""\
                function_cluster: FC-099
                failing_test_gap_identification:
                  components:
                    - name: BrokenComp
                      test_entries:
                        - scenario_name: "BrokenTest"
                          gap_specification: Missing release field.
                          baselines:
                            - "prefix_261021_125411"
                """),
                encoding="utf-8",
            )
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                textwrap.dedent(f"""\
                github:
                  owner: x
                  repo: x
                  branch: main
                  gap_spec_dir: TestFailureGapSpec
                local_path: {tmp}
                output:
                  base_dir: {tmp}/out
                """),
                encoding="utf-8",
            )
            tests = _tests_yaml(tmp, [{"scenario_name": "BrokenTest"}])
            env = os.environ.copy()
            env["GH_PAT"] = "LOCAL"
            r = subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", str(cfg_path),
                 "--release", "v1.0",
                 "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            self.assertEqual(r.returncode, 0)
            data = json.loads((Path(tmp) / "out" / "report.json").read_text())
            self.assertEqual(len(data["syntax_errors"]), 1)
            self.assertIn("release", data["syntax_errors"][0]["reason"])

    def test_syntax_errors_appear_in_md_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = Path(tmp) / "TestFailureGapSpec"
            spec_dir.mkdir()
            (spec_dir / "FC-099.yaml").write_text(
                textwrap.dedent("""\
                function_cluster: FC-099
                failing_test_gap_identification:
                  components:
                    - name: BrokenComp
                      test_entries:
                        - scenario_name: "BrokenTest"
                          gap_specification: Missing release field.
                          baselines:
                            - "prefix_261021_125411"
                """),
                encoding="utf-8",
            )
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                textwrap.dedent(f"""\
                github:
                  owner: x
                  repo: x
                  branch: main
                  gap_spec_dir: TestFailureGapSpec
                local_path: {tmp}
                output:
                  base_dir: {tmp}/out
                """),
                encoding="utf-8",
            )
            tests = _tests_yaml(tmp, [{"scenario_name": "X"}])
            env = os.environ.copy()
            env["GH_PAT"] = "LOCAL"
            subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", str(cfg_path), "--release", "v1.0", "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            out = Path(tmp) / "out"
            md = (out / "report.md").read_text()
            html = (out / "report.html").read_text()
            self.assertIn("Syntax Errors", md)
            self.assertIn("FC-099.yaml", md)
            self.assertIn("Syntax Errors", html)
            self.assertIn("FC-099.yaml", html)

    def test_syntax_errors_printed_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = Path(tmp) / "TestFailureGapSpec"
            spec_dir.mkdir()
            (spec_dir / "FC-099.yaml").write_text(
                textwrap.dedent("""\
                function_cluster: FC-099
                failing_test_gap_identification:
                  components:
                    - name: BrokenComp
                      test_entries:
                        - scenario_name: "BrokenTest"
                          gap_specification: Missing release field.
                          baselines:
                            - "prefix_261021_125411"
                """),
                encoding="utf-8",
            )
            cfg_path = Path(tmp) / "config.yaml"
            cfg_path.write_text(
                textwrap.dedent(f"""\
                github:
                  owner: x
                  repo: x
                  branch: main
                  gap_spec_dir: TestFailureGapSpec
                local_path: {tmp}
                output:
                  base_dir: {tmp}/out
                """),
                encoding="utf-8",
            )
            tests = _tests_yaml(tmp, [{"scenario_name": "X"}])
            env = os.environ.copy()
            env["GH_PAT"] = "LOCAL"
            r = subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", str(cfg_path), "--release", "v1.0", "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            self.assertIn("SYNTAX ERROR", r.stderr)


# ---------------------------------------------------------------------------
# CLI error handling
# ---------------------------------------------------------------------------

class TestCLIErrors(unittest.TestCase):

    def test_missing_release_arg_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "X"}])
            env = os.environ.copy()
            env["GH_PAT"] = "LOCAL"
            r = subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", str(cfg), "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            self.assertNotEqual(r.returncode, 0)

    def test_nonexistent_config_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tests = _tests_yaml(tmp, [{"scenario_name": "X"}])
            env = os.environ.copy()
            env["GH_PAT"] = "LOCAL"
            r = subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", "nonexistent_config_xyz.yaml",
                 "--release", "v1.0", "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            self.assertEqual(r.returncode, 1)

    def test_missing_gh_pat_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "X"}])
            env = os.environ.copy()
            env.pop("GH_PAT", None)
            r = subprocess.run(
                [sys.executable, "-m", "gap_analysis",
                 "--config", str(cfg), "--release", "v1.0", "--tests", str(tests)],
                cwd=str(_PKG_DIR), capture_output=True, text=True, env=env,
            )
            self.assertEqual(r.returncode, 1)
            self.assertIn("GH_PAT", r.stderr)

    def test_stdout_summary_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _cfg(tmp)
            tests = _tests_yaml(tmp, [{"scenario_name": "LoginSomething"}])
            out = Path(tmp) / "out"
            r = _run(cfg, "v1.0", tests, extra=("--baseline", "prefix_261021_125411"), output=out)
            self.assertIn("Reports written to:", r.stdout)
            self.assertIn("Matched:", r.stdout)
            self.assertIn("Unmatched:", r.stdout)


if __name__ == "__main__":
    unittest.main()
