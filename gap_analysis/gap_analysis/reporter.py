"""Generate HTML, JSON and Markdown reports."""
from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from .models import FailingTestInput, GapEntry, GapSyntaxError, MatchResult, RunContext


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

def _next_version(output_dir: Path) -> str:
    """Return YYYY.MM.DD.NNN version; increments NNN within the same UTC day."""
    today = datetime.now(timezone.utc).strftime("%Y.%m.%d")
    version_file = output_dir / ".version"
    counter = 1
    if version_file.exists():
        stored = version_file.read_text(encoding="utf-8").strip()
        parts = stored.rsplit(".", 1)
        if len(parts) == 2 and parts[0] == today:
            try:
                counter = int(parts[1]) + 1
            except ValueError:
                counter = 1
    version = f"{today}.{counter:03d}"
    version_file.write_text(version, encoding="utf-8")
    return version


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_reports(
    matched: List[MatchResult],
    unmatched: List[FailingTestInput],
    syntax_errors: List[GapSyntaxError],
    ctx: RunContext,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    version = _next_version(output_dir)
    ctx = dataclasses.replace(ctx, version=version)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    _write_json(matched, unmatched, syntax_errors, ctx, generated_at, output_dir)
    _write_md(matched, unmatched, ctx, generated_at, output_dir)
    _write_html(matched, unmatched, ctx, generated_at, output_dir)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def _write_json(
    matched: List[MatchResult],
    unmatched: List[FailingTestInput],
    syntax_errors: List[GapSyntaxError],
    ctx: RunContext,
    generated_at: str,
    output_dir: Path,
) -> None:
    payload = {
        "version": ctx.version,
        "generated_at": generated_at,
        "run_context": dataclasses.asdict(ctx),
        "matched": [dataclasses.asdict(r) for r in matched],
        "unmatched": [dataclasses.asdict(u) for u in unmatched],
        "syntax_errors": [dataclasses.asdict(e) for e in syntax_errors],
    }
    (output_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _write_md(
    matched: List[MatchResult],
    unmatched: List[FailingTestInput],
    ctx: RunContext,
    generated_at: str,
    output_dir: Path,
) -> None:
    lines: List[str] = []
    lines.append("# Regression Analysis Report\n\n")
    lines.append(_md_header(ctx, generated_at))
    lines.append(f"\n**Matched:** {len(matched)}  \n**Unmatched:** {len(unmatched)}\n")

    if matched:
        lines.append("\n---\n\n## Matched Entries\n")
        for result in matched:
            inp = result.input
            lines.append(f"\n### Input: `{inp.scenario_name}`\n\n")
            if result.is_ambiguous:
                lines.append(
                    "> **Warning:** Ambiguous — multiple entries share the highest "
                    "specificity score. All are listed below.\n\n"
                )
            lines.append(_md_input_table(inp))
            lines.append(f"\n**Specificity Score:** {result.specificity_score}\n")
            for entry in result.matched_entries:
                lines.append(f"\n#### {entry.function_cluster} / {entry.component}\n\n")
                lines.append(_md_entry_table(entry))

    if unmatched:
        lines.append("\n---\n\n## Unmatched Inputs\n\n")
        lines.append("| Scenario Name | Configuration Name | Machine Type | Test Case Name |\n")
        lines.append("|---|---|---|---|\n")
        for inp in unmatched:
            lines.append(
                f"| {inp.scenario_name} "
                f"| {inp.configuration_name or '—'} "
                f"| {inp.machine_type or '—'} "
                f"| {inp.test_case_name or '—'} |\n"
            )

    (output_dir / "report.md").write_text("".join(lines), encoding="utf-8")


def _md_header(ctx: RunContext, generated_at: str) -> str:
    baselines = ", ".join(ctx.reference_baselines) if ctx.reference_baselines else "—"
    patches = ", ".join(ctx.patch_ids) if ctx.patch_ids else "—"
    return (
        f"| Field | Value |\n|---|---|\n"
        f"| **Report Version** | {ctx.version} |\n"
        f"| **Generated at** | {generated_at} |\n"
        f"| **Release** | {ctx.release} |\n"
        f"| **Reference Baselines** | {baselines} |\n"
        f"| **Patch IDs** | {patches} |\n"
    )


def _md_input_table(inp: FailingTestInput) -> str:
    return (
        "| Field | Value |\n|---|---|\n"
        f"| Scenario Name | {inp.scenario_name} |\n"
        f"| Configuration Name | {inp.configuration_name or '—'} |\n"
        f"| Machine Type | {inp.machine_type or '—'} |\n"
        f"| Test Case Name | {inp.test_case_name or '—'} |\n"
    )


def _md_entry_table(entry: GapEntry) -> str:
    return (
        "| Field | Value |\n|---|---|\n"
        f"| Scenario Name (pattern) | {entry.scenario_name} |\n"
        f"| Configuration Name (pattern) | {entry.configuration_name or '—'} |\n"
        f"| Machine Type (pattern) | {entry.machine_type or '—'} |\n"
        f"| Test Case Name (pattern) | {entry.test_case_name or '—'} |\n"
        f"| Release | {entry.release} |\n"
        f"| Baselines | {', '.join(entry.baselines) if entry.baselines else '—'} |\n"
        f"| Patch IDs | {', '.join(entry.patch_ids) if entry.patch_ids else '—'} |\n"
        f"| Tags | {', '.join(entry.tags) if entry.tags else '—'} |\n"
        f"| Gap Specification | {entry.gap_specification.replace(chr(10), ' ')} |\n"
        f"| Mitigations | {(entry.mitigations or '—').replace(chr(10), ' ')} |\n"
        f"| Remarks | {(entry.remarks or '—').replace(chr(10), ' ')} |\n"
        f"| Source File | {entry.source_file} |\n"
    )


# ---------------------------------------------------------------------------
# HTML  (plain f-string; no Jinja2)
# ---------------------------------------------------------------------------

def _h(s: str) -> str:
    """Minimal HTML escaping."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _tr(label: str, value: str) -> str:
    return f"<tr><th>{label}</th><td>{value}</td></tr>\n"


def _write_html(
    matched: List[MatchResult],
    unmatched: List[FailingTestInput],
    ctx: RunContext,
    generated_at: str,
    output_dir: Path,
) -> None:
    baselines = _h(", ".join(ctx.reference_baselines)) if ctx.reference_baselines else "&mdash;"
    patches = _h(", ".join(ctx.patch_ids)) if ctx.patch_ids else "&mdash;"

    header_rows = (
        _tr("Report Version", _h(ctx.version))
        + _tr("Generated at", _h(generated_at))
        + _tr("Release", _h(ctx.release))
        + _tr("Reference Baselines", baselines)
        + _tr("Patch IDs", patches)
        + _tr("Matched", str(len(matched)))
        + _tr("Unmatched", str(len(unmatched)))
    )

    matched_html = _html_matched_section(matched)
    unmatched_html = _html_unmatched_section(unmatched)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Regression Analysis Report</title>
  <style>
    body {{ font-family: sans-serif; margin: 2em; color: #222; }}
    h1 {{ border-bottom: 2px solid #444; }}
    h2 {{ border-bottom: 1px solid #aaa; margin-top: 2em; }}
    h3 {{ margin-top: 1.5em; border-top: 1px solid #ddd; padding-top: 0.5em; }}
    table {{ border-collapse: collapse; margin-bottom: 1em; min-width: 400px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 12px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; white-space: nowrap; }}
    pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    .warn {{ color: #a05000; border-left: 3px solid orange; padding: 4px 8px; }}
    .entry-table {{ margin-left: 1.5em; }}
    .unmatched td, .unmatched th {{ background: #fff8f0; }}
  </style>
</head>
<body>
  <h1>Regression Analysis Report</h1>
  <table>{header_rows}</table>

  <h2>Matched Entries</h2>
  {matched_html or "<p>No matches found.</p>"}

  <h2>Unmatched Inputs</h2>
  {unmatched_html or "<p>All inputs were matched.</p>"}
</body>
</html>"""

    (output_dir / "report.html").write_text(html, encoding="utf-8")


def _html_matched_section(matched: List[MatchResult]) -> str:
    parts: List[str] = []
    for result in matched:
        inp = result.input
        warning = (
            '<p class="warn">&#9888; Ambiguous &mdash; multiple entries share the highest '
            "specificity score. All are listed below.</p>"
            if result.is_ambiguous
            else ""
        )
        input_rows = (
            _tr("Scenario Name", _h(inp.scenario_name))
            + _tr("Configuration Name", _h(inp.configuration_name or "—"))
            + _tr("Machine Type", _h(inp.machine_type or "—"))
            + _tr("Test Case Name", _h(inp.test_case_name or "—"))
        )
        entries_html = "".join(_html_entry(e) for e in result.matched_entries)
        parts.append(
            f"<h3>Input: <code>{_h(inp.scenario_name)}</code></h3>\n"
            f"{warning}\n"
            f"<p><strong>Specificity Score:</strong> {result.specificity_score}</p>\n"
            f"<table>{input_rows}</table>\n"
            f"{entries_html}"
        )
    return "\n".join(parts)


def _html_entry(entry: GapEntry) -> str:
    rows = (
        _tr("Function Cluster / Component", f"{_h(entry.function_cluster)} / {_h(entry.component)}")
        + _tr("Scenario Name (pattern)", _h(entry.scenario_name))
        + _tr("Configuration Name (pattern)", _h(entry.configuration_name or "—"))
        + _tr("Machine Type (pattern)", _h(entry.machine_type or "—"))
        + _tr("Test Case Name (pattern)", _h(entry.test_case_name or "—"))
        + _tr("Release", _h(entry.release))
        + _tr("Baselines", _h(", ".join(entry.baselines) or "—"))
        + _tr("Patch IDs", _h(", ".join(entry.patch_ids) or "—"))
        + _tr("Tags", _h(", ".join(entry.tags) or "—"))
        + _tr("Gap Specification", f"<pre>{_h(entry.gap_specification)}</pre>")
        + _tr("Mitigations", f"<pre>{_h(entry.mitigations or '—')}</pre>")
        + _tr("Remarks", f"<pre>{_h(entry.remarks or '—')}</pre>")
        + _tr("Source File", _h(entry.source_file))
    )
    return f'<table class="entry-table">{rows}</table>\n'


def _html_unmatched_section(unmatched: List[FailingTestInput]) -> str:
    if not unmatched:
        return ""
    rows = "".join(
        f"<tr>"
        f"<td>{_h(u.scenario_name)}</td>"
        f"<td>{_h(u.configuration_name or '—')}</td>"
        f"<td>{_h(u.machine_type or '—')}</td>"
        f"<td>{_h(u.test_case_name or '—')}</td>"
        f"</tr>\n"
        for u in unmatched
    )
    return (
        '<table class="unmatched">'
        "<thead><tr>"
        "<th>Scenario Name</th><th>Configuration Name</th>"
        "<th>Machine Type</th><th>Test Case Name</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )
