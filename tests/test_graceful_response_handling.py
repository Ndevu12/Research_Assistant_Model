# -*- coding: utf-8 -*-
"""Tests for graceful response handling implementation.

This module contains basic tests to verify the graceful response handling
components work correctly and integrate properly with the existing system.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from dataclasses import dataclass
from typing import List, Optional

from src.utils.response_models import (
    ResponseHandlerConfig, RequestContext, ProcessingResult, ProcessingPath,
    ValidationResult, RetryStrategy, ContentIssue, ContentIssueType, IssueSeverity
)
from src.utils.retry_manager import RetryManager
from src.utils.quality_monitor import QualityMonitor
from src.utils.enhanced_validation import enhance_validation_result
from src.utils.content_quality import ContentQualityValidator, QueryAnalyzer, RelevanceScorer


# Mock classes for testing
@dataclass(frozen=True)  # Make it hashable
class MockPaperAnalysis:
    """Mock paper analysis for testing."""
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    key_points: tuple = ()  # Use tuple instead of list for hashability
    why_relevant: tuple = ()  # Use tuple instead of list for hashability
    
    def __post_init__(self):
        # Convert lists to tuples if needed
        if isinstance(self.key_points, list):
            object.__setattr__(self, 'key_points', tuple(self.key_points))
        if isinstance(self.why_relevant, list):
            object.__setattr__(self, 'why_relevant', tuple(self.why_relevant))


@dataclass
class MockResearchReport:
    """Mock research report for testing."""
    query: str
    papers: List[MockPaperAnalysis]


class TestRetryManager:
    """Test retry manager functionality."""
    
    def test_retry_manager_initialization(self):
        """Test retry manager initializes correctly."""
        from src.utils.response_models import RetryConfig
        
        config = RetryConfig(max_retries=2, base_delay=0.5)
        retry_manager = RetryManager(config)
        
        assert retry_manager.config.max_retries == 2
        assert retry_manager.config.base_delay == 0.5
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        from src.utils.response_models import RetryConfig
        
        config = RetryConfig(max_retries=3, enabled_for_errors={"syntax", "schema"})
        retry_manager = RetryManager(config)
        
        # Should retry for enabled error types within limit
        assert retry_manager.should_retry("syntax", 0) == True
        assert retry_manager.should_retry("syntax", 2) == True
        assert retry_manager.should_retry("schema", 1) == True
        
        # Should not retry beyond limit
        assert retry_manager.should_retry("syntax", 3) == False
        assert retry_manager.should_retry("syntax", 5) == False
        
        # Should not retry for disabled error types
        assert retry_manager.should_retry("unknown", 0) == False
    
    def test_prompt_enhancement(self):
        """Test prompt enhancement for different error types."""
        from src.utils.response_models import RetryConfig
        
        retry_manager = RetryManager(RetryConfig())
        original_prompt = "Analyze these papers"
        
        # Test syntax enhancement
        enhanced = retry_manager.enhance_prompt(original_prompt, "syntax")
        assert "valid JSON" in enhanced
        assert original_prompt in enhanced
        
        # Test schema enhancement
        enhanced = retry_manager.enhance_prompt(original_prompt, "schema")
        assert "Required JSON format" in enhanced
        assert original_prompt in enhanced
        
        # Test generic enhancement
        enhanced = retry_manager.enhance_prompt(original_prompt, "unknown")
        assert "ensure your response" in enhanced
        assert original_prompt in enhanced


class TestQualityMonitor:
    """Test quality monitoring functionality."""
    
    def test_quality_monitor_initialization(self):
        """Test quality monitor initializes correctly."""
        from src.utils.response_models import QualityConfig
        
        config = QualityConfig(enable_monitoring=True)
        monitor = QualityMonitor(config)
        
        assert monitor.config.enable_monitoring == True
        assert monitor.metrics.total_attempts == 0
    
    def test_success_recording(self):
        """Test recording successful operations."""
        from src.utils.response_models import QualityConfig
        
        monitor = QualityMonitor(QualityConfig(enable_monitoring=True))
        context = RequestContext(
            user_query="test query",
            model_name="test_model",
            attempt_count=0
        )
        
        monitor.record_success(context)
        
        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.successful_attempts == 1
        assert monitor.metrics.success_by_model["test_model"] == 1
    
    def test_failure_recording(self):
        """Test recording failed operations."""
        from src.utils.response_models import QualityConfig
        
        monitor = QualityMonitor(QualityConfig(enable_monitoring=True))
        context = RequestContext(
            user_query="test query",
            model_name="test_model",
            attempt_count=0
        )
        
        monitor.record_failure(context, "syntax_error", recovery_attempted=True, final_failure=True)
        
        assert monitor.metrics.total_attempts == 1
        assert monitor.metrics.failed_attempts == 1
        assert monitor.metrics.failures_by_type["syntax_error"] == 1
        assert monitor.metrics.recovery_attempts == 1
    
    def test_quality_report_generation(self):
        """Test quality report generation."""
        from src.utils.response_models import QualityConfig
        
        monitor = QualityMonitor(QualityConfig(enable_monitoring=True))
        context = RequestContext(
            user_query="test query",
            model_name="test_model",
            attempt_count=0
        )
        
        # Record some operations
        monitor.record_success(context)
        monitor.record_success(context)
        monitor.record_failure(context, "syntax_error", final_failure=True)
        
        report = monitor.get_quality_report()
        
        assert report.total_attempts == 3
        assert report.success_rate == 2/3  # 2 successes out of 3 attempts
        assert "syntax_error" in report.failure_breakdown


class TestEnhancedValidation:
    """Test enhanced validation functionality."""
    
    def test_validation_enhancement(self):
        """Test validation result enhancement with retry strategy."""
        # Create a validation result
        validation_result = ValidationResult(
            is_valid=False,
            error_message="Test error",
            error_type="syntax"
        )
        
        # Enhance it
        enhanced = enhance_validation_result(validation_result)
        
        assert enhanced.is_valid == False
        assert enhanced.error_type == "syntax"
        assert enhanced.retry_strategy == RetryStrategy.SYNTAX_EMPHASIS
    
    def test_valid_response_enhancement(self):
        """Test enhancement of valid responses."""
        validation_result = ValidationResult(is_valid=True)
        enhanced = enhance_validation_result(validation_result)
        
        assert enhanced.is_valid == True
        assert enhanced.retry_strategy is None


class TestContentQuality:
    """Test content quality validation."""
    
    def test_content_quality_validator_initialization(self):
        """Test content quality validator initializes correctly."""
        from src.utils.response_models import ContentQualityConfig
        
        config = ContentQualityConfig(min_expected_papers=3)
        validator = ContentQualityValidator(config)
        
        assert validator.config.min_expected_papers == 3
        assert validator.query_analyzer is not None
        assert validator.relevance_scorer is not None
    
    def test_empty_results_detection(self):
        """Test detection of empty results."""
        from src.utils.response_models import ContentQualityConfig
        
        validator = ContentQualityValidator(ContentQualityConfig())
        report = MockResearchReport(query="test query", papers=[])
        
        result = validator.validate_content_quality(report, "test query")
        
        assert result.has_issues == True
        assert len(result.issues) == 1
        assert result.issues[0].type == ContentIssueType.EMPTY_RESULTS
        assert result.issues[0].severity == IssueSeverity.HIGH
    
    def test_insufficient_results_detection(self):
        """Test detection of insufficient results."""
        from src.utils.response_models import ContentQualityConfig
        
        config = ContentQualityConfig(min_expected_papers=3)
        validator = ContentQualityValidator(config)
        
        # Create report with only 1 paper (less than minimum of 3)
        papers = [MockPaperAnalysis(title="Test Paper", key_points=(), why_relevant=())]
        report = MockResearchReport(query="test query", papers=papers)
        
        result = validator.validate_content_quality(report, "test query")
        
        assert result.has_issues == True
        insufficient_issues = [issue for issue in result.issues if issue.type == ContentIssueType.INSUFFICIENT_RESULTS]
        assert len(insufficient_issues) == 1
        assert insufficient_issues[0].severity == IssueSeverity.MEDIUM
    
    def test_incomplete_analysis_detection(self):
        """Test detection of incomplete paper analysis."""
        from src.utils.response_models import ContentQualityConfig
        
        validator = ContentQualityValidator(ContentQualityConfig())
        
        # Create paper with missing key_points and why_relevant
        papers = [MockPaperAnalysis(title="Test Paper", key_points=(), why_relevant=())]
        report = MockResearchReport(query="test query", papers=papers)
        
        result = validator.validate_content_quality(report, "test query")
        
        assert result.has_issues == True
        incomplete_issues = [issue for issue in result.issues if issue.type == ContentIssueType.INCOMPLETE_ANALYSIS]
        assert len(incomplete_issues) == 1
        assert incomplete_issues[0].severity == IssueSeverity.LOW
    
    def test_quality_with_complete_papers(self):
        """Test quality validation with complete, relevant papers."""
        from src.utils.response_models import ContentQualityConfig
        
        config = ContentQualityConfig(min_expected_papers=2)
        validator = ContentQualityValidator(config)
        
        # Create complete papers
        papers = [
            MockPaperAnalysis(
                title="Machine Learning Paper",
                key_points=("Uses neural networks", "Achieves high accuracy", "Novel architecture"),
                why_relevant=("Addresses the research question", "Uses similar methodology")
            ),
            MockPaperAnalysis(
                title="Deep Learning Study",
                key_points=("Compares different models", "Extensive evaluation", "Open source code"),
                why_relevant=("Relevant to the domain", "Provides baseline comparisons")
            )
        ]
        report = MockResearchReport(query="machine learning", papers=papers)
        
        result = validator.validate_content_quality(report, "machine learning")
        
        # Should have no major issues (might have low relevance but that's expected)
        high_severity_issues = [issue for issue in result.issues if issue.severity == IssueSeverity.HIGH]
        assert len(high_severity_issues) == 0


class TestQueryAnalyzer:
    """Test query analysis functionality."""
    
    def test_broader_terms_suggestion(self):
        """Test suggestion of broader terms."""
        analyzer = QueryAnalyzer()
        
        # Test with specific query
        suggestions = analyzer.suggest_broader_terms("advanced neural networks 2023")
        
        assert len(suggestions) > 0
        # Should remove year and specific modifiers in at least some suggestions
        has_year_removed = any("2023" not in suggestion for suggestion in suggestions)
        has_modifier_removed = any("advanced" not in suggestion.lower() for suggestion in suggestions)
        assert has_year_removed or has_modifier_removed
    
    def test_query_expansion_suggestion(self):
        """Test query expansion suggestions."""
        analyzer = QueryAnalyzer()
        
        suggestions = analyzer.suggest_query_expansion("machine learning")
        
        assert len(suggestions) > 0
        # Should include related terms
        assert any("artificial intelligence" in suggestion.lower() for suggestion in suggestions)
    
    def test_specific_terms_suggestion(self):
        """Test more specific terms suggestion."""
        analyzer = QueryAnalyzer()
        
        suggestions = analyzer.suggest_more_specific_terms("learning")
        
        assert len(suggestions) > 0
        # Should add modifiers or contexts
        assert any(len(suggestion.split()) > 1 for suggestion in suggestions)


class TestRelevanceScorer:
    """Test relevance scoring functionality."""
    
    def test_relevance_scoring(self):
        """Test paper relevance scoring."""
        scorer = RelevanceScorer()
        
        # Create papers with different relevance levels
        papers = [
            MockPaperAnalysis(
                title="Machine Learning Classification",
                key_points=("machine learning", "classification algorithms"),
                why_relevant=("directly addresses machine learning",)
            ),
            MockPaperAnalysis(
                title="Database Systems",
                key_points=("database design", "query optimization"),
                why_relevant=("not directly related",)
            )
        ]
        
        scores = scorer.score_papers(papers, "machine learning classification")
        
        assert len(scores) == 2
        # First paper should have higher relevance score
        paper_scores = list(scores.values())
        assert paper_scores[0] > paper_scores[1]
        assert all(0.0 <= score <= 1.0 for score in paper_scores)


class TestJSONProcessing:
    """Test enhanced JSON processing functionality."""
    
    def test_json_processor_initialization(self):
        """Test JSON processor initializes correctly."""
        from src.utils.json_processing import EnhancedJSONProcessor
        
        processor = EnhancedJSONProcessor()
        assert processor is not None
        assert processor.logger is not None
    
    def test_direct_json_extraction(self):
        """Test direct JSON extraction."""
        from src.utils.json_processing import extract_json
        
        json_text = '{"query": "test", "papers": []}'
        result = extract_json(json_text)
        
        assert result.success == True
        assert result.json_string == json_text
        assert result.confidence_score == 1.0
    
    def test_json_extraction_with_surrounding_text(self):
        """Test JSON extraction from text with surrounding content."""
        from src.utils.json_processing import extract_json
        
        text = '''
        Here is the analysis:
        {
            "query": "machine learning",
            "papers": [
                {"title": "Paper 1"}
            ]
        }
        End of analysis.
        '''
        
        result = extract_json(text)
        
        assert result.success == True
        assert '"query"' in result.json_string
        assert result.confidence_score > 0.0
    
    def test_json_parsing_with_error_details(self):
        """Test JSON parsing with detailed error information."""
        from src.utils.json_processing import parse_json
        
        invalid_json = '{"query": "test", "papers": [}'
        success, parsed, error = parse_json(invalid_json)
        
        assert success == False
        assert parsed is None
        assert error is not None
        assert error.error_type == "json_syntax"
        assert error.line_number is not None
    
    def test_json_pretty_printing(self):
        """Test JSON pretty printing."""
        from src.utils.json_processing import pretty_print_json
        
        compact_json = '{"query":"test","papers":[]}'
        pretty = pretty_print_json(compact_json)
        
        assert pretty is not None
        assert '\n' in pretty
        assert '"query"' in pretty
    
    def test_json_structure_validation(self):
        """Test JSON structure validation."""
        from src.utils.json_processing import EnhancedJSONProcessor
        
        processor = EnhancedJSONProcessor()
        
        # Valid JSON
        valid_json = '{"query": "test", "papers": []}'
        is_valid, errors = processor.validate_json_structure(valid_json)
        
        assert is_valid == True
        assert len(errors) == 0
        
        # Invalid JSON
        invalid_json = '{"query": "test", "papers": [}'
        is_valid, errors = processor.validate_json_structure(invalid_json)
        
        assert is_valid == False
        assert len(errors) > 0


# Integration test
class TestBasicIntegration:
    """Test basic integration between components."""
    
    def test_components_work_together(self):
        """Test that components can work together without errors."""
        from src.utils.response_models import ResponseHandlerConfig
        
        # Create configuration
        config = ResponseHandlerConfig()
        
        # Initialize components
        retry_manager = RetryManager(config.retry_config)
        quality_monitor = QualityMonitor(config.quality_config)
        content_validator = ContentQualityValidator(config.content_quality_config)
        
        # Test basic operations
        context = RequestContext(
            user_query="test query",
            model_name="test_model",
            attempt_count=0
        )
        
        # Test quality monitoring
        quality_monitor.record_success(context)
        report = quality_monitor.get_quality_report()
        assert report.success_rate == 1.0
        
        # Test content validation
        papers = [MockPaperAnalysis(title="Test Paper", key_points=(), why_relevant=())]
        mock_report = MockResearchReport(query="test", papers=papers)
        content_result = content_validator.validate_content_quality(mock_report, "test")
        assert isinstance(content_result.has_issues, bool)
        
        # Test retry logic
        assert retry_manager.should_retry("syntax", 0) == True
        enhanced_prompt = retry_manager.enhance_prompt("test prompt", "syntax")
        assert "test prompt" in enhanced_prompt


class TestModelAdaptation:
    """Test model adaptation functionality."""
    
    def test_model_adaptation_engine_initialization(self):
        """Test model adaptation engine initializes correctly."""
        from src.utils.model_adaptation import ModelAdaptationEngine, ModelType
        
        engine = ModelAdaptationEngine()
        
        assert engine is not None
        assert len(engine.model_patterns) > 0
        assert ModelType.OPENAI_GPT in engine.model_patterns
        assert ModelType.ANTHROPIC_CLAUDE in engine.model_patterns
    
    def test_model_type_detection(self):
        """Test detection of model types."""
        from src.utils.model_adaptation import ModelAdaptationEngine, ModelType
        
        engine = ModelAdaptationEngine()
        
        # Test OpenAI detection
        context_gpt = RequestContext(
            user_query="test",
            model_name="gpt-4-turbo",
            attempt_count=0
        )
        assert engine.detect_model_type(context_gpt) == ModelType.OPENAI_GPT
        
        # Test Claude detection
        context_claude = RequestContext(
            user_query="test",
            model_name="claude-3-opus",
            attempt_count=0
        )
        assert engine.detect_model_type(context_claude) == ModelType.ANTHROPIC_CLAUDE
        
        # Test generic fallback
        context_unknown = RequestContext(
            user_query="test",
            model_name="unknown-model-xyz",
            attempt_count=0
        )
        assert engine.detect_model_type(context_unknown) == ModelType.GENERIC
    
    def test_response_preprocessing(self):
        """Test response preprocessing for different models."""
        from src.utils.model_adaptation import ModelAdaptationEngine
        
        engine = ModelAdaptationEngine()
        
        # Test OpenAI response with markdown code blocks
        gpt_response = '''```json
{
  "query": "test",
  "papers": []
}
```'''
        
        context_gpt = RequestContext(
            user_query="test",
            model_name="gpt-4",
            attempt_count=0
        )
        
        result = engine.preprocess_response(gpt_response, context_gpt)
        
        assert result.success == True
        assert "```" not in result.adapted_response
        assert "{" in result.adapted_response
    
    def test_prompt_enhancement_for_model(self):
        """Test prompt enhancement for specific models."""
        from src.utils.model_adaptation import ModelAdaptationEngine
        
        engine = ModelAdaptationEngine()
        
        original_prompt = "Analyze these papers"
        
        context_gpt = RequestContext(
            user_query="test",
            model_name="gpt-4",
            attempt_count=0
        )
        
        enhanced = engine.enhance_prompt_for_model(original_prompt, context_gpt)
        
        assert enhanced != original_prompt
        assert "JSON" in enhanced or "json" in enhanced
        assert original_prompt in enhanced
    
    def test_schema_preferences_by_model(self):
        """Test schema preferences for different models."""
        from src.utils.model_adaptation import ModelAdaptationEngine, ModelType
        
        engine = ModelAdaptationEngine()
        
        context_gpt = RequestContext(
            user_query="test",
            model_name="gpt-4",
            attempt_count=0
        )
        
        prefs = engine.get_model_schema_preferences(context_gpt)
        
        assert isinstance(prefs, dict)
        assert len(prefs) > 0
        # GPT should prefer strict types
        assert prefs.get("strict_types") == True
    
    def test_adaptation_statistics(self):
        """Test adaptation statistics collection."""
        from src.utils.model_adaptation import ModelAdaptationEngine
        
        engine = ModelAdaptationEngine()
        
        # Detect a few models to populate cache
        for model_name in ["gpt-4", "claude-3", "gemini-pro"]:
            context = RequestContext(
                user_query="test",
                model_name=model_name,
                attempt_count=0
            )
            engine.detect_model_type(context)
        
        stats = engine.get_adaptation_statistics()
        
        assert "total_models_seen" in stats
        assert "model_type_distribution" in stats
        assert "supported_model_types" in stats
        assert stats["total_models_seen"] >= 3


class TestFallbackProcessing:
    """Test fallback processing functionality."""
    
    def test_fallback_processor_initialization(self):
        """Test fallback processor initializes correctly."""
        from src.utils.fallback_processing import TextFallbackProcessor
        from src.utils.response_models import RecoveryConfig
        
        config = RecoveryConfig()
        processor = TextFallbackProcessor(config)
        
        assert processor.config is not None
        assert processor.logger is not None
    
    def test_paper_extraction_from_text(self):
        """Test extraction of paper mentions from unstructured text."""
        from src.utils.fallback_processing import TextFallbackProcessor
        
        processor = TextFallbackProcessor()
        
        # Sample unstructured response with paper mentions
        response = '''
        The research shows several important findings. The paper "Deep Learning for Natural Language Processing" 
        by Smith et al. demonstrates significant improvements in accuracy. Another study titled 
        "Machine Learning Applications in Healthcare" published in 2023 shows promising results.
        The authors found that neural networks can achieve 95% accuracy on classification tasks.
        '''
        
        result = processor.process_unstructured_response(response, "machine learning")
        
        assert result.success == True
        # The processor may choose different extraction methods based on confidence
        # Check that some useful content was extracted
        assert result.extracted_content is not None
        assert len(result.extracted_content) > 0
        
        # Test the specific paper extraction method directly
        paper_result = processor._extract_paper_mentions(response, "machine learning")
        assert "papers" in paper_result.extracted_content
        papers = paper_result.extracted_content["papers"]
        assert len(papers) > 0
        
        # Check that at least one paper was extracted
        paper_titles = [p["title"] for p in papers]
        assert any("Deep Learning" in title for title in paper_titles)
    
    def test_key_findings_extraction(self):
        """Test extraction of key findings from text."""
        from src.utils.fallback_processing import TextFallbackProcessor
        
        processor = TextFallbackProcessor()
        
        response = '''
        The study found that machine learning models perform better with larger datasets.
        Research shows that deep learning demonstrates superior performance on image recognition tasks.
        The analysis indicates that preprocessing improves model accuracy by 15%.
        '''
        
        result = processor._extract_key_findings(response, "machine learning performance")
        
        assert result.success == True
        assert "key_findings" in result.extracted_content
        findings = result.extracted_content["key_findings"]
        assert len(findings) > 0
        assert any("found that" in finding for finding in findings)
    
    def test_research_themes_extraction(self):
        """Test extraction of research themes."""
        from src.utils.fallback_processing import TextFallbackProcessor
        
        processor = TextFallbackProcessor()
        
        response = '''
        This paper focuses on machine learning algorithms for natural language processing.
        The deep learning model uses neural networks to improve classification accuracy.
        Data mining techniques are applied to extract patterns from big data.
        The experiment evaluates performance on multiple datasets.
        '''
        
        result = processor._extract_research_themes(response, "AI research")
        
        assert result.success == True
        assert "research_themes" in result.extracted_content
        themes = result.extracted_content["research_themes"]
        assert len(themes) > 0
        assert any("machine learning" in theme.lower() for theme in themes)
    
    def test_structured_summary_creation(self):
        """Test creation of structured summaries."""
        from src.utils.fallback_processing import TextFallbackProcessor
        
        processor = TextFallbackProcessor()
        
        response = '''
        Introduction: This study examines machine learning applications.
        
        The main findings show that neural networks achieve high accuracy.
        Deep learning models outperform traditional algorithms.
        
        In conclusion, machine learning shows great promise for future applications.
        '''
        
        result = processor._create_structured_summary(response, "machine learning study")
        
        assert result.success == True
        assert "structured_summary" in result.extracted_content
        summary = result.extracted_content["structured_summary"]
        assert "query_context" in summary
        assert summary["query_context"] == "machine learning study"
    
    def test_fallback_report_creation(self):
        """Test creation of research report from fallback results."""
        from src.utils.fallback_processing import create_fallback_research_report, FallbackResult, FallbackMethod
        
        # Create mock fallback result
        fallback_result = FallbackResult(
            success=True,
            method=FallbackMethod.PATTERN_MATCHING,
            extracted_content={
                "papers": [
                    {
                        "title": "Test Paper",
                        "authors": "Test Author",
                        "key_points": ["Key finding 1", "Key finding 2"],
                        "why_relevant": "Relevant to query"
                    }
                ]
            },
            confidence_score=0.6,
            warnings=["Low confidence extraction"],
            raw_sections=["test section"]
        )
        
        report = create_fallback_research_report(fallback_result, "test query")
        
        assert report["query"] == "test query"
        assert len(report["papers"]) == 1
        assert report["papers"][0]["title"] == "Test Paper"
        assert report["metadata"]["processing_method"] == "fallback"
        assert report["metadata"]["confidence"] == 0.6