# -*- coding: utf-8 -*-
"""Model adaptation for handling different AI model response patterns.

This module provides capabilities to detect and adapt to different AI model
response patterns, preprocessing quirks, and output formats to improve
parsing success rates across different models.
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from .response_models import RequestContext
from .logging_system import logger


class ModelType(Enum):
    """Known model types with specific adaptation patterns."""
    OPENAI_GPT = "openai_gpt"
    ANTHROPIC_CLAUDE = "anthropic_claude"
    GOOGLE_GEMINI = "google_gemini"
    OLLAMA_LOCAL = "ollama_local"
    GENERIC = "generic"


class AdaptationStrategy(Enum):
    """Strategies for model adaptation."""
    RESPONSE_CLEANING = "response_cleaning"
    FORMAT_NORMALIZATION = "format_normalization"
    SCHEMA_ADJUSTMENT = "schema_adjustment"
    PROMPT_MODIFICATION = "prompt_modification"


@dataclass
class ModelPattern:
    """Pattern definition for a specific model."""
    model_type: ModelType
    name_patterns: List[str]  # Regex patterns to match model names
    response_quirks: List[str]  # Known response formatting issues
    cleaning_rules: List[Tuple[str, str]]  # (pattern, replacement) pairs
    schema_preferences: Dict[str, Any]  # Preferred schema formats
    prompt_adjustments: Dict[str, str]  # Prompt modifications


@dataclass
class AdaptationResult:
    """Result of model adaptation processing."""
    success: bool
    adapted_response: str
    adaptations_applied: List[AdaptationStrategy]
    model_type: ModelType
    confidence_score: float
    warnings: List[str]


class ModelAdaptationEngine:
    """Engine for adapting responses based on model-specific patterns."""
    
    def __init__(self):
        """Initialize model adaptation engine."""
        self.logger = logger
        self.model_patterns = self._initialize_model_patterns()
        self.adaptation_cache: Dict[str, ModelType] = {}
    
    def _initialize_model_patterns(self) -> Dict[ModelType, ModelPattern]:
        """Initialize known model patterns and adaptations.
        
        Returns:
            Dict[ModelType, ModelPattern]: Model patterns by type
        """
        patterns = {}
        
        # OpenAI GPT patterns
        patterns[ModelType.OPENAI_GPT] = ModelPattern(
            model_type=ModelType.OPENAI_GPT,
            name_patterns=[
                r"gpt-[34]\.?5?-?turbo",
                r"gpt-[34]",
                r"openai",
                r"chatgpt"
            ],
            response_quirks=[
                "Sometimes adds explanatory text before JSON",
                "May include markdown code blocks",
                "Occasionally adds trailing comments"
            ],
            cleaning_rules=[
                (r"```json\s*", ""),  # Remove markdown JSON blocks
                (r"```\s*$", ""),     # Remove closing markdown
                (r"^[^{]*({.*})[^}]*$", r"\1"),  # Extract JSON from surrounding text
                (r"//.*$", ""),       # Remove trailing comments
            ],
            schema_preferences={
                "strict_types": True,
                "required_fields": True,
                "array_format": "standard"
            },
            prompt_adjustments={
                "json_emphasis": "Please respond with ONLY valid JSON, no additional text or formatting.",
                "schema_reminder": "Ensure your response follows the exact JSON schema provided."
            }
        )
        
        # Anthropic Claude patterns
        patterns[ModelType.ANTHROPIC_CLAUDE] = ModelPattern(
            model_type=ModelType.ANTHROPIC_CLAUDE,
            name_patterns=[
                r"claude-[123]",
                r"claude-instant",
                r"anthropic",
                r"claude"
            ],
            response_quirks=[
                "Often provides detailed explanations",
                "May structure responses with headers",
                "Sometimes uses XML-like tags"
            ],
            cleaning_rules=[
                (r"<thinking>.*?</thinking>", ""),  # Remove thinking tags
                (r"<json>\s*", ""),                 # Remove XML-style JSON tags
                (r"</json>\s*", ""),
                (r"^.*?Here's the JSON.*?:\s*", ""),  # Remove explanatory prefixes
                (r"^.*?(?=\{)", ""),                # Remove text before first {
            ],
            schema_preferences={
                "strict_types": True,
                "detailed_descriptions": True,
                "nested_objects": True
            },
            prompt_adjustments={
                "json_emphasis": "Respond with only the JSON object, without any explanatory text or tags.",
                "format_instruction": "Do not include <thinking> tags or explanations, just the JSON."
            }
        )
        
        # Google Gemini patterns
        patterns[ModelType.GOOGLE_GEMINI] = ModelPattern(
            model_type=ModelType.GOOGLE_GEMINI,
            name_patterns=[
                r"gemini-pro",
                r"gemini-[0-9]",
                r"google",
                r"bard"
            ],
            response_quirks=[
                "May include safety disclaimers",
                "Sometimes formats with bullet points",
                "Can include multiple JSON objects"
            ],
            cleaning_rules=[
                (r"^\*\*.*?\*\*\s*", ""),          # Remove bold headers
                (r"^- .*?:\s*", ""),               # Remove bullet points
                (r"I cannot.*?However,?\s*", ""),  # Remove safety disclaimers
                (r"(?<=})\s*{", "},{"),            # Fix multiple JSON objects
            ],
            schema_preferences={
                "flexible_types": True,
                "optional_fields": True,
                "simple_structure": True
            },
            prompt_adjustments={
                "json_emphasis": "Return only a single valid JSON object with no additional formatting.",
                "safety_note": "This is for research purposes. Please provide the requested JSON format."
            }
        )
        
        # Ollama/Local model patterns
        patterns[ModelType.OLLAMA_LOCAL] = ModelPattern(
            model_type=ModelType.OLLAMA_LOCAL,
            name_patterns=[
                r"llama",
                r"mistral",
                r"codellama",
                r"ollama",
                r"local"
            ],
            response_quirks=[
                "May have inconsistent formatting",
                "Sometimes includes model artifacts",
                "Can have encoding issues"
            ],
            cleaning_rules=[
                (r"<\|.*?\|>", ""),               # Remove special tokens
                (r"###.*?###", ""),               # Remove section headers
                (r"^\s*\d+\.\s*", ""),            # Remove numbered lists
                (r"[^\x00-\x7F]+", ""),           # Remove non-ASCII characters
            ],
            schema_preferences={
                "simple_types": True,
                "minimal_nesting": True,
                "string_fallbacks": True
            },
            prompt_adjustments={
                "json_emphasis": "Output valid JSON only. No explanations or additional text.",
                "format_strict": "Use double quotes for all strings. Ensure proper JSON syntax."
            }
        )
        
        return patterns
    
    def detect_model_type(self, context: RequestContext) -> ModelType:
        """Detect model type from context information.
        
        Args:
            context: Request context with model information
            
        Returns:
            ModelType: Detected model type
        """
        model_name = context.model_name.lower()
        
        # Check cache first
        if model_name in self.adaptation_cache:
            return self.adaptation_cache[model_name]
        
        # Try to match against known patterns
        for model_type, pattern in self.model_patterns.items():
            for name_pattern in pattern.name_patterns:
                if re.search(name_pattern, model_name, re.IGNORECASE):
                    self.adaptation_cache[model_name] = model_type
                    self.logger.info(
                        f"Detected model type {model_type.value} for {model_name}",
                        extra={'model_name': model_name, 'detected_type': model_type.value}
                    )
                    return model_type
        
        # Default to generic if no match
        self.adaptation_cache[model_name] = ModelType.GENERIC
        self.logger.info(
            f"Using generic adaptation for unknown model {model_name}",
            extra={'model_name': model_name}
        )
        return ModelType.GENERIC
    
    def preprocess_response(
        self, 
        raw_response: str, 
        context: RequestContext
    ) -> AdaptationResult:
        """Preprocess response based on detected model type.
        
        Args:
            raw_response: Raw model response
            context: Request context
            
        Returns:
            AdaptationResult: Preprocessed response with adaptations applied
        """
        model_type = self.detect_model_type(context)
        adaptations_applied = []
        warnings = []
        
        # Start with original response
        adapted_response = raw_response
        
        # Apply model-specific cleaning rules
        if model_type in self.model_patterns:
            pattern = self.model_patterns[model_type]
            
            self.logger.debug(
                f"Applying {len(pattern.cleaning_rules)} cleaning rules for {model_type.value}",
                extra={'model_type': model_type.value, 'rules_count': len(pattern.cleaning_rules)}
            )
            
            for rule_pattern, replacement in pattern.cleaning_rules:
                try:
                    before_length = len(adapted_response)
                    adapted_response = re.sub(rule_pattern, replacement, adapted_response, flags=re.DOTALL | re.MULTILINE)
                    after_length = len(adapted_response)
                    
                    if before_length != after_length:
                        adaptations_applied.append(AdaptationStrategy.RESPONSE_CLEANING)
                        self.logger.debug(
                            f"Applied cleaning rule: {rule_pattern[:50]}...",
                            extra={
                                'rule_pattern': rule_pattern,
                                'length_change': after_length - before_length
                            }
                        )
                except re.error as e:
                    warnings.append(f"Failed to apply cleaning rule {rule_pattern}: {str(e)}")
                    self.logger.warning(
                        f"Regex error in cleaning rule: {str(e)}",
                        extra={'rule_pattern': rule_pattern}
                    )
        
        # Apply generic cleaning if no specific patterns or if generic type
        if model_type == ModelType.GENERIC or not adaptations_applied:
            adapted_response = self._apply_generic_cleaning(adapted_response)
            if adapted_response != raw_response:
                adaptations_applied.append(AdaptationStrategy.RESPONSE_CLEANING)
        
        # Calculate confidence based on adaptations and response quality
        confidence_score = self._calculate_adaptation_confidence(
            raw_response, adapted_response, adaptations_applied
        )
        
        return AdaptationResult(
            success=len(adaptations_applied) > 0 or adapted_response != raw_response,
            adapted_response=adapted_response,
            adaptations_applied=adaptations_applied,
            model_type=model_type,
            confidence_score=confidence_score,
            warnings=warnings
        )
    
    def _apply_generic_cleaning(self, response: str) -> str:
        """Apply generic cleaning rules for unknown models.
        
        Args:
            response: Raw response text
            
        Returns:
            str: Cleaned response
        """
        # Generic cleaning rules that work for most models
        generic_rules = [
            (r"```(?:json)?\s*", ""),     # Remove code blocks
            (r"```\s*$", ""),             # Remove closing code blocks
            (r"^[^{\[]*", ""),            # Remove text before JSON/array
            (r"[^}\]]*$", ""),            # Remove text after JSON/array
            (r"\n\s*\n", "\n"),           # Collapse multiple newlines
            (r"^\s+|\s+$", ""),           # Trim whitespace
        ]
        
        cleaned = response
        for pattern, replacement in generic_rules:
            try:
                cleaned = re.sub(pattern, replacement, cleaned, flags=re.DOTALL | re.MULTILINE)
            except re.error:
                continue  # Skip problematic patterns
        
        return cleaned
    
    def _calculate_adaptation_confidence(
        self, 
        original: str, 
        adapted: str, 
        adaptations: List[AdaptationStrategy]
    ) -> float:
        """Calculate confidence score for adaptation result.
        
        Args:
            original: Original response
            adapted: Adapted response
            adaptations: List of adaptations applied
            
        Returns:
            float: Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.5
        
        # Increase confidence if adaptations were applied
        if adaptations:
            base_confidence += 0.2 * len(set(adaptations))
        
        # Increase confidence if response looks more JSON-like after adaptation
        if self._looks_like_json(adapted) and not self._looks_like_json(original):
            base_confidence += 0.3
        
        # Decrease confidence if response became much shorter (might have removed too much)
        length_ratio = len(adapted) / max(len(original), 1)
        if length_ratio < 0.3:
            base_confidence -= 0.2
        
        return min(1.0, max(0.0, base_confidence))
    
    def _looks_like_json(self, text: str) -> bool:
        """Check if text looks like JSON.
        
        Args:
            text: Text to check
            
        Returns:
            bool: True if text appears to be JSON
        """
        text = text.strip()
        return (
            (text.startswith('{') and text.endswith('}')) or
            (text.startswith('[') and text.endswith(']'))
        )
    
    def get_model_prompt_adjustments(self, context: RequestContext) -> Dict[str, str]:
        """Get prompt adjustments for specific model type.
        
        Args:
            context: Request context
            
        Returns:
            Dict[str, str]: Prompt adjustments by category
        """
        model_type = self.detect_model_type(context)
        
        if model_type in self.model_patterns:
            return self.model_patterns[model_type].prompt_adjustments.copy()
        
        # Generic adjustments
        return {
            "json_emphasis": "Please respond with valid JSON only.",
            "format_instruction": "Ensure proper JSON formatting with double quotes."
        }
    
    def enhance_prompt_for_model(self, prompt: str, context: RequestContext) -> str:
        """Enhance prompt with model-specific adjustments.
        
        Args:
            prompt: Original prompt
            context: Request context
            
        Returns:
            str: Enhanced prompt with model-specific adjustments
        """
        adjustments = self.get_model_prompt_adjustments(context)
        
        if not adjustments:
            return prompt
        
        # Add model-specific instructions
        enhanced_prompt = prompt
        
        # Add JSON emphasis if available
        if "json_emphasis" in adjustments:
            enhanced_prompt += f"\n\nIMPORTANT: {adjustments['json_emphasis']}"
        
        # Add format instructions if available
        if "format_instruction" in adjustments:
            enhanced_prompt += f"\n{adjustments['format_instruction']}"
        
        self.logger.debug(
            f"Enhanced prompt for model type {self.detect_model_type(context).value}",
            extra={
                'model_type': self.detect_model_type(context).value,
                'adjustments_applied': list(adjustments.keys())
            }
        )
        
        return enhanced_prompt
    
    def get_model_schema_preferences(self, context: RequestContext) -> Dict[str, Any]:
        """Get schema preferences for specific model type.
        
        Args:
            context: Request context
            
        Returns:
            Dict[str, Any]: Schema preferences
        """
        model_type = self.detect_model_type(context)
        
        if model_type in self.model_patterns:
            return self.model_patterns[model_type].schema_preferences.copy()
        
        # Generic preferences
        return {
            "strict_types": False,
            "flexible_format": True,
            "simple_structure": True
        }
    
    def get_adaptation_statistics(self) -> Dict[str, Any]:
        """Get statistics about model adaptations.
        
        Returns:
            Dict[str, Any]: Adaptation statistics
        """
        model_counts = {}
        for model_name, model_type in self.adaptation_cache.items():
            model_counts[model_type.value] = model_counts.get(model_type.value, 0) + 1
        
        return {
            "total_models_seen": len(self.adaptation_cache),
            "model_type_distribution": model_counts,
            "supported_model_types": [mt.value for mt in self.model_patterns.keys()],
            "adaptation_strategies": [strategy.value for strategy in AdaptationStrategy]
        }


# Global adaptation engine instance
_adaptation_engine: Optional[ModelAdaptationEngine] = None


def get_adaptation_engine() -> ModelAdaptationEngine:
    """Get the global model adaptation engine.
    
    Returns:
        ModelAdaptationEngine: Global adaptation engine instance
    """
    global _adaptation_engine
    if _adaptation_engine is None:
        _adaptation_engine = ModelAdaptationEngine()
    return _adaptation_engine


def preprocess_model_response(raw_response: str, context: RequestContext) -> AdaptationResult:
    """Preprocess model response with adaptation.
    
    Args:
        raw_response: Raw model response
        context: Request context
        
    Returns:
        AdaptationResult: Preprocessed response
    """
    engine = get_adaptation_engine()
    return engine.preprocess_response(raw_response, context)


def enhance_prompt_for_model(prompt: str, context: RequestContext) -> str:
    """Enhance prompt for specific model.
    
    Args:
        prompt: Original prompt
        context: Request context
        
    Returns:
        str: Enhanced prompt
    """
    engine = get_adaptation_engine()
    return engine.enhance_prompt_for_model(prompt, context)