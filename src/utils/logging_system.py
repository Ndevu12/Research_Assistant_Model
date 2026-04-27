# -*- coding: utf-8 -*-
"""Reusable logging system for the AI Research Assistant.

This module provides a flexible, reusable logging system that can be used
throughout the application. It supports multiple log levels, structured logging,
file rotation, and configurable output formats.
"""

import json
import logging
import logging.handlers
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass, asdict


class LogLevel(Enum):
    """Log levels for the logging system."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Log output formats."""
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"
    STRUCTURED = "structured"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: str
    level: str
    logger_name: str
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    extra_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert log entry to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class LoggingConfig:
    """Configuration for the logging system."""
    # Basic settings
    name: str = "ai_research_assistant"
    level: LogLevel = LogLevel.INFO
    format_type: LogFormat = LogFormat.DETAILED
    
    # File logging
    enable_file_logging: bool = True
    log_directory: str = "logs"
    log_filename: Optional[str] = None  # Auto-generated if None
    max_file_size_mb: int = 10
    backup_count: int = 5
    
    # Console logging
    enable_console_logging: bool = True
    console_level: Optional[LogLevel] = None  # Uses main level if None
    
    # Structured logging
    enable_structured_logging: bool = False
    include_caller_info: bool = True
    
    # Custom fields
    default_extra_fields: Optional[Dict[str, Any]] = None


class StructuredLogger:
    """Reusable structured logger with multiple output options."""
    
    def __init__(self, config: LoggingConfig):
        """Initialize the structured logger.
        
        Args:
            config: Logging configuration
        """
        self.config = config
        self.logger = logging.getLogger(config.name)
        self.logger.setLevel(getattr(logging, config.level.value))
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        # Set up handlers
        self._setup_file_handler()
        self._setup_console_handler()
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def _setup_file_handler(self) -> None:
        """Set up file logging handler."""
        if not self.config.enable_file_logging:
            return
        
        # Create log directory
        log_dir = Path(self.config.log_directory)
        log_dir.mkdir(exist_ok=True)
        
        # Generate filename if not provided
        if self.config.log_filename:
            log_file = log_dir / self.config.log_filename
        else:
            timestamp = datetime.now().strftime("%Y%m%d")
            log_file = log_dir / f"{self.config.name}_{timestamp}.log"
        
        # Create rotating file handler
        max_bytes = self.config.max_file_size_mb * 1024 * 1024
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=self.config.backup_count
        )
        
        # Set formatter
        file_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(file_handler)
    
    def _setup_console_handler(self) -> None:
        """Set up console logging handler."""
        if not self.config.enable_console_logging:
            return
        
        console_handler = logging.StreamHandler()
        
        # Set console-specific level if provided
        if self.config.console_level:
            console_handler.setLevel(getattr(logging, self.config.console_level.value))
        
        # Set formatter
        console_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(console_handler)
    
    def _get_formatter(self) -> logging.Formatter:
        """Get appropriate formatter based on configuration."""
        if self.config.format_type == LogFormat.SIMPLE:
            return logging.Formatter('%(levelname)s - %(message)s')
        
        elif self.config.format_type == LogFormat.DETAILED:
            return logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        elif self.config.format_type == LogFormat.JSON:
            return JsonFormatter()
        
        elif self.config.format_type == LogFormat.STRUCTURED:
            return StructuredFormatter(include_caller=self.config.include_caller_info)
        
        else:
            return logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    def _create_log_entry(
        self, 
        level: str, 
        message: str, 
        extra_data: Optional[Dict[str, Any]] = None
    ) -> LogEntry:
        """Create structured log entry."""
        # Get caller information if enabled
        caller_info = {}
        if self.config.include_caller_info:
            import inspect
            frame = inspect.currentframe()
            try:
                # Go up the stack to find the actual caller
                caller_frame = frame.f_back.f_back.f_back
                if caller_frame:
                    caller_info = {
                        'module': caller_frame.f_globals.get('__name__'),
                        'function': caller_frame.f_code.co_name,
                        'line_number': caller_frame.f_lineno
                    }
            finally:
                del frame
        
        # Merge extra data
        merged_extra = {}
        if self.config.default_extra_fields:
            merged_extra.update(self.config.default_extra_fields)
        if extra_data:
            merged_extra.update(extra_data)
        
        return LogEntry(
            timestamp=datetime.now().isoformat(),
            level=level,
            logger_name=self.config.name,
            message=message,
            module=caller_info.get('module'),
            function=caller_info.get('function'),
            line_number=caller_info.get('line_number'),
            extra_data=merged_extra if merged_extra else None
        )
    
    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        if self.config.enable_structured_logging:
            entry = self._create_log_entry("DEBUG", message, extra_data)
            self.logger.debug(entry.to_json() if self.config.format_type == LogFormat.JSON else message)
        else:
            self.logger.debug(message)
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        if self.config.enable_structured_logging:
            entry = self._create_log_entry("INFO", message, extra_data)
            self.logger.info(entry.to_json() if self.config.format_type == LogFormat.JSON else message)
        else:
            self.logger.info(message)
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        if self.config.enable_structured_logging:
            entry = self._create_log_entry("WARNING", message, extra_data)
            self.logger.warning(entry.to_json() if self.config.format_type == LogFormat.JSON else message)
        else:
            self.logger.warning(message)
    
    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log error message."""
        if self.config.enable_structured_logging:
            entry = self._create_log_entry("ERROR", message, extra_data)
            self.logger.error(entry.to_json() if self.config.format_type == LogFormat.JSON else message)
        else:
            self.logger.error(message)
    
    def critical(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message."""
        if self.config.enable_structured_logging:
            entry = self._create_log_entry("CRITICAL", message, extra_data)
            self.logger.critical(entry.to_json() if self.config.format_type == LogFormat.JSON else message)
        else:
            self.logger.critical(message)
    
    def log_event(
        self, 
        event_type: str, 
        message: str, 
        level: LogLevel = LogLevel.INFO,
        **kwargs
    ) -> None:
        """Log a structured event with additional context.
        
        Args:
            event_type: Type of event (e.g., 'user_action', 'system_event')
            message: Event message
            level: Log level
            **kwargs: Additional event data
        """
        extra_data = {
            'event_type': event_type,
            **kwargs
        }
        
        log_method = getattr(self, level.value.lower())
        log_method(message, extra_data)
    
    def log_performance(
        self, 
        operation: str, 
        duration_ms: float, 
        success: bool = True,
        **kwargs
    ) -> None:
        """Log performance metrics.
        
        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether operation was successful
            **kwargs: Additional performance data
        """
        extra_data = {
            'event_type': 'performance',
            'operation': operation,
            'duration_ms': duration_ms,
            'success': success,
            **kwargs
        }
        
        message = f"Operation '{operation}' {'succeeded' if success else 'failed'} in {duration_ms:.2f}ms"
        self.info(message, extra_data)
    
    def log_user_action(
        self, 
        action: str, 
        user_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log user actions.
        
        Args:
            action: User action description
            user_id: Optional user identifier
            **kwargs: Additional action data
        """
        extra_data = {
            'event_type': 'user_action',
            'action': action,
            'user_id': user_id,
            **kwargs
        }
        
        message = f"User action: {action}"
        self.info(message, extra_data)
    
    def log_system_event(
        self, 
        event: str, 
        component: Optional[str] = None,
        **kwargs
    ) -> None:
        """Log system events.
        
        Args:
            event: System event description
            component: Component that generated the event
            **kwargs: Additional event data
        """
        extra_data = {
            'event_type': 'system_event',
            'event': event,
            'component': component,
            **kwargs
        }
        
        message = f"System event: {event}"
        if component:
            message += f" (component: {component})"
        
        self.info(message, extra_data)


class JsonFormatter(logging.Formatter):
    """JSON formatter for log records."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add any extra fields
        if hasattr(record, 'extra_data') and record.extra_data:
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, default=str)


class StructuredFormatter(logging.Formatter):
    """Structured formatter for log records."""
    
    def __init__(self, include_caller: bool = True):
        """Initialize structured formatter.
        
        Args:
            include_caller: Whether to include caller information
        """
        self.include_caller = include_caller
        super().__init__()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with structure."""
        parts = [
            f"[{datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')}]",
            f"[{record.levelname}]",
            f"[{record.name}]"
        ]
        
        if self.include_caller:
            parts.append(f"[{record.module}.{record.funcName}:{record.lineno}]")
        
        parts.append(record.getMessage())
        
        return " ".join(parts)


# Factory functions for common logger configurations
def create_application_logger(
    name: str = "ai_research_assistant",
    level: LogLevel = LogLevel.INFO,
    log_directory: str = "logs"
) -> StructuredLogger:
    """Create a standard application logger.
    
    Args:
        name: Logger name
        level: Log level
        log_directory: Directory for log files
        
    Returns:
        StructuredLogger: Configured logger
    """
    config = LoggingConfig(
        name=name,
        level=level,
        format_type=LogFormat.DETAILED,
        log_directory=log_directory,
        enable_structured_logging=False
    )
    return StructuredLogger(config)


def create_performance_logger(
    name: str = "performance",
    log_directory: str = "logs"
) -> StructuredLogger:
    """Create a performance-focused logger.
    
    Args:
        name: Logger name
        log_directory: Directory for log files
        
    Returns:
        StructuredLogger: Configured performance logger
    """
    config = LoggingConfig(
        name=name,
        level=LogLevel.INFO,
        format_type=LogFormat.JSON,
        log_directory=log_directory,
        enable_structured_logging=True,
        enable_console_logging=False,  # Performance logs typically go to file only
        default_extra_fields={'logger_type': 'performance'}
    )
    return StructuredLogger(config)


def create_debug_logger(
    name: str = "debug",
    log_directory: str = "logs"
) -> StructuredLogger:
    """Create a debug-focused logger.
    
    Args:
        name: Logger name
        log_directory: Directory for log files
        
    Returns:
        StructuredLogger: Configured debug logger
    """
    config = LoggingConfig(
        name=name,
        level=LogLevel.DEBUG,
        format_type=LogFormat.STRUCTURED,
        log_directory=log_directory,
        enable_structured_logging=True,
        include_caller_info=True,
        console_level=LogLevel.WARNING  # Only show warnings+ on console
    )
    return StructuredLogger(config)


def create_audit_logger(
    name: str = "audit",
    log_directory: str = "logs"
) -> StructuredLogger:
    """Create an audit-focused logger for tracking user actions and system events.
    
    Args:
        name: Logger name
        log_directory: Directory for log files
        
    Returns:
        StructuredLogger: Configured audit logger
    """
    config = LoggingConfig(
        name=name,
        level=LogLevel.INFO,
        format_type=LogFormat.JSON,
        log_directory=log_directory,
        enable_structured_logging=True,
        enable_console_logging=False,  # Audit logs typically go to file only
        default_extra_fields={'logger_type': 'audit'}
    )
    return StructuredLogger(config)


# Global logger instances (lazy-loaded)
_application_logger: Optional[StructuredLogger] = None
_performance_logger: Optional[StructuredLogger] = None
_debug_logger: Optional[StructuredLogger] = None
_audit_logger: Optional[StructuredLogger] = None


def get_application_logger() -> StructuredLogger:
    """Get the global application logger."""
    global _application_logger
    if _application_logger is None:
        _application_logger = create_application_logger()
    return _application_logger


def get_performance_logger() -> StructuredLogger:
    """Get the global performance logger."""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = create_performance_logger()
    return _performance_logger


def get_debug_logger() -> StructuredLogger:
    """Get the global debug logger."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = create_debug_logger()
    return _debug_logger


def get_audit_logger() -> StructuredLogger:
    """Get the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = create_audit_logger()
    return _audit_logger