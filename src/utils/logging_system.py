# -*- coding: utf-8 -*-
"""Logging system for the AI Research Assistant.

This module provides a production-ready logger with all standard logging levels
and helper functions for domain-specific logging patterns. The logger is configured
to write to multiple files for better log tracing:
- combined.log: All logs
- error.log: Errors and warnings only
- performance.log: Performance metrics only
- events.log: Structured events only

Usage:
    from src.utils.logging_system import logger
    
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.log_event("event_type", "message", extra_data={...})
    logger.log_performance("operation", duration_ms=100, success=True, **kwargs)
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from rich.console import Console
from rich.logging import RichHandler


class ApplicationLogger(logging.Logger):
    """Extended logger with domain-specific logging methods."""
    
    def log_event(
        self,
        event_type: str,
        message: str,
        level: str = 'info',
        extra_data: Dict[str, Any] = None,
        **kwargs
    ) -> None:
        """Log a structured event with additional context.
        
        Args:
            event_type: Type of event (e.g., 'quality_monitoring', 'model_detection')
            message: Event message
            level: Log level as string ('debug', 'info', 'warning', 'error')
            extra_data: Additional event data dictionary
            **kwargs: Additional event data as keyword arguments
        """
        # Merge extra_data and kwargs
        context_data = {'event_type': event_type}
        if extra_data:
            context_data.update(extra_data)
        context_data.update(kwargs)
        
        log_method = getattr(self, level.lower(), self.info)
        log_method(message, extra={'context': context_data, 'is_event': True})
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        extra_data: Dict[str, Any] = None,
        **kwargs
    ) -> None:
        """Log performance metrics for an operation.
        
        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether operation was successful
            extra_data: Additional performance data dictionary
            **kwargs: Additional performance data as keyword arguments
        """
        message = f"Operation '{operation}' {'succeeded' if success else 'failed'} in {duration_ms:.2f}ms"
        
        # Merge extra_data and kwargs
        context_data = {
            'event_type': 'performance',
            'operation': operation,
            'duration_ms': duration_ms,
            'success': success
        }
        if extra_data:
            context_data.update(extra_data)
        context_data.update(kwargs)
        
        self.info(message, extra={'context': context_data, 'is_performance': True})


class LevelFilter(logging.Filter):
    """Filter logs by level."""
    
    def __init__(self, level):
        self.level = level
    
    def filter(self, record):
        return record.levelno >= self.level


class EventFilter(logging.Filter):
    """Filter to include only event logs."""
    
    def filter(self, record):
        return record.__dict__.get('is_event', False)


class PerformanceFilter(logging.Filter):
    """Filter to include only performance logs."""
    
    def filter(self, record):
        return record.__dict__.get('is_performance', False)


def _setup_logger(
    name: str = "ai_research_assistant",
    level: int = logging.INFO,
    log_directory: str = "logs",
    max_file_size_mb: int = 10,
    backup_count: int = 5
) -> ApplicationLogger:
    """Set up the application logger with multiple file handlers for log tracing.
    
    Creates the following log files:
    - combined.log: All logs
    - error.log: Errors and warnings only
    - performance.log: Performance metrics only
    - events.log: Structured events only
    
    Args:
        name: Logger name
        level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_directory: Directory for log files
        max_file_size_mb: Maximum file size before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        ApplicationLogger: Configured logger instance
    """
    # Set the logger class
    logging.setLoggerClass(ApplicationLogger)
    
    # Create logger
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(level)
    
    # Clear any existing handlers to avoid duplicates
    logger_instance.handlers.clear()
    
    # Prevent propagation to root logger
    logger_instance.propagate = False
    
    # Standard formatter with timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create log directory
    log_dir = Path(log_directory)
    log_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    max_bytes = max_file_size_mb * 1024 * 1024
    
    # 1. Combined log file (all logs)
    combined_log = log_dir / f"combined_{timestamp}.log"
    combined_handler = logging.handlers.RotatingFileHandler(
        combined_log,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    combined_handler.setFormatter(formatter)
    logger_instance.addHandler(combined_handler)
    
    # 2. Error log file (warnings and errors only)
    error_log = log_dir / f"error_{timestamp}.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    error_handler.setFormatter(formatter)
    error_handler.addFilter(LevelFilter(logging.WARNING))
    logger_instance.addHandler(error_handler)
    
    # 3. Performance log file (performance metrics only)
    performance_log = log_dir / f"performance_{timestamp}.log"
    performance_handler = logging.handlers.RotatingFileHandler(
        performance_log,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    performance_handler.setFormatter(formatter)
    performance_handler.addFilter(PerformanceFilter())
    logger_instance.addHandler(performance_handler)
    
    # 4. Events log file (structured events only)
    events_log = log_dir / f"events_{timestamp}.log"
    events_handler = logging.handlers.RotatingFileHandler(
        events_log,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    events_handler.setFormatter(formatter)
    events_handler.addFilter(EventFilter())
    logger_instance.addHandler(events_handler)
    
    # Console handler: quiet by default so pipeline output stays readable.
    # Full INFO/DEBUG detail always goes to the log files above; the console
    # only shows warnings and errors unless verbosity is raised explicitly
    # (--verbose flag, RA_CONSOLE_LOG_LEVEL, or RA_DEBUG).
    console_handler = RichHandler(
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        markup=False,
    )
    console_handler.setLevel(_default_console_level())
    logger_instance.addHandler(console_handler)
    global _console_handler
    _console_handler = console_handler

    return logger_instance


_console_handler: logging.Handler | None = None


def _default_console_level() -> int:
    """Resolve the console log level from the environment."""
    override = os.environ.get("RA_CONSOLE_LOG_LEVEL", "").strip().upper()
    if override in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        return getattr(logging, override)
    if os.environ.get("RA_DEBUG", "").strip().lower() in {"1", "true", "yes"}:
        return logging.DEBUG
    return logging.WARNING


def set_console_log_level(level: int) -> None:
    """Change how much log detail reaches the console (files are unaffected)."""
    if _console_handler is not None:
        _console_handler.setLevel(level)


# Initialize the global logger instance
logger: ApplicationLogger = _setup_logger()
