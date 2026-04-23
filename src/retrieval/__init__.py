# AI Research Assistant - Retrieval Module

# Expose key components for easy imports
from .models import RetrievedPaper, PaperAnalysis, ResearchReport
from .helpers import _normalize_title, _dedupe, _openalex_abstract_from_inverted_index
from .openalex import search_openalex
from .semanticscholar import search_semantic_scholar
from .rendering import render_markdown
from .orchestrator import run_research_helper
