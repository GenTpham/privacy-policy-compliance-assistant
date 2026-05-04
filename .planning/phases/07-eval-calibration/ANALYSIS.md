# Phase 7 Eval & Calibration — Analysis

**Experiment date:** 2026-05-04
**Dataset:** privacy-qa-validation
**Current score_threshold:** 0.25
**Experiment runs:** baseline-calibration-run1, baseline-calibration-run2

## Experiment Results

| Metric | Run 1 | Run 2 | Mean |
|--------|-------|-------|------|
| context_hit | 0.286 | 0.230 | 0.258 |
| answer_match | 0.298 | 0.325 | 0.312 |
| retrieved | 1.000 | 1.000 | 1.000 |

**Run 1 notes:** 58 of 100 examples errored with 401 Unauthorized due to backend service instability at experiment start (Docker containers were returning intermittent 401s). 42 examples evaluated successfully.

**Run 2 notes:** 100 of 100 examples evaluated successfully (0 errors). This is the more reliable run.

Variance across runs: context_hit varies between 23.0% and 28.6%, confirming Nemotron non-determinism noted in STATE.md watch-outs. Retrieved stays at 100% — the current threshold (0.25) does not cause zero-result responses; it appears passages are being retrieved but the ground-truth passage is not always among them.

## Score Distribution

*To be populated after Phoenix trace analysis in Task 2 — scores collected from retrieval.scores span attributes.*

## Passage Existence Check

*To be populated in Task 2 — direct Qdrant queries for low-context_hit examples.*

## Root Cause Analysis

*To be populated after passage existence check in Task 2.*

## Threshold Recommendation

*To be populated after full analysis in Task 2.*

## KEY DECISIONS Update

*To be populated after Plan 4 implementation.*
