# Phase 7: Eval & Calibration - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Run a full experiment on the validation dataset, investigate why context_hit is low (score distribution + passage existence check), determine the optimal score_threshold (>= 0.20, maximize context_hit), update the threshold in Settings, and align test_rag.py so tests always reflect the live production config value.

**Does NOT include:** UI changes, new RAG features, corpus expansion, or user-facing features — those are Phases 8–10.

</domain>

<decisions>
## Implementation Decisions

### Score Threshold Configuration
- **D-01:** Move `score_threshold` from hardcoded literals in `rag.py` into `Settings` as `score_threshold: float = 0.25`, overridable via `SCORE_THRESHOLD` env var. Both `stream_answer` and `stream_conflict_answer` read `get_settings().score_threshold` — one config source, no duplication.
- **D-02:** A single threshold value for both standard and conflict pipelines — no separate setting for each. Simplicity preferred until data shows they need to diverge.

### Analysis Approach
- **D-03:** Two-pronged investigation for context_hit = 0%:
  1. **Score distribution analysis** — run experiment on 50+ validation examples, collect scores from the `qdrant.retrieve` spans in Phoenix, plot/report distribution to understand where the relevant-passage scores actually land.
  2. **Passage existence check** — for a sample of low-context_hit examples, directly query Qdrant with the ground-truth context text to verify whether the passage is indexed at all. If passages are missing, the problem is corpus coverage not threshold.
- **D-04:** Analysis findings written to `.planning/phases/07-eval-calibration/ANALYSIS.md` and committed to git. This becomes the decision record for the chosen threshold.

### Threshold Optimization Criteria
- **D-05:** Optimize for **maximize context_hit** — find the threshold where the most ground-truth passages are retrieved. Compliance use case prioritizes recall over precision (missing a relevant policy is worse than returning a slightly less relevant one).
- **D-06:** Hard floor: threshold must stay >= 0.20. Below 0.20 the risk of returning noise passages is too high for a compliance context.
- **D-07:** After calibration, update `score_threshold` default in `Settings` to the empirically determined value and document the reasoning in `ANALYSIS.md` and the decision log.

### Test Suite Alignment
- **D-08:** Fix `test_rag.py` to assert `call_kwargs.get("score_threshold") == get_settings().score_threshold` instead of the hardcoded `0.55`. Both occurrences (line 71 for `test_retrieve_params` and line 222 for the conflict equivalent) get this treatment. Tests will always reflect whatever the live production config value is — the divergence becomes structurally impossible.

### Claude's Discretion
- Exact experiment sample size (50–200 examples from validation set) — pick based on run time; aim for statistical coverage across the 20 policy sources
- Histogram/chart format for score distribution — markdown table or inline summary is fine; no need for plotting libraries
- Whether to run multiple experiment repetitions to account for Nemotron non-determinism — run at least 2 to check variance in context_hit

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Eval Infrastructure
- `backend/eval/run_experiment.py` — experiment runner: login, fetch Phoenix dataset examples, call /api/chat (SSE), run 3 evaluators (context_hit, answer_match, retrieved), POST runs + evaluations to Phoenix
- `backend/eval/upload_phoenix_dataset.py` — dataset upload script; `privacy-qa-validation` already uploaded

### RAG Pipeline (threshold locations to update)
- `backend/app/services/rag.py` — `score_threshold=0.25` hardcoded at lines 175 and 317 (both `query_points` calls); `_retrieval_span` already logs `retrieval.score_threshold` as a span attribute
- `backend/app/core/config.py` — `Settings` class; add `score_threshold: float = 0.25` alongside existing fields

### Test Files to Fix
- `backend/app/tests/test_rag.py` — asserts `score_threshold == 0.55` at lines 71 and 222; fix to read from `get_settings().score_threshold`

### Project Context
- `.planning/REQUIREMENTS.md` — EVAL-01 through EVAL-04 are the requirements this phase must close
- `.planning/PROJECT.md` §Key Decisions — `score_threshold=0.25` decision already logged; update outcome after calibration

### No external ADRs — all decisions captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/eval/run_experiment.py`: fully functional experiment runner — extend with score distribution logging, no rewrite needed
- `backend/app/core/config.py`: `Settings` class with `get_settings()` cached singleton — add `score_threshold` field here
- `backend/app/services/rag.py`: `_retrieval_span()` already captures `retrieval.scores` as a span attribute — Phoenix already has the raw score data per query

### Established Patterns
- `get_settings()` is the authoritative config source — all runtime values flow through it (OpenRouter key, Qdrant host, JWT params)
- OTel span attributes in `_retrieval_span()` use dot-notation keys (`retrieval.score_threshold`, `retrieval.scores`) — follow same convention for any new attributes
- Tests mock `rag.qdrant` and `rag.openrouter` as module-level singletons via `patch.object` — test fixture pattern established in `conftest.py`

### Integration Points
- `rag.py` reads `_settings = get_settings()` at module load and builds singletons — after adding `score_threshold` to Settings, `rag.py` must call `get_settings().score_threshold` at query time (not at module load) to pick up any env-var override
- `run_experiment.py` calls the live backend `/api/chat` endpoint — experiment runs require both backend and Phoenix running (`docker compose --profile observability up`)

</code_context>

<specifics>
## Specific Ideas

- Score distribution report: after running 50+ examples, extract `retrieval.scores` from Phoenix traces and produce a histogram summary showing min/max/mean/p25/p75/p90 — helps visually identify where relevant and irrelevant passages cluster
- Passage existence check: use `qdrant.scroll()` with a payload filter on `text == ground_truth_answer` (exact match) or embed the ground_truth and do a direct similarity search with `score_threshold=0.0` to get the raw score for the known-correct passage

</specifics>

<deferred>
## Deferred Ideas

- Separate thresholds for standard vs conflict queries — deferred; use one value unless data shows clear need
- Automated threshold sweep (grid search over 0.15–0.40) — could be added as a script but not required for Phase 7; manual analysis from experiment data is sufficient
- CI/CD integration for eval regression — post-v2

</deferred>

---

*Phase: 07-eval-calibration*
*Context gathered: 2026-05-04*
