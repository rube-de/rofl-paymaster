"""Tests for structured logging."""

import json
import logging
import tempfile
from pathlib import Path

from rofl_paymaster.logging import (
    LoggingManager,
    StructuredLogger,
    PerformanceTimer,
    get_logger,
    configure_logging_from_config,
)


def test_logging_manager_configuration():
    """Test logging manager configuration."""
    manager = LoggingManager()

    # Configure with JSON format
    manager.configure_logging(
        level="DEBUG", format_type="json", correlation_id_enabled=True
    )

    logger = manager.get_logger("test")
    assert logger.level <= logging.DEBUG


def test_structured_logger():
    """Test structured logger functionality."""
    manager = LoggingManager()
    manager.configure_logging(level="DEBUG", format_type="json")

    logger = StructuredLogger("test", manager)

    # Test basic logging methods
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")


def test_log_event():
    """Test structured event logging."""
    manager = LoggingManager()
    manager.configure_logging(level="INFO", format_type="json")

    logger = StructuredLogger("test", manager)

    logger.log_event(
        event_type="test_event",
        message="Test event occurred",
        user_id="test_user",
        amount=100.50,
    )


def test_log_performance():
    """Test performance logging."""
    manager = LoggingManager()
    manager.configure_logging(level="INFO", format_type="json")

    logger = StructuredLogger("test", manager)

    logger.log_performance(
        operation="test_operation",
        duration_ms=123.45,
        success=True,
        records_processed=100,
    )


def test_log_audit():
    """Test audit logging."""
    manager = LoggingManager()
    manager.configure_logging(level="INFO", format_type="json")

    logger = StructuredLogger("test", manager)

    logger.log_audit(
        action="create",
        resource="deposit",
        user="test_user",
        success=True,
        amount=500.0,
    )


def test_performance_timer():
    """Test performance timer context manager."""
    manager = LoggingManager()
    manager.configure_logging(level="INFO", format_type="json")

    logger = StructuredLogger("test", manager)

    # Test successful operation
    with PerformanceTimer(logger, "test_operation", user="test_user"):
        pass  # Simulate work

    # Test failed operation
    timer = PerformanceTimer(logger, "failed_operation")
    with timer:
        timer.mark_failed("Test error")


def test_correlation_id():
    """Test correlation ID functionality."""
    manager = LoggingManager()

    # Test creating and setting correlation ID
    corr_id = manager.create_correlation_id()
    assert isinstance(corr_id, str)
    assert len(corr_id) > 0

    # Test setting correlation ID
    set_id = manager.set_correlation_id("test-123")
    assert set_id == "test-123"

    # Test getting correlation ID
    current_id = manager.get_correlation_id()
    assert current_id == "test-123"

    # Test clearing correlation ID
    manager.clear_correlation_id()
    assert manager.get_correlation_id() is None


def test_configure_logging_from_config():
    """Test configuring logging from config dictionary."""
    config = {"level": "DEBUG", "format": "json", "correlation_id": True}

    configure_logging_from_config(config)

    # Get a logger and test it works
    logger = get_logger("test")
    logger.info("Test message")


def test_file_logging():
    """Test file logging configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"

        manager = LoggingManager()
        manager.configure_logging(
            level="INFO",
            format_type="json",
            file_path=str(log_file),
            max_file_size=1024,
            backup_count=2,
        )

        logger = StructuredLogger("test", manager)
        logger.info("Test file logging", extra={"test_field": "test_value"})

        # Check that log file was created and has content
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test file logging" in content


def test_json_formatter():
    """Test JSON formatter output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"

        manager = LoggingManager()
        manager.configure_logging(
            level="INFO", format_type="json", file_path=str(log_file)
        )

        logger = StructuredLogger("test", manager)
        logger.info(
            "Test JSON formatting",
            extra={"test_field": "test_value", "numeric_field": 123},
        )

        # Read and parse JSON log
        content = log_file.read_text().strip()
        log_entry = json.loads(content)

        assert log_entry["message"] == "Test JSON formatting"
        assert log_entry["test_field"] == "test_value"
        assert log_entry["numeric_field"] == 123
        assert "timestamp" in log_entry
        assert "service" in log_entry


def test_text_formatter():
    """Test text formatter output."""
    with tempfile.TemporaryDirectory() as temp_dir:
        log_file = Path(temp_dir) / "test.log"

        manager = LoggingManager()
        manager.configure_logging(
            level="INFO", format_type="text", file_path=str(log_file)
        )

        logger = StructuredLogger("test", manager)
        logger.info("Test text formatting")

        content = log_file.read_text()
        assert "Test text formatting" in content
        assert "INFO" in content
