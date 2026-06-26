"""
Benchmark-specific configuration constants.
All tunables live here — no magic numbers scattered across modules.
"""

# -- Qdrant collection names (separate from production "policies" collection) --
NAIVE_COLLECTION = "fiqa_naive_rag"
OPTIMIZED_COLLECTION = "fiqa_optimized_rag"

# -- FiQA dataset --
FIQA_DATASET_NAME = "BeIR/fiqa"

# -- Sampling --
# Number of test queries to evaluate (controls API cost)
NUM_TEST_QUERIES = 100

# -- Retrieval --
TOP_K = 5  # chunks retrieved per query

# -- Naive chunker --
NAIVE_CHUNK_SIZE = 1000   # characters — intentionally crude
NAIVE_CHUNK_OVERLAP = 0   # no overlap — this is the "lazy default" baseline

# -- Embedding --
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_BATCH_SIZE = 50
EMBED_SLEEP_SECONDS = 3  # polite delay for free-tier

# -- Generation --
# Read from rag.py's configured CHAT_MODEL — do NOT hardcode a model here.
# The generator module will import CHAT_MODEL from backend.app.services.rag.

# -- Output --
REPORT_PATH = "benchmark_report.csv"
