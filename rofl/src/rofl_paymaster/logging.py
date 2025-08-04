"""Structured logging framework for ROFL Paymaster."""

import logging
import logging.handlers
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from pythonjsonlogger.json import JsonFormatter


# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class CorrelationIDFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        record.correlation_id = correlation_id.get()
        return True


class JSONFormatter(JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO format
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()

        # Add application context
        log_record["service"] = "rofl-paymaster"
        log_record["version"] = getattr(record, "version", "0.1.0")

        # Add correlation ID if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_record["correlation_id"] = record.correlation_id

        # Add process/thread info
        log_record["process_id"] = record.process
        log_record["thread_id"] = record.thread

        # Clean up None values
        log_record = {k: v for k, v in log_record.items() if v is not None}


class TextFormatter(logging.Formatter):
    """Custom text formatter with correlation ID support."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text with correlation ID."""
        # Add correlation ID to the record if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            record.msg = f"[{record.correlation_id}] {record.msg}"

        return super().format(record)


class LoggingManager:
    """Manages structured logging configuration for the application."""

    def __init__(self):
        """Initialize logging manager."""
        self._loggers: Dict[str, logging.Logger] = {}
        self._configured = False

    def configure_logging(
        self,
        level: str = "INFO",
        format_type: str = "json",
        file_path: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 5,
        correlation_id_enabled: bool = True,
    ) -> None:
        """Configure structured logging.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            format_type: Log format ('json' or 'text')
            file_path: Optional file path for log output
            max_file_size: Maximum log file size in bytes
            backup_count: Number of backup files to keep
            correlation_id_enabled: Whether to include correlation IDs
        """
        if self._configured:
            return

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.upper()))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Create formatter
        if format_type.lower() == "json":
            formatter = JSONFormatter(
                fmt="%(timestamp)s %(level)s %(name)s %(message)s"
            )
        else:
            formatter = TextFormatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        if correlation_id_enabled:
            console_handler.addFilter(CorrelationIDFilter())

        root_logger.addHandler(console_handler)

        # File handler if specified
        if file_path:
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                filename=file_path,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)

            if correlation_id_enabled:
                file_handler.addFilter(CorrelationIDFilter())

            root_logger.addHandler(file_handler)

        # Disable propagation for some noisy loggers
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("web3").setLevel(logging.WARNING)

        self._configured = True

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance.

        Args:
            name: Logger name

        Returns:
            Logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)

        return self._loggers[name]

    def create_correlation_id(self) -> str:
        """Create a new correlation ID.

        Returns:
            Unique correlation ID
        """
        return str(uuid.uuid4())

    def set_correlation_id(self, corr_id: Optional[str] = None) -> str:
        """Set correlation ID for current context.

        Args:
            corr_id: Correlation ID to set. If None, generates a new one.

        Returns:
            The correlation ID that was set
        """
        if corr_id is None:
            corr_id = self.create_correlation_id()

        correlation_id.set(corr_id)
        return corr_id

    def get_correlation_id(self) -> Optional[str]:
        """Get current correlation ID.

        Returns:
            Current correlation ID or None
        """
        return correlation_id.get()

    def clear_correlation_id(self) -> None:
        """Clear current correlation ID."""
        correlation_id.set(None)


class StructuredLogger:
    """Wrapper for structured logging with additional context."""

    def __init__(self, name: str, manager: Optional[LoggingManager] = None):
        """Initialize structured logger.

        Args:
            name: Logger name
            manager: Logging manager instance
        """
        self._manager = manager or logging_manager
        self._logger = self._manager.get_logger(name)
        self._name = name

    def _log_with_context(
        self,
        level: int,
        message: str,
        extra_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log message with additional context.

        Args:
            level: Log level
            message: Log message
            extra_context: Additional context to include
            **kwargs: Additional keyword arguments
        """
        context = extra_context or {}

        # Add any additional context from kwargs
        for key, value in kwargs.items():
            if key not in ["exc_info", "extra", "stack_info"]:
                context[key] = value

        # Create extra dict for structured logging
        extra = kwargs.get("extra", {})
        extra.update(context)

        self._logger.log(
            level,
            message,
            extra=extra,
            **{k: v for k, v in kwargs.items() if k != "extra"},
        )

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def log_event(
        self, event_type: str, message: str, level: int = logging.INFO, **kwargs
    ) -> None:
        """Log a structured event.

        Args:
            event_type: Type of event (e.g., 'deposit_processed', 'proof_generated')
            message: Human-readable message
            level: Log level
            **kwargs: Additional event data
        """
        context = {"event_type": event_type, "timestamp": time.time()}
        context.update(kwargs)

        self._log_with_context(level, message, extra_context=context)

    def log_performance(
        self, operation: str, duration_ms: float, success: bool = True, **kwargs
    ) -> None:
        """Log performance metrics.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation was successful
            **kwargs: Additional metrics
        """
        context = {
            "metric_type": "performance",
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
        }
        context.update(kwargs)

        level = logging.INFO if success else logging.WARNING
        message = f"{operation} completed in {duration_ms:.2f}ms"

        self._log_with_context(level, message, extra_context=context)

    def log_audit(
        self,
        action: str,
        resource: str,
        user: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log audit events.

        Args:
            action: Action performed
            resource: Resource affected
            user: User performing action
            success: Whether action was successful
            **kwargs: Additional audit data
        """
        context = {
            "audit": True,
            "action": action,
            "resource": resource,
            "user": user,
            "success": success,
            "timestamp": time.time(),
        }
        context.update(kwargs)

        level = logging.INFO if success else logging.WARNING
        message = f"Audit: {action} on {resource}"
        if user:
            message += f" by {user}"

        self._log_with_context(level, message, extra_context=context)


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, logger: StructuredLogger, operation: str, **kwargs):
        """Initialize performance timer.

        Args:
            logger: Structured logger instance
            operation: Operation name
            **kwargs: Additional context
        """
        self.logger = logger
        self.operation = operation
        self.context = kwargs
        self.start_time = None
        self.success = True

    def __enter__(self):
        """Start timing."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End timing and log performance."""
        if self.start_time is not None:
            duration_ms = (time.perf_counter() - self.start_time) * 1000

            # Mark as failed if exception occurred
            if exc_type is not None:
                self.success = False
                self.context["error"] = str(exc_val)

            self.logger.log_performance(
                operation=self.operation,
                duration_ms=duration_ms,
                success=self.success,
                **self.context,
            )

    def mark_failed(self, error: Optional[str] = None):
        """Mark operation as failed."""
        self.success = False
        if error:
            self.context["error"] = error


# Global logging manager instance
logging_manager = LoggingManager()


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name

    Returns:
        Structured logger instance
    """
    return StructuredLogger(name, logging_manager)


def configure_logging_from_config(config: Dict[str, Any]) -> None:
    """Configure logging from configuration dictionary.

    Args:
        config: Logging configuration
    """
    logging_manager.configure_logging(
        level=config.get("level", "INFO"),
        format_type=config.get("format", "json"),
        file_path=config.get("file_path"),
        max_file_size=config.get("max_file_size", 100 * 1024 * 1024),
        backup_count=config.get("backup_count", 5),
        correlation_id_enabled=config.get("correlation_id", True),
    )
