# -*- coding: utf-8 -*-
"""Quality alerting and reporting system.

This module provides advanced quality reporting and alerting mechanisms
that can notify administrators of quality degradation and provide detailed
analysis of system performance patterns.
"""

import smtplib
from datetime import datetime, timedelta
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
from pathlib import Path
from typing import Dict, List, Optional, Callable

from .response_models import QualityReport, QualityConfig
from .quality_monitor import QualityMonitor


class QualityAlerter:
    """Advanced quality alerting system."""
    
    def __init__(self, config: QualityConfig, quality_monitor: QualityMonitor):
        """Initialize quality alerter.
        
        Args:
            config: Quality configuration
            quality_monitor: Quality monitor instance
        """
        self.config = config
        self.quality_monitor = quality_monitor
        self.alert_handlers: List[Callable[[QualityReport], None]] = []
        self.last_alert_time: Optional[datetime] = None
        self.alert_cooldown_minutes = 30  # Prevent spam alerts
        
    def add_alert_handler(self, handler: Callable[[QualityReport], None]) -> None:
        """Add custom alert handler.
        
        Args:
            handler: Function that takes QualityReport and handles the alert
        """
        self.alert_handlers.append(handler)
    
    def check_and_alert(self) -> bool:
        """Check quality metrics and trigger alerts if needed.
        
        Returns:
            bool: True if alert was triggered
        """
        if not self.config.alert_on_degradation:
            return False
            
        # Check cooldown period
        if self._is_in_cooldown():
            return False
            
        report = self.quality_monitor.get_quality_report()
        
        # Check various quality thresholds
        alerts_triggered = []
        
        # Overall success rate alert
        if report.success_rate < (1.0 - self.config.failure_threshold):
            alerts_triggered.append(f"Low success rate: {report.success_rate:.1%}")
        
        # High retry rate alert
        if report.total_attempts > 0:
            retry_rate = self.quality_monitor.metrics.retry_attempts / report.total_attempts
            if retry_rate > 0.5:  # More than 50% of requests need retries
                alerts_triggered.append(f"High retry rate: {retry_rate:.1%}")
        
        # Content quality issues alert
        if self.config.track_content_quality and "total_content_issues" in report.content_quality_metrics:
            content_issue_rate = report.content_quality_metrics["content_issue_rate"]
            if content_issue_rate > 0.3:  # More than 30% of requests have content issues
                alerts_triggered.append(f"High content issue rate: {content_issue_rate:.1%}")
        
        # Model-specific performance alerts
        model_alerts = self._check_model_performance(report)
        alerts_triggered.extend(model_alerts)
        
        # Trigger alerts if any issues found
        if alerts_triggered:
            self._trigger_alerts(report, alerts_triggered)
            self.last_alert_time = datetime.now()
            return True
            
        return False
    
    def _is_in_cooldown(self) -> bool:
        """Check if we're in alert cooldown period."""
        if self.last_alert_time is None:
            return False
            
        cooldown_end = self.last_alert_time + timedelta(minutes=self.alert_cooldown_minutes)
        return datetime.now() < cooldown_end
    
    def _check_model_performance(self, report: QualityReport) -> List[str]:
        """Check for model-specific performance issues.
        
        Args:
            report: Quality report
            
        Returns:
            List[str]: List of model performance alerts
        """
        alerts = []
        model_performance = self.quality_monitor.get_model_performance_summary()
        
        for model_name, metrics in model_performance.items():
            if metrics["total_attempts"] >= 5:  # Only alert for models with sufficient data
                if metrics["success_rate"] < 0.5:  # Less than 50% success rate
                    alerts.append(f"Model {model_name} low success rate: {metrics['success_rate']:.1%}")
        
        return alerts
    
    def _trigger_alerts(self, report: QualityReport, alerts: List[str]) -> None:
        """Trigger all configured alert handlers.
        
        Args:
            report: Quality report
            alerts: List of alert messages
        """
        # Add alert summary to report
        alert_summary = {
            "timestamp": datetime.now().isoformat(),
            "alerts": alerts,
            "report": report
        }
        
        # Call all registered handlers
        for handler in self.alert_handlers:
            try:
                handler(report)
            except Exception as e:
                # Log error but don't let one handler failure stop others
                print(f"Alert handler failed: {e}")
        
        # Default console alert if no handlers registered
        if not self.alert_handlers:
            self._console_alert(alerts, report)
    
    def _console_alert(self, alerts: List[str], report: QualityReport) -> None:
        """Default console alert handler.
        
        Args:
            alerts: List of alert messages
            report: Quality report
        """
        print("\n" + "="*60)
        print("🚨 QUALITY ALERT")
        print("="*60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Overall Success Rate: {report.success_rate:.1%}")
        print(f"Total Attempts: {report.total_attempts}")
        print("\nIssues Detected:")
        for alert in alerts:
            print(f"  • {alert}")
        print("="*60)


class QualityReporter:
    """Advanced quality reporting system."""
    
    def __init__(self, quality_monitor: QualityMonitor):
        """Initialize quality reporter.
        
        Args:
            quality_monitor: Quality monitor instance
        """
        self.quality_monitor = quality_monitor
    
    def generate_detailed_report(self) -> str:
        """Generate detailed quality report.
        
        Returns:
            str: Formatted detailed report
        """
        report = self.quality_monitor.get_quality_report()
        model_performance = self.quality_monitor.get_model_performance_summary()
        
        lines = []
        lines.append("="*80)
        lines.append("QUALITY REPORT")
        lines.append("="*80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Overall metrics
        lines.append("OVERALL PERFORMANCE")
        lines.append("-" * 40)
        lines.append(f"Success Rate: {report.success_rate:.1%}")
        lines.append(f"Total Attempts: {report.total_attempts}")
        lines.append(f"Successful: {self.quality_monitor.metrics.successful_attempts}")
        lines.append(f"Failed: {self.quality_monitor.metrics.failed_attempts}")
        lines.append(f"Retry Attempts: {self.quality_monitor.metrics.retry_attempts}")
        lines.append(f"Recovery Attempts: {self.quality_monitor.metrics.recovery_attempts}")
        lines.append("")
        
        # Failure breakdown
        if report.failure_breakdown:
            lines.append("FAILURE BREAKDOWN")
            lines.append("-" * 40)
            for error_type, count in sorted(report.failure_breakdown.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / max(report.total_attempts, 1)) * 100
                lines.append(f"{error_type}: {count} ({percentage:.1f}%)")
            lines.append("")
        
        # Model performance
        if model_performance:
            lines.append("MODEL PERFORMANCE")
            lines.append("-" * 40)
            for model_name, metrics in model_performance.items():
                lines.append(f"{model_name}:")
                lines.append(f"  Success Rate: {metrics['success_rate']:.1%}")
                lines.append(f"  Total Attempts: {metrics['total_attempts']}")
                lines.append(f"  Successes: {metrics['successes']}")
                lines.append(f"  Failures: {metrics['failures']}")
            lines.append("")
        
        # Content quality metrics
        if report.content_quality_metrics:
            lines.append("CONTENT QUALITY")
            lines.append("-" * 40)
            cq_metrics = report.content_quality_metrics
            lines.append(f"Total Content Issues: {cq_metrics.get('total_content_issues', 0)}")
            lines.append(f"Content Issue Rate: {cq_metrics.get('content_issue_rate', 0):.1%}")
            
            if "issues_by_type" in cq_metrics:
                lines.append("Issues by Type:")
                for issue_type, count in cq_metrics["issues_by_type"].items():
                    lines.append(f"  {issue_type}: {count}")
            lines.append("")
        
        # Enhancement metrics
        if report.enhancement_metrics:
            lines.append("ENHANCEMENT PERFORMANCE")
            lines.append("-" * 40)
            enh_metrics = report.enhancement_metrics
            lines.append(f"Enhancement Attempts: {enh_metrics.get('total_enhancement_attempts', 0)}")
            lines.append(f"Enhancement Rate: {enh_metrics.get('enhancement_rate', 0):.1%}")
            
            if "success_by_strategy" in enh_metrics:
                lines.append("Success by Strategy:")
                for strategy, count in enh_metrics["success_by_strategy"].items():
                    lines.append(f"  {strategy}: {count}")
            lines.append("")
        
        lines.append("="*80)
        
        return "\n".join(lines)
    
    def generate_summary_report(self) -> str:
        """Generate concise summary report.
        
        Returns:
            str: Formatted summary report
        """
        report = self.quality_monitor.get_quality_report()
        
        summary_lines = [
            f"Quality Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
            f"Success Rate: {report.success_rate:.1%} ({self.quality_monitor.metrics.successful_attempts}/{report.total_attempts})",
            f"Retries: {self.quality_monitor.metrics.retry_attempts}",
            f"Content Issues: {self.quality_monitor.metrics.content_quality_issues}",
            f"Enhancements: {self.quality_monitor.metrics.enhancement_attempts}"
        ]
        
        return " | ".join(summary_lines)
    
    def save_report(self, filepath: Optional[Path] = None, detailed: bool = True) -> Path:
        """Save quality report to file.
        
        Args:
            filepath: Optional path for report file
            detailed: Whether to generate detailed or summary report
            
        Returns:
            Path: Path to saved report
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_type = "detailed" if detailed else "summary"
            filepath = Path(f"logs/quality_report_{report_type}_{timestamp}.txt")
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate and save report
        if detailed:
            content = self.generate_detailed_report()
        else:
            content = self.generate_summary_report()
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return filepath


def setup_default_alerting(quality_monitor: QualityMonitor, config: QualityConfig) -> QualityAlerter:
    """Set up default alerting configuration.
    
    Args:
        quality_monitor: Quality monitor instance
        config: Quality configuration
        
    Returns:
        QualityAlerter: Configured alerter
    """
    alerter = QualityAlerter(config, quality_monitor)
    
    # Add default console alert handler
    def console_handler(report: QualityReport) -> None:
        print(f"\n🚨 Quality Alert: Success rate dropped to {report.success_rate:.1%}")
    
    alerter.add_alert_handler(console_handler)
    
    return alerter