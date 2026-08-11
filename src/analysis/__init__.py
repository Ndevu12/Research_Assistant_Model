# AI Research Assistant - Analysis Module
from typing import Any

from .gap_analysis import GapAnalysisStage, analyze_gaps
from .llm import get_analysis_agent
from .synthesis import SynthesisStage, extract_papers, run_synthesis, synthesize_collective
from ..retrieval.models import (
    GapAnalysisResult,
    PaperAnalysis,
    PaperExtraction,
    ResearchReport,
    SynthesisResult,
)

__all__ = [
    "GapAnalysisResult",
    "GapAnalysisStage",
    "PaperAnalysis",
    "PaperExtraction",
    "ResearchReport",
    "SynthesisResult",
    "SynthesisStage",
    "analysis_agent",
    "analyze_gaps",
    "extract_papers",
    "get_analysis_agent",
    "run_synthesis",
    "synthesize_collective",
]


def __getattr__(name: str) -> Any:
    # "analysis_agent" stays importable but is now built lazily on first access.
    if name == "analysis_agent":
        return get_analysis_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
