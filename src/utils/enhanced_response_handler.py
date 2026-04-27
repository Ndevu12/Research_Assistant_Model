# -*- coding: utf-8 -*-
"""Enhanced response handler for graceful model response processing.

This module implements the main EnhancedResponseHandler that wraps existing
validation and recovery logic with retry capabilities, quality monitoring,
and content quality validation.
"""

import asyncio
import json
import time
from typing import Optional, Any

from pydantic_ai import Agent

from .response_models import (
    ResponseHandlerConfig, RequestContext, ProcessingResult, ProcessingPath,
    ValidationResult, RecoveryResult, ContentQualityResult
)
from .retry_manager import RetryManager
from .quality_monitor import QualityMonitor
from .enhanced_validation import enhance_validation_result, should_attempt_retry, get_enhanced_prompt_for_retry, _enhanced_partial_recovery
from .message_formatter import MessageFormatter
from .logging_system import get_application_logger, StructuredLogger
from .model_adaptation import get_adaptation_engine


class EnhancedResponseHandler:
    """Enhanced wrapper around existing response processing with retry capabilities."""
    
    def __init__(self, config: Optional[ResponseHandlerConfig] = None):
        """Initialize enhanced response handler.
        
        Args:
            config: Configuration for response handling behavior
        """
        self.config = config or ResponseHandlerConfig()
        self.retry_manager = RetryManager(self.config.retry_config)
        self.quality_monitor = QualityMonitor(self.config.quality_config)
        self.adaptation_engine = get_adaptation_engine()
        
        # Set up logging integration
        self.logger = get_application_logger()
        
        # Integrate quality monitor with logging system
        def log_quality_event(message: str, extra_data: dict) -> None:
            """Log quality events through the logging system."""
            self.logger.log_event(
                event_type='quality_monitoring',
                message=message,
                **extra_data
            )
        
        self.quality_monitor.set_external_logger(log_quality_event)
        
        # Import content quality components if enabled
        self.content_validator = None
        self.enhancement_engine = None
        
        if self.config.content_quality_config.enable_quality_validation:
            try:
                from .content_quality import ContentQualityValidator, ResultEnhancementEngine
                self.content_validator = ContentQualityValidator(self.config.content_quality_config)
                if self.config.content_quality_config.enable_result_enhancement:
                    self.enhancement_engine = ResultEnhancementEngine(self.config.enhancement_config)
            except ImportError:
                # Content quality components not yet implemented, continue without them
                pass
    
    async def process_response_with_retries(
        self, 
        analysis_agent: Agent,
        prompt: str,
        context: RequestContext
    ) -> ProcessingResult:
        """Process response with retry logic around existing validation.
        
        Args:
            analysis_agent: The AI agent to use for processing
            prompt: The prompt to send to the agent
            context: Request context information
            
        Returns:
            ProcessingResult: Result of processing with success/failure status
        """
        start_time = time.time()
        debug_info = {
            "original_prompt": prompt,
            "retry_attempts": [],
            "validation_history": [],
            "recovery_attempts": [],
            "content_quality_issues": []
        } if self.config.debug_mode else None
        
        # Log the start of processing
        self.logger.log_performance(
            operation="response_processing_start",
            duration_ms=0,
            success=True,
            user_query_length=len(context.user_query),
            model_name=context.model_name,
            session_id=context.session_id
        )
        
        # Import necessary functions from orchestrator
        from ..retrieval.orchestrator import (
            _extract_and_clean_json, _validate_json_structure, 
            _enhance_validation_with_retry_strategy, _enhanced_partial_recovery
        )
        from ..retrieval.models import ResearchReport
        
        current_prompt = prompt
        
        for attempt in range(self.retry_manager.config.max_retries + 1):
            try:
                # Update context for this attempt
                attempt_context = RequestContext(
                    user_query=context.user_query,
                    model_name=context.model_name,
                    attempt_count=attempt,
                    previous_errors=context.previous_errors.copy(),
                    timestamp=context.timestamp,
                    session_id=context.session_id
                )
                
                # Add retry delay if this is a retry attempt
                if attempt > 0:
                    delay = await self.retry_manager.get_retry_delay(attempt)
                    if delay > 0:
                        self.logger.info(
                            f"Applying retry delay of {delay}s before attempt {attempt + 1}",
                            extra_data={
                                'retry_attempt': attempt + 1,
                                'delay_seconds': delay,
                                'session_id': context.session_id
                            }
                        )
                        await asyncio.sleep(delay)
                
                # Enhance prompt with model-specific adjustments on first attempt
                if attempt == 0:
                    current_prompt = self.adaptation_engine.enhance_prompt_for_model(current_prompt, attempt_context)
                
                # Use existing agent execution
                result = await analysis_agent.run(current_prompt)
                raw_output = result.output
                
                if debug_info:
                    debug_info["retry_attempts"].append({
                        "attempt": attempt,
                        "prompt": current_prompt,
                        "raw_response": raw_output[:500] + "..." if len(raw_output) > 500 else raw_output
                    })
                
                # Apply model adaptation preprocessing
                adaptation_result = self.adaptation_engine.preprocess_response(raw_output, attempt_context)
                if adaptation_result.success:
                    raw_output = adaptation_result.adapted_response
                    self.logger.debug(
                        f"Applied model adaptation for {adaptation_result.model_type.value}",
                        extra_data={
                            'model_type': adaptation_result.model_type.value,
                            'adaptations': [a.value for a in adaptation_result.adaptations_applied],
                            'confidence': adaptation_result.confidence_score
                        }
                    )
                
                # Use existing extraction and validation
                try:
                    clean_json = _extract_and_clean_json(raw_output)
                    parsed = json.loads(clean_json)
                    
                    # Use existing validation with enhancement
                    validation_result = _validate_json_structure(parsed)
                    enhanced_validation = _enhance_validation_with_retry_strategy(validation_result)
                    
                    if debug_info:
                        debug_info["validation_history"].append({
                            "attempt": attempt,
                            "is_valid": enhanced_validation.is_valid,
                            "error_type": enhanced_validation.error_type,
                            "retry_strategy": enhanced_validation.retry_strategy.value if enhanced_validation.retry_strategy else None
                        })
                    
                    if enhanced_validation.is_valid:
                        # Success path - use existing ResearchReport validation
                        try:
                            report = ResearchReport.model_validate(parsed)
                            
                            # Check content quality if enabled
                            content_quality_result = None
                            if self.content_validator:
                                content_quality_result = self.content_validator.validate_content_quality(
                                    report, context.user_query
                                )
                                
                                if debug_info and content_quality_result.has_issues:
                                    debug_info["content_quality_issues"].extend([
                                        {"type": issue.type.value, "message": issue.message}
                                        for issue in content_quality_result.issues
                                    ])
                                
                                # Record content quality issues
                                if content_quality_result.has_issues:
                                    self.quality_monitor.record_content_quality_issue(
                                        attempt_context, content_quality_result.issues
                                    )
                                
                                # Attempt enhancement if needed and enabled
                                if (content_quality_result.has_issues and 
                                    self.enhancement_engine and 
                                    attempt < self.retry_manager.config.max_retries):
                                    
                                    enhancement_result = await self.enhancement_engine.enhance_insufficient_results(
                                        report, content_quality_result.issues, analysis_agent, current_prompt
                                    )
                                    
                                    self.quality_monitor.record_enhancement_attempt(
                                        attempt_context, enhancement_result
                                    )
                                    
                                    if enhancement_result.success:
                                        report = enhancement_result.enhanced_report
                                        self.quality_monitor.record_success(
                                            attempt_context, ProcessingPath.CONTENT_ENHANCED_SUCCESS
                                        )
                                        
                                        return ProcessingResult(
                                            success=True,
                                            data=report,
                                            processing_path=ProcessingPath.CONTENT_ENHANCED_SUCCESS,
                                            quality_score=content_quality_result.overall_quality_score,
                                            debug_info=debug_info
                                        )
                            
                            # Record success
                            processing_path = ProcessingPath.RETRY_SUCCESS if attempt > 0 else ProcessingPath.DIRECT_SUCCESS
                            self.quality_monitor.record_success(attempt_context, processing_path)
                            
                            # Log successful completion
                            duration_ms = (time.time() - start_time) * 1000
                            self.logger.log_performance(
                                operation="response_processing_complete",
                                duration_ms=duration_ms,
                                success=True,
                                processing_path=processing_path.value,
                                total_attempts=attempt + 1,
                                session_id=context.session_id
                            )
                            
                            return ProcessingResult(
                                success=True,
                                data=report,
                                processing_path=processing_path,
                                quality_score=content_quality_result.overall_quality_score if content_quality_result else 1.0,
                                debug_info=debug_info
                            )
                            
                        except Exception as pydantic_error:
                            # Pydantic validation failed
                            if attempt == self.retry_manager.config.max_retries:
                                self.quality_monitor.record_failure(
                                    attempt_context, "pydantic_validation", False, True
                                )
                                print(MessageFormatter.validation_error(str(pydantic_error)))
                                return ProcessingResult(
                                    success=False,
                                    processing_path=ProcessingPath.COMPLETE_FAILURE,
                                    debug_info=debug_info
                                )
                            
                            # Try to enhance prompt for pydantic validation error
                            current_prompt = self.retry_manager.enhance_prompt_generic(
                                current_prompt, str(pydantic_error)
                            )
                            continue
                    
                    else:
                        # Validation failed - check if we should retry
                        if should_attempt_retry(enhanced_validation, attempt, self.retry_manager):
                            # Record retry attempt
                            self.quality_monitor.record_retry(attempt_context, enhanced_validation.error_type)
                            
                            # Log retry decision
                            self.logger.warning(
                                f"Validation failed, attempting retry {attempt + 1}/{self.retry_manager.config.max_retries}",
                                extra_data={
                                    'error_type': enhanced_validation.error_type,
                                    'retry_strategy': enhanced_validation.retry_strategy.value if enhanced_validation.retry_strategy else None,
                                    'attempt': attempt + 1,
                                    'session_id': context.session_id
                                }
                            )
                            
                            # Enhance prompt for retry
                            current_prompt = get_enhanced_prompt_for_retry(
                                prompt, enhanced_validation, self.retry_manager, raw_output
                            )
                            
                            # Add to previous errors
                            attempt_context.previous_errors.append(enhanced_validation.error_type)
                            continue
                        else:
                            # No more retries - attempt recovery
                            self.logger.warning(
                                f"Maximum retries reached, attempting recovery",
                                extra_data={
                                    'error_type': enhanced_validation.error_type,
                                    'total_attempts': attempt + 1,
                                    'session_id': context.session_id
                                }
                            )
                            
                            recovery_result = _enhanced_partial_recovery(
                                raw_output, clean_json, parsed, self.config.recovery_config, context.user_query
                            )
                            
                            if debug_info:
                                debug_info["recovery_attempts"].append({
                                    "success": recovery_result.success,
                                    "method": recovery_result.recovery_method.value if recovery_result.recovery_method else None,
                                    "confidence": recovery_result.confidence_score
                                })
                            
                            processing_path = ProcessingPath.RECOVERY_SUCCESS if recovery_result.success else ProcessingPath.COMPLETE_FAILURE
                            
                            if recovery_result.success:
                                self.quality_monitor.record_success(attempt_context, processing_path)
                                self.logger.info(
                                    f"Recovery successful using {recovery_result.recovery_method.value if recovery_result.recovery_method else 'unknown'} method",
                                    extra_data={
                                        'recovery_method': recovery_result.recovery_method.value if recovery_result.recovery_method else None,
                                        'confidence_score': recovery_result.confidence_score,
                                        'session_id': context.session_id
                                    }
                                )
                            else:
                                self.quality_monitor.record_failure(
                                    attempt_context, enhanced_validation.error_type, True, True
                                )
                                self.logger.error(
                                    f"Recovery failed after {attempt + 1} attempts",
                                    extra_data={
                                        'final_error_type': enhanced_validation.error_type,
                                        'total_attempts': attempt + 1,
                                        'session_id': context.session_id
                                    }
                                )
                            
                            return ProcessingResult(
                                success=recovery_result.success,
                                data=recovery_result.recovered_data,
                                processing_path=processing_path,
                                quality_score=recovery_result.confidence_score,
                                warnings=recovery_result.warnings,
                                debug_info=debug_info
                            )
                
                except json.JSONDecodeError as e:
                    # JSON parsing failed
                    if attempt == self.retry_manager.config.max_retries:
                        # Final attempt - use existing error handling
                        self.quality_monitor.record_failure(
                            attempt_context, "json_syntax", False, True
                        )
                        self.logger.error(
                            f"JSON parsing failed on final attempt: {str(e)}",
                            extra_data={
                                'error_line': e.lineno,
                                'error_column': e.colno,
                                'total_attempts': attempt + 1,
                                'session_id': context.session_id
                            }
                        )
                        print(MessageFormatter.json_syntax_error(str(e), e.lineno, e.colno))
                        print(MessageFormatter.debugging_suggestion("syntax"))
                        print(MessageFormatter.raw_response_header())
                        print(raw_output)
                        
                        return ProcessingResult(
                            success=False,
                            processing_path=ProcessingPath.COMPLETE_FAILURE,
                            debug_info=debug_info
                        )
                    
                    # Record retry and enhance prompt for syntax retry
                    self.quality_monitor.record_retry(attempt_context, "json_syntax")
                    self.logger.warning(
                        f"JSON syntax error, retrying with enhanced prompt: {str(e)}",
                        extra_data={
                            'error_line': e.lineno,
                            'error_column': e.colno,
                            'attempt': attempt + 1,
                            'session_id': context.session_id
                        }
                    )
                    current_prompt = self.retry_manager.enhance_prompt_for_syntax_error(
                        current_prompt, str(e)
                    )
                    continue
                
                except ValueError as extraction_error:
                    # JSON extraction failed
                    if attempt == self.retry_manager.config.max_retries:
                        self.quality_monitor.record_failure(
                            attempt_context, "extraction", False, True
                        )
                        self.logger.error(
                            f"JSON extraction failed on final attempt: {str(extraction_error)}",
                            extra_data={
                                'total_attempts': attempt + 1,
                                'session_id': context.session_id
                            }
                        )
                        print(MessageFormatter.extraction_error(str(extraction_error)))
                        print(MessageFormatter.debugging_suggestion("extraction"))
                        print(MessageFormatter.raw_response_header())
                        print(raw_output)
                        
                        return ProcessingResult(
                            success=False,
                            processing_path=ProcessingPath.COMPLETE_FAILURE,
                            debug_info=debug_info
                        )
                    
                    # Record retry and enhance prompt for extraction retry
                    self.quality_monitor.record_retry(attempt_context, "extraction")
                    self.logger.warning(
                        f"JSON extraction failed, retrying with enhanced prompt: {str(extraction_error)}",
                        extra_data={
                            'attempt': attempt + 1,
                            'session_id': context.session_id
                        }
                    )
                    current_prompt = self.retry_manager.enhance_prompt(
                        current_prompt, "extraction", raw_output
                    )
                    continue
                
            except Exception as e:
                # Unexpected error
                if attempt == self.retry_manager.config.max_retries:
                    self.quality_monitor.record_failure(
                        attempt_context, "unexpected", False, True
                    )
                    self.logger.error(
                        f"Unexpected error on final attempt: {str(e)}",
                        extra_data={
                            'error_type': type(e).__name__,
                            'total_attempts': attempt + 1,
                            'session_id': context.session_id
                        }
                    )
                    print(MessageFormatter.parsing_error(str(e)))
                    print(MessageFormatter.debugging_suggestion("validation"))
                    
                    return ProcessingResult(
                        success=False,
                        processing_path=ProcessingPath.COMPLETE_FAILURE,
                        debug_info=debug_info
                    )
                
                # Record retry and enhance prompt generically
                self.quality_monitor.record_retry(attempt_context, "unexpected")
                self.logger.warning(
                    f"Unexpected error, retrying with enhanced prompt: {str(e)}",
                    extra_data={
                        'error_type': type(e).__name__,
                        'attempt': attempt + 1,
                        'session_id': context.session_id
                    }
                )
                current_prompt = self.retry_manager.enhance_prompt_generic(
                    current_prompt, str(e)
                )
                continue
        
        # Should not reach here, but handle gracefully
        self.logger.error(
            "Response processing completed without returning result",
            extra_data={'session_id': context.session_id}
        )
        return ProcessingResult(
            success=False,
            processing_path=ProcessingPath.COMPLETE_FAILURE,
            debug_info=debug_info
        )
    
    def get_quality_report(self):
        """Get quality monitoring report."""
        return self.quality_monitor.get_quality_report()
    
    def check_quality_degradation(self) -> bool:
        """Check if quality has degraded."""
        return self.quality_monitor.check_quality_degradation()
    
    def export_metrics(self, filepath=None):
        """Export quality metrics."""
        return self.quality_monitor.export_metrics(filepath)
    
    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self.quality_monitor.is_monitoring_enabled()