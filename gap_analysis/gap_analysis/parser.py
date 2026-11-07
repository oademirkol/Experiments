"""Discover and parse FC-<ddd> gap-specification files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

import yaml

from .models import GapEntry, GapSyntaxError

_FILE_RE = re.compile(r"^FC-\d{3}\.(yaml|yml|json)$", re.IGNORECASE)


def discover_files(gap_spec_dir: Path) -> List[Path]:
    if not gap_spec_dir.exists():
        return []
    return sorted(p for p in gap_spec_dir.rglob("*") if p.is_file() and _FILE_RE.match(p.name))


def parse_all(gap_spec_dir: Path) -> Tuple[List[GapEntry], List[GapSyntaxError]]:
    entries: List[GapEntry] = []
    errors: List[GapSyntaxError] = []
    for file_path in discover_files(gap_spec_dir):
        fe, er = parse_file(file_path)
        entries.extend(fe)
        errors.extend(er)
    return entries, errors


def _load_raw(file_path: Path) -> object:
    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


def parse_file(file_path: Path) -> Tuple[List[GapEntry], List[GapSyntaxError]]:
    entries: List[GapEntry] = []
    errors: List[GapSyntaxError] = []

    try:
        raw = _load_raw(file_path)
    except Exception as exc:
        errors.append(GapSyntaxError(str(file_path), -1, f"Parse error: {exc}"))
        return entries, errors

    if not isinstance(raw, dict):
        errors.append(GapSyntaxError(str(file_path), -1, "Root document must be a mapping."))
        return entries, errors

    function_cluster = str(raw.get("function_cluster") or "")
    gap_section = raw.get("failing_test_gap_identification") or {}
    components = gap_section.get("components") or []

    idx = 0
    for comp in components:
        if not isinstance(comp, dict):
            continue
        component_name = str(comp.get("name") or "unknown")
        for te in (comp.get("test_entries") or []):
            if not isinstance(te, dict):
                errors.append(GapSyntaxError(str(file_path), idx, "test_entry must be a mapping."))
                idx += 1
                continue
            entry, err = _parse_entry(te, function_cluster, component_name, str(file_path), idx)
            if err:
                errors.append(err)
            else:
                entries.append(entry)  # type: ignore[arg-type]
            idx += 1

    return entries, errors


def _parse_entry(
    te: dict,
    function_cluster: str,
    component: str,
    source_file: str,
    idx: int,
) -> Tuple[Optional[GapEntry], Optional[GapSyntaxError]]:
    scenario_name = te.get("scenario_name")
    if not scenario_name:
        return None, GapSyntaxError(source_file, idx, "Missing mandatory field: scenario_name")

    release = te.get("release")
    if not release:
        return None, GapSyntaxError(source_file, idx, "Missing mandatory field: release")

    gap_specification = te.get("gap_specification")
    if not gap_specification:
        return None, GapSyntaxError(source_file, idx, "Missing mandatory field: gap_specification")

    baselines: List[str] = [str(b) for b in (te.get("baselines") or [])]
    patch_ids: List[str] = [str(p) for p in (te.get("patch_ids") or [])]
    if not baselines and not patch_ids:
        return None, GapSyntaxError(
            source_file, idx,
            "Entry must have at least one of: baselines, patch_ids"
        )

    output_dir_raw = te.get("output_dir")
    output_dir: Optional[str] = str(Path(str(output_dir_raw)).resolve()) if output_dir_raw else None

    return GapEntry(
        function_cluster=function_cluster,
        component=component,
        scenario_name=str(scenario_name),
        configuration_name=_opt_str(te.get("configuration_name")),
        machine_type=_opt_str(te.get("machine_type")),
        test_case_name=_opt_str(te.get("test_case_name")),
        gap_specification=str(gap_specification).strip(),
        mitigations=_opt_str(te.get("mitigations")),
        tags=[str(t) for t in (te.get("tags") or [])],
        baselines=baselines,
        release=str(release),
        patch_ids=patch_ids,
        remarks=_opt_str(te.get("remarks")),
        output_dir=output_dir,
        source_file=source_file,
    ), None


def _opt_str(value: object) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None
