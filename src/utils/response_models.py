# -*- coding: utf-8 -*-
"""Data models for graceful response handling.

This module defines the core data structures used throughout the graceful
model response handling system, including configuration models, result types,
and error classifications.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict


# Enums for error types and processing paths
class ErrorType(Enum):
    """Types of errors that can occur during response processing."""
    SYNTAX_ERROR = "syntax_error"
    SCHEMA_VALIDATION = "schema_validation"
    MISSING_FIELDS = "missing_fields"
    WRONG_TYPES = "wrong_types"
    EXTRACTION_FAILURE = "extraction_failure"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


class ProcessingPath(Enum):
    """Different paths through the response processing pipeline."""
    DIRECT_SUCCESS = "direct_success"
    RECOVERY_SUCCESS = "recovery_success"
    RETRY_SUCCESS = "retry_success"
    FALLBACK_SUCCESS = "fallback_success"
    CONTENT_ENHANCED_SUCCESS = "content_enhanced_success"
    COMPLETE_FAILURE = "complete_failure"


class RetryStrategy(Enum):
    """Retry strategies based on error classification."""
    SYNTAX_EMPHASIS = "syntax_emphasis"
    SCHEMA_EXAMPLE = "schema_example"
    TYPE_CLARIFICATION = "type_clarification"
    FORMAT_INSTRUCTION = "format_instruction"
    GENERIC_CLARIFICATION = "generic_clarification"


class RecoveryMethod(Enum):
    """Methods used for response recovery."""
    SYNTAX_REPAIR = "syntax_repair"
    PARTIAL_EXTRACTION = "partial_extraction"
    PATTERN_MATCHING = "pattern_matching"
    TYPE_COERCION = "type_coercion"
    ENHANCED_PATTERNS = "enhanced_patterns"
    FALLBACK_PROCESSING = "fallback_processing"


class ContentIssueType(Enum):
    """Types of content quality issues."""
    EMPTY_RESULTS = "empty_results"
    INSUFFICIENT_RESULTS = "insufficient_results"
    INCOMPLETE_ANALYSIS = "incomplete_analysis"
    LOW_RELEVANCE = "low_relevance"
    CONVERSATIONAL_RESPONSE = "conversational_response"


class IssueSeverity(Enum):
    """Severity levels for content issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnhancementStrategy(Enum):
    """Strategies for enhancing insufficient results."""
    BROADER_QUERY = "broader_query"
    QUERY_EXPANSION = "query_expansion"
    DETAILED_ANALYSIS = "detailed_analysis"
    RELEVANCE_FOCUS = "relevance_focus"


# Configuration models
@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    timeout_per_attempt: float = 30.0
    enabled_for_errors: Set[str] = field(default_factory=lambda: {
        "syntax", "schema", "field_type", "structure"
    })


@dataclass
class RecoveryConfig:
    """Configuration for recovery strategies."""
    enable_syntax_repair: bool = True
    enable_partial_extraction: bool = True
    enable_type_coercion: bool = True
    enable_pattern_matching: bool = True
    enable_enhanced_extraction: bool = True
    min_confidence_threshold: float = 0.6


@dataclass
class ContentQualityConfig:
    """Configuration for content quality validation."""
    min_expected_papers: int = 3
    min_relevance_threshold: float = 0.7
    enable_quality_validation: bool = True
    enable_result_enhancement: bool = True


@dataclass
class EnhancementConfig:
    """Configuration for result enhancement."""
    max_enhancement_attempts: int = 2
    enable_query_broadening: bool = True
    enable_query_expansion: bool = True
    enable_analysis_enhancement: bool = True


@dataclass
class QualityConfig:
    """Configuration for quality monitoring."""
    enable_monitoring: bool = True
    failure_threshold: float = 0.3
    alert_on_degradation: bool = True
    track_model_patterns: bool = True
    track_content_quality: bool = True


@dataclass
class ResponseHandlerConfig:
    """Main configuration for response handler behavior."""
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    recovery_config: RecoveryConfig = field(default_factory=RecoveryConfig)
    content_quality_config: ContentQualityConfig = field(default_factory=ContentQualityConfig)
    enhancement_config: EnhancementConfig = field(default_factory=EnhancementConfig)
    quality_config: QualityConfig = field(default_factory=QualityConfig)
    debug_mode: bool = False


# Request context and result models
@dataclass
class RequestContext:
    """Context information for request processing."""
    user_query: str
    model_name: str
    attempt_count: int = 0
    previous_errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str = ""


@dataclass
class ValidationResult:
    """Extended validation result with retry classification."""
    is_valid: bool
    error_message: str = ""
    error_type: str = ""
    show_raw_response: bool = True
    retry_strategy: Optional[RetryStrategy] = None


@dataclass
class RecoveryResult:
    """Result of recovery attempt."""
    success: bool
    recovered_data: Optional[Dict[str, Any]] = None
    recovery_method: Optional[RecoveryMethod] = None
    confidence_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    error_message: str = ""


@dataclass
class ProcessingResult:
    """Result of complete response processing."""
    success: bool
    data: Optional[Any] = None
    processing_path: ProcessingPath = ProcessingPath.COMPLETE_FAILURE
    quality_score: float = 0.0
    warnings: List[str] = field(default_factory=list)
    debug_info: Optional[Dict[str, Any]] = None


# Content quality models
@dataclass
class ContentIssue:
    """Represents a content quality issue."""
    type: ContentIssueType
    severity: IssueSeverity
    message: str
    suggestions: List[str] = field(default_factory=list)
    affected_papers: List[Any] = field(default_factory=list)


@dataclass
class ContentQualityResult:
    """Result of content quality validation."""
    has_issues: bool
    issues: List[ContentIssue] = field(default_factory=list)
    overall_quality_score: float = 1.0


@dataclass
class EnhancementAttempt:
    """Represents an enhancement attempt."""
    strategy: EnhancementStrategy
    enhanced_prompt: str
    reason: str


@dataclass
class EnhancementResult:
    """Result of enhancement attempts."""
    success: bool
    enhanced_report: Optional[Any] = None
    attempts_made: List[EnhancementAttempt] = field(default_factory=list)
    improvement_score: float = 0.0


# Quality monitoring models
@dataclass
class ResponseMetrics:
    """Metrics for response processing quality."""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    retry_attempts: int = 0
    recovery_attempts: int = 0
    content_quality_issues: int = 0
    enhancement_attempts: int = 0
    failures_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    failures_by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    success_by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    retries_by_error_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    content_issues_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    enhancement_success_by_strategy: Dict[str, int] = field(default_factory=lambda: defaultdict(int))


@dataclass
class QualityReport:
    """Quality report for monitoring."""
    success_rate: float
    total_attempts: int
    failure_breakdown: Dict[str, int]
    model_performance: Dict[str, int]
    content_quality_metrics: Dict[str, int] = field(default_factory=dict)
    enhancement_metrics: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


# Debug information model
@dataclass
class DebugInfo:
    """Debug information for troubleshooting."""
    original_response: str
    cleaned_response: str
    validation_details: Dict[str, Any]
    recovery_attempts: List[Dict[str, Any]]
    retry_history: List[Dict[str, Any]]
    content_quality_analysis: Dict[str, Any]
    enhancement_history: List[Dict[str, Any]]
    processing_time_ms: float