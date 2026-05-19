# Phase 7: Eval & Calibration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 07-eval-calibration
**Areas discussed:** Threshold config, Analysis plan, Threshold criteria, Test fix approach

---

## Threshold Config

| Option | Description | Selected |
|--------|-------------|----------|
| Move to Settings | Add `score_threshold: float = 0.25` to Settings, readable via SCORE_THRESHOLD env var | ✓ |
| Keep hardcoded, update value | Simpler — just change the number after calibration | |
| Module constant in rag.py | Define `SCORE_THRESHOLD = 0.25` at top of rag.py, import in tests | |

**User's choice:** Move to Settings
**Notes:** Single value for both standard and conflict pipelines — no separate thresholds.

---

## Analysis Plan

| Option | Description | Selected |
|--------|-------------|----------|
| Both | Score distribution (50+ examples) + passage existence check | ✓ |
| Only score distribution | Focus on score numbers to find threshold root cause | |
| Only passage check | Verify ground-truth passages are actually indexed | |

**User's choice:** Both
**Notes:** Output saved to `.planning/phases/07-eval-calibration/ANALYSIS.md`, committed to git.

---

## Threshold Criteria

| Option | Description | Selected |
|--------|-------------|----------|
| Maximize context_hit | Recall-first — find threshold where most ground-truth passages are retrieved | ✓ |
| F1: balance precision/recall | More precise but more complex | |
| Retrieved rate | Just ensure queries return results, no quality check | |

**User's choice:** Maximize context_hit
**Notes:** Hard floor >= 0.20. Compliance use case prioritizes recall — missing a policy is worse than returning a marginal one.

---

## Test Fix Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Import from Settings | `assert call_kwargs.get("score_threshold") == get_settings().score_threshold` — structurally impossible to diverge | ✓ |
| Import constant from rag.py | If using module constant, tests import same constant | |
| Hardcode new number | Update 0.55 → calibrated value — simpler but fragile | |

**User's choice:** Import from Settings
**Notes:** Both occurrences in test_rag.py (lines 71 and 222) get this treatment.

---

## Claude's Discretion

- Exact experiment sample size (50–200 examples)
- Score distribution report format (markdown table vs histogram)
- Number of experiment repetitions to account for Nemotron non-determinism

## Deferred Ideas

- Separate thresholds for standard vs conflict queries — one value until data shows need
- Automated threshold sweep (grid search) — manual analysis sufficient for Phase 7
- CI/CD eval regression integration — post-v2
