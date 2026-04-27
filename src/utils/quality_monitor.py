# -*- coding: utf-8 -*-
"""Quality monitoring for response processing.

This module provides quality monitoring capabilities that track response
processing patterns, success rates, and failure modes. It focuses purely
on metrics collection and analysis, with optional integration with external
logging systems.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from .response_models import (
    QualityConfig, RequestContext, ResponseMetrics, QualityReport,
    ContentIssue, EnhancementResult, ProcessingPath
)


class QualityMonitor:
    """Monitor response quality patterns and collect metrics."""
    
    def __init__(self, config: Optional[QualityConfig] = None):
        """Initialize quality monitor with configuration.
        
        Args:
            config: Quality monitoring configuration
        """
        self.config = config or QualityConfig()
        self.metrics = ResponseMetrics()
        
        # Optional external logger integration
        self._external_logger: Optional[Callable[[str, Dict[str, Any]], None]] = None
        
        # Event listeners for external integration
        self._event_listeners: List[Callable[[str, Dict[str, Any]], None]] = []
    
    def set_external_logger(self, logger_func: Callable[[str, Dict[str, Any]], None]) -> None:
        """Set external logger function for integration.
        
        Args:
            logger_func: Function that takes (message, extra_data) and logs it
        """
        self._external_logger = logger_func
    
    def add_event_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add event listener for quality events.
        
        Args:
            listener: Function that receives quality events
        """
        self._event_listeners.append(listener)
    
    def _emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit quality event to listeners and logger.
        
        Args:
            event_type: Type of quality event
            data: Event data
        """
        event_data = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            **data
        }
        
        # Send to external logger if configured
        if self._external_logger:
            message = f"Quality event: {event_type}"
            self._external_logger(message, event_data)
        
        # Send to event listeners
        for listener in self._event_listeners:
            try:
                listener(event_type, event_data)
            except Exception:
                # Don't let listener failures affect monitoring
                pass
    
    def record_success(self, context: RequestContext, processing_path: ProcessingPath = ProcessingPath.DIRECT_SUCCESS) -> None:
        """Record successful response processing.
        
        Args:
            context: Request context information
            processing_path: How the success was achieved
        """
        if not self.config.enable_monitoring:
            return
            
        self.metrics.total_attempts += 1
        self.metrics.successful_attempts += 1
        self.metrics.success_by_model[context.model_name] += 1
        
        # Emit success event
        self._emit_event('success', {
            'model': context.model_name,
            'processing_path': processing_path.value,
            'attempt_count': context.attempt_count + 1,
            'query_length': len(context.user_query),
            'session_id': context.session_id
        })
    
    def record_failure(
        self, 
        context: RequestContext, 
        error_type: str, 
        recovery_attempted: bool = False,
        final_failure: bool = True
    ) -> None:
        """Record failed response processing.
        
        Args:
            context: Request context information
            error_type: Type of error that occurred
            recovery_attempted: Whether recovery was attempted
            final_failure: Whether this is the final failure (after all retries)
        """
        if not self.config.enable_monitoring:
            return
            
        if final_failure:
            self.metrics.total_attempts += 1
            self.metrics.failed_attempts += 1
            self.metrics.failures_by_model[context.model_name] += 1
        
        self.metrics.failures_by_type[error_type] += 1
        
        if recovery_attempted:
            self.metrics.recovery_attempts += 1
        
        # Emit failure event
        self._emit_event('failure', {
            'model': context.model_name,
            'error_type': error_type,
            'recovery_attempted': recovery_attempted,
            'final_failure': final_failure,
            'attempt_count': context.attempt_count + 1,
            'session_id': context.session_id
        })
    
    def record_retry(self, context: RequestContext, error_type: str) -> None:
        """Record retry attempt.
        
        Args:
            context: Request context information
            error_type: Type of error that triggered retry
        """
        if not self.config.enable_monitoring:
            return
            
        self.metrics.retry_attempts += 1
        self.metrics.retries_by_error_type[error_type] += 1
        
        # Emit retry event
        self._emit_event('retry', {
            'model': context.model_name,
            'error_type': error_type,
            'attempt_count': context.attempt_count + 1,
            'session_id': context.session_id
        })
    
    def record_content_quality_issue(
        self, 
        context: RequestContext, 
        issues: List[ContentIssue]
    ) -> None:
        """Record content quality issues.
        
        Args:
            context: Request context information
            issues: List of content quality issues detected
        """
        if not self.config.enable_monitoring or not self.config.track_content_quality:
            return
            
        self.metrics.content_quality_issues += len(issues)
        
        for issue in issues:
            self.metrics.content_issues_by_type[issue.type.value] += 1
        
        # Emit content quality event
        issue_types = [issue.type.value for issue in issues]
        self._emit_event('content_quality_issues', {
            'model': context.model_name,
            'issue_types': issue_types,
            'issue_count': len(issues),
            'session_id': context.session_id
        })
    
    def record_enhancement_attempt(
        self, 
        context: RequestContext, 
        enhancement_result: EnhancementResult
    ) -> None:
        """Record result enhancement attempt.
        
        Args:
            context: Request context information
            enhancement_result: Result of enhancement attempt
        """
        if not self.config.enable_monitoring:
            return
            
        self.metrics.enhancement_attempts += 1
        
        for attempt in enhancement_result.attempts_made:
            strategy = attempt.strategy.value
            if enhancement_result.success:
                self.metrics.enhancement_success_by_strategy[strategy] += 1
        
        # Emit enhancement event
        strategies = [a.strategy.value for a in enhancement_result.attempts_made]
        self._emit_event('enhancement_attempt', {
            'model': context.model_name,
            'success': enhancement_result.success,
            'strategies': strategies,
            'improvement_score': enhancement_result.improvement_score,
            'session_id': context.session_id
        })
    
    def get_quality_report(self) -> QualityReport:
        """Generate quality report for monitoring.
        
        Returns:
            QualityReport: Current quality metrics and analysis
        """
        success_rate = (
            self.metrics.successful_attempts / max(self.metrics.total_attempts, 1)
        )
        
        content_quality_metrics = {}
        if self.config.track_content_quality:
            total_content_issues = sum(self.metrics.content_issues_by_type.values())
            content_quality_metrics = {
                "total_content_issues": total_content_issues,
                "content_issue_rate": total_content_issues / max(self.metrics.total_attempts, 1),
                "issues_by_type": dict(self.metrics.content_issues_by_type)
            }
        
        enhancement_metrics = {
            "total_enhancement_attempts": self.metrics.enhancement_attempts,
            "enhancement_rate": self.metrics.enhancement_attempts / max(self.metrics.total_attempts, 1),
            "success_by_strategy": dict(self.metrics.enhancement_success_by_strategy)
        }
        
        return QualityReport(
            success_rate=success_rate,
            total_attempts=self.metrics.total_attempts,
            failure_breakdown=dict(self.metrics.failures_by_type),
            model_performance=dict(self.metrics.success_by_model),
            content_quality_metrics=content_quality_metrics,
            enhancement_metrics=enhancement_metrics
        )
    
    def check_quality_degradation(self) -> bool:
        """Check if quality has degraded below threshold.
        
        Returns:
            bool: True if quality degradation detected
        """
        if not self.config.alert_on_degradation:
            return False
            
        report = self.get_quality_report()
        
        # Check overall success rate
        if report.success_rate < (1.0 - self.config.failure_threshold):
            self._emit_event('quality_degradation', {
                'success_rate': report.success_rate,
                'threshold': 1.0 - self.config.failure_threshold,
                'total_attempts': report.total_attempts
            })
            return True
        
        return False
    
    def get_model_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Get performance summary by model.
        
        Returns:
            Dict: Performance metrics by model name
        """
        summary = {}
        
        for model_name in self.metrics.success_by_model.keys():
            successes = self.metrics.success_by_model[model_name]
            failures = self.metrics.failures_by_model.get(model_name, 0)
            total = successes + failures
            
            if total > 0:
                summary[model_name] = {
                    "success_rate": successes / total,
                    "total_attempts": total,
                    "successes": successes,
                    "failures": failures
                }
        
        return summary
    
    def export_metrics(self, filepath: Optional[Path] = None) -> Path:
        """Export metrics to JSON file.
        
        Args:
            filepath: Optional path for export file
            
        Returns:
            Path: Path to exported file
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(f"logs/quality_metrics_{timestamp}.json")
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare export data
        export_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "total_attempts": self.metrics.total_attempts,
                "successful_attempts": self.metrics.successful_attempts,
                "failed_attempts": self.metrics.failed_attempts,
                "retry_attempts": self.metrics.retry_attempts,
                "recovery_attempts": self.metrics.recovery_attempts,
                "content_quality_issues": self.metrics.content_quality_issues,
                "enhancement_attempts": self.metrics.enhancement_attempts,
                "failures_by_type": dict(self.metrics.failures_by_type),
                "failures_by_model": dict(self.metrics.failures_by_model),
                "success_by_model": dict(self.metrics.success_by_model),
                "retries_by_error_type": dict(self.metrics.retries_by_error_type),
                "content_issues_by_type": dict(self.metrics.content_issues_by_type),
                "enhancement_success_by_strategy": dict(self.metrics.enhancement_success_by_strategy)
            },
            "quality_report": self.get_quality_report().__dict__,
            "model_performance": self.get_model_performance_summary()
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        # Emit export event
        self._emit_event('metrics_exported', {
            'filepath': str(filepath),
            'total_attempts': self.metrics.total_attempts
        })
        
        return filepath
    
    def reset_metrics(self) -> None:
        """Reset all metrics to initial state."""
        self.metrics = ResponseMetrics()
        self._emit_event('metrics_reset', {})
    
    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is enabled.
        
        Returns:
            bool: True if monitoring is enabled
        """
        return self.config.enable_monitoring
    
    def get_current_metrics(self) -> ResponseMetrics:
        """Get current metrics object.
        
        Returns:
            ResponseMetrics: Current metrics
        """
        return self.metrics
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics.
        
        Returns:
            Dict: Summary of key metrics
        """
        total = max(self.metrics.total_attempts, 1)
        
        return {
            'total_attempts': self.metrics.total_attempts,
            'success_rate': self.metrics.successful_attempts / total,
            'failure_rate': self.metrics.failed_attempts / total,
            'retry_rate': self.metrics.retry_attempts / total,
            'recovery_rate': self.metrics.recovery_attempts / total,
            'content_issue_rate': self.metrics.content_quality_issues / total,
            'enhancement_rate': self.metrics.enhancement_attempts / total,
            'top_failure_types': dict(sorted(
                self.metrics.failures_by_type.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]),
            'model_count': len(self.metrics.success_by_model)
        }