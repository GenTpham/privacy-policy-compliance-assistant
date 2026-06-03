"""
backend/eval/passage_existence_check.py

Passage existence check for Phase 7 calibration analysis.

For a sample of validation examples, directly query Qdrant with score_threshold=0.0
to understand raw similarity scores for ground-truth contexts.

This script determines:
  (a) Does the ground-truth passage exist in Qdrant at all?
  (b) What raw similarity score does it receive?
  (c) Does it score above 0.25 (current threshold)?
  (d) Does it score above 0.20 (proposed floor)?

Usage:
  python -m backend.eval.passage_existence_check
  python -m backend.eval.passage_existence_check --sample 20

Output:
  JSON results to stdout + summary statistics
"""
import argparse
import asyncio
import json
import os
import random
import statistics
import sys
from pathlib import Path

from openai import AsyncOpenAI

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client


# -- .env loader -----------------------------------------------------------------

def _load_dotenv(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key not in os.environ:
            os.environ[key] = val


_load_dotenv()


# -- Core check ------------------------------------------------------------------

async def check_passage(
    openrouter: AsyncOpenAI,
    qdrant: AsyncQdrantClient,
    context_text: str,
    question: str,
    title: str,
) -> dict:
    """
    Embed the context text (the ground-truth passage) and query Qdrant
    with score_threshold=0.0 to see what raw scores come back.
    Returns a dict with scores and analysis.
    """
    # Embed the ground-truth context (what was indexed)
    resp = await openrouter.embeddings.create(
        model="nvidia/llama-nemotron-embed-vl-1b-v2",
        input=context_text,
        encoding_format="float",
    )
    vec = resp.data[0].embedding

    # Query Qdrant with NO threshold — get raw scores
    results = await qdrant.query_points(
        collection_name="policies",
        query=vec,
        limit=5,
        score_threshold=0.0,
        with_payload=True,
    )

    top_scores = [r.score for r in results.points]
    best_score = top_scores[0] if top_scores else 0.0

    # Check if any returned passage has matching text
    context_lower = context_text.lower()[:100]
    found_in_corpus = any(
        context_lower[:50] in (r.payload.get("text", "") or "").lower()
        for r in results.points
    )

    top_passages = [
        {
            "score": round(r.score, 4),
            "title": (r.payload.get("title") or "")[:40],
            "text_preview": (r.payload.get("text") or "")[:60],
        }
        for r in results.points[:3]
    ]

    return {
        "title": title,
        "question": question[:60],
        "context_preview": context_text[:80],
        "best_raw_score": round(best_score, 4),
        "top_5_scores": [round(s, 4) for s in top_scores],
        "above_0_25": best_score >= 0.25,
        "above_0_20": best_score >= 0.20,
        "found_in_corpus": found_in_corpus,
        "top_passages": top_passages,
    }


async def run_check(sample_size: int) -> None:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[error] OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Load validation dataset
    dataset_path = Path("dataset/json/test_valid/policy_qa_validation.json")
    if not dataset_path.exists():
        print(f"[error] Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    print(f"[dataset] Loaded {len(data)} validation examples")

    # Sample randomly for diverse coverage
    random.seed(42)
    sample = random.sample(data, min(sample_size, len(data)))
    print(f"[sample] Using {len(sample)} examples (seed=42 for reproducibility)")

    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    qdrant = make_qdrant_client(get_settings())

    print(f"\n{'#':>4}  {'Title':20}  {'Best score':10}  {'>0.25':5}  {'>0.20':5}  {'In corpus':9}")
    print("-" * 75)

    all_results = []
    all_scores = []
    all_top5_scores = []

    for i, ex in enumerate(sample, 1):
        context_text = ex.get("context", "")
        # Use first answer text for embedding check
        answer_texts = ex.get("answers", {}).get("text", [])
        ground_truth = answer_texts[0] if answer_texts else ""
        question = ex.get("question", "")
        title = ex.get("title", "")

        # Use context (the full passage) for existence check
        text_to_check = context_text if context_text else ground_truth

        try:
            result = await check_passage(
                openrouter, qdrant, text_to_check, question, title
            )
            all_results.append(result)
            all_scores.append(result["best_raw_score"])
            all_top5_scores.extend(result["top_5_scores"])

            print(
                f"{i:>4}  {title[:20]:20}  {result['best_raw_score']:.4f}      "
                f"{'Y' if result['above_0_25'] else 'N':5}  "
                f"{'Y' if result['above_0_20'] else 'N':5}  "
                f"{'Y' if result['found_in_corpus'] else 'N'}"
            )
        except Exception as exc:
            print(f"{i:>4}  {title[:20]:20}  ERROR: {exc}", file=sys.stderr)

    # Summary statistics
    print("\n" + "=" * 75)
    print("PASSAGE EXISTENCE CHECK SUMMARY")
    print("=" * 75)

    n = len(all_results)
    if n == 0:
        print("[error] No results collected")
        return

    above_025 = sum(1 for r in all_results if r["above_0_25"])
    above_020 = sum(1 for r in all_results if r["above_0_20"])
    in_corpus = sum(1 for r in all_results if r["found_in_corpus"])

    print(f"\nSamples checked: {n}")
    print(f"  Best score >= 0.25: {above_025}/{n} ({above_025/n:.1%})")
    print(f"  Best score >= 0.20: {above_020}/{n} ({above_020/n:.1%})")
    print(f"  Text found in top results: {in_corpus}/{n} ({in_corpus/n:.1%})")

    if all_scores:
        sorted_scores = sorted(all_scores)
        p25_idx = int(len(sorted_scores) * 0.25)
        p75_idx = int(len(sorted_scores) * 0.75)
        p90_idx = int(len(sorted_scores) * 0.90)

        print(f"\nBest-score distribution (per example):")
        print(f"  Min:  {min(all_scores):.4f}")
        print(f"  p25:  {sorted_scores[p25_idx]:.4f}")
        print(f"  Mean: {statistics.mean(all_scores):.4f}")
        print(f"  p75:  {sorted_scores[p75_idx]:.4f}")
        print(f"  p90:  {sorted_scores[p90_idx]:.4f}")
        print(f"  Max:  {max(all_scores):.4f}")

    if all_top5_scores:
        sorted_all = sorted(all_top5_scores)
        p25_idx = int(len(sorted_all) * 0.25)
        p75_idx = int(len(sorted_all) * 0.75)
        p90_idx = int(len(sorted_all) * 0.90)

        print(f"\nAll top-5 scores distribution ({len(all_top5_scores)} scores):")
        print(f"  Min:  {min(all_top5_scores):.4f}")
        print(f"  p25:  {sorted_all[p25_idx]:.4f}")
        print(f"  Mean: {statistics.mean(all_top5_scores):.4f}")
        print(f"  p75:  {sorted_all[p75_idx]:.4f}")
        print(f"  p90:  {sorted_all[p90_idx]:.4f}")
        print(f"  Max:  {max(all_top5_scores):.4f}")

    # Histogram
    buckets = [
        ("0.00-0.10", 0.00, 0.10),
        ("0.10-0.20", 0.10, 0.20),
        ("0.20-0.25", 0.20, 0.25),
        ("0.25-0.30", 0.25, 0.30),
        ("0.30-0.35", 0.30, 0.35),
        ("0.35-0.40", 0.35, 0.40),
        ("0.40-0.50", 0.40, 0.50),
        ("0.50+",     0.50, 1.00),
    ]

    print(f"\nAll top-5 scores histogram:")
    print(f"  {'Range':12}  Count")
    for label, lo, hi in buckets:
        count = sum(1 for s in all_top5_scores if lo <= s < hi)
        bar = "#" * (count // max(1, len(all_top5_scores) // 40))
        print(f"  {label:12}  {count:4}  {bar}")

    # Save results to file for ANALYSIS.md reference
    output_path = Path(".planning/phases/07-eval-calibration/passage_check_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "sample_size": n,
                "results": all_results,
                "summary": {
                    "above_0_25": above_025,
                    "above_0_20": above_020,
                    "in_corpus": in_corpus,
                    "best_score_stats": {
                        "min": min(all_scores) if all_scores else None,
                        "mean": round(statistics.mean(all_scores), 4) if all_scores else None,
                        "max": max(all_scores) if all_scores else None,
                    },
                },
            },
            f,
            indent=2,
        )
    print(f"\n[output] Results saved to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20, help="Number of examples to check")
    args = parser.parse_args()

    asyncio.run(run_check(args.sample))


if __name__ == "__main__":
    main()
