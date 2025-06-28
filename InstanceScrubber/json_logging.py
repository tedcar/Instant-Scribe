"""JSON Lines logging configuration - Task 54

This module provides structured logging in JSON Lines format with daily rotation.
It extends the existing logging configuration to support both traditional text
and structured JSON logging formats.

Key features:
- JSON Lines format for structured log data
- Daily log rotation with configurable retention
- Backward compatibility with existing text format
- Enhanced metadata capture (process ID, thread ID, etc.)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["JSONFormatter", "setup_json_logging", "get_json_log_files"]


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs log records as JSON Lines.
    
    Each log record is converted to a JSON object with structured fields
    including timestamp, level, logger name, message, and additional metadata.
    """
    
    def __init__(self, include_extra: bool = True):
        """Initialize the JSON formatter.
        
        Args:
            include_extra: Whether to include extra fields from log records
        """
        super().__init__()
        self.include_extra = include_extra
        self.hostname = os.environ.get('COMPUTERNAME', 'unknown')
        self.process_id = os.getpid()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string.
        
        Args:
            record: The log record to format
            
        Returns:
            JSON string representation of the log record
        """
        # Create base log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread_id": record.thread,
            "thread_name": getattr(record, 'threadName', threading.current_thread().name),
            "process_id": self.process_id,
            "hostname": self.hostname,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None,
            }
        
        # Add extra fields if enabled
        if self.include_extra:
            # Add any extra fields that were passed to the log call
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                    'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                    'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                    'processName', 'process', 'message'
                }:
                    try:
                        # Only include JSON-serializable values
                        json.dumps(value)
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)
            
            if extra_fields:
                log_entry["extra"] = extra_fields
        
        # Add performance timing if available
        if hasattr(record, 'duration'):
            log_entry["duration_ms"] = getattr(record, 'duration')
        
        # Add request/session context if available
        if hasattr(record, 'session_id'):
            log_entry["session_id"] = getattr(record, 'session_id')
        
        if hasattr(record, 'user_id'):
            log_entry["user_id"] = getattr(record, 'user_id')
        
        try:
            return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError) as e:
            # Fallback to basic format if JSON serialization fails
            fallback_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "error": f"JSON serialization failed: {e}"
            }
            return json.dumps(fallback_entry, ensure_ascii=False, separators=(',', ':'))


def setup_json_logging(
    *,
    log_file: str | os.PathLike[str] = "logs/app.jsonl",
    when: str = "midnight",
    interval: int = 1,
    backup_count: int = 30,
    level: int | str = logging.INFO,
    include_extra: bool = True,
) -> logging.Handler:
    """Set up JSON Lines logging with daily rotation.
    
    Args:
        log_file: Path to the JSON log file
        when: When to rotate ('midnight', 'H', 'D', etc.)
        interval: Rotation interval (1 = daily for 'midnight')
        backup_count: Number of backup files to keep
        level: Minimum log level
        include_extra: Whether to include extra fields in JSON output
        
    Returns:
        The configured TimedRotatingFileHandler
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create JSON formatter
    json_formatter = JSONFormatter(include_extra=include_extra)
    
    # Create timed rotating file handler
    try:
        json_handler = TimedRotatingFileHandler(
            filename=str(log_path),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding="utf-8",
            utc=False  # Use local time for rotation
        )

        # Set suffix for rotated files (YYYY-MM-DD format)
        json_handler.suffix = "%Y-%m-%d"
    except OSError:
        # Fallback to regular FileHandler if TimedRotatingFileHandler fails
        json_handler = logging.FileHandler(
            filename=str(log_path),
            encoding="utf-8"
        )
    
    json_handler.setFormatter(json_formatter)
    json_handler.setLevel(level)
    
    return json_handler


def get_json_log_files(log_dir: str | os.PathLike[str] = "logs") -> list[Path]:
    """Get all JSON log files in the specified directory.
    
    Args:
        log_dir: Directory to search for log files
        
    Returns:
        List of JSON log file paths, sorted by modification time (newest first)
    """
    log_path = Path(log_dir)
    if not log_path.exists():
        return []
    
    # Find all .jsonl files and rotated JSON log files
    json_files = []
    
    # Current log file
    current_log = log_path / "app.jsonl"
    if current_log.exists():
        json_files.append(current_log)
    
    # Rotated log files (app.jsonl.YYYY-MM-DD)
    for file_path in log_path.glob("app.jsonl.*"):
        if file_path.is_file():
            json_files.append(file_path)
    
    # Sort by modification time (newest first)
    json_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    return json_files


def add_json_logging_to_root(
    log_file: str | os.PathLike[str] = "logs/app.jsonl",
    **kwargs
) -> None:
    """Add JSON logging handler to the root logger.
    
    This function adds a JSON logging handler alongside existing handlers,
    allowing both text and JSON logging to coexist.
    
    Args:
        log_file: Path to the JSON log file
        **kwargs: Additional arguments passed to setup_json_logging
    """
    root_logger = logging.getLogger()
    
    # Check if JSON handler already exists
    json_handler_exists = any(
        isinstance(handler, TimedRotatingFileHandler) and 
        isinstance(handler.formatter, JSONFormatter)
        for handler in root_logger.handlers
    )
    
    if not json_handler_exists:
        json_handler = setup_json_logging(log_file=log_file, **kwargs)
        root_logger.addHandler(json_handler)


# Performance logging helpers
class PerformanceLogger:
    """Context manager for logging performance metrics."""
    
    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration_ms = (time.perf_counter() - self.start_time) * 1000
            self.logger.log(
                self.level,
                f"Operation '{self.operation}' completed",
                extra={"operation": self.operation, "duration": duration_ms}
            )
