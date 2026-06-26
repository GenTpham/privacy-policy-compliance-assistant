"""Tests for FiQA data loader."""
import pytest

from backend.benchmark.data_loader import FiQAData, load_fiqa, sample_test_set


class TestLoadFiqa:
    """Test that load_fiqa returns the expected structure."""

    def test_returns_fiqa_data(self):
        data = load_fiqa()
        assert isinstance(data, FiQAData)
        assert len(data.corpus) > 0
        assert len(data.queries) > 0
        assert len(data.qrels) > 0

    def test_corpus_entries_have_text(self):
        data = load_fiqa()
        first_key = next(iter(data.corpus))
        assert isinstance(data.corpus[first_key], str)
        assert len(data.corpus[first_key]) > 0

    def test_queries_are_strings(self):
        data = load_fiqa()
        first_key = next(iter(data.queries))
        assert isinstance(data.queries[first_key], str)

    def test_qrels_map_query_to_doc_ids(self):
        data = load_fiqa()
        first_qid = next(iter(data.qrels))
        assert isinstance(data.qrels[first_qid], list)
        assert len(data.qrels[first_qid]) > 0


class TestSampleTestSet:
    """Test that sample_test_set filters correctly."""

    def test_returns_requested_count(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        assert len(sampled.queries) == 10

    def test_corpus_contains_only_relevant_docs(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        # Every doc_id referenced in qrels must exist in corpus
        for qid, doc_ids in sampled.qrels.items():
            for doc_id in doc_ids:
                assert doc_id in sampled.corpus, (
                    f"doc_id {doc_id} from qrels not found in sampled corpus"
                )

    def test_qrels_match_queries(self):
        data = load_fiqa()
        sampled = sample_test_set(data, n=10)
        assert set(sampled.qrels.keys()) == set(sampled.queries.keys())
