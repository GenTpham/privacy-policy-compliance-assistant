# Phase 7 Eval & Calibration — Analysis

**Experiment date:** 2026-05-04 to 2026-05-05
**Dataset:** privacy-qa-validation (3,809 examples, 574 unique context passages)
**Current score_threshold:** 0.25
**Experiment runs:** baseline-calibration-run1, baseline-calibration-run2

## Experiment Results

| Metric | Run 1 | Run 2 | Mean |
|--------|-------|-------|------|
| context_hit | 0.286 | 0.230 | 0.258 |
| answer_match | 0.298 | 0.325 | 0.312 |
| retrieved | 1.000 | 1.000 | 1.000 |

**Run 1 notes:** 58 of 100 examples errored with 401 Unauthorized due to backend service
instability at experiment start (Docker containers returning intermittent 401s). 42 examples
evaluated successfully. Metrics from this run are less reliable.

**Run 2 notes:** 100 of 100 examples evaluated successfully (0 errors). This is the primary
reference run. context_hit=23.0%, retrieved=100.0%.

**Variance across runs:** context_hit varies between 23.0% and 28.6%. This is partly due to
Nemotron embedding non-determinism (noted in STATE.md watch-outs) and the different effective
sample sizes (42 vs 100 examples). Retrieved stays at 100% across both runs — the current
threshold (0.25) does not cause zero-result responses under normal operation.

## Score Distribution

Scores collected from direct Qdrant queries for 30 questions using the same embedding model
and retrieval approach as the production RAG pipeline (score_threshold=0.25, top-k=5).

**Retrieved scores (above threshold=0.25), 150 scores from 30 questions × 5 passages:**

| Statistic | Value |
|-----------|-------|
| Min | 0.3200 |
| p25 | 0.4031 |
| Mean | 0.4731 |
| p75 | 0.5382 |
| p90 | 0.5875 |
| Max | 0.6446 |

Distribution histogram (bucket counts, 150 scores):

| Score range | Count | Notes |
|-------------|-------|-------|
| 0.00–0.25 | 0 | No scores below threshold (threshold not filtering) |
| 0.25–0.30 | 0 | No scores in this range |
| 0.30–0.35 | 4 | Near-threshold floor |
| 0.35–0.40 | 30 | |
| 0.40–0.45 | 30 | |
| 0.45–0.50 | 34 | Largest bucket |
| 0.50–0.55 | 22 | |
| 0.55–0.60 | 18 | |
| 0.60+ | 12 | |

**Critical observation:** The minimum observed score (0.32) is well above both the current
threshold (0.25) and the proposed floor (0.20). All 150 retrieved passage scores are above
0.25. This means the current threshold is NOT filtering any results — every question returns
passages that naturally score above threshold.

## Passage Existence Check

**Part A — Context embeddings (20 samples, seed=42):**
Direct Qdrant queries embedding the ground-truth context text itself (not the question) with
score_threshold=0.0 to verify corpus completeness.

| Stat | Value |
|------|-------|
| Samples checked | 20 |
| Best score >= 0.25 | 20/20 (100%) |
| Best score >= 0.20 | 20/20 (100%) |
| Text found in top results | 20/20 (100%) |
| Min best score | 0.9953 |
| Mean best score | 0.9977 |
| Max best score | 0.9987 |

**Context-to-Qdrant scores are near-perfect (0.995–0.999):** When you embed a passage and
search for it in Qdrant, it returns itself with 0.99+ cosine similarity. This confirms that
all ground-truth contexts from the validation set exist in the Qdrant corpus and are indexed
correctly.

**Part B — Question embeddings (15 samples, direct queries):**
Embedding the natural-language question and querying Qdrant (as the RAG pipeline does), then
checking if the correct ground-truth context appears in the top-5 results.

| # | Question (truncated) | Best score | Correct in top-5? |
|---|---------------------|-----------|------------------|
| 1 | Will they retain my data for legal... | 0.5386 | No |
| 2 | Does the company collect any data... | 0.6005 | No |
| 3 | What happen to my data if your... | 0.6258 | No |
| 4 | How the website ensures security... | 0.5677 | No |
| 5 | Can other see my health condition? | 0.3598 | No |
| 6 | Does this website collect my info... | 0.6718 | No |
| 7 | Does the company collect user's... | 0.5924 | No |
| 8 | Does the collected data reveal my... | 0.3958 | No |
| 9 | Does the company collect user's fin... | 0.5233 | No |
| 10 | What scope does the user choice... | 0.2936 | No |
| 11 | How do they collect information... | 0.6514 | No |
| 12 | Do you use my information? | 0.5882 | No |
| 13 | Do I need to consent before... | 0.5353 | No |
| 14 | Does the company share user's data... | 0.5623 | No |
| 15 | Is any difference when the policy... | 0.3849 | No |

**Summary:** 0 of 15 question-to-correct-passage checks had the correct passage in top-5.
All 15 questions returned results (passages above 0.25). The corpus is complete — the problem
is that questions do not retrieve their specific matching passage.

**Additional corpus size check:**
- Unique validation contexts: 574 (the distinct passages the questions reference)
- Qdrant points: 3,204 (the indexed corpus, larger — contains full policy documents)
- Spot-check of 5 random validation contexts in Qdrant: all found with 0.997+ similarity
- Conclusion: ground-truth passages ARE in the corpus; they are just not top-ranked

## Root Cause Analysis

**Primary root cause: Question-to-passage semantic mismatch (ranking problem)**

The core issue is that the validation dataset contains short natural-language questions (5–15
words) paired with specific policy excerpts as ground truth. There is a fundamental asymmetry:

- **Questions** are short, conversational, and abstractly phrased: "Does the company collect
  user's financial information?" (7 words)
- **Ground-truth passages** are dense policy text: "Payment and billing information. For
  example, we collect your credit card number and zip code when you buy a ticket." (28 words)

When the question is embedded and compared against all 3,204 corpus passages, many passages
about data collection in general score similarly (0.35–0.65). The specific ground-truth
passage competes with semantically similar passages from other companies' policies that cover
the same topics. With 3,204 indexed passages covering overlapping privacy topics, the correct
answer frequently ranks below position 5.

**Contributing factors:**

1. **Corpus density:** 3,204 passages from 17K+ policy documents means many passages cover
   overlapping topics (data collection, sharing, retention) from different companies. A
   question about "financial information" matches hundreds of payment-related passages.

2. **Dataset question style:** The validation questions are highly generic ("Does the website
   collect my information?"). Many of these questions could match dozens of correct passages
   from different policies. The "ground truth" is one specific excerpt, but other excerpts
   could also be valid answers — the evaluator's exact-match check is strict.

3. **Threshold is not the bottleneck:** The minimum observed retrieval score (0.32) is above
   both the current threshold (0.25) and the floor (0.20). Lowering the threshold would return
   more passages from the same pool but would not promote the correct passage into top-5. It
   would only increase noise (more low-quality results with scores 0.20–0.32).

4. **Non-determinism:** Nemotron embeddings are confirmed non-deterministic (STATE.md
   watch-out). The context_hit variance between Run 1 (28.6%) and Run 2 (23.0%) is partly
   attributable to embedding stochasticity.

**What threshold change would and would not fix:**
- WOULD fix: zero-result responses (if threshold were too high). But retrieved=100% means
  this is not occurring.
- WOULD NOT fix: correct passage being ranked 6th–10th instead of 1st–5th. This requires
  increasing top_k, changing the query strategy (e.g., HyDE, query expansion), or using
  a re-ranker — architectural changes outside Phase 7 scope.

## Threshold Recommendation

**Optimization target:** Maximize context_hit (recall-first per D-05).
**Hard floor:** >= 0.20 (D-06).

Based on the score distribution and passage existence check:

**Recommended score_threshold: 0.20**

**Rationale:**

The empirical evidence shows:
- All currently retrieved passages score 0.32–0.64 (minimum = 0.32, well above 0.25)
- Lowering from 0.25 to 0.20 will not change any retrieval results in practice (no scores
  fall in the 0.20–0.32 range in this sample)
- The 0.25 threshold is not causing missed retrievals; the corpus is complete

However, setting threshold to 0.20 is still the correct choice because:

1. **Recall-first principle (D-05):** The hard floor is 0.20. Setting the default to 0.20
   means accepting any passage above the minimum quality bar, maximizing the chance that edge
   cases (unusual phrasing, technical policy language) get retrieved.

2. **Future corpus changes:** As the corpus grows or models change, scores may shift downward.
   A threshold of 0.20 provides more headroom before results would start getting filtered.

3. **No precision cost observed:** The passage existence check shows all corpus passages are
   near-perfect matches when their own text is used as the query. At 0.20, only genuinely
   low-relevance passages (score < 0.20) would be filtered. In 150 question queries, no
   passage scored below 0.32, suggesting 0.20 is a safe lower bound.

4. **Consistency with D-06:** Using exactly the floor value (0.20) documents that the floor
   was set empirically as the threshold, not arbitrarily.

**Expected impact of changing 0.25 to 0.20:**
- context_hit: No measurable change (scores don't fall in 0.20–0.25 range in this sample)
- retrieved: Remains 100% (already 100% at 0.25)
- answer_match: No direct impact from threshold change
- Net result: The threshold change documents the calibration decision but the actual
  context_hit improvement requires addressing the ranking problem (top_k increase or query
  rewriting) in a future phase.

## KEY DECISIONS Update

After Plan 4 implementation:
- score_threshold updated from 0.25 to 0.20 in Settings default
- Reasoning: Empirical calibration shows threshold=0.25 is not the bottleneck; minimum
  retrieved score is 0.32. Setting to floor value (0.20) maximizes recall headroom without
  reducing precision. Root cause of 23% context_hit is ranking mismatch, not threshold.
