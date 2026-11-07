"""Tests for the matching and specificity engine."""
from __future__ import annotations

import unittest
from typing import List, Optional

from gap_analysis.matcher import (
    _baseline_in_range,
    _field_score,
    _parse_baseline_dt,
    match,
)
from gap_analysis.models import FailingTestInput, GapEntry, MatchResult, RunContext


def _entry(
    scenario_name: str = "Login",
    configuration_name: Optional[str] = None,
    machine_type: Optional[str] = None,
    test_case_name: Optional[str] = None,
    release: str = "v1.0",
    baselines: Optional[List[str]] = None,
    patch_ids: Optional[List[str]] = None,
) -> GapEntry:
    return GapEntry(
        function_cluster="FC-001",
        component="Auth",
        scenario_name=scenario_name,
        configuration_name=configuration_name,
        machine_type=machine_type,
        test_case_name=test_case_name,
        gap_specification="Gap.",
        mitigations=None,
        tags=[],
        baselines=baselines if baselines is not None else ["prefix_261021_125411"],
        release=release,
        patch_ids=patch_ids if patch_ids is not None else [],
        remarks=None,
        output_dir=None,
        source_file="FC-001.yaml",
    )


def _ctx(
    release: str = "v1.0",
    reference_baselines: Optional[List[str]] = None,
    patch_ids: Optional[List[str]] = None,
) -> RunContext:
    return RunContext(
        release=release,
        reference_baselines=reference_baselines or [],
        patch_ids=patch_ids or [],
    )


class TestFieldScore(unittest.TestCase):

    def test_exact_match_scores_3(self):
        self.assertEqual(_field_score("Login", "Login"), 3)

    def test_partial_wildcard_scores_1(self):
        self.assertEqual(_field_score("Login*", "LoginFoo"), 1)
        self.assertEqual(_field_score("*_cfg", "prod_cfg"), 1)

    def test_full_wildcard_scores_0(self):
        self.assertEqual(_field_score("*", "anything"), 0)

    def test_no_pattern_scores_0(self):
        self.assertEqual(_field_score(None, "anything"), 0)
        self.assertEqual(_field_score(None, None), 0)

    def test_no_match_returns_none(self):
        self.assertIsNone(_field_score("Logout", "Login"))

    def test_none_value_treated_as_empty_string(self):
        # full wildcard matches empty string
        self.assertEqual(_field_score("*", None), 0)
        # partial wildcard does not match empty string
        self.assertIsNone(_field_score("Login*", None))


class TestBaselineParsing(unittest.TestCase):

    def test_parses_valid_baseline(self):
        dt = _parse_baseline_dt("prefix_261021_125411")
        self.assertIsNotNone(dt)

    def test_returns_none_for_invalid(self):
        self.assertIsNone(_parse_baseline_dt("not_a_baseline"))

    def test_range_in_bounds(self):
        self.assertTrue(
            _baseline_in_range(
                "prefix_261025_000000",
                "range:prefix_261021_125411 - prefix_261101_101145",
            )
        )

    def test_range_out_of_bounds(self):
        self.assertFalse(
            _baseline_in_range(
                "prefix_261015_000000",
                "range:prefix_261021_125411 - prefix_261101_101145",
            )
        )

    def test_range_on_boundary(self):
        self.assertTrue(
            _baseline_in_range(
                "prefix_261021_125411",
                "range:prefix_261021_125411 - prefix_261101_101145",
            )
        )


class TestMatch(unittest.TestCase):

    def test_exact_match_all_fields_scores_12(self):
        e = _entry("Login", "default", "x86_64", "test_login")
        inp = FailingTestInput("Login", "default", "x86_64", "test_login")
        matched, unmatched = match([inp], [e], _ctx())
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].specificity_score, 12)
        self.assertFalse(matched[0].is_ambiguous)
        self.assertEqual(len(unmatched), 0)

    def test_wildcard_scenario_scores_less_than_exact(self):
        e = _entry("Login*")
        inp = FailingTestInput("LoginFoo")
        matched, _ = match([inp], [e], _ctx())
        self.assertEqual(len(matched), 1)
        self.assertLess(matched[0].specificity_score, 12)

    def test_unmatched_input(self):
        e = _entry("Logout")
        inp = FailingTestInput("Login")
        matched, unmatched = match([inp], [e], _ctx())
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(unmatched), 1)
        self.assertIs(unmatched[0], inp)

    def test_tie_produces_ambiguous_result(self):
        e1 = _entry("Login*", patch_ids=["P1"], baselines=[])
        e2 = _entry("Login*", patch_ids=["P2"], baselines=[])
        inp = FailingTestInput("LoginFoo")
        matched, _ = match([inp], [e1, e2], _ctx())
        self.assertEqual(len(matched), 1)
        self.assertTrue(matched[0].is_ambiguous)
        self.assertEqual(len(matched[0].matched_entries), 2)

    def test_most_specific_entry_wins_over_wildcard(self):
        """Exact entry must beat wildcard entry for same input."""
        exact_entry = _entry("LoginFoo")
        wildcard_entry = _entry("Login*")
        inp = FailingTestInput("LoginFoo")
        matched, _ = match([inp], [exact_entry, wildcard_entry], _ctx())
        self.assertEqual(len(matched), 1)
        self.assertFalse(matched[0].is_ambiguous)
        self.assertEqual(matched[0].matched_entries[0].scenario_name, "LoginFoo")

    def test_release_filter_excludes_wrong_release(self):
        e = _entry(release="v2.0")
        inp = FailingTestInput("Login")
        matched, unmatched = match([inp], [e], _ctx(release="v1.0"))
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(len(matched), 0)

    def test_baseline_filter_passes_when_ctx_empty(self):
        e = _entry(baselines=["prefix_261021_125411"])
        inp = FailingTestInput("Login")
        matched, _ = match([inp], [e], _ctx(reference_baselines=[]))
        self.assertEqual(len(matched), 1)

    def test_baseline_filter_excludes_non_matching(self):
        e = _entry(baselines=["prefix_261021_125411"])
        inp = FailingTestInput("Login")
        matched, unmatched = match([inp], [e], _ctx(reference_baselines=["prefix_999999_000000"]))
        self.assertEqual(len(unmatched), 1)

    def test_baseline_range_match(self):
        e = _entry(baselines=["range:prefix_261021_125411 - prefix_261101_101145"])
        inp = FailingTestInput("Login")
        matched, _ = match(
            [inp], [e],
            _ctx(reference_baselines=["prefix_261025_000000"])
        )
        self.assertEqual(len(matched), 1)

    def test_patch_filter_passes_when_ctx_patches_empty(self):
        e = _entry(patch_ids=["PATCH-001"])
        inp = FailingTestInput("Login")
        matched, _ = match([inp], [e], _ctx(patch_ids=[]))
        self.assertEqual(len(matched), 1)

    def test_patch_filter_with_intersection(self):
        e = _entry(patch_ids=["PATCH-001", "PATCH-002"])
        inp = FailingTestInput("Login")
        matched, _ = match([inp], [e], _ctx(patch_ids=["PATCH-001"]))
        self.assertEqual(len(matched), 1)

    def test_patch_filter_no_intersection(self):
        e = _entry(patch_ids=["PATCH-001"])
        inp = FailingTestInput("Login")
        matched, unmatched = match([inp], [e], _ctx(patch_ids=["PATCH-999"]))
        self.assertEqual(len(unmatched), 1)

    def test_multiple_inputs(self):
        e = _entry("Login")
        inputs = [FailingTestInput("Login"), FailingTestInput("Logout")]
        matched, unmatched = match(inputs, [e], _ctx())
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(unmatched), 1)

    def test_empty_entries_all_unmatched(self):
        inputs = [FailingTestInput("Login"), FailingTestInput("Logout")]
        matched, unmatched = match(inputs, [], _ctx())
        self.assertEqual(len(matched), 0)
        self.assertEqual(len(unmatched), 2)


if __name__ == "__main__":
    unittest.main()
