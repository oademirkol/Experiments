"""Pure data models — no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FailingTestInput:
    scenario_name: str
    configuration_name: Optional[str] = None
    machine_type: Optional[str] = None
    test_case_name: Optional[str] = None


@dataclass
class GapEntry:
    function_cluster: str
    component: str
    scenario_name: str
    configuration_name: Optional[str]
    machine_type: Optional[str]
    test_case_name: Optional[str]
    gap_specification: str
    mitigations: Optional[str]
    tags: List[str]
    baselines: List[str]
    release: str
    patch_ids: List[str]
    remarks: Optional[str]
    output_dir: Optional[str]
    source_file: str


@dataclass
class MatchResult:
    input: FailingTestInput
    matched_entries: List[GapEntry]
    specificity_score: int
    is_ambiguous: bool


@dataclass
class RunContext:
    release: str
    reference_baselines: List[str]
    patch_ids: List[str]
    version: str = field(default="")


@dataclass
class GapSyntaxError:
    source_file: str
    entry_index: int
    reason: str
