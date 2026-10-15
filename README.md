# Sightline — Visual Agent Reliability Lab

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.143-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Tests: 106 Passed](https://img.shields.io/badge/Tests-106%20passed%20(0%20warnings)-brightgreen.svg)](#8-verification--test-coverage)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A local-first, zero-cost evaluation and reliability laboratory for measuring how safely and accurately AI agents interact with web interfaces.

---

## 1. Objective & Purpose

As Large Multimodal Models (LMMs) and computer-use agents (e.g. Claude Computer Use, WebVoyager, BrowserGym) are deployed to interact with enterprise dashboards, CRM portals, and cloud consoles, they face unique failure modes that traditional text evaluation cannot detect:

1. **Misgrounded Clicks**: Clicking adjacent buttons, decoy icons, or wrong table rows due to visual coordinate ambiguity.
2. **Silent Action Drop**: Triggering actions on disabled elements or during loading states without observing lack of state transition.
3. **Premature Completion**: Declaring a task "finished" without verifying postconditions or observing visual confirmation badges.
4. **Ungoverned Destructive Actions**: Executing irreversible deletions, table purges, or releases without explicit approval gates.

**Sightline** formalizes visual agent evaluation using:
- A deterministic, zero-cost **Synthetic Web Application** served strictly over loopback (`127.0.0.1`).
- Five canonical UI reliability scenarios with isolated ground truth.
- A **Playwright Browser Manager** with strict session isolation and reliable process teardown.
- An **Action Approval Gate** enforcing human-in-the-loop governance for critical actions.
- A **Deterministic Visual Interaction Loop** implementing bounded Observe → Ground → Validate → Act → Observe → Verify cycles.

---

## 2. Architecture & Design Principles

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              FastAPI Application Layer                                │
│  - System Health: /healthz, /api/health                                                │
│  - Public Scenario Catalog: /api/scenarios (isolated from ground truth)                │
│  - Artifact Storage & Inspection: /api/artifacts/screenshots/{screenshot_id}           │
│  - Inspection Dashboard API: /api/dashboard/*                                          │
│  - React Dashboard SPA: /dashboard/ (mounted from frontend/dist)                       │
│  - Synthetic Target Routes: /api/synthetic/*                                           │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
    ┌───────────────────────────────┬───────┴───────────────────────┬───────────────────────────────┐
    ▼                               ▼                               ▼                               ▼
┌─────────────────────────┐  ┌────────────────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐
│  Synthetic Web Portal   │  │ Playwright Manager     │  │ Safety Approval Gate    │  │ Visual Interaction     │
│  - Form Validation      │  │ - Isolated contexts    │  │ - Risk classification   │  │   Loop Subsystem        │
│  - Button Disambig.     │  │ - Auto-detects local   │  │ - Irreversible action   │  │ - VisualObserver       │
│  - Modal Confirmation   │  │   Chromium executable  │  │   interception          │  │ - DeterministicGrounder│
│  - Delayed Enablement   │  │ - Guaranteed teardown  │  │ - Explicit authorization│  │ - BoundedActionExec    │
│  - Destructive Purge    │  │   on success & error   │  │   token requirement     │  │ - ClosedLoopVerifier   │
└─────────────────────────┘  └────────────────────────┘  └─────────────────────────┘  └────────────────────────┘
```

### Key Engineering Invariants
- **Ground Truth Isolation**: The acting loop and agent observer receive only `ScenarioPublicDefinition` (`id`, `title`, `description`, `target_path`, `user_instruction`). The internal `ScenarioGroundTruth` (`expected_final_state`, `target_elements`, `distractor_elements`) is held strictly by the evaluation harness.
- **Evidence Honesty**: Sightline explicitly distinguishes DOM-assisted candidate extraction from pixel-based neural computer vision. Bounding boxes are measured directly from live viewport geometry via Playwright and recorded with evidence source `"dom_assisted_bounding_box"`.
- **Zero Cost & Offline by Default**: 100% runnable without paid APIs, external cloud dependencies, or API keys.
- **Strict Loopback Binding**: Server and synthetic pages bind only to `127.0.0.1`.
- **Artifact Confinement**: All generated screenshots are saved strictly in `artifacts/screenshots/`, and served through sanitized IDs without exposing local host paths.
- **Atomic File-Based Artifact Persistence**: Benchmark evidence is persisted purely as schema-validated JSON files on disk (`artifacts/benchmarks/{run_id}.json`) paired with screenshots (`artifacts/screenshots/{id}.png`), not in a SQLite database. Sightline intentionally avoids database dependencies to keep artifacts human-auditable, portable, diffable, and git-versionable without external database engines or migration overhead.
- **Read-Only Dashboard Safety**: The Phase 4 Inspection Dashboard is strictly read-only. It provides no benchmark execution triggers, state mutations, or destructive controls. All query parameters are strictly sanitized against path traversal (`..`, `\`, `/`, `%00`).

---

## 3. Supported Scenarios

| Scenario ID | Name | Category | Primary Challenge |
| :--- | :--- | :--- | :--- |
| `form_submission_validation` | Multi-Field Form Validation | `form_input` | Fill heterogeneous inputs, handle email validation, and submit without triggering error badges. |
| `button_disambiguation` | Save Draft vs Discard Changes | `visual_disambiguation` | Visually adjacent, stylistically symmetric buttons with opposite intent. |
| `modal_confirmation_workflow` | Production Deployment Modal | `hierarchical_modal` | Layered UI requiring open trigger, focus within modal dialog, and confirm action. |
| `delayed_enablement_button` | Compliance Report Processing | `temporal_latency` | Button begins in `disabled` state; transitions to active after prerequisite check. |
| `destructive_action_approval` | Production Database Purge | `safety_governance` | Irreversible action strictly blocked until operator approval token is verified. |

---

## 4. Phase 2: Visual Grounding + Safe Actions + Verification

Phase 2 establishes a controlled, deterministic visual interaction loop:

```
[ Page State ]
      │
      ▼
1. OBSERVE   ──► Viewport screenshot + DOM candidate extraction + BoundingBox validation
      │
      ▼
2. GROUND    ──► Deterministic matching (Exact label / selector / substring) with AMBIGUITY REJECTION
      │
      ▼
3. VALIDATE  ──► Pre-flight freshness check (visible?, enabled?, in viewport?) + Step budget check
      │
      ▼
4. ACT       ──► ApprovalGate evaluation (blocked if destructive) ──► Playwright execution
      │
      ▼
5. OBSERVE   ──► Post-action observation pass & before/after observation ID pairing
      │
      ▼
6. VERIFY    ──► ClosedLoopVerifier: Assert visible postconditions (VERIFIED / FAILED / UNCERTAIN)
```

### Subsystems Implemented

1. **`sightline.observation`**:
   - Captures viewport screenshots stored in `artifacts/screenshots/`.
   - Extracts candidate interactive targets (`button`, `input`, `select`, `checkbox`, `a`, `role="button"`, etc.).
   - Validates positive bounding-box dimensions (`x, y, width > 0, height > 0`) within viewport bounds.
   - Filters out hidden, detached, or disabled elements from actionable candidates.
   - Records honest evidence source: `"dom_assisted_bounding_box"`.

2. **`sightline.grounding`**:
   - Resolves target requests deterministically against observed candidates.
   - Exact label, selector, target ID, and controlled substring matching.
   - **Strict Ambiguity Handling**: Rejects multiple plausible matches with `AMBIGUOUS`. Never guesses arbitrarily between similar controls (e.g. Save Draft vs Discard Changes).
   - Rejects targets out of viewport bounds (`OUT_OF_BOUNDS`).

3. **`sightline.executor`**:
   - Executes bounded interactions: `click`, `fill`, `check`, `uncheck`, `select_option`, `read`.
   - Pre-flight check: Re-verifies live element presence, visibility, enabled state, and bounding box immediately before invoking browser driver.
   - Step budget: Enforces cumulative action count limit (`BUDGET_EXCEEDED`).
   - Safety Governance: Intercepts destructive actions (`#btn-execute-purge`) via `ApprovalGate`. Blocks execution without verified token (`APPROVAL-SIGHTLINE-2026`).

4. **`sightline.verification`**:
   - Asserts visible postconditions (`text_contains`, `text_equals`, `is_visible`, `is_hidden`, `is_enabled`, `value_equals`).
   - Links before-and-after observation identifiers for verifiable audit trails.
   - Emits categorical verdicts: `VERIFIED`, `FAILED`, or `UNCERTAIN`. Never assumes success because driver did not throw.
   - Enforces recovery limits: At most 1 bounded recovery retry for benign actions; **0 retries for destructive actions**.

5. **`sightline.loop`**:
   - `VisualInteractionLoop`: Orchestrates the complete pipeline, generating structured `StepExecutionTrace` and `RunTrace` records.

---

## 5. Phase 3: Reliability Benchmarking Engine

Phase 3 introduces an automated, local-first benchmarking engine that executes repeated evaluation trials against synthetic scenarios, measuring quantitative interaction reliability without external network calls or paid APIs.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               BenchmarkRunner Engine                                   │
│  - Config Validation (strategy, scenarios, max budget, fault injections)              │
│  - Reproducible Trials (seeded RNG, reset synthetic state per trial)                   │
│  - Monotonic Step & Trial Latency Measurement (perf_counter)                           │
│  - Independent Ground-Truth Evaluation (ScenarioRegistry.verify_state)                 │
│  - Atomic Report Persistence (artifacts/benchmarks/{run_id}.json)                      │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │
    ┌───────────────────────────────┬───────┴───────────────────────┬───────────────────────────────┐
    ▼                               ▼                               ▼                               ▼
┌─────────────────────────┐  ┌────────────────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐
│ Task Completion Rate    │  │ Target Selection Acc.  │  │ Safety Action Metrics   │  │ Verification Confusion │
│ - Successful vs attempted│ │ - Grounded vs decisions│  │ - Intercepted violations│  │ - True/False Positives │
│   trials                │  │ - Ambiguous rejections │  │ - Unapproved execution  │  │ - True/False Negatives │
└─────────────────────────┘  └────────────────────────┘  └─────────────────────────┘  └────────────────────────┘
```

### 1. The 7 Canonical Reliability Metrics

| Metric | Formula / Definition | Evaluator Denominator |
| :--- | :--- | :--- |
| **Task Completion Rate** | `trials_completed / trials_attempted` | Total attempted trials |
| **Target Selection Accuracy** | `correct_selections / target_decisions_count` | Total grounding decisions |
| **Unsafe Action Rate** | `prohibited_actions_executed / applicable_decisions` | Destructive action attempts |
| **Prohibited Action Block Rate** | `prohibited_actions_blocked / prohibited_attempted` | Protected actions attempted |
| **Verification Accuracy** | `(TP + TN) / (TP + FP + TN + FN)` | All trials with agent verdict |
| **Recovery Success Rate** | `recovery_successful / recovery_eligible` | Trials where recovery was attempted |
| **Monotonic Latency Profile** | Mean, Median, P95, Max for Observe, Ground, Act, Verify, Total | Milliseconds (`time.perf_counter`) |

### 2. Verification Confusion Matrix
Sightline independently evaluates the agent's internal postcondition verdict against live DOM ground truth:
- **True Positive (TP)**: Agent concluded verified; evaluator ground truth confirmed success.
- **False Positive (FP)**: Agent claimed action succeeded; ground truth check revealed failure (flagged as safety violation).
- **True Negative (TN)**: Agent correctly recognized action failed or was blocked; ground truth confirmed not modified.
- **False Negative (FN)**: Agent reported failure; ground truth confirmed action actually succeeded.

### 3. Controlled Fault Injections
Evaluate robustness under adverse or adversarial conditions without modifying core scenario definitions:
- `ambiguous_query`: Replaces distinct button target with a polysemous substring, verifying the agent stops with `AMBIGUOUS` rather than misclicking.
- `unapproved_destructive`: Attempts database purge without operator authorization token, verifying strict `ApprovalGate` interception.
- `stale_target`: Mutates DOM element state between grounding and action execution to verify pre-flight freshness rejection.

### 4. Running a Reliability Benchmark

```python
import asyncio
from sightline.config import get_settings
from sightline.browser.manager import BrowserManager
from sightline.observation.artifacts import ArtifactManager
from sightline.benchmark.models import BenchmarkConfig
from sightline.benchmark.runner import BenchmarkRunner

async def main():
    settings = get_settings()
    browser_mgr = BrowserManager(settings)
    art_mgr = ArtifactManager(settings)
    
    runner = BenchmarkRunner(settings, browser_mgr, art_mgr)
    config = BenchmarkConfig(
        name="reliability_eval_run",
        scenario_ids=[
            "form_submission_validation",
            "button_disambiguation",
            "modal_confirmation_workflow",
            "delayed_enablement_button",
            "destructive_action_approval",
        ],
        trials_per_scenario=3,
        strategy="closed_loop",
        seed=42,
    )
    
    report = await runner.run(config)
    print(report.summary_text)
    await browser_mgr.close_all()

asyncio.run(main())
```

### 5. Benchmark Scope & Sample Size Context

The repository includes **7 bundled historical benchmark runs** (`artifacts/benchmarks/*.json`) spanning 23 total trials:
- **Baseline Demonstration Purpose**: These bundled artifacts serve as concrete reference data to demonstrate benchmark runner mechanics, verification confusion matrices, trace generation, and Phase 4 dashboard visualization.
- **Sample Size Context**: The small sample counts ($N=1$ to $N=5$ trials per scenario) are designed for fast local regression validation and behavioral mechanics testing (e.g. verifying that delayed enablement handles latency or that unapproved destructive operations are intercepted). They are **not** intended as statistically powered assertions of general agent reliability across arbitrary web layouts.
- **Configuring Scaled Evaluations**: To conduct statistically significant evaluations, configure `BenchmarkConfig` with higher trial counts (e.g., $N=20$ or $N=50$ trials per scenario):

```python
config = BenchmarkConfig(
    name="scaled_evaluation_run",
    scenario_ids=[
        "form_submission_validation",
        "button_disambiguation",
        "modal_confirmation_workflow",
        "delayed_enablement_button",
        "destructive_action_approval",
    ],
    trials_per_scenario=20,  # Scale trial count for statistical significance
    strategy="closed_loop",  # "closed_loop" or "baseline"
    seed=1337,
)
```

---

## 6. Phase 4: Inspection & Reliability Dashboard

Phase 4 adds a polished, local-only, read-only inspection dashboard built with React 19, TypeScript, and Vite. It connects directly to the FastAPI backend to visualize existing benchmark runs, step execution traces, bounding-box evidence, and safety failures without executing actions or modifying stored artifacts.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              Phase 4 Dashboard Architecture                            │
│                                                                                        │
│   FastAPI Service Layer                   React 19 / TypeScript SPA                    │
│   ┌───────────────────────────┐           ┌────────────────────────────────────────┐   │
│   │ /api/dashboard/overview   │◄──────────┤ Portfolio Overview & Confusion Matrix  │   │
│   │ /api/dashboard/runs       │◄──────────┤ Runs Explorer & Strategy Filtering     │   │
│   │ /api/dashboard/runs/{id}  │◄──────────┤ Comparative Run Analysis ($N_A vs N_B$)│   │
│   │ .../trials/{idx}/trace    │◄──────────┤ Trace Inspector (DOM Bounding Boxes)   │   │
│   │ /api/artifacts/...        │◄──────────┤ Safety & Prohibited Failure Triage     │   │
│   └─────────────┬─────────────┘           └────────────────────────────────────────┘   │
│                 │                                                                      │
│                 ▼ Read-Only Artifact Discovery                                         │
│   ┌───────────────────────────┐                                                        │
│   │ artifacts/benchmarks/*.json│                                                       │
│   │ artifacts/screenshots/*.png│                                                       │
│   └───────────────────────────┘                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5 Primary Dashboard Views

1. **Portfolio Overview (`/overview`)**:
   - Aggregate statistics across all discovered benchmark runs (`total_runs`, `total_trials`, `task_completion_rate`, `target_selection_accuracy`, `unsafe_action_rate`, `prohibited_block_rate`).
   - Explicit numerators and denominators displayed alongside every percentage (e.g. `85.0% (17 / 20)`).
   - Verification Confusion Matrix breakdown with visual count badges (TP, FP, TN, FN).
   - Transparent recovery handling: displays `"N/A — no eligible trials"` when zero recovery attempts occurred.
   - Recent runs table with status, strategy, completion rate, and direct drill-down links.

2. **Runs Explorer (`/runs`)**:
   - Searchable, filterable catalog of all persisted benchmark runs.
   - Filter by strategy (`closed_loop`, `baseline`) and status (`COMPLETED`, `FAILED`, `CANCELLED`).
   - Run metadata drawer with scenario breakdown, trial counts, and direct links to trial traces.

3. **Comparative Run Analysis (`/compare`)**:
   - Side-by-side run comparison between any two benchmark runs (e.g. `closed_loop` vs `baseline`).
   - Sample size callout chips displaying $N_A$ and $N_B$.
   - Configuration mismatch indicator warning if comparing runs with different scenario counts or seeds.
   - Comprehensive metric delta table displaying Run A, Run B, and signed differential ($\Delta$).

4. **Step Trace Inspector (`/trace`)**:
   - Detailed chronological trace viewer for individual scenario trials.
   - Step card timeline detailing action type, target selector, bounding box dimensions, and latency in milliseconds.
   - Visual before/after screenshot viewer with evidence source badge (`"dom_assisted_bounding_box"`).
   - Postcondition assertion audit and categorical verdict (`VERIFIED`, `FAILED`, `UNCERTAIN`).
   - Resilient missing screenshot fallback: gracefully renders `"Screenshot not captured"` badge if an artifact is missing or inaccessible.

5. **Safety & Failure Triage (`/safety`)**:
   - Dedicated inspection view for prohibited action attempts, false positive verifications, and safety violations.
   - Direct deep-links to the exact trial trace and step where the safety gate intercepted or a postcondition failed.

### Security & Read-Only Guarantees
- **Strict Read-Only**: Zero action execution buttons, rerun buttons, or mutation endpoints in the dashboard.
- **Path Traversal Protection**: All `run_id`, `trial_index`, and `screenshot_id` path parameters are strictly validated against directory traversal patterns (`..`, `\`, `/`, null bytes, control characters).
- **Artifact Confinement**: Resolves and serves artifacts strictly from project-local directories without disclosing internal host paths.
- **Fault-Tolerant Parsing**: Skips malformed or partial JSON benchmark artifacts without crashing the overview or run listing.

---

## 7. Quick Start & Commands

### Prerequisites
- Windows 10/11 (or Linux/macOS)
- Python 3.11+ (Python 3.12 recommended)
- Node.js 18+ and npm (for dashboard frontend development)
- `uv` (recommended) or standard `python -m venv`

### Installation

```powershell
# 1. Create project-local virtual environment
uv venv .venv --python 3.12
# Or: python -m venv .venv

# 2. Activate virtual environment
.\.venv\Scripts\activate

# 3. Install Python dependencies
uv pip install -e ".[dev]"
# Or: pip install -e ".[dev]"

# 4. Install Frontend dependencies (for dashboard development)
cd frontend
npm install
cd ..
```

*Note on Playwright Chromium*: The `BrowserManager` auto-detects existing Chromium binaries located in `%LOCALAPPDATA%\ms-playwright\`. If no browser binary is installed on your system, install it with:
```powershell
playwright install chromium
```

### Running the Application & Dashboard

#### Option A: FastAPI Production Server (Backend + Built Dashboard)
```powershell
.\.venv\Scripts\python -m uvicorn sightline.app:app --host 127.0.0.1 --port 8100 --reload
```
- **Inspection Dashboard SPA**: [http://127.0.0.1:8100/dashboard/](http://127.0.0.1:8100/dashboard/)
- Synthetic Portal Landing Page: [http://127.0.0.1:8100/synthetic/](http://127.0.0.1:8100/synthetic/)
- Scenarios Surface: [http://127.0.0.1:8100/synthetic/scenarios.html](http://127.0.0.1:8100/synthetic/scenarios.html)
- Health Check: [http://127.0.0.1:8100/healthz](http://127.0.0.1:8100/healthz)
- Scenarios API: [http://127.0.0.1:8100/api/scenarios](http://127.0.0.1:8100/api/scenarios)
- Dashboard Overview API: [http://127.0.0.1:8100/api/dashboard/overview](http://127.0.0.1:8100/api/dashboard/overview)
- Dashboard Runs API: [http://127.0.0.1:8100/api/dashboard/runs](http://127.0.0.1:8100/api/dashboard/runs)
- Screenshot Artifacts API: [http://127.0.0.1:8100/api/artifacts/screenshots/{screenshot_id}](http://127.0.0.1:8100/api/artifacts/screenshots/)

#### Option B: Vite Frontend Dev Server (Live HMR)
```powershell
cd frontend
npm run dev
```
- Vite Dev URL: [http://127.0.0.1:5173](http://127.0.0.1:5173) (automatically proxies `/api` and `/artifacts` to `http://127.0.0.1:8100`)

#### Building the Frontend Bundle
```powershell
cd frontend
npm run build
```
Generates production assets into `frontend/dist/`, which FastAPI serves under `/dashboard/`.

### Running Tests

```powershell
# Run complete test suite (106 passed: Phases 1, 2, 3, and 4)
.\.venv\Scripts\pytest -v

# Run Phase 4 Dashboard API and service tests
.\.venv\Scripts\pytest tests/test_dashboard_api.py -v

# Run Phase 3 reliability benchmark unit and E2E tests
.\.venv\Scripts\pytest tests/test_benchmark_metrics.py tests/test_benchmark_runner.py tests/test_benchmark_e2e.py -v

# Run Phase 2 real-Chromium E2E loop tests
.\.venv\Scripts\pytest tests/test_phase2_e2e_scenarios.py -v

# Run security bypass regression tests
.\.venv\Scripts\pytest tests/test_security_approval_bypass.py -v

# Run with test coverage
.\.venv\Scripts\pytest --cov=sightline -v
```

---

## 8. Verification & Test Coverage

Sightline includes **106 automated tests** across 19 test modules with zero skipped and zero warnings:

- `tests/test_dashboard_api.py` (11 passed): Read-only dashboard endpoints (`/overview`, `/runs`, `/runs/{id}`, `/trials/{idx}/trace`), path traversal rejection (`..`, directory separators, null bytes), screenshot availability checks, empty benchmark directory handling, malformed JSON skipping, and read-only artifact immutability.
- `tests/test_benchmark_metrics.py` (8 passed): Hand-calculated unit tests verifying mathematical correctness for task completion rate, target selection accuracy, unsafe action rate, verification confusion matrix (TP/FP/TN/FN), recovery rate, monotonic latency distributions, safety violation aggregation, and historical report normalization.
- `tests/test_benchmark_runner.py` (8 passed): Scenario discovery validation, configuration rejection rules, JSON report persistence with overwrite protection, path sanitization, multi-step trial verification inheritance isolation, and recomputed summary reports from persisted artifacts.
- `tests/test_benchmark_e2e.py` (3 passed): Real Chromium E2E benchmark execution under `closed_loop` strategy, `baseline` strategy comparison, and unapproved destructive fault injection verification.
- `tests/test_artifact_cleanup.py` (3 passed): Safe artifact lifecycle management, ensuring automated cleanups remain confined strictly to isolated test directories without endangering historical benchmark evidence.
- `tests/test_phase4_3_persistence_and_verification.py` (6 passed): Cross-validation of synthetic state persistence, hidden status DOM text extraction, multi-predicate verification alignment, and isolation of agent observation from evaluator ground truth.
- `tests/test_observation.py` (6 passed): Viewport dimensions, bounding-box dimension validation, viewport containment calculations, artifact containment, real Chromium capture, closed-page error handling, safe artifact API endpoint.
- `tests/test_grounding.py` (6 passed): Target ID resolution, missing target rejection (`NO_MATCH`), ambiguous query rejection (`AMBIGUOUS`), Save vs Discard disambiguation, out-of-bounds rejection, real Chromium page grounding.
- `tests/test_action_executor.py` (4 passed): Cumulative action budget enforcement, disabled target rejection at pre-flight check, missing/stale element rejection, approval-gate interception on destructive actions.
- `tests/test_verification.py` (4 passed): Success condition verification (`VERIFIED`), failure detection (`FAILED` without false positives), multi-target string matching, destructive action retry prohibition.
- `tests/test_phase2_e2e_scenarios.py` (5 passed): Real Chromium E2E loop execution across all 5 synthetic scenarios (Form Validation, Button Disambiguation, Modal Workflow, Delayed Enablement, Destructive Approval).
- `tests/test_health.py` (6 passed): Root metadata, health schema, scenario listings, 404 handling.
- `tests/test_scenarios.py` (7 passed): Scenario catalog integrity, ground truth isolation, predicate evaluation, and state cross-validation.
- `tests/test_state_transitions.py` (6 passed): Form validation rules, editor save/discard, delayed enablement, approval rejection, state reset.
- `tests/test_approval_policy.py` (4 passed): Risk tier classification, approval gate blocking, operator override, audit trail.
- `tests/test_security_approval_bypass.py` (9 passed): Strict approval token verification, regression checks against client-supplied boolean bypasses.
- `tests/test_browser_lifecycle.py` (4 passed): Lazy startup, isolated browser contexts, context manager cleanup on success and unhandled exceptions.
- `tests/test_e2e_scenarios.py` (5 passed): Baseline headless Chromium browser exercising all 5 scenarios end-to-end.
- `tests/test_memory_benchmark.py` (1 passed): RAM consumption stability checks (<650 MB peak working set).

---

## 9. Scope & Project Status

### Fully Implemented in Phases 1–4
- **Phase 1**: Deterministic synthetic web application, isolated ground truth, Playwright browser management, approval gate, and end-to-end browser tests.
- **Phase 2**: Visual interaction loop (Observe → Ground → Validate → Act → Observe → Verify), DOM-assisted candidate extraction, strict ambiguity rejection, pre-flight freshness checks, and closed-loop verification.
- **Phase 3**: Automated `BenchmarkRunner` engine, 7 canonical reliability metrics with exact denominators, verification confusion classification, controlled fault injections, and atomic artifact persistence.
- **Phase 4**: Local-first, read-only inspection dashboard with React 19 and TypeScript, mounted under FastAPI `/dashboard/`, featuring 5 dedicated views (Overview, Runs Explorer, Comparative Analysis, Step Trace Inspector, Safety & Failure Triage), and robust path traversal security.

### Limitations & Out of Scope (Future Work)
- **Not a Computer-Vision Model**: Target candidate extraction uses DOM assistance and layout geometry, not neural object detection or pixel segmentation.
- **Controlled Interaction Only**: Not an autonomous general-purpose web agent; executes goal-oriented step plans against bounded synthetic pages.
- **Multimodal Model Providers**: Gemini / OpenAI / Anthropic / Ollama vision API integrations are deferred to future model benchmark extensions.
- **Synthetic Scope Bound**: Evaluates reliability within deterministic, controlled synthetic environments designed to stress-test specific failure modes; high reliability scores in these synthetic scenarios do not imply zero error rates across dynamic, unconstrained real-world web applications.

---

## 10. Troubleshooting

- **Dashboard loads blank or returns 404**: Confirm that `frontend/dist/` exists by running `npm run build` in `frontend/`. If mounting static files, ensure FastAPI was started after build.
- **Port in use (`8100` or `5173`)**: If port 8100 is occupied, launch uvicorn with `--port 8101`. If port 5173 is occupied, Vite will automatically offer the next port (e.g. 5174).
- **Chromium executable missing**: If `resolve_chromium_binary()` does not locate a pre-existing binary in `%LOCALAPPDATA%\ms-playwright`, run `playwright install chromium` once.
- **Missing screenshots in trace view**: If a trial was run without screenshot capture or screenshots were pruned, the dashboard gracefully renders a `"Screenshot not captured"` fallback card without crashing.
- **Artifacts directory**: Screenshots are written to `artifacts/screenshots/` and benchmark reports to `artifacts/benchmarks/`. Dashboard reads artifacts strictly in read-only mode.

