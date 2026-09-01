# -*- coding: utf-8 -*-
"""Okapi BM25 lexical scoring over a candidate corpus.

BM25 gives ranking a proper term-frequency signal with document-length
normalization and inverse document frequency — a principled upgrade over
plain keyword-overlap ratios, and a lexical complement to embedding
similarity in hybrid ranking. Pure Python: corpora here are ranking
candidates (tens to low hundreds of documents), not web-scale indexes.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"\b\w+\b")

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens."""
    return _TOKEN_RE.findall(text.lower())


class BM25Corpus:
    """BM25 index over a fixed list of documents."""

    def __init__(
        self,
        documents: list[str],
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        self.k1 = k1
        self.b = b
        self._term_counts = [Counter(tokenize(document)) for document in documents]
        self._doc_lengths = [sum(counts.values()) for counts in self._term_counts]
        total_length = sum(self._doc_lengths)
        self._avg_doc_length = total_length / len(documents) if documents else 0.0

        document_frequency: Counter[str] = Counter()
        for counts in self._term_counts:
            document_frequency.update(counts.keys())
        self._document_frequency = document_frequency
        self._num_documents = len(documents)

    def _idf(self, term: str) -> float:
        frequency = self._document_frequency.get(term, 0)
        # BM25+ style floor keeps common terms from going negative.
        return math.log(1 + (self._num_documents - frequency + 0.5) / (frequency + 0.5))

    def score(self, query_terms: list[str], document_index: int) -> float:
        """BM25 score of one document against the query terms."""
        if self._num_documents == 0 or self._avg_doc_length == 0:
            return 0.0

        counts = self._term_counts[document_index]
        doc_length = self._doc_lengths[document_index]
        length_norm = 1 - self.b + self.b * (doc_length / self._avg_doc_length)

        total = 0.0
        for term in query_terms:
            term_frequency = counts.get(term, 0)
            if term_frequency == 0:
                continue
            total += self._idf(term) * (
                term_frequency
                * (self.k1 + 1)
                / (term_frequency + self.k1 * length_norm)
            )
        return total

    def scores(self, query: str) -> list[float]:
        """BM25 scores of every document against the query."""
        query_terms = tokenize(query)
        return [
            self.score(query_terms, index) for index in range(self._num_documents)
        ]


def normalized_bm25_scores(query: str, documents: list[str]) -> list[float]:
    """BM25 scores scaled to [0, 1] by the corpus maximum."""
    corpus = BM25Corpus(documents)
    raw = corpus.scores(query)
    peak = max(raw) if raw else 0.0
    if peak <= 0.0:
        return [0.0] * len(raw)
    return [score / peak for score in raw]
