"""
Download and prepare BeIR/FiQA dataset for benchmarking.

Uses HuggingFace `datasets` library. Caches locally after first download.
Returns structured data with corpus (doc_id → text), queries (qid → question),
and qrels (qid → [list of relevant doc_ids]).
"""
from dataclasses import dataclass

from datasets import load_dataset


@dataclass
class FiQAData:
    """Structured container for FiQA benchmark data."""
    corpus: dict[str, str]       # doc_id → text
    queries: dict[str, str]      # query_id → question text
    qrels: dict[str, list[str]]  # query_id → [relevant doc_ids]


def load_fiqa() -> FiQAData:
    """
    Load BeIR/FiQA from HuggingFace.

    FiQA has three configs on HuggingFace:
      - "corpus": columns [_id, title, text]
      - "queries": columns [_id, text]
      - "default" (qrels): columns [query-id, corpus-id, score]

    Returns a FiQAData with all three components.
    """
    # Load corpus
    corpus_ds = load_dataset("BeIR/fiqa", "corpus", split="corpus")
    corpus: dict[str, str] = {}
    for row in corpus_ds:
        doc_id = str(row["_id"])
        title = row.get("title", "")
        text = row.get("text", "")
        full_text = f"{title}\n{text}".strip() if title else text
        corpus[doc_id] = full_text

    # Load queries
    queries_ds = load_dataset("BeIR/fiqa", "queries", split="queries")
    queries: dict[str, str] = {}
    for row in queries_ds:
        qid = str(row["_id"])
        queries[qid] = row["text"]

    # Load qrels (relevance judgments)
    qrels_ds = load_dataset("BeIR/fiqa", "default", split="test")
    qrels: dict[str, list[str]] = {}
    for row in qrels_ds:
        qid = str(row["query-id"])
        doc_id = str(row["corpus-id"])
        score = row.get("score", 1)
        if score > 0:  # only positive relevance
            if qid not in qrels:
                qrels[qid] = []
            qrels[qid].append(doc_id)

    return FiQAData(corpus=corpus, queries=queries, qrels=qrels)


def sample_test_set(data: FiQAData, n: int) -> FiQAData:
    """
    Sample n queries (that have qrels) and return a filtered FiQAData
    containing only the relevant corpus documents.

    Args:
        data: Full FiQAData from load_fiqa().
        n: Number of test queries to sample.

    Returns:
        A new FiQAData with only the sampled queries, their qrels,
        and the corpus documents referenced by those qrels.
    """
    # Only queries that have relevance judgments
    valid_qids = [qid for qid in data.qrels if qid in data.queries]
    selected_qids = valid_qids[:n]  # deterministic — first n

    sampled_queries = {qid: data.queries[qid] for qid in selected_qids}
    sampled_qrels = {qid: data.qrels[qid] for qid in selected_qids}

    # Collect all referenced doc_ids
    relevant_doc_ids = set()
    for doc_ids in sampled_qrels.values():
        relevant_doc_ids.update(doc_ids)

    sampled_corpus = {
        doc_id: data.corpus[doc_id]
        for doc_id in relevant_doc_ids
        if doc_id in data.corpus
    }

    return FiQAData(
        corpus=sampled_corpus,
        queries=sampled_queries,
        qrels=sampled_qrels,
    )
