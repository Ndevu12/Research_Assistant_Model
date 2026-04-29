# -*- coding: utf-8 -*-
"""Fallback processing for complete response failures.

This module provides enhanced fallback mechanisms when structured JSON parsing
completely fails. It attempts to extract useful information from unstructured
text responses and present it in a helpful format to users.
"""

import re
import json
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .response_models import RecoveryConfig, RecoveryMethod, RecoveryResult
from .logging_system import logger


class FallbackMethod(Enum):
    """Methods for fallback processing."""
    TEXT_EXTRACTION = "text_extraction"
    PATTERN_MATCHING = "pattern_matching"
    KEYWORD_ANALYSIS = "keyword_analysis"
    STRUCTURED_SUMMARY = "structured_summary"


@dataclass
class FallbackResult:
    """Result of fallback processing."""
    success: bool
    method: FallbackMethod
    extracted_content: Dict[str, Any]
    confidence_score: float
    warnings: List[str]
    raw_sections: List[str]


class TextFallbackProcessor:
    """Process unstructured text responses as fallback."""
    
    def __init__(self, config: Optional[RecoveryConfig] = None):
        """Initialize text fallback processor.
        
        Args:
            config: Recovery configuration
        """
        self.config = config or RecoveryConfig()
        self.logger = logger
    
    def process_unstructured_response(
        self, 
        raw_response: str, 
        user_query: str
    ) -> FallbackResult:
        """Process unstructured response text to extract useful information.
        
        Args:
            raw_response: The raw model response
            user_query: Original user query for context
            
        Returns:
            FallbackResult: Extracted information and metadata
        """
        self.logger.info(
            "Attempting fallback processing for unstructured response",
            extra={
                'response_length': len(raw_response),
                'query_length': len(user_query)
            }
        )
        
        # Try different fallback methods in order of preference
        methods = [
            self._extract_paper_mentions,
            self._extract_key_findings,
            self._extract_research_themes,
            self._create_structured_summary
        ]
        
        best_result = None
        best_confidence = 0.0
        
        for method in methods:
            try:
                result = method(raw_response, user_query)
                if result.success and result.confidence_score > best_confidence:
                    best_result = result
                    best_confidence = result.confidence_score
            except Exception as e:
                self.logger.warning(
                    f"Fallback method {method.__name__} failed: {str(e)}",
                    extra={'method': method.__name__}
                )
                continue
        
        if best_result is None:
            # Create minimal fallback result
            best_result = FallbackResult(
                success=False,
                method=FallbackMethod.TEXT_EXTRACTION,
                extracted_content={
                    "summary": "Unable to extract structured information from response",
                    "raw_text": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response
                },
                confidence_score=0.1,
                warnings=["Could not extract structured information"],
                raw_sections=[raw_response]
            )
        
        return best_result
    
    def _extract_paper_mentions(self, response: str, query: str) -> FallbackResult:
        """Extract paper mentions from unstructured text.
        
        Args:
            response: Raw response text
            query: User query
            
        Returns:
            FallbackResult: Extracted paper information
        """
        papers = []
        warnings = []
        
        # Look for paper title patterns
        title_patterns = [
            r'"([^"]{10,100})"',  # Quoted titles
            r'titled?\s+"([^"]{10,100})"',  # "titled X"
            r'paper\s+"([^"]{10,100})"',  # "paper X"
            r'study\s+"([^"]{10,100})"',  # "study X"
            r'article\s+"([^"]{10,100})"',  # "article X"
        ]
        
        found_titles = set()
        for pattern in title_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                title = match.group(1).strip()
                if len(title) > 10 and title not in found_titles:
                    found_titles.add(title)
        
        # Look for author patterns
        author_patterns = [
            r'by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+et\s+al\.?)?)',
            r'authors?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+et\s+al\.?)?)',
        ]
        
        found_authors = set()
        for pattern in author_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                author = match.group(1).strip()
                if len(author) > 3 and author not in found_authors:
                    found_authors.add(author)
        
        # Look for year patterns
        year_pattern = r'\b(19|20)\d{2}\b'
        found_years = set()
        for match in re.finditer(year_pattern, response):
            year = int(match.group(0))
            if 1990 <= year <= 2024:
                found_years.add(year)
        
        # Create paper entries from found information
        for i, title in enumerate(list(found_titles)[:5]):  # Limit to 5 papers
            paper = {
                "title": title,
                "authors": list(found_authors)[i] if i < len(found_authors) else "Unknown",
                "year": list(found_years)[i] if i < len(found_years) else None,
                "key_points": self._extract_key_points_for_paper(response, title),
                "why_relevant": f"Mentioned in response to query about {query}",
                "confidence": "low",
                "source": "text_extraction"
            }
            papers.append(paper)
        
        if not papers:
            warnings.append("No clear paper mentions found in response")
        
        confidence = min(0.7, len(papers) * 0.2) if papers else 0.1
        
        return FallbackResult(
            success=len(papers) > 0,
            method=FallbackMethod.PATTERN_MATCHING,
            extracted_content={
                "papers": papers,
                "extraction_method": "pattern_matching",
                "total_found": len(papers)
            },
            confidence_score=confidence,
            warnings=warnings,
            raw_sections=[response]
        )
    
    def _extract_key_points_for_paper(self, response: str, title: str) -> List[str]:
        """Extract key points related to a specific paper.
        
        Args:
            response: Full response text
            title: Paper title to find context for
            
        Returns:
            List[str]: Key points related to the paper
        """
        # Find sentences containing the title or nearby
        sentences = re.split(r'[.!?]+', response)
        relevant_sentences = []
        
        for i, sentence in enumerate(sentences):
            if title.lower() in sentence.lower():
                # Include this sentence and nearby ones
                start = max(0, i - 1)
                end = min(len(sentences), i + 2)
                relevant_sentences.extend(sentences[start:end])
        
        # Extract key points from relevant sentences
        key_points = []
        for sentence in relevant_sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and any(word in sentence.lower() for word in 
                ['shows', 'demonstrates', 'finds', 'concludes', 'reports', 'indicates']):
                key_points.append(sentence)
        
        return key_points[:3]  # Limit to 3 key points
    
    def _extract_key_findings(self, response: str, query: str) -> FallbackResult:
        """Extract key findings from unstructured text.
        
        Args:
            response: Raw response text
            query: User query
            
        Returns:
            FallbackResult: Extracted findings
        """
        findings = []
        warnings = []
        
        # Look for finding indicators
        finding_patterns = [
            r'(found that [^.!?]{20,200})',
            r'(shows that [^.!?]{20,200})',
            r'(demonstrates [^.!?]{20,200})',
            r'(indicates [^.!?]{20,200})',
            r'(suggests [^.!?]{20,200})',
            r'(concludes [^.!?]{20,200})',
            r'(reveals [^.!?]{20,200})',
        ]
        
        for pattern in finding_patterns:
            matches = re.finditer(pattern, response, re.IGNORECASE)
            for match in matches:
                finding = match.group(1).strip()
                if len(finding) > 30:
                    findings.append(finding)
        
        # Remove duplicates and limit
        unique_findings = list(dict.fromkeys(findings))[:10]
        
        if not unique_findings:
            warnings.append("No clear research findings identified")
        
        confidence = min(0.6, len(unique_findings) * 0.1) if unique_findings else 0.1
        
        return FallbackResult(
            success=len(unique_findings) > 0,
            method=FallbackMethod.KEYWORD_ANALYSIS,
            extracted_content={
                "key_findings": unique_findings,
                "total_findings": len(unique_findings),
                "extraction_method": "keyword_analysis"
            },
            confidence_score=confidence,
            warnings=warnings,
            raw_sections=[response]
        )
    
    def _extract_research_themes(self, response: str, query: str) -> FallbackResult:
        """Extract research themes and topics from text.
        
        Args:
            response: Raw response text
            query: User query
            
        Returns:
            FallbackResult: Extracted themes
        """
        themes = []
        warnings = []
        
        # Look for research-related keywords
        research_keywords = [
            'machine learning', 'artificial intelligence', 'deep learning',
            'neural networks', 'natural language processing', 'computer vision',
            'data mining', 'big data', 'algorithm', 'model', 'training',
            'classification', 'regression', 'clustering', 'optimization',
            'performance', 'accuracy', 'evaluation', 'dataset', 'experiment'
        ]
        
        found_themes = {}
        for keyword in research_keywords:
            count = len(re.findall(keyword, response, re.IGNORECASE))
            if count > 0:
                found_themes[keyword] = count
        
        # Sort by frequency
        sorted_themes = sorted(found_themes.items(), key=lambda x: x[1], reverse=True)
        top_themes = [theme for theme, count in sorted_themes[:8]]
        
        # Extract sentences containing top themes
        theme_contexts = {}
        for theme in top_themes[:3]:  # Top 3 themes
            sentences = []
            for sentence in re.split(r'[.!?]+', response):
                if theme.lower() in sentence.lower() and len(sentence.strip()) > 20:
                    sentences.append(sentence.strip())
            theme_contexts[theme] = sentences[:2]  # Max 2 sentences per theme
        
        if not top_themes:
            warnings.append("No clear research themes identified")
        
        confidence = min(0.5, len(top_themes) * 0.08) if top_themes else 0.1
        
        return FallbackResult(
            success=len(top_themes) > 0,
            method=FallbackMethod.KEYWORD_ANALYSIS,
            extracted_content={
                "research_themes": top_themes,
                "theme_contexts": theme_contexts,
                "theme_frequencies": dict(sorted_themes[:5]),
                "extraction_method": "theme_analysis"
            },
            confidence_score=confidence,
            warnings=warnings,
            raw_sections=[response]
        )
    
    def _create_structured_summary(self, response: str, query: str) -> FallbackResult:
        """Create a structured summary of the response.
        
        Args:
            response: Raw response text
            query: User query
            
        Returns:
            FallbackResult: Structured summary
        """
        warnings = []
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in response.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in response.split('\n') if p.strip()]
        
        # Identify different sections
        summary_sections = {
            "introduction": [],
            "main_content": [],
            "conclusions": []
        }
        
        for i, paragraph in enumerate(paragraphs):
            if len(paragraph) < 20:
                continue
                
            # Classify paragraph
            if i == 0 or any(word in paragraph.lower() for word in ['introduction', 'overview', 'background']):
                summary_sections["introduction"].append(paragraph)
            elif i >= len(paragraphs) - 2 or any(word in paragraph.lower() for word in ['conclusion', 'summary', 'in summary']):
                summary_sections["conclusions"].append(paragraph)
            else:
                summary_sections["main_content"].append(paragraph)
        
        # Create summary
        structured_summary = {}
        
        if summary_sections["introduction"]:
            structured_summary["overview"] = summary_sections["introduction"][0][:300] + "..."
        
        if summary_sections["main_content"]:
            structured_summary["key_content"] = [
                p[:200] + "..." if len(p) > 200 else p 
                for p in summary_sections["main_content"][:3]
            ]
        
        if summary_sections["conclusions"]:
            structured_summary["conclusions"] = summary_sections["conclusions"][0][:300] + "..."
        
        # Add metadata
        structured_summary["word_count"] = len(response.split())
        structured_summary["paragraph_count"] = len(paragraphs)
        structured_summary["query_context"] = query
        
        if not any(summary_sections.values()):
            warnings.append("Could not identify clear document structure")
        
        confidence = 0.3 if any(summary_sections.values()) else 0.1
        
        return FallbackResult(
            success=True,  # Always succeeds as a last resort
            method=FallbackMethod.STRUCTURED_SUMMARY,
            extracted_content={
                "structured_summary": structured_summary,
                "extraction_method": "structured_summary",
                "sections_found": {k: len(v) for k, v in summary_sections.items()}
            },
            confidence_score=confidence,
            warnings=warnings,
            raw_sections=paragraphs
        )


def create_fallback_research_report(fallback_result: FallbackResult, user_query: str) -> Dict[str, Any]:
    """Create a research report structure from fallback processing results.
    
    Args:
        fallback_result: Result from fallback processing
        user_query: Original user query
        
    Returns:
        Dict[str, Any]: Research report structure with fallback data
    """
    report = {
        "query": user_query,
        "papers": [],
        "summary": "",
        "metadata": {
            "processing_method": "fallback",
            "fallback_method": fallback_result.method.value,
            "confidence": fallback_result.confidence_score,
            "warnings": fallback_result.warnings,
            "data_completeness": "partial"
        }
    }
    
    content = fallback_result.extracted_content
    
    # Handle different types of extracted content
    if "papers" in content:
        report["papers"] = content["papers"]
        report["summary"] = f"Extracted {len(content['papers'])} paper references from unstructured response."
    
    elif "key_findings" in content:
        # Convert findings to paper-like structure
        for i, finding in enumerate(content["key_findings"][:5]):
            paper = {
                "title": f"Finding {i+1}",
                "key_points": [finding],
                "why_relevant": "Extracted from model response",
                "confidence": "low",
                "source": "text_extraction"
            }
            report["papers"].append(paper)
        report["summary"] = f"Extracted {len(content['key_findings'])} key findings from response."
    
    elif "research_themes" in content:
        # Convert themes to paper-like structure
        for theme in content["research_themes"][:5]:
            contexts = content.get("theme_contexts", {}).get(theme, [])
            paper = {
                "title": f"Research Theme: {theme.title()}",
                "key_points": contexts,
                "why_relevant": f"Identified as relevant theme for query about {user_query}",
                "confidence": "low",
                "source": "theme_extraction"
            }
            report["papers"].append(paper)
        report["summary"] = f"Identified {len(content['research_themes'])} research themes."
    
    elif "structured_summary" in content:
        summary_data = content["structured_summary"]
        
        # Create a single "paper" from the summary
        paper = {
            "title": "Response Summary",
            "key_points": summary_data.get("key_content", []),
            "why_relevant": "Summary of model response",
            "confidence": "low",
            "source": "summary_extraction"
        }
        
        if "overview" in summary_data:
            paper["abstract"] = summary_data["overview"]
        
        if "conclusions" in summary_data:
            paper["conclusions"] = summary_data["conclusions"]
        
        report["papers"] = [paper]
        report["summary"] = "Created structured summary from unstructured response."
    
    # Add fallback indicators
    if report["papers"]:
        for paper in report["papers"]:
            paper["_fallback_processed"] = True
            paper["_original_confidence"] = fallback_result.confidence_score
    
    return report


def enhance_partial_recovery_with_fallback(
    raw_output: str,
    clean_json: str,
    parsed_data: Any,
    config: RecoveryConfig,
    user_query: str
) -> RecoveryResult:
    """Enhance existing partial recovery with fallback processing.
    
    Args:
        raw_output: Original model output
        clean_json: Cleaned JSON string (may be invalid)
        parsed_data: Partially parsed data (may be incomplete)
        config: Recovery configuration
        user_query: Original user query for context
        
    Returns:
        RecoveryResult: Enhanced recovery result with fallback data
    """
    # First try existing recovery methods
    from ..retrieval.orchestrator import _attempt_partial_recovery
    
    try:
        existing_result = _attempt_partial_recovery(raw_output, clean_json, parsed_data)
        if existing_result.success and existing_result.confidence_score > 0.5:
            logger.info("Existing recovery method succeeded, using that result")
            return existing_result
    except Exception as e:
        logger.warning(f"Existing recovery method failed: {str(e)}")
    
    # If existing recovery failed or has low confidence, try fallback processing
    logger.info("Attempting enhanced fallback processing")
    
    fallback_processor = TextFallbackProcessor(config)
    fallback_result = fallback_processor.process_unstructured_response(raw_output, user_query)
    
    if fallback_result.success:
        # Create research report from fallback data
        fallback_report = create_fallback_research_report(fallback_result, user_query)
        
        # Convert to expected format (ResearchReport-like structure)
        try:
            from ..retrieval.models import ResearchReport, PaperAnalysis
            
            # Convert fallback papers to PaperAnalysis objects
            papers = []
            for paper_data in fallback_report["papers"]:
                paper = PaperAnalysis(
                    title=paper_data.get("title", "Unknown Title"),
                    authors=paper_data.get("authors", "Unknown"),
                    year=paper_data.get("year"),
                    venue=paper_data.get("venue"),
                    url=paper_data.get("url"),
                    doi=paper_data.get("doi"),
                    key_points=paper_data.get("key_points", []),
                    why_relevant=paper_data.get("why_relevant", "Extracted from response")
                )
                papers.append(paper)
            
            recovered_report = ResearchReport(
                query=user_query,
                papers=papers
            )
            
            return RecoveryResult(
                success=True,
                recovered_data=recovered_report,
                recovery_method=RecoveryMethod.FALLBACK_PROCESSING,
                confidence_score=fallback_result.confidence_score,
                warnings=fallback_result.warnings + ["Data extracted using fallback processing - completeness not guaranteed"]
            )
            
        except Exception as e:
            logger.warning(f"Failed to create ResearchReport from fallback data: {str(e)}")
            
            # Return raw fallback data if ResearchReport creation fails
            return RecoveryResult(
                success=True,
                recovered_data=fallback_report,
                recovery_method=RecoveryMethod.FALLBACK_PROCESSING,
                confidence_score=fallback_result.confidence_score * 0.8,  # Reduce confidence for raw data
                warnings=fallback_result.warnings + ["Returning raw extracted data - structure may be incomplete"]
            )
    
    # If all recovery methods fail
    return RecoveryResult(
        success=False,
        recovered_data=None,
        recovery_method=RecoveryMethod.FALLBACK_PROCESSING,
        confidence_score=0.0,
        warnings=["All recovery methods failed, including fallback processing"]
    )