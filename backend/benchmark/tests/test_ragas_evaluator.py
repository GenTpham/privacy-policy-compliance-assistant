"""Tests for Ragas evaluation wrapper."""
import pytest

from backend.benchmark.ragas_evaluator import (
    BenchmarkRecord,
    prepare_ragas_dataset,
)


class TestBenchmarkRecord:
    def test_fields(self):
        rec = BenchmarkRecord(
            question="What?",
            answer="42",
            contexts=["passage 1"],
            ground_truth="The answer is 42",
        )
        assert rec.question == "What?"
        assert rec.answer == "42"
        assert rec.contexts == ["passage 1"]
        assert rec.ground_truth == "The answer is 42"


class TestPrepareRagasDataset:
    def test_returns_dataset_with_correct_columns(self):
        records = [
            BenchmarkRecord(
                question="Q1",
                answer="A1",
                contexts=["C1"],
                ground_truth="GT1",
            ),
            BenchmarkRecord(
                question="Q2",
                answer="A2",
                contexts=["C2a", "C2b"],
                ground_truth="GT2",
            ),
        ]
        ds = prepare_ragas_dataset(records)
        assert "question" in ds.column_names
        assert "answer" in ds.column_names
        assert "contexts" in ds.column_names
        assert "ground_truth" in ds.column_names
        assert len(ds) == 2

    def test_contexts_are_lists(self):
        records = [
            BenchmarkRecord(
                question="Q",
                answer="A",
                contexts=["C1", "C2"],
                ground_truth="GT",
            ),
        ]
        ds = prepare_ragas_dataset(records)
        assert isinstance(ds[0]["contexts"], list)
        assert ds[0]["contexts"] == ["C1", "C2"]
