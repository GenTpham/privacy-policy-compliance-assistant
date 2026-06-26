"""
CLI entry point for the full benchmark pipeline.

Usage:
  python -m backend.benchmark.run_benchmark
  python -m backend.benchmark.run_benchmark --num-queries 50
  python -m backend.benchmark.run_benchmark --skip-ingest  (if collections already populated)

Pipeline:
  1. Download & sample FiQA dataset
  2. Ingest into naive + optimized Qdrant collections
  3. For each query: retrieve from both → generate answer with OSS LLM
  4. Score with Ragas → export comparison CSV
"""
import argparse
import asyncio
import time

from openai import AsyncOpenAI

from backend.app.core.config import get_settings
from backend.app.core.qdrant_client import make_qdrant_client
from backend.app.services.rag import CHAT_MODEL, llm_client
from backend.benchmark.config import (
    NAIVE_COLLECTION,
    NUM_TEST_QUERIES,
    OPTIMIZED_COLLECTION,
    REPORT_PATH,
    TOP_K,
)
from backend.benchmark.data_loader import load_fiqa, sample_test_set
from backend.benchmark.generator import generate_answer
from backend.benchmark.ingest_benchmark import ingest_both
from backend.benchmark.ragas_evaluator import BenchmarkRecord, run_ragas_evaluation
from backend.benchmark.retriever import retrieve_chunks


async def run_benchmark(
    num_queries: int = NUM_TEST_QUERIES,
    skip_ingest: bool = False,
    report_path: str = REPORT_PATH,
) -> None:
    """Execute the full benchmark pipeline."""

    print("=" * 80)
    print("  RAG Benchmark: Naive vs Optimized (BeIR/FiQA + Ragas)")
    print("=" * 80)

    # Step 1: Load and sample data
    print("\n[1/4] Loading FiQA dataset...")
    t0 = time.perf_counter()
    data = load_fiqa()
    sampled = sample_test_set(data, n=num_queries)
    print(
        f"  Loaded: {len(data.corpus)} docs, {len(data.queries)} queries\n"
        f"  Sampled: {len(sampled.queries)} queries, {len(sampled.corpus)} relevant docs\n"
        f"  Time: {time.perf_counter() - t0:.1f}s"
    )

    # Step 2: Ingest into both collections
    if not skip_ingest:
        print("\n[2/4] Ingesting into Qdrant (naive + optimized)...")
        t0 = time.perf_counter()
        counts = await ingest_both(sampled)
        print(
            f"  Naive: {counts['naive']} chunks | Optimized: {counts['optimized']} chunks\n"
            f"  Time: {time.perf_counter() - t0:.1f}s"
        )
    else:
        print("\n[2/4] Skipping ingestion (--skip-ingest)")

    # Step 3: Retrieve + Generate for both pipelines
    print(f"\n[3/4] Running inference loop ({len(sampled.queries)} queries × 2 pipelines)...")
    settings = get_settings()
    openrouter = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    qdrant = make_qdrant_client(settings)

    naive_records: list[BenchmarkRecord] = []
    optimized_records: list[BenchmarkRecord] = []

    t0 = time.perf_counter()
    for i, (qid, question) in enumerate(sampled.queries.items(), 1):
        # Ground truth: concatenate all relevant doc texts
        gt_doc_ids = sampled.qrels.get(qid, [])
        ground_truth = " ".join(
            sampled.corpus.get(did, "") for did in gt_doc_ids
        ).strip()

        # Retrieve from both collections
        naive_result = await retrieve_chunks(
            query=question,
            collection_name=NAIVE_COLLECTION,
            qdrant=qdrant,
            openrouter=openrouter,
            top_k=TOP_K,
        )
        optimized_result = await retrieve_chunks(
            query=question,
            collection_name=OPTIMIZED_COLLECTION,
            qdrant=qdrant,
            openrouter=openrouter,
            top_k=TOP_K,
        )

        # Generate answers using project's configured OSS LLM
        naive_answer = await generate_answer(
            question=question,
            contexts=naive_result.texts,
            llm_client=llm_client,
            chat_model=CHAT_MODEL,
        )
        optimized_answer = await generate_answer(
            question=question,
            contexts=optimized_result.texts,
            llm_client=llm_client,
            chat_model=CHAT_MODEL,
        )

        naive_records.append(BenchmarkRecord(
            question=question,
            answer=naive_answer,
            contexts=naive_result.texts,
            ground_truth=ground_truth,
        ))
        optimized_records.append(BenchmarkRecord(
            question=question,
            answer=optimized_answer,
            contexts=optimized_result.texts,
            ground_truth=ground_truth,
        ))

        # Progress
        if i % 10 == 0 or i == len(sampled.queries):
            elapsed = time.perf_counter() - t0
            print(f"  {i}/{len(sampled.queries)} queries done ({elapsed:.0f}s)")

    # Step 4: Ragas evaluation
    print(f"\n[4/4] Running Ragas evaluation...")
    results = run_ragas_evaluation(
        naive_records=naive_records,
        optimized_records=optimized_records,
        report_path=report_path,
    )

    # Print summary
    print("\n" + "=" * 80)
    print("  BENCHMARK RESULTS")
    print("=" * 80)
    print(f"\n{'Metric':<25} {'Naive RAG':>12} {'Optimized RAG':>15} {'Δ':>10}")
    print("-" * 65)
    for metric in results["naive"]:
        naive_val = results["naive"][metric]
        opt_val = results["optimized"][metric]
        if isinstance(naive_val, (int, float)) and isinstance(opt_val, (int, float)):
            delta = opt_val - naive_val
            print(f"{metric:<25} {naive_val:>12.4f} {opt_val:>15.4f} {delta:>+10.4f}")
    print("-" * 65)
    print(f"\nReport saved to: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Run RAG benchmark: Naive vs Optimized using BeIR/FiQA + Ragas"
    )
    parser.add_argument(
        "--num-queries", type=int, default=NUM_TEST_QUERIES,
        help=f"Number of test queries to evaluate (default: {NUM_TEST_QUERIES})"
    )
    parser.add_argument(
        "--skip-ingest", action="store_true",
        help="Skip ingestion step (use existing collections)"
    )
    parser.add_argument(
        "--report", default=REPORT_PATH,
        help=f"Output report path (default: {REPORT_PATH})"
    )
    args = parser.parse_args()

    asyncio.run(run_benchmark(
        num_queries=args.num_queries,
        skip_ingest=args.skip_ingest,
        report_path=args.report,
    ))


if __name__ == "__main__":
    main()
