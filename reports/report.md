# Regression Analysis Report

| Field | Value |
|---|---|
| **Report Version** | 2026.11.07.005 |
| **Generated at** | 2026-11-07 06:59:57 UTC |
| **Release** | v1.0 |
| **Reference Baselines** | prefix_261021_125411 |
| **Patch IDs** | PATCH-001 |

**Matched:** 3  
**Unmatched:** 2  
**Syntax Errors:** 0

---

## Matched Entries

### Input: `LoginExact`

| Field | Value |
|---|---|
| Scenario Name | LoginExact |
| Configuration Name | default |
| Machine Type | x86_64 |
| Test Case Name | test_login_success |

**Specificity Score:** 12

#### FC-001 / AuthService

| Field | Value |
|---|---|
| Scenario Name (pattern) | LoginExact |
| Configuration Name (pattern) | default |
| Machine Type (pattern) | x86_64 |
| Test Case Name (pattern) | test_login_success |
| Release | v1.0 |
| Baselines | prefix_261021_125411 |
| Patch IDs | PATCH-001 |
| Tags | auth, login, smoke, jwt |
| Gap Specification | Login success path is not exercised in the current baseline suite. Missing assertion on JWT token expiry handling. |
| Mitigations | Covered by AuthService integration tests in CI pipeline. Manual verification performed on v1.0 RC2. |
| Remarks | Tracked in JIRA AUTH-42. |
| Source File | C:\Users\oadem\Documents\projects\experiment\Experiments\gap_analysis\_repo_cache\Experiments\TestFailureGapSpec\FC-001.yaml |

### Input: `LoginWildcardMatch`

| Field | Value |
|---|---|
| Scenario Name | LoginWildcardMatch |
| Configuration Name | — |
| Machine Type | — |
| Test Case Name | — |

**Specificity Score:** 1

#### FC-001 / AuthService

| Field | Value |
|---|---|
| Scenario Name (pattern) | Login* |
| Configuration Name (pattern) | — |
| Machine Type (pattern) | — |
| Test Case Name (pattern) | — |
| Release | v1.0 |
| Baselines | prefix_261021_125411 |
| Patch IDs | — |
| Tags | — |
| Gap Specification | All Login variant scenarios lack negative path coverage. Edge cases such as account lockout and concurrent sessions are missing. |
| Mitigations | — |
| Remarks | — |
| Source File | C:\Users\oadem\Documents\projects\experiment\Experiments\gap_analysis\_repo_cache\Experiments\TestFailureGapSpec\FC-001.yaml |

### Input: `LoginExact`

| Field | Value |
|---|---|
| Scenario Name | LoginExact |
| Configuration Name | default |
| Machine Type | x86_77 |
| Test Case Name | test_login_success |

**Specificity Score:** 1

#### FC-001 / AuthService

| Field | Value |
|---|---|
| Scenario Name (pattern) | Login* |
| Configuration Name (pattern) | — |
| Machine Type (pattern) | — |
| Test Case Name (pattern) | — |
| Release | v1.0 |
| Baselines | prefix_261021_125411 |
| Patch IDs | — |
| Tags | — |
| Gap Specification | All Login variant scenarios lack negative path coverage. Edge cases such as account lockout and concurrent sessions are missing. |
| Mitigations | — |
| Remarks | — |
| Source File | C:\Users\oadem\Documents\projects\experiment\Experiments\gap_analysis\_repo_cache\Experiments\TestFailureGapSpec\FC-001.yaml |

---

## Unmatched Inputs

| Scenario Name | Configuration Name | Machine Type | Test Case Name |
|---|---|---|---|
| NoMatchScenario | — | — | — |
| NoMatchScenario3 | asdsa | asdasd | dddd |
