# AI Research Assistant - Evaluation Harness
from .citation_validity import CitationValidityResult, check_citation_validity
from .dataset import GoldenCandidate, GoldenDataset, GoldenQuery, load_golden_dataset
from .harness import EvaluationReport, QueryEvaluation, run_golden_evaluation
from .metrics import mrr, ndcg_at_k, recall_at_k

__all__ = [
    "CitationValidityResult",
    "EvaluationReport",
    "GoldenCandidate",
    "GoldenDataset",
    "GoldenQuery",
    "QueryEvaluation",
    "check_citation_validity",
    "load_golden_dataset",
    "mrr",
    "ndcg_at_k",
    "recall_at_k",
    "run_golden_evaluation",
]
