"""
Ragas evaluation wrapper.

Prepares benchmark records into Ragas-compatible Dataset format,
runs evaluation with configured metrics, and exports results.
"""
import csv
from dataclasses import dataclass
from pathlib import Path

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_correctness,
    context_precision,
    context_recall,
    faithfulness,
)
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from backend.app.core.config import get_settings
from backend.benchmark.config import REPORT_PATH, EMBED_MODEL


@dataclass
class BenchmarkRecord:
    """A single benchmark evaluation record."""
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str


def prepare_ragas_dataset(records: list[BenchmarkRecord]) -> Dataset:
    """
    Convert BenchmarkRecords into a HuggingFace Dataset with
    the columns Ragas expects: question, answer, contexts, ground_truth.
    """
    data = {
        "question": [r.question for r in records],
        "answer": [r.answer for r in records],
        "contexts": [r.contexts for r in records],
        "ground_truth": [r.ground_truth for r in records],
    }
    return Dataset.from_dict(data)


def _make_judge_llm() -> ChatOpenAI:
    """
    Create the LLM used by Ragas as a "judge" to score metrics.
    Uses the project's configured OSS model via OpenRouter.
    """
    settings = get_settings()
    return ChatOpenAI(
        model="openai/gpt-oss-120b:free",
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.0,
    )

def _make_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=EMBED_MODEL,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )


def run_ragas_evaluation(
    naive_records: list[BenchmarkRecord],
    optimized_records: list[BenchmarkRecord],
    report_path: str = REPORT_PATH,
) -> dict:
    """
    Run Ragas evaluation on both naive and optimized record sets.

    Args:
        naive_records: Records from the naive RAG pipeline.
        optimized_records: Records from the optimized RAG pipeline.
        report_path: Path to save the CSV report.

    Returns:
        Dict with keys "naive" and "optimized", each containing
        a dict of metric_name → score.
    """
    judge_llm = _make_judge_llm()
    embeddings = _make_embeddings()
    metrics = [faithfulness, answer_correctness, context_precision, context_recall]

    # Evaluate naive
    print("[ragas] Evaluating Naive RAG...")
    naive_ds = prepare_ragas_dataset(naive_records)
    naive_result = evaluate(
        dataset=naive_ds,
        metrics=metrics,
        llm=judge_llm,
        embeddings=embeddings,
    )

    # Evaluate optimized
    print("[ragas] Evaluating Optimized RAG...")
    optimized_ds = prepare_ragas_dataset(optimized_records)
    optimized_result = evaluate(
        dataset=optimized_ds,
        metrics=metrics,
        llm=judge_llm,
        embeddings=embeddings,
    )

    results = {
        "naive": dict(naive_result),
        "optimized": dict(optimized_result),
    }

    # Export CSV report
    _export_report(results, report_path)

    return results


def _export_report(results: dict, report_path: str) -> None:
    """Export comparison results to CSV."""
    path = Path(report_path)
    metrics = list(results["naive"].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Naive RAG", "Optimized RAG", "Improvement"])

        for metric in metrics:
            naive_score = results["naive"].get(metric, 0)
            opt_score = results["optimized"].get(metric, 0)

            if isinstance(naive_score, (int, float)) and isinstance(opt_score, (int, float)):
                improvement = opt_score - naive_score
                writer.writerow([
                    metric,
                    f"{naive_score:.4f}",
                    f"{opt_score:.4f}",
                    f"{improvement:+.4f}",
                ])
            else:
                writer.writerow([metric, str(naive_score), str(opt_score), "N/A"])

    print(f"[ragas] Report saved to {path}")
