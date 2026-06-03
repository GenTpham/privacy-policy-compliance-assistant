"""Env defaults so ingestion modules can import Settings-backed clients in tests."""
import os

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("QDRANT_URL", "https://cluster.qdrant.io")
os.environ.setdefault("QDRANT_API_KEY", "test-qdrant-key")
