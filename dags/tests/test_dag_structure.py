"""Tests for DAG structure — verifies tasks, dependencies, and basic properties."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


class DummyTask:
    def __init__(self, task_id, **kwargs):
        self.task_id = task_id
        self.upstream_list = []
    def __rshift__(self, other):
        if isinstance(other, list):
            for t in other:
                t.upstream_list.append(self)
        else:
            other.upstream_list.append(self)
        return other
    def __rrshift__(self, other):
        if isinstance(other, list):
            for t in other:
                self.upstream_list.append(t)
        return self

class DummyDAG:
    def __init__(self, **kwargs):
        self.tasks = []
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def get_task(self, task_id):
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None

def dummy_operator(task_id, **kwargs):
    from dags.pdf_ingestion import dag
    t = DummyTask(task_id)
    dag.tasks.append(t)
    return t

sys.modules["airflow"] = type("airflow", (), {"DAG": DummyDAG})
sys.modules["airflow.models"] = type("models", (), {})
sys.modules["airflow.decorators"] = type("decorators", (), {})
sys.modules["airflow.hooks.base"] = type("base", (), {})
sys.modules["airflow.operators"] = type("operators", (), {})
sys.modules["airflow.operators.python"] = type("python", (), {"PythonOperator": dummy_operator})
sys.modules["airflow.utils"] = type("utils", (), {})
sys.modules["airflow.utils.dates"] = type("dates", (), {"days_ago": lambda x: None})


class TestDagStructure:
    def test_dag_file_is_importable(self):
        """DAG Python file can be imported without errors."""
        # Add dags/ to path for import
        dags_dir = str(Path(__file__).parent.parent)
        if dags_dir not in sys.path:
            sys.path.insert(0, dags_dir)

        # This should not raise
        from dags.pdf_ingestion import dag
        assert dag is not None

    def test_dag_has_correct_task_count(self):
        from dags.pdf_ingestion import dag
        assert len(dag.tasks) == 8

    def test_dag_task_names(self):
        from dags.pdf_ingestion import dag
        task_ids = {t.task_id for t in dag.tasks}
        expected = {
            "download_pdf", "extract_text", "validate_text", "chunk_text",
            "embed_and_upsert_qdrant",
            "build_graph", "upsert_neo4j", "finalize",
        }
        # embed + upsert_qdrant may be combined into one task
        # adjust based on implementation
        assert "download_pdf" in task_ids
        assert "finalize" in task_ids
        assert task_ids == expected

    def test_finalize_depends_on_both_branches(self):
        from dags.pdf_ingestion import dag
        finalize = dag.get_task("finalize")
        upstream_ids = {t.task_id for t in finalize.upstream_list}
        # finalize must wait for both vector and graph branches
        assert len(upstream_ids) >= 2
