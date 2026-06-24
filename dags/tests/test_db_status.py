"""Tests for DAG status update helpers."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from tasks.db_status import update_current_task, mark_completed, mark_failed


class TestUpdateCurrentTask:
    @patch("tasks.db_status._get_engine")
    def test_updates_status_and_current_task(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        update_current_task("job-123", "download_pdf")

        mock_conn.execute.assert_called_once()
        sql_text = str(mock_conn.execute.call_args[0][0])
        assert "ingestion_jobs" in sql_text
        assert "running" in sql_text


class TestMarkCompleted:
    @patch("tasks.db_status._get_engine")
    def test_sets_status_completed_and_clears_current_task(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        mark_completed("job-123", "doc-456")

        # Should execute 2 UPDATE statements: ingestion_jobs + documents
        assert mock_conn.execute.call_count == 2


class TestMarkFailed:
    @patch("tasks.db_status._get_engine")
    def test_sets_status_failed_with_error_details(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        mark_failed("job-123", "doc-456", "extract_text", "OCR failed: corrupt PDF")

        assert mock_conn.execute.call_count == 2
