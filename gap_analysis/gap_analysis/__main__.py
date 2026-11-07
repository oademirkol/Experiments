"""CLI entry point: python -m gap_analysis."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

import yaml

from .config import load_config
from .matcher import match
from .models import FailingTestInput, RunContext
from .parser import parse_all
from .repo import checkout_repo
from .reporter import generate_reports


def _load_failing_tests(value: str) -> List[dict]:
    p = Path(value)
    if p.exists():
        text = p.read_text(encoding="utf-8")
        if p.suffix.lower() == ".json":
            return json.loads(text)
        return yaml.safe_load(text)
    # fallback: treat value as inline JSON string
    return json.loads(value)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="gap_analysis",
        description="Match failing tests against gap-specification entries.",
    )
    ap.add_argument("--config", default="config.yaml", metavar="PATH",
                    help="Path to config.yaml (default: ./config.yaml)")
    ap.add_argument("--release", required=True,
                    help="Release name (mandatory)")
    ap.add_argument("--baseline", action="append", default=[], dest="baselines",
                    metavar="BASELINE",
                    help="Reference baseline (repeatable)")
    ap.add_argument("--patch", action="append", default=[], dest="patches",
                    metavar="PATCH_ID",
                    help="Patch ID (repeatable)")
    ap.add_argument("--tests", required=True, metavar="FILE_OR_JSON",
                    help="YAML/JSON file with list of failing test dicts, or inline JSON string")
    ap.add_argument("--output", default=None, metavar="DIR",
                    help="Output directory override")
    args = ap.parse_args()

    # --- load config --------------------------------------------------------
    try:
        cfg = load_config(Path(args.config))
    except Exception as exc:
        print(f"ERROR loading config: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- checkout repo ------------------------------------------------------
    try:
        repo_root = checkout_repo(cfg)
    except Exception as exc:
        print(f"ERROR checking out repository: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- parse gap specs ----------------------------------------------------
    gap_spec_dir = repo_root / cfg["github"]["gap_spec_dir"]
    entries, syntax_errors = parse_all(gap_spec_dir)

    for err in syntax_errors:
        print(
            f"SYNTAX ERROR [{Path(err.source_file).name}#{err.entry_index}]: {err.reason}",
            file=sys.stderr,
        )

    # --- build failing test list --------------------------------------------
    try:
        raw_tests = _load_failing_tests(args.tests)
    except Exception as exc:
        print(f"ERROR loading failing tests: {exc}", file=sys.stderr)
        sys.exit(1)

    failing_tests: List[FailingTestInput] = [
        FailingTestInput(
            scenario_name=t["scenario_name"],
            configuration_name=t.get("configuration_name"),
            machine_type=t.get("machine_type"),
            test_case_name=t.get("test_case_name"),
        )
        for t in raw_tests
    ]

    # --- run matching -------------------------------------------------------
    ctx = RunContext(
        release=args.release,
        reference_baselines=args.baselines,
        patch_ids=args.patches,
    )
    matched_results, unmatched_inputs = match(failing_tests, entries, ctx)

    # --- resolve output directory (priority: CLI > entry > config) ----------
    output_dir: Path
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        first_entry_outdir = next(
            (e.output_dir for r in matched_results for e in r.matched_entries if e.output_dir),
            None,
        )
        output_dir = (
            Path(first_entry_outdir).resolve()
            if first_entry_outdir
            else Path(cfg["output"]["base_dir"]).resolve()
        )

    # --- generate reports ---------------------------------------------------
    generate_reports(matched_results, unmatched_inputs, syntax_errors, ctx, output_dir)

    # --- summary ------------------------------------------------------------
    print(f"Reports written to: {output_dir}")
    print(f"  Matched:   {len(matched_results)}")
    print(f"  Unmatched: {len(unmatched_inputs)}")
    if syntax_errors:
        print(f"  Syntax errors in gap specs: {len(syntax_errors)}")


if __name__ == "__main__":
    main()
