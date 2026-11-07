"""Wildcard matching and specificity-based ranking engine."""
from __future__ import annotations

import fnmatch
import re
from datetime import datetime
from typing import List, Optional, Tuple

from .models import FailingTestInput, GapEntry, MatchResult, RunContext

_BASELINE_DT_RE = re.compile(r"^.+_(?P<dt>\d{6}_\d{6})$")
_RANGE_RE = re.compile(r"^range:\s*(?P<start>.+?)\s*-\s*(?P<end>.+)$")


# ---------------------------------------------------------------------------
# Baseline helpers
# ---------------------------------------------------------------------------

def _parse_baseline_dt(baseline: str) -> Optional[datetime]:
    m = _BASELINE_DT_RE.match(baseline.strip())
    if not m:
        return None
    try:
        # Format: YYMMDD_HHMMSS  e.g. "261021_125411" = 2026-10-21 12:54:11
        return datetime.strptime(m.group("dt"), "%y%m%d_%H%M%S")
    except ValueError:
        return None


def _baseline_in_range(input_baseline: str, range_str: str) -> bool:
    m = _RANGE_RE.match(range_str.strip())
    if not m:
        return False
    start_dt = _parse_baseline_dt(m.group("start").strip())
    end_dt = _parse_baseline_dt(m.group("end").strip())
    target_dt = _parse_baseline_dt(input_baseline.strip())
    if not (start_dt and end_dt and target_dt):
        return False
    return start_dt <= target_dt <= end_dt


def _baseline_covered(input_baseline: str, entry_baseline: str) -> bool:
    if entry_baseline.startswith("range:"):
        return _baseline_in_range(input_baseline, entry_baseline)
    return input_baseline.strip() == entry_baseline.strip()


# ---------------------------------------------------------------------------
# Specificity scoring
# ---------------------------------------------------------------------------

def _field_score(pattern: Optional[str], value: Optional[str]) -> Optional[int]:
    """Return the specificity score for a single field, or None if no match.

    None means the entry is disqualified for this input.
    """
    if pattern is None:
        return 0  # no constraint on this field
    candidate = value if value is not None else ""
    if not fnmatch.fnmatchcase(candidate, pattern):
        return None  # pattern present but does not match — disqualify
    if "*" not in pattern:
        return 3  # exact match
    if pattern.strip("*"):
        return 1  # partial wildcard (e.g. "Login*", "*_cfg")
    return 0  # full wildcard ("*" only)


def _score_entry(entry: GapEntry, test_input: FailingTestInput) -> Optional[int]:
    """Return total specificity score, or None if entry does not match input."""
    total = 0
    pairs = [
        (entry.scenario_name, test_input.scenario_name),
        (entry.configuration_name, test_input.configuration_name),
        (entry.machine_type, test_input.machine_type),
        (entry.test_case_name, test_input.test_case_name),
    ]
    for pattern, value in pairs:
        s = _field_score(pattern, value)
        if s is None:
            return None
        total += s
    return total


# ---------------------------------------------------------------------------
# Context filters (release / baseline / patch)
# ---------------------------------------------------------------------------

def _release_filter(entry: GapEntry, ctx: RunContext) -> bool:
    return entry.release == ctx.release


def _baseline_filter(entry: GapEntry, ctx: RunContext) -> bool:
    if not ctx.reference_baselines:
        return True  # caller provided no baselines — do not restrict
    for ib in ctx.reference_baselines:
        for eb in entry.baselines:
            if _baseline_covered(ib, eb):
                return True
    return False


def _patch_filter(entry: GapEntry, ctx: RunContext) -> bool:
    if not ctx.patch_ids or not entry.patch_ids:
        return True  # one side empty — do not restrict
    return bool(set(ctx.patch_ids) & set(entry.patch_ids))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match(
    failing_tests: List[FailingTestInput],
    entries: List[GapEntry],
    ctx: RunContext,
) -> Tuple[List[MatchResult], List[FailingTestInput]]:
    """Match each failing test against all entries, returning matched and unmatched lists."""
    matched: List[MatchResult] = []
    unmatched: List[FailingTestInput] = []

    for test_input in failing_tests:
        candidates: List[Tuple[int, GapEntry]] = []

        for entry in entries:
            if not _release_filter(entry, ctx):
                continue
            if not _baseline_filter(entry, ctx):
                continue
            if not _patch_filter(entry, ctx):
                continue
            score = _score_entry(entry, test_input)
            if score is not None:
                candidates.append((score, entry))

        if not candidates:
            unmatched.append(test_input)
            continue

        max_score = max(s for s, _ in candidates)
        top = [e for s, e in candidates if s == max_score]
        matched.append(MatchResult(
            input=test_input,
            matched_entries=top,
            specificity_score=max_score,
            is_ambiguous=len(top) > 1,
        ))

    return matched, unmatched
