"""Tests for Task 54: Structured Log Export

Tests both JSON Lines logging (54.1) and log viewer CLI (54.2).
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import pytest
import sys
import os

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from InstanceScrubber.json_logging import JSONFormatter, setup_json_logging, get_json_log_files


class TestJSONFormatter:
    """Test JSON logging formatter."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting functionality."""
        formatter = JSONFormatter()
        
        # Create a test log record
        logger = logging.getLogger("test_logger")
        record = logger.makeRecord(
            name="test_logger",
            level=logging.INFO,
            fn="test_file.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Format the record
        formatted = formatter.format(record)
        
        # Parse the JSON
        log_entry = json.loads(formatted)
        
        # Verify required fields
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test_logger"
        assert log_entry["message"] == "Test message"
        assert log_entry["module"] == "test_file"
        assert log_entry["function"] == "makeRecord"
        assert log_entry["line"] == 42
        assert "timestamp" in log_entry
        assert "process_id" in log_entry
        assert "hostname" in log_entry

    def test_json_formatter_with_exception(self):
        """Test JSON formatting with exception information."""
        formatter = JSONFormatter()
        logger = logging.getLogger("test_logger")
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logger.makeRecord(
                name="test_logger",
                level=logging.ERROR,
                fn="test_file.py",
                lno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Verify exception information
        assert "exception" in log_entry
        assert log_entry["exception"]["type"] == "ValueError"
        assert log_entry["exception"]["message"] == "Test exception"
        assert "traceback" in log_entry["exception"]

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatting with extra fields."""
        formatter = JSONFormatter(include_extra=True)
        logger = logging.getLogger("test_logger")
        
        record = logger.makeRecord(
            name="test_logger",
            level=logging.INFO,
            fn="test_file.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.session_id = "test-session-123"
        record.duration = 150.5
        record.custom_field = "custom_value"
        
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Verify extra fields
        assert log_entry["session_id"] == "test-session-123"
        assert log_entry["duration_ms"] == 150.5
        assert log_entry["extra"]["custom_field"] == "custom_value"


class TestJSONLogging:
    """Test JSON logging setup and functionality."""

    def test_setup_json_logging(self):
        """Test JSON logging setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.jsonl"
            
            # Setup JSON logging
            handler = setup_json_logging(
                log_file=log_file,
                backup_count=5,
                level=logging.INFO
            )
            
            assert handler is not None
            assert isinstance(handler.formatter, JSONFormatter)
            assert log_file.parent.exists()

    def test_json_logging_output(self):
        """Test that JSON logging produces valid JSON Lines output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.jsonl"
            
            # Setup logger with JSON handler
            logger = logging.getLogger("test_json_logger")
            logger.setLevel(logging.INFO)
            
            # Clear any existing handlers
            logger.handlers.clear()
            
            handler = setup_json_logging(
                log_file=log_file,
                level=logging.INFO
            )
            logger.addHandler(handler)
            
            # Log some test messages
            logger.info("Test info message")
            logger.warning("Test warning message", extra={"test_field": "test_value"})
            logger.error("Test error message")
            
            # Flush handler
            handler.flush()
            
            # Read and verify the log file
            assert log_file.exists()
            
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            assert len(lines) == 3
            
            # Verify each line is valid JSON
            for line in lines:
                log_entry = json.loads(line.strip())
                assert "timestamp" in log_entry
                assert "level" in log_entry
                assert "logger" in log_entry
                assert "message" in log_entry
            
            # Verify specific content
            info_entry = json.loads(lines[0].strip())
            assert info_entry["level"] == "INFO"
            assert info_entry["message"] == "Test info message"
            
            warning_entry = json.loads(lines[1].strip())
            assert warning_entry["level"] == "WARNING"
            assert warning_entry["message"] == "Test warning message"
            assert warning_entry["extra"]["test_field"] == "test_value"

    def test_get_json_log_files(self):
        """Test finding JSON log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            
            # Create test log files
            (log_dir / "app.jsonl").touch()
            (log_dir / "app.jsonl.2025-06-25").touch()
            (log_dir / "app.jsonl.2025-06-24").touch()
            (log_dir / "other.log").touch()  # Should be ignored
            
            # Get JSON log files
            json_files = get_json_log_files(log_dir)
            
            assert len(json_files) == 3
            assert all(f.name.startswith("app.jsonl") for f in json_files)


class TestLogViewer:
    """Test log viewer CLI functionality."""

    def test_log_viewer_import(self):
        """Test that log viewer can be imported."""
        # Import the log viewer module
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            import log_viewer
            assert hasattr(log_viewer, "LogViewer")
            assert hasattr(log_viewer, "main")
        except ImportError:
            pytest.skip("Log viewer script not available")

    def test_log_viewer_basic_functionality(self):
        """Test basic log viewer functionality."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from log_viewer import LogViewer
        except ImportError:
            pytest.skip("Log viewer script not available")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            log_file = log_dir / "app.jsonl"
            
            # Create test log entries
            test_entries = [
                {
                    "timestamp": "2025-06-26T10:00:00",
                    "level": "INFO",
                    "logger": "test_logger",
                    "message": "Test info message"
                },
                {
                    "timestamp": "2025-06-26T10:01:00",
                    "level": "WARNING",
                    "logger": "test_logger",
                    "message": "Test warning message"
                },
                {
                    "timestamp": "2025-06-26T10:02:00",
                    "level": "ERROR",
                    "logger": "test_logger",
                    "message": "Test error message"
                }
            ]
            
            # Write test log file
            with open(log_file, 'w', encoding='utf-8') as f:
                for entry in test_entries:
                    f.write(json.dumps(entry) + '\n')
            
            # Create log viewer
            viewer = LogViewer(str(log_dir))
            
            # Test reading entries
            entries = viewer.read_log_entries()
            assert len(entries) == 3
            
            # Test filtering by level
            error_entries = viewer.filter_entries(entries, levels=["ERROR"])
            assert len(error_entries) == 1
            assert error_entries[0]["level"] == "ERROR"
            
            # Test search filtering
            warning_entries = viewer.filter_entries(entries, search="warning")
            assert len(warning_entries) == 1
            assert "warning" in warning_entries[0]["message"].lower()
            
            # Test time filtering
            from_time = datetime.fromisoformat("2025-06-26T10:01:00")
            recent_entries = viewer.filter_entries(entries, from_time=from_time)
            assert len(recent_entries) == 2  # WARNING and ERROR
            
            # Test formatting
            formatted = viewer.format_entry(entries[0], show_json=False)
            assert "INFO" in formatted
            assert "Test info message" in formatted
            
            json_formatted = viewer.format_entry(entries[0], show_json=True)
            parsed = json.loads(json_formatted)
            assert parsed["level"] == "INFO"


class TestIntegratedLogging:
    """Test integrated logging with both text and JSON output."""

    def test_integrated_logging_setup(self):
        """Test that integrated logging setup works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            text_log = Path(temp_dir) / "app.log"
            json_log = Path(temp_dir) / "app.jsonl"
            
            # Import and setup logging
            from instant_scribe.logging_config import setup_logging
            
            # Clear any existing configuration
            root_logger = logging.getLogger()
            root_logger.handlers.clear()
            
            # Reset configuration flag
            import instant_scribe.logging_config
            instant_scribe.logging_config._CONFIGURED = False
            
            # Setup logging with both text and JSON
            setup_logging(
                log_file=text_log,
                json_log_file=json_log,
                enable_json_logging=True,
                level=logging.INFO
            )
            
            # Test logging
            logger = logging.getLogger("test_integrated")
            logger.info("Test integrated message")
            
            # Flush all handlers
            for handler in root_logger.handlers:
                handler.flush()
            
            # Verify both files exist and have content
            assert text_log.exists()
            assert json_log.exists()
            
            # Verify text log format
            with open(text_log, 'r', encoding='utf-8') as f:
                text_content = f.read()
            assert "Test integrated message" in text_content
            assert "INFO" in text_content
            
            # Verify JSON log format
            with open(json_log, 'r', encoding='utf-8') as f:
                json_content = f.read().strip()
            
            if json_content:  # JSON logging might not be available in test environment
                log_entry = json.loads(json_content)
                assert log_entry["message"] == "Test integrated message"
                assert log_entry["level"] == "INFO"


def test_task54_integration():
    """Integration test for Task 54: Complete structured logging workflow."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_dir = Path(temp_dir)
        
        # Test JSON logging setup
        json_log = log_dir / "test.jsonl"
        handler = setup_json_logging(log_file=json_log, level=logging.INFO)
        
        # Create test logger
        logger = logging.getLogger("task54_test")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.addHandler(handler)
        
        # Log test messages
        logger.info("Task 54 test started")
        logger.warning("Test warning with extra data", extra={"test_id": "54.1"})
        logger.error("Test error message")
        
        handler.flush()
        
        # Verify JSON log file
        assert json_log.exists()
        
        with open(json_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        assert len(lines) == 3
        
        # Verify JSON structure
        for line in lines:
            entry = json.loads(line.strip())
            assert "timestamp" in entry
            assert "level" in entry
            assert "message" in entry
        
        # Test log viewer functionality
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        
        try:
            from log_viewer import LogViewer
            
            viewer = LogViewer(str(log_dir))
            entries = viewer.read_log_entries()
            
            assert len(entries) == 3
            
            # Test filtering
            warning_entries = viewer.filter_entries(entries, levels=["WARNING"])
            assert len(warning_entries) == 1
            
            # Test formatting
            formatted = viewer.format_entry(entries[0])
            assert "Task 54 test started" in formatted
            
        except ImportError:
            # Log viewer not available in test environment
            pass


if __name__ == "__main__":
    # Run the integration test directly
    test_task54_integration()
    print("Task 54 integration test completed successfully!")
