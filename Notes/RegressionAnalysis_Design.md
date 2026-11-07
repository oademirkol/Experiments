# Regression Analysis Tooling — Requirements and Design Document

**Version:** 1.2  
**Date:** 2026-11-07  
**Purpose:** This document is the single source of truth required to recreate the `gap_analysis` tool from scratch on any machine, using only this document and no other context.

---

## 1. Purpose and Scope

### What the tool does
The `gap_analysis` tool accepts a list of failing test records and a run context (release name, reference baselines, patch IDs). It connects to a GitHub repository, reads **gap specification files** from a known directory, matches each failing test record against the gap entries using a wildcard-capable specificity engine, and generates three reports (HTML, JSON, Markdown).

### What the tool does NOT do
- It does not run tests.
- It does not modify gap specification files.
- It does not post results to GitHub PRs or issues.
- It does not import any module from the `scripts/` directory of the host repository.

---

## 2. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.9+ | Uses `from __future__ import annotations` throughout |
| GitPython | 3.1+ | Repository checkout |
| PyYAML | 6.0+ | Config and gap-spec parsing |
| `GH_PAT` env var | — | GitHub Personal Access Token; set to `LOCAL` for offline mode |

Install dependencies:
```
pip install -r gap_analysis/requirements.txt
```

`requirements.txt` content:
```
GitPython>=3.1
PyYAML>=6.0
```

---

## 3. Directory and File Inventory

All files live under the `gap_analysis/` directory at the repository root. No files outside this directory are used.

```
gap_analysis/
├── requirements.txt
├── config.yaml
├── gap_analysis/
│   ├── __init__.py           (package marker, one-line docstring)
│   ├── __main__.py           (CLI entry point)
│   ├── models.py             (dataclasses — no I/O)
│   ├── config.py             (config.yaml loader)
│   ├── repo.py               (GitHub checkout)
│   ├── parser.py             (gap-spec file parser + validator)
│   ├── matcher.py            (wildcard matching + specificity scoring)
│   └── reporter.py           (HTML/JSON/MD report writer)
└── tests/
    ├── __init__.py           (empty)
    ├── fixtures/
    │   ├── FC-001.yaml       (synthetic unit-test fixture)
    │   └── sample_tests.yaml (sample failing test list)
    ├── test_parser.py
    ├── test_matcher.py
    ├── test_reporter.py
    └── test_integration.py   (end-to-end CLI tests via subprocess)
```

Additional files outside `gap_analysis/`:

```
TestFailureGapSpec/            ← production gap-spec files read by the tool
│   FC-001.yaml               (Auth Service — exact, wildcard, range, patch-only entries)
│   FC-002.yaml               (Payment Service — multi-baseline, multi-patch, suffix wildcard)
│   FC-003.yaml               (API Gateway — mixed releases, machine_type exact + wildcard)
│   FC-004.yaml               (Notification Service — tags, mitigations, remarks)
│   FC-005.yaml               (Data Pipeline — two identical DataPipeline_* entries → ambiguous)
.vscode/
│   launch.json               (5 VS Code run/debug configurations)
Notes/
│   RegressionAnalysis_Design.md   (this document)
│   GapAnalysis_ClassDiagram.puml  (PlantUML class diagram)
│   GapAnalysis_FlowDiagram.puml   (PlantUML activity flow diagram)
```

---

## 4. Data Models (`models.py`)

All models are `@dataclass` classes. Import: `from gap_analysis.models import ...`

### 4.1 `FailingTestInput`

Represents one failing test provided by the caller.

| Field | Type | Mandatory | Notes |
|---|---|---|---|
| `scenario_name` | `str` | Yes | |
| `configuration_name` | `Optional[str]` | No | default `None` |
| `machine_type` | `Optional[str]` | No | default `None` |
| `test_case_name` | `Optional[str]` | No | default `None` |

### 4.2 `GapEntry`

One test entry parsed from a gap specification file.

| Field | Type | Mandatory | Notes |
|---|---|---|---|
| `function_cluster` | `str` | — | e.g. `FC-001` |
| `component` | `str` | — | Container only; no matching logic |
| `scenario_name` | `str` | Yes | May contain wildcards |
| `configuration_name` | `Optional[str]` | No | May contain wildcards |
| `machine_type` | `Optional[str]` | No | May contain wildcards |
| `test_case_name` | `Optional[str]` | No | May contain wildcards |
| `gap_specification` | `str` | Yes | Multi-line; stripped |
| `mitigations` | `Optional[str]` | No | Multi-line |
| `tags` | `List[str]` | No | |
| `baselines` | `List[str]` | Conditional | Required unless `patch_ids` non-empty |
| `release` | `str` | Yes | |
| `patch_ids` | `List[str]` | Conditional | Required unless `baselines` non-empty |
| `remarks` | `Optional[str]` | No | Multi-line |
| `output_dir` | `Optional[str]` | No | Stored as resolved absolute path string |
| `source_file` | `str` | — | Absolute path to the originating file |

### 4.3 `MatchResult`

One result per `FailingTestInput`.

| Field | Type | Notes |
|---|---|---|
| `input` | `FailingTestInput` | The original input |
| `matched_entries` | `List[GapEntry]` | All top-scoring entries |
| `specificity_score` | `int` | 0–12 |
| `is_ambiguous` | `bool` | `True` when `len(matched_entries) > 1` |

### 4.4 `RunContext`

Run-level metadata.

| Field | Type | Default | Notes |
|---|---|---|---|
| `release` | `str` | — | Mandatory CLI input |
| `reference_baselines` | `List[str]` | — | From `--baseline` args |
| `patch_ids` | `List[str]` | — | From `--patch` args |
| `version` | `str` | `""` | Filled in by `reporter.py` |

### 4.5 `GapSyntaxError`

Validation error collected during parsing.

| Field | Type | Notes |
|---|---|---|
| `source_file` | `str` | Absolute path |
| `entry_index` | `int` | 0-based index within file; `-1` for file-level errors |
| `reason` | `str` | Human-readable description |

---

## 5. `config.yaml` Contract

File location: `gap_analysis/config.yaml` (relative to the working directory when invoking `python -m gap_analysis`).

### Full annotated example
```yaml
github:
  owner: oademirkol        # GitHub repository owner (string)
  repo: Experiments        # GitHub repository name (string)
  branch: main             # Branch to clone/reset to (string)
  gap_spec_dir: TestFailureGapSpec  # Directory within the repo root (string)

# Relative path used when GH_PAT=LOCAL; ".." resolves to repo root when cwd=gap_analysis/
local_path: ..

# Optional: where to cache the repo clone (default: ./_repo_cache/<repo>)
# checkout_dir: ./_repo_cache/Experiments

output:
  base_dir: ./reports      # Default output directory (relative or absolute path)
```

### Validation rules (enforced by `config.py`)

| Condition | Behaviour |
|---|---|
| File does not exist | `FileNotFoundError` |
| File is empty | `ValueError("Config file is empty.")` |
| `github` section missing | `ValueError("Config missing section: [github]")` |
| `github` section is null | `ValueError("Config section [github] is empty.")` |
| Any of `owner/repo/branch/gap_spec_dir` missing | `ValueError("Config missing key: [github].<key>")` |
| `output` section missing | `ValueError("Config missing section: [output]")` |
| `output.base_dir` missing | `ValueError("Config missing key: [output].base_dir")` |

---

## 6. Gap-Specification YAML Schema

### File naming convention
- Pattern: `FC-\d{3}` followed by `.yaml`, `.yml`, or `.json` (case-insensitive)
- Examples: `FC-001.yaml`, `FC-042.yml`, `FC-100.json`
- Files are discovered recursively under `{repo_root}/{gap_spec_dir}/`

### Authoritative format: YAML

JSON is also accepted for reading; YAML is the recommended authoring format.

### Full annotated YAML example
```yaml
function_cluster: FC-001       # string; top-level key; stored verbatim in GapEntry

failing_test_gap_identification:
  components:
    - name: ComponentName      # string; container only; stored in GapEntry.component

      test_entries:

        - scenario_name: "Login*"           # MANDATORY string; wildcard-eligible
          configuration_name: "default"    # optional string; wildcard-eligible; null = absent
          machine_type: "x86_64"           # optional string; wildcard-eligible; null = absent
          test_case_name: null             # optional string; wildcard-eligible; null = absent

          gap_specification: |             # MANDATORY multi-line string
            Description of the coverage gap caused by this failing test.

          mitigations: |                   # optional multi-line string
            How the coverage gap risk is mitigated.

          tags:                            # optional list of strings
            - auth
            - smoke

          baselines:                       # CONDITIONAL: required unless patch_ids non-empty
            - "prefix_261021_125411"       # exact baseline string
            - "range:prefix_261021_125411 - prefix_261101_101145"  # range entry

          release: "v1.0"                  # MANDATORY string

          patch_ids:                       # CONDITIONAL: required unless baselines non-empty
            - "PATCH-001"

          remarks: |                       # optional multi-line string
            Additional notes.

          output_dir: ./reports            # optional path; resolved to absolute at parse time
```

### Baseline format
  - Exact baseline: `<prefix>_<YYMMDD>_<HHMMSS>`
  - Example: `prefix_261021_125411` → 21 Oct 2026 12:54:11
  - Datetime parsed using Python `strptime` format `%y%m%d_%H%M%S`
- Range baseline: `range:<start> - <end>` where `<start>` and `<end>` are exact baseline strings
  - The keyword `range:` must appear at the beginning of the string
  - A space is allowed around `-`
  - A given input baseline falls in range if its parsed datetime is between start and end **inclusive**

### Validation rules (enforced by `parser.py`)

| Condition | Behaviour |
|---|---|
| File cannot be parsed | `GapSyntaxError(entry_index=-1, reason="Parse error: ...")` |
| Root document not a dict | `GapSyntaxError(entry_index=-1, ...)` |
| `scenario_name` absent or empty | `GapSyntaxError(..., "Missing mandatory field: scenario_name")` |
| `release` absent or empty | `GapSyntaxError(..., "Missing mandatory field: release")` |
| `gap_specification` absent or empty | `GapSyntaxError(..., "Missing mandatory field: gap_specification")` |
| Both `baselines` and `patch_ids` empty | `GapSyntaxError(..., "Entry must have at least one of: baselines, patch_ids")` |
| One entry invalid | Error collected; remaining entries still parsed |

---

## 7. Matching Algorithm (`matcher.py`)

### Overview

For each `FailingTestInput`, iterate over all `GapEntry` objects. Apply context filters, then score by specificity. Keep only the highest-scoring entries.

### Step 1 — Context filters

All three filters must pass. If any fails, the entry is skipped for this input.

**Release filter:**
```
entry.release == ctx.release
```

**Baseline filter:**
- If `ctx.reference_baselines` is empty: **pass** (no restriction).
- Otherwise: at least one `(input_baseline, entry_baseline)` pair must match.
  - Exact match: `input_baseline.strip() == entry_baseline.strip()`
  - Range match: `input_baseline` datetime is between range start and end (inclusive)

**Patch filter:**
- If `ctx.patch_ids` is empty **or** `entry.patch_ids` is empty: **pass** (no restriction).
- Otherwise: `set(ctx.patch_ids) ∩ set(entry.patch_ids)` must be non-empty.

### Step 2 — Specificity scoring

Four fields are scored: `scenario_name`, `configuration_name`, `machine_type`, `test_case_name`.

**`_field_score(pattern, value)` rules:**

| Condition | Score | Meaning |
|---|---|---|
| `pattern is None` | 0 | No constraint on this field; entry not disqualified |
| `pattern` does not match `value` | `None` | Entry **disqualified** for this input |
| `pattern` matches, no `*` in pattern | 3 | Exact match |
| `pattern` matches, `*` present, `pattern.strip("*")` is truthy | 1 | Partial wildcard (e.g. `Login*`, `*_cfg`) |
| `pattern` matches, `pattern.strip("*")` is falsy (e.g. `*`) | 0 | Full wildcard |

- Matching uses `fnmatch.fnmatchcase(value, pattern)` from Python stdlib.
- If `value` is `None`, it is treated as `""` before matching.
- Maximum total score: 4 fields × 3 = **12 points**.

**`_score_entry(entry, test_input)` returns:**
- `None` if any field is disqualified (`_field_score` returned `None`)
- `int` (0–12) sum of all four field scores

### Step 3 — Selection

- Collect all `(score, entry)` pairs that passed filters and returned a non-None score.
- Find `max_score = max(score for score, _ in candidates)`.
- Keep all entries with `score == max_score`.
- If `len(top) > 1`: `is_ambiguous = True`.
- If zero candidates: input goes to the **unmatched** list.

### Return value

`match(failing_tests, entries, ctx)` returns `(List[MatchResult], List[FailingTestInput])`.

---

## 8. CLI Reference (`__main__.py`)

**Invocation:**
```
python -m gap_analysis [options]
```

**Arguments:**

| Argument | Type | Required | Repeatable | Default | Description |
|---|---|---|---|---|---|
| `--config` | path | No | No | `./config.yaml` | Path to config.yaml |
| `--release` | str | **Yes** | No | — | Release name |
| `--baseline` | str | No | Yes | `[]` | Reference baseline(s) |
| `--patch` | str | No | Yes | `[]` | Patch ID(s) |
| `--tests` | str | **Yes** | No | — | Path to YAML/JSON file with list of dicts, or inline JSON string |
| `--output` | path | No | No | from config | Output directory override |

**Failing tests file format** (`--tests`):
```yaml
- scenario_name: LoginExact
  configuration_name: default
  machine_type: x86_64
  test_case_name: test_login_success

- scenario_name: LoginWild
```

Or inline JSON:
```
--tests '[{"scenario_name": "Login", "configuration_name": null}]'
```

**Exit codes:**

| Code | Condition |
|---|---|
| 0 | Success (even if some inputs are unmatched) |
| 1 | Config load error, repo checkout error, or failing tests parse error |

**Stdout summary (always printed):**
```
Reports written to: /absolute/path/to/reports
  Matched:   3
  Unmatched: 1
  Syntax errors in gap specs: 1
```

**Stderr (only on errors/warnings):**
```
SYNTAX ERROR [FC-001.yaml#5]: Missing mandatory field: release
ERROR loading config: Config missing section: [github]
```

---

## 9. Repository Checkout (`repo.py`)

**Function:** `checkout_repo(cfg: dict) -> Path`

**Logic:**
1. Read `GH_PAT` from environment (`os.environ.get("GH_PAT", "")`).
2. If `GH_PAT == "LOCAL"`:
   - Read `cfg.get("local_path")`.
   - If absent: raise `ValueError("GH_PAT=LOCAL requires a 'local_path' key in config.yaml ...")`.
   - Return `Path(local_path).resolve()`.
3. If `GH_PAT` is empty: raise `EnvironmentError("Environment variable GH_PAT is not set. ...")`.
4. Build URL: `f"https://{gh_pat}@github.com/{owner}/{repo}.git"`.
5. Determine `checkout_dir = Path(cfg.get("checkout_dir", f"_repo_cache/{repo}"))`.
6. If `checkout_dir` exists and contains `.git/`:
   - `repo_obj.remotes.origin.fetch()`
   - `repo_obj.git.reset("--hard", f"origin/{branch}")`
7. Otherwise:
   - `checkout_dir.parent.mkdir(parents=True, exist_ok=True)`
   - `git.Repo.clone_from(remote_url, checkout_dir, branch=branch, depth=1)`
8. Return `checkout_dir.resolve()`.

---

## 10. Report Generation (`reporter.py`)

### Versioning

**Scheme:** `YYYY.MM.DD.NNN`  
**Counter file:** `{output_dir}/.version` (plain text, one line)

**Algorithm (`_next_version`):**
1. `today = datetime.now(timezone.utc).strftime("%Y.%m.%d")`
2. If `.version` exists: read stored string, split on last `.` to get `(date_part, counter_str)`.
   - If `date_part == today`: `counter = int(counter_str) + 1`
   - Else: `counter = 1`
3. Else: `counter = 1`
4. Write `f"{today}.{counter:03d}"` to `.version`.
5. Return the version string.

### `generate_reports(matched, unmatched, syntax_errors, ctx, output_dir)`

1. `output_dir.mkdir(parents=True, exist_ok=True)`
2. Call `_next_version(output_dir)` → fill `ctx.version`
3. `generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")`
4. Write `report.json`, `report.md`, `report.html` — all in `output_dir`

### Output directory resolution (in `__main__.py`)

Priority (highest first):
1. `--output` CLI argument (if provided)
2. First non-None `entry.output_dir` from any matched entry
3. `cfg["output"]["base_dir"]` from config

Always call `Path(...).resolve()` on the chosen path.

### JSON report (`report.json`)

```json
{
  "version": "2026.11.07.001",
  "generated_at": "2026-11-07 10:30:00 UTC",
  "run_context": {
    "release": "v1.0",
    "reference_baselines": ["prefix_261021_125411"],
    "patch_ids": ["PATCH-001"],
    "version": "2026.11.07.001"
  },
  "matched": [
    {
      "input": { "scenario_name": "Login", ... },
      "matched_entries": [ { ... GapEntry fields ... } ],
      "specificity_score": 12,
      "is_ambiguous": false
    }
  ],
  "unmatched": [
    { "scenario_name": "NoMatch", "configuration_name": null, "machine_type": null, "test_case_name": null }
  ],
  "syntax_errors": [
    { "source_file": "/abs/path/FC-001.yaml", "entry_index": 5, "reason": "Missing mandatory field: release" }
  ]
}
```

Serialization: `dataclasses.asdict(obj)` applied to each dataclass instance.

### Markdown report (`report.md`)

Structure:
1. `# Regression Analysis Report`
2. Header table (6 rows): Report Version, Generated at, Release, Reference Baselines, Patch IDs
3. Summary line: `**Matched:** N  **Unmatched:** N  **Syntax Errors:** N`
4. `## Matched Entries`
   - Per `MatchResult`: `### Input: \`<scenario_name>\``
   - Ambiguity warning (blockquote) if `is_ambiguous`
   - Input table (4 rows)
   - Specificity Score line
   - Per entry: `#### FC-xxx / ComponentName` + entry table (13 rows)
5. `## Unmatched Inputs`
   - Table with 4 columns: `Scenario Name | Configuration Name | Machine Type | Test Case Name`
6. `## Syntax Errors in Gap Specifications` *(only present when errors exist)*
   - Table with 3 columns: `Source File | Entry # | Reason`

### HTML report (`report.html`)

Structure:
- `<!DOCTYPE html>` + UTF-8 charset + inline CSS (no external dependencies)
- `<h1>Regression Analysis Report</h1>`
- Header `<table>` (8 rows: Report Version, Generated at, Release, Reference Baselines, Patch IDs, Matched, Unmatched, Syntax Errors)
- `<h2>Matched Entries</h2>` section — `<h3>Input: <code>...</code></h3>` per result
- `<h2>Unmatched Inputs</h2>` section — `<table class="unmatched">` with 4 `<th>` columns
- `<h2>Syntax Errors in Gap Specifications</h2>` section — `<table class="syntax-errors">` with 3 `<th>` columns: Source File, Entry #, Reason

CSS classes used for visual differentiation:

| Class | Background | Used for |
|---|---|---|
| `.entry-table` | (indented) | Matched gap entry details |
| `.unmatched` | `#fff8f0` (orange tint) | Unmatched inputs table |
| `.syntax-errors` | `#fff0f0` (red tint) | Syntax error table |

HTML escaping: all dynamic values escaped via `_h(s)`:
```python
def _h(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

No Jinja2. No external CSS files.

---

## 11. Offline / Test Mode

Set `GH_PAT=LOCAL`. The `config.yaml` shipped in `gap_analysis/` already has `local_path: ..` set, which resolves to the repository root when the working directory is `gap_analysis/`. No manual edit is needed.

- `repo.py` skips all git operations and returns `Path(local_path).resolve()` directly.
- Useful for CI fixture testing and development without a network connection.

**Example invocation (no config edit required):**
```powershell
$env:GH_PAT = "LOCAL"
python -m gap_analysis `
  --config config.yaml `
  --release v1.0 `
  --baseline prefix_261021_125411 `
  --tests tests/fixtures/sample_tests.yaml
```

To point to a different directory (e.g. a separate clone), override `local_path` in `config.yaml` with an absolute path:
```yaml
local_path: C:/path/to/other/clone
```

---

## 12. Error Handling Contract

| Error type | Where raised | Behaviour |
|---|---|---|
| Config file not found | `config.py` | `FileNotFoundError` → CLI prints `ERROR loading config: ...` → `sys.exit(1)` |
| Config validation error | `config.py` | `ValueError` → CLI prints `ERROR loading config: ...` → `sys.exit(1)` |
| Repo checkout failure | `repo.py` | Any exception → CLI prints `ERROR checking out repository: ...` → `sys.exit(1)` |
| Failing tests file not found / invalid | `__main__.py` | Exception → `ERROR loading failing tests: ...` → `sys.exit(1)` |
| Gap-spec file parse / validation error | `parser.py` | Collected as `GapSyntaxError`; parsing continues; errors printed to stderr **and included in all three report formats** |
| No gap-spec files found | `parser.py` | Returns `([], [])` — tool runs normally, all inputs unmatched |

---

## 13. Test Fixture Specification

### Unit test fixture: `tests/fixtures/FC-001.yaml`

Contains 6 test entries designed to exercise distinct parser scenarios:

| Entry # | `scenario_name` | Purpose |
|---|---|---|
| 1 | `LoginExact` | Exact match on all 4 fields; has both baselines and patch_ids |
| 2 | `Login*` | Wildcard scenario name; no optional fields; baseline only |
| 3 | `PasswordReset` | Baseline range entry |
| 4 | `OAuthFlow` | patch_ids only (no baselines) |
| 5 | `PaymentCapture` | Different release (`v2.0`); valid syntax but excluded by release filter |
| 6 | `BrokenEntry` | Missing `release`; triggers `GapSyntaxError` |

**Expected parse result:** `len(entries) == 5`, `len(errors) == 1`.

### Unit test sample inputs: `tests/fixtures/sample_tests.yaml`

Three failing test records:
1. `LoginExact` with all 4 fields — exactly matches entry 1
2. `LoginWildcardMatch` with all Nones — matches entry 2 via `Login*`
3. `NoMatchScenario` — appears in unmatched

### Integration test fixtures: `TestFailureGapSpec/FC-001.yaml` – `FC-005.yaml`

Five production-style gap-spec files used exclusively by `test_integration.py`. Each exercises distinct features:

| File | Components | Key features exercised |
|---|---|---|
| `FC-001.yaml` | AuthService, PasswordService | Exact all-4-fields (score=12); `Login*` partial wildcard; `*Session*` double wildcard + baseline range; `LogoutExact` patch-only; `PasswordReset*` range |
| `FC-002.yaml` | PaymentProcessor, InvoiceService | Multiple baselines; multiple patch IDs; `Refund_*` suffix wildcard; `machine_type: *` full wildcard; `*Invoice*` double wildcard with tags/remarks |
| `FC-003.yaml` | GatewayCore, HealthMonitor | `API_RateLimit` exact score=12; `API_*` + exact machine_type (score=4); `*_Timeout` suffix wildcard + range; `Gateway_Health` **release v2.0** (release filter test) |
| `FC-004.yaml` | SMSGateway, EmailService | All 4 fields + tags + mitigations + remarks; `SMS_*` multi-patch; `Email_*` range; `Push_Notification*` patch-only |
| `FC-005.yaml` | DataIngestion, DataProcessing, DataExport | Two `DataPipeline_*` entries with identical score → `is_ambiguous=True`; multi-baseline export entry |

### Integration test module: `tests/test_integration.py`

- **36 tests** across 9 test classes.
- Each test creates an isolated temp directory, writes a config pointing `local_path` to the workspace root with `GH_PAT=LOCAL`, runs the CLI via `subprocess.run`, and inspects stdout, exit code, and report files.
- No shared state between tests; each test is fully self-contained.
- Test classes: `TestExactMatch`, `TestWildcardMatch`, `TestReleaseFilter`, `TestBaselineFilter`, `TestPatchFilter`, `TestAmbiguousMatch`, `TestUnmatched`, `TestReportFiles`, `TestSyntaxErrors`, `TestCLIErrors`.

---

## 14. VS Code Launch Configurations (`.vscode/launch.json`)

Five configurations available in the Run & Debug panel:

| Name | Module | `cwd` | `GH_PAT` | Purpose |
|---|---|---|---|---|
| Unit Tests | `unittest discover tests/ -v` | `gap_analysis/` | not set | Run parser/matcher/reporter unit tests only |
| Integration Tests | `unittest tests/test_integration.py -v` | `gap_analysis/` | `LOCAL` | Run CLI integration tests only |
| All Tests (Unit + Integration) | `unittest discover tests/ -v` | `gap_analysis/` | `LOCAL` | Run all 96 tests |
| Run Tool (sample data, LOCAL) | `gap_analysis` | `gap_analysis/` | `LOCAL` | Execute tool against local gap specs with sample data |
| Debug Tool (step through) | `gap_analysis` | `gap_analysis/` | `LOCAL` | Same as above with `justMyCode: false` for stepping into library code |

All configurations use `"type": "debugpy"` and `"console": "integratedTerminal"`.

---

## 15. GitHub Actions Reusable Workflow

The `gap_analysis` runner can be used from any repository via a reusable GitHub workflow. This is the recommended way to trigger the tool from another repo without copying the CLI code. The reusable workflow lives in this repository at `.github/workflows/gap-analysis-reusable.yml`.

### Contract

The workflow accepts the following inputs:

| Input | Required | Default | Purpose |
|---|---|---|---|
| `target_repo` | No | current repo | The repository to analyze, in `owner/repo` form |
| `target_ref` | No | `main` | Branch or tag to inspect |
| `gap_spec_dir` | Yes | — | Directory under the target repo root containing gap-spec YAML files |
| `release` | Yes | — | Release label used for matching |
| `tests_file` | Yes | — | Relative path to the failing-tests YAML/JSON file |
| `baseline` | No | `""` | Comma-separated list of reference baselines |
| `patch` | No | `""` | Comma-separated list of patch IDs |
| `output_dir` | No | `reports` | Output directory inside the target repo |
| `tool_ref` | No | `main` | Branch/tag/SHA of the tool repo to check out |
| `clone_mode` | No | `local` | `local` uses a checked-out repo; `remote` enables GitHub clone mode |

The workflow also accepts an optional `GH_PAT` secret for remote clone mode. Local mode works without a secret and is the default because it is deterministic and does not depend on repository network access.

### Example caller workflow

```yaml
jobs:
  regression-analysis:
    uses: oademirkol/Experiments/.github/workflows/gap-analysis-reusable.yml@main
    with:
      target_repo: my-org/target-repo
      target_ref: main
      gap_spec_dir: TestFailureGapSpec
      release: v1.0
      tests_file: artifacts/failing-tests.yaml
      baseline: prefix_261021_125411
      patch: PATCH-001
      output_dir: reports
    secrets:
      GH_PAT: ${{ secrets.GH_PAT }}
```

### Runtime behavior

1. The workflow checks out the target repository into a local directory.
2. It checks out the tool repository and installs the Python dependency set.
3. It creates a temporary `config.yaml` that points the CLI at the checked-out target repo using `local_path`.
4. It runs `python -m gap_analysis` with the provided release, baseline, patch, and failing-tests inputs.
5. It uploads the generated `report.json`, `report.md`, `report.html`, and `.version` files as workflow artifacts.

This makes the gap-analysis script reusable across repos without copying any implementation code into each consumer repository.

---

## 16. Verification Checklist

Run all commands from the `gap_analysis/` directory.

### Step 1 — Install dependencies
```powershell
cd gap_analysis
pip install -r requirements.txt
```
Expected: exits 0, installs `GitPython` and `PyYAML`.

### Step 2 — Run unit tests
```powershell
python -m unittest discover tests/
```
Expected: **59 tests**, all pass (`OK`).

### Step 3 — Run integration tests
```powershell
$env:GH_PAT = "LOCAL"
python -m unittest tests/test_integration.py -v
```
Expected: **36 tests**, all pass (`OK`). Requires `TestFailureGapSpec/FC-001.yaml` – `FC-005.yaml` to exist.

### Step 4 — Run full suite
```powershell
$env:GH_PAT = "LOCAL"
python -m unittest discover tests/ -v
```
Expected: **96 tests total**, all pass.

### Step 5 — Offline smoke test
`local_path: ..` is already set in `config.yaml`. Run from `gap_analysis/`:
```powershell
$env:GH_PAT = "LOCAL"
python -m gap_analysis `
  --config config.yaml `
  --release v1.0 `
  --baseline prefix_261021_125411 `
  --patch PATCH-001 `
  --tests tests/fixtures/sample_tests.yaml
```
Expected stdout:
```
Reports written to: <absolute path to reports/>
  Matched:   <n>
  Unmatched: <n>
```

### Step 6 — Verify report files
```powershell
Test-Path reports/report.json  # → True
Test-Path reports/report.md    # → True
Test-Path reports/report.html  # → True
Test-Path reports/.version     # → True
Get-Content reports/.version   # → e.g. 2026.11.07.001
```

### Step 7 — Verify JSON structure
```powershell
python -c "import json; d=json.load(open('reports/report.json')); print(list(d.keys()))"
```
Expected: `['version', 'generated_at', 'run_context', 'matched', 'unmatched', 'syntax_errors']`

### Step 8 — Verify Markdown sections
```powershell
Select-String -Path reports/report.md -Pattern "Scenario Name|Configuration Name|Machine Type|Test Case Name"
Select-String -Path reports/report.md -Pattern "Syntax Errors"
```
Expected: all four unmatched-table column headers found; `Syntax Errors` section heading found.

### Step 9 — Verify HTML escaping
```powershell
Select-String -Path reports/report.html -Pattern "<script>"
```
Expected: no matches (special chars escaped as `&lt;script&gt;`).

### Step 10 — Verify syntax errors appear in reports
Run the tool pointing at a gap-spec directory containing a file with a missing `release` field. Confirm:
- `report.json` has `syntax_errors` array with at least one entry.
- `report.md` contains `## Syntax Errors in Gap Specifications` section.
- `report.html` contains `<h2>Syntax Errors` and a table with class `syntax-errors`.

### Step 11 — Version counter increments
```powershell
python -m gap_analysis --config config.yaml --release v1.0 --tests tests/fixtures/sample_tests.yaml
Get-Content reports/.version   # → ...001
python -m gap_analysis --config config.yaml --release v1.0 --tests tests/fixtures/sample_tests.yaml
Get-Content reports/.version   # → ...002
```

---

## 17. Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| File format | YAML (JSON also read) | Handles multi-line strings and arrays; human-readable; AI-reproducible |
| Config format | YAML | Consistent with gap-spec format; well-supported in CI |
| Wildcard matching | `fnmatch.fnmatchcase` (stdlib) | No extra dependency; supports `*` patterns |
| HTML generation | Plain Python f-strings | No Jinja2 dependency |
| Component role | Container only | Spec §2.2: component has no functional impact on matching |
| Tie-breaking | Retain all; `is_ambiguous=True` | Avoids silent incorrect selection |
| Version scheme | `YYYY.MM.DD.NNN` | Human-readable; unique per day; no external state except `.version` file |
| External libraries | GitPython + PyYAML only | Minimal surface; easy to reproduce |
| Syntax errors in reports | All three formats | Broken entries are never silently discarded; they appear in JSON `syntax_errors` array, MD `## Syntax Errors` table, and HTML `<table class="syntax-errors">` so operators can audit gaps in the gap-spec files themselves |
| Integration tests | `subprocess.run` + `GH_PAT=LOCAL` | Tests the real CLI contract end-to-end; each test is isolated via a temp directory config; no monkeypatching |
