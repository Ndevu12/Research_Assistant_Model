# AI Research Assistant - Retrieval Module

# Expose key components for easy imports
from .models import (
    EnhancedResearchReport,
    ExpandedQuerySet,
    PaperAnalysis,
    PaperCluster,
    QueryUnderstandingResult,
    RankedPaper,
    ResearchReport,
    RetrievedPaper,
    SynthesisResult,
)
from .helpers import _normalize_title, _dedupe, _openalex_abstract_from_inverted_index
from .providers import (
    ArxivProvider,
    CrossRefProvider,
    OpenAlexProvider,
    ProviderHealth,
    RetrievalProvider,
    SemanticScholarProvider,
    create_provider,
    get_enabled_providers,
    get_provider_class,
    health_check_enabled_providers,
    list_providers,
    register_provider,
    search_all_enabled,
    search_enabled_providers,
)
from .rendering import render_markdown
