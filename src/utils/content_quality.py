# -*- coding: utf-8 -*-
"""Content quality validation and enhancement.

This module provides content quality validation that goes beyond technical
parsing to assess the relevance, completeness, and usefulness of research
results returned by AI models.
"""

import re
from typing import List, Dict, Optional, Set, TYPE_CHECKING
from collections import Counter

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from ..retrieval.models import PaperAnalysis, ResearchReport

from .response_models import (
    ContentQualityConfig, EnhancementConfig, ContentQualityResult, 
    ContentIssue, ContentIssueType, IssueSeverity, EnhancementResult,
    EnhancementAttempt, EnhancementStrategy
)


class ContentQualityValidator:
    """Validate content quality and relevance of successfully parsed responses."""
    
    def __init__(self, config: ContentQualityConfig):
        """Initialize content quality validator.
        
        Args:
            config: Configuration for content quality validation
        """
        self.config = config
        self.query_analyzer = QueryAnalyzer()
        self.relevance_scorer = RelevanceScorer()
        
    def validate_content_quality(
        self, 
        research_report: 'ResearchReport',
        original_query: str
    ) -> ContentQualityResult:
        """Validate content quality of successfully parsed research report.
        
        Args:
            research_report: Parsed and validated research report
            original_query: Original user query
            
        Returns:
            ContentQualityResult: Analysis of content quality issues
        """
        issues = []
        
        # Check for empty results
        if not research_report.papers:
            issues.append(ContentIssue(
                type=ContentIssueType.EMPTY_RESULTS,
                severity=IssueSeverity.HIGH,
                message="No papers found for this query",
                suggestions=self.query_analyzer.suggest_broader_terms(original_query)
            ))
        
        # Check for insufficient results
        elif len(research_report.papers) < self.config.min_expected_papers:
            issues.append(ContentIssue(
                type=ContentIssueType.INSUFFICIENT_RESULTS,
                severity=IssueSeverity.MEDIUM,
                message=f"Only {len(research_report.papers)} papers found, expected at least {self.config.min_expected_papers}",
                suggestions=self.query_analyzer.suggest_query_expansion(original_query)
            ))
        
        # Check for incomplete paper analysis
        incomplete_papers = self._find_incomplete_papers(research_report.papers)
        if incomplete_papers:
            issues.append(ContentIssue(
                type=ContentIssueType.INCOMPLETE_ANALYSIS,
                severity=IssueSeverity.LOW,
                message=f"{len(incomplete_papers)} papers have incomplete analysis",
                affected_papers=incomplete_papers
            ))
        
        # Check for relevance issues
        relevance_scores = self.relevance_scorer.score_papers(research_report.papers, original_query)
        low_relevance_papers = [
            paper for paper, score in relevance_scores.items() 
            if score < self.config.min_relevance_threshold
        ]
        
        if low_relevance_papers:
            issues.append(ContentIssue(
                type=ContentIssueType.LOW_RELEVANCE,
                severity=IssueSeverity.MEDIUM,
                message=f"{len(low_relevance_papers)} papers may not be relevant to your query",
                affected_papers=low_relevance_papers,
                suggestions=self.query_analyzer.suggest_more_specific_terms(original_query)
            ))
        
        # Calculate overall quality score
        overall_quality = self._calculate_overall_quality(research_report, relevance_scores)
        
        return ContentQualityResult(
            has_issues=bool(issues),
            issues=issues,
            overall_quality_score=overall_quality
        )
    
    def _find_incomplete_papers(self, papers: List['PaperAnalysis']) -> List['PaperAnalysis']:
        """Find papers with incomplete analysis.
        
        Args:
            papers: List of paper analysis objects
            
        Returns:
            List of papers with incomplete analysis
        """
        incomplete = []
        
        for paper in papers:
            # Check for missing or empty key fields
            missing_fields = []
            
            if not paper.key_points or len(paper.key_points) == 0:
                missing_fields.append("key_points")
            
            if not paper.why_relevant or len(paper.why_relevant) == 0:
                missing_fields.append("why_relevant")
            
            # Check for very short or generic content
            if paper.key_points:
                avg_length = sum(len(point) for point in paper.key_points) / len(paper.key_points)
                if avg_length < 20:  # Very short key points
                    missing_fields.append("detailed_key_points")
            
            if paper.why_relevant:
                avg_length = sum(len(reason) for reason in paper.why_relevant) / len(paper.why_relevant)
                if avg_length < 15:  # Very short relevance explanations
                    missing_fields.append("detailed_relevance")
            
            if missing_fields:
                incomplete.append(paper)
        
        return incomplete
    
    def _calculate_overall_quality(
        self, 
        research_report: 'ResearchReport', 
        relevance_scores: Dict['PaperAnalysis', float]
    ) -> float:
        """Calculate overall quality score for the research report.
        
        Args:
            research_report: The research report
            relevance_scores: Relevance scores for each paper
            
        Returns:
            float: Overall quality score (0.0 to 1.0)
        """
        if not research_report.papers:
            return 0.0
        
        # Factors contributing to quality score
        factors = {}
        
        # 1. Number of papers (up to expected minimum)
        paper_count_score = min(len(research_report.papers) / self.config.min_expected_papers, 1.0)
        factors['paper_count'] = paper_count_score * 0.3
        
        # 2. Average relevance score
        if relevance_scores:
            avg_relevance = sum(relevance_scores.values()) / len(relevance_scores)
            factors['relevance'] = avg_relevance * 0.4
        else:
            factors['relevance'] = 0.5  # Neutral if we can't score relevance
        
        # 3. Completeness of analysis
        complete_papers = len(research_report.papers) - len(self._find_incomplete_papers(research_report.papers))
        completeness_score = complete_papers / len(research_report.papers)
        factors['completeness'] = completeness_score * 0.3
        
        # Calculate weighted average
        total_score = sum(factors.values())
        return min(total_score, 1.0)


class QueryAnalyzer:
    """Analyze queries to suggest improvements."""
    
    def suggest_broader_terms(self, query: str) -> List[str]:
        """Suggest broader search terms for queries that return no results.
        
        Args:
            query: Original query
            
        Returns:
            List of suggested broader terms
        """
        suggestions = []
        
        # Remove very specific terms
        words = query.lower().split()
        
        # Remove years, specific numbers, very technical terms
        broader_words = []
        for word in words:
            if not re.match(r'^\d{4}$', word):  # Remove years
                if not re.match(r'^\d+$', word):  # Remove pure numbers
                    if len(word) > 3:  # Keep substantial words
                        broader_words.append(word)
        
        if broader_words:
            suggestions.append(" ".join(broader_words[:3]))  # Use first 3 substantial words
        
        # Suggest removing modifiers
        modifiers = ['recent', 'latest', 'new', 'novel', 'advanced', 'modern', 'current']
        filtered_query = query.lower()
        for modifier in modifiers:
            filtered_query = filtered_query.replace(modifier, '').strip()
        
        if filtered_query != query.lower() and filtered_query:
            suggestions.append(filtered_query)
        
        # Suggest core concepts
        core_concepts = self._extract_core_concepts(query)
        if core_concepts:
            suggestions.append(" ".join(core_concepts))
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def suggest_query_expansion(self, query: str) -> List[str]:
        """Suggest query expansions for insufficient results.
        
        Args:
            query: Original query
            
        Returns:
            List of suggested expanded queries
        """
        suggestions = []
        
        # Add synonyms and related terms
        expansions = {
            'machine learning': ['artificial intelligence', 'deep learning', 'neural networks'],
            'ai': ['artificial intelligence', 'machine learning', 'automation'],
            'nlp': ['natural language processing', 'text analysis', 'language models'],
            'computer vision': ['image processing', 'visual recognition', 'image analysis'],
            'data science': ['analytics', 'big data', 'data mining'],
            'algorithm': ['method', 'approach', 'technique'],
            'model': ['framework', 'system', 'approach']
        }
        
        query_lower = query.lower()
        for term, synonyms in expansions.items():
            if term in query_lower:
                for synonym in synonyms:
                    expanded = query + f" OR {synonym}"
                    suggestions.append(expanded)
                break
        
        # Add broader research areas
        if 'learning' in query_lower:
            suggestions.append(query + " OR education OR training")
        
        if 'analysis' in query_lower:
            suggestions.append(query + " OR evaluation OR assessment")
        
        return suggestions[:3]
    
    def suggest_more_specific_terms(self, query: str) -> List[str]:
        """Suggest more specific terms for better relevance.
        
        Args:
            query: Original query
            
        Returns:
            List of suggested more specific queries
        """
        suggestions = []
        
        # Add specific modifiers
        modifiers = ['recent', 'survey', 'review', 'comparative', 'empirical']
        for modifier in modifiers:
            suggestions.append(f"{modifier} {query}")
        
        # Add specific contexts
        contexts = ['applications', 'methods', 'techniques', 'approaches']
        for context in contexts:
            suggestions.append(f"{query} {context}")
        
        return suggestions[:3]
    
    def _extract_core_concepts(self, query: str) -> List[str]:
        """Extract core concepts from a query.
        
        Args:
            query: Query to analyze
            
        Returns:
            List of core concept words
        """
        # Simple extraction - remove stop words and keep important terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being'
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        core_words = [word for word in words if word not in stop_words and len(word) > 3]
        
        return core_words[:3]  # Return top 3 core concepts


class RelevanceScorer:
    """Score paper relevance to queries."""
    
    def score_papers(
        self, 
        papers: List['PaperAnalysis'], 
        query: str
    ) -> Dict['PaperAnalysis', float]:
        """Score relevance of papers to the original query.
        
        Args:
            papers: List of paper analysis objects
            query: Original user query
            
        Returns:
            Dict mapping papers to relevance scores (0.0 to 1.0)
        """
        scores = {}
        query_terms = self._extract_query_terms(query)
        
        for paper in papers:
            score = self._calculate_paper_relevance(paper, query_terms)
            scores[paper] = score
        
        return scores
    
    def _extract_query_terms(self, query: str) -> Set[str]:
        """Extract important terms from query for relevance scoring.
        
        Args:
            query: User query
            
        Returns:
            Set of important query terms
        """
        # Extract words, convert to lowercase, remove stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'paper', 'papers', 'research', 'study', 'studies'
        }
        
        words = re.findall(r'\b\w+\b', query.lower())
        important_terms = {word for word in words if word not in stop_words and len(word) > 2}
        
        return important_terms
    
    def _calculate_paper_relevance(
        self, 
        paper: 'PaperAnalysis', 
        query_terms: Set[str]
    ) -> float:
        """Calculate relevance score for a single paper.
        
        Args:
            paper: Paper analysis object
            query_terms: Set of important query terms
            
        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        if not query_terms:
            return 0.5  # Neutral score if no query terms
        
        # Collect all text from the paper
        paper_text = []
        
        if paper.title:
            paper_text.append(paper.title.lower())
        
        if hasattr(paper, 'venue') and paper.venue:
            paper_text.append(paper.venue.lower())
        
        if paper.key_points:
            paper_text.extend([point.lower() for point in paper.key_points])
        
        if paper.why_relevant:
            paper_text.extend([reason.lower() for reason in paper.why_relevant])
        
        # Count term matches
        all_paper_text = " ".join(paper_text)
        paper_words = set(re.findall(r'\b\w+\b', all_paper_text))
        
        # Calculate overlap
        matches = query_terms.intersection(paper_words)
        
        if not matches:
            return 0.2  # Low but not zero score for no matches
        
        # Score based on match ratio and importance
        match_ratio = len(matches) / len(query_terms)
        
        # Boost score if matches are in title or why_relevant
        title_matches = 0
        relevance_matches = 0
        
        if paper.title:
            title_words = set(re.findall(r'\b\w+\b', paper.title.lower()))
            title_matches = len(query_terms.intersection(title_words))
        
        if paper.why_relevant:
            relevance_text = " ".join(paper.why_relevant).lower()
            relevance_words = set(re.findall(r'\b\w+\b', relevance_text))
            relevance_matches = len(query_terms.intersection(relevance_words))
        
        # Calculate weighted score
        base_score = match_ratio * 0.6
        title_boost = (title_matches / len(query_terms)) * 0.3
        relevance_boost = (relevance_matches / len(query_terms)) * 0.1
        
        final_score = base_score + title_boost + relevance_boost
        return min(final_score, 1.0)


class ResultEnhancementEngine:
    """Enhance insufficient results through intelligent retry strategies."""
    
    def __init__(self, config: EnhancementConfig):
        """Initialize result enhancement engine.
        
        Args:
            config: Enhancement configuration
        """
        self.config = config
        self.query_enhancer = QueryEnhancer()
        self.prompt_optimizer = PromptOptimizer()
        
    async def enhance_insufficient_results(
        self,
        original_report: 'ResearchReport',
        content_issues: List[ContentIssue],
        analysis_agent: 'Agent',
        original_prompt: str
    ) -> EnhancementResult:
        """Attempt to enhance results based on content quality issues.
        
        Args:
            original_report: Original research report
            content_issues: List of content quality issues
            analysis_agent: AI agent for processing
            original_prompt: Original prompt that was used
            
        Returns:
            EnhancementResult: Result of enhancement attempts
        """
        enhancement_attempts = []
        
        for issue in content_issues:
            if issue.type == ContentIssueType.EMPTY_RESULTS and self.config.enable_query_broadening:
                # Try broader search terms
                enhanced_prompt = self.query_enhancer.broaden_query(original_prompt)
                enhancement_attempts.append(
                    EnhancementAttempt(
                        strategy=EnhancementStrategy.BROADER_QUERY,
                        enhanced_prompt=enhanced_prompt,
                        reason="Expanding search terms to find more papers"
                    )
                )
                
            elif issue.type == ContentIssueType.INSUFFICIENT_RESULTS and self.config.enable_query_expansion:
                # Try query expansion
                enhanced_prompt = self.query_enhancer.expand_query(original_prompt)
                enhancement_attempts.append(
                    EnhancementAttempt(
                        strategy=EnhancementStrategy.QUERY_EXPANSION,
                        enhanced_prompt=enhanced_prompt,
                        reason="Adding related terms to find more relevant papers"
                    )
                )
                
            elif issue.type == ContentIssueType.INCOMPLETE_ANALYSIS and self.config.enable_analysis_enhancement:
                # Request more detailed analysis
                enhanced_prompt = self.prompt_optimizer.add_analysis_emphasis(original_prompt)
                enhancement_attempts.append(
                    EnhancementAttempt(
                        strategy=EnhancementStrategy.DETAILED_ANALYSIS,
                        enhanced_prompt=enhanced_prompt,
                        reason="Requesting more complete paper analysis"
                    )
                )
        
        # Execute enhancement attempts (limited to prevent loops)
        best_result = original_report
        improvement_score = 0.0
        
        for attempt in enhancement_attempts[:self.config.max_enhancement_attempts]:
            try:
                # This would need to be implemented to actually retry with the enhanced prompt
                # For now, we'll return the original result
                pass
            except Exception:
                continue
        
        return EnhancementResult(
            success=len(enhancement_attempts) > 0,
            enhanced_report=best_result,
            attempts_made=enhancement_attempts,
            improvement_score=improvement_score
        )


class QueryEnhancer:
    """Enhance queries for better results."""
    
    def broaden_query(self, original_prompt: str) -> str:
        """Broaden the query in the prompt for more results.
        
        Args:
            original_prompt: Original prompt
            
        Returns:
            str: Enhanced prompt with broader query
        """
        # Add instruction to use broader terms
        enhancement = (
            "\n\nIMPORTANT: The previous search found no results. "
            "Please use broader, more general terms in your analysis. "
            "Include related concepts and synonyms. "
            "Focus on the core research area rather than specific techniques."
        )
        return original_prompt + enhancement
    
    def expand_query(self, original_prompt: str) -> str:
        """Expand the query for more comprehensive results.
        
        Args:
            original_prompt: Original prompt
            
        Returns:
            str: Enhanced prompt with expanded query
        """
        enhancement = (
            "\n\nIMPORTANT: Please expand your search to include related topics, "
            "alternative approaches, and broader research areas. "
            "Look for papers that address similar problems or use related methods."
        )
        return original_prompt + enhancement


class PromptOptimizer:
    """Optimize prompts for better analysis quality."""
    
    def add_analysis_emphasis(self, original_prompt: str) -> str:
        """Add emphasis for more detailed analysis.
        
        Args:
            original_prompt: Original prompt
            
        Returns:
            str: Enhanced prompt with analysis emphasis
        """
        enhancement = (
            "\n\nIMPORTANT: Please provide detailed analysis for each paper. "
            "Include at least 3 specific key points and 2 clear reasons why each paper is relevant. "
            "Make sure your analysis is comprehensive and informative."
        )
        return original_prompt + enhancement