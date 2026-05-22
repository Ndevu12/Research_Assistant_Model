# -*- coding: utf-8 -*-
"""Sentence-transformers embedding provider (default: bge-small-en-v1.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from .base import EmbeddingProvider
from .cache import EmbeddingCache

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

    from ..config.settings import EmbeddingConfig


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by ``sentence-transformers``."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        batch_size: int = 32,
        cache_dir: str = "data/embeddings",
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.cache = EmbeddingCache(cache_dir)
        self._model: SentenceTransformer | None = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)

        cached_vectors, missing_indices = self.cache.partition_hits(texts, self.model_name)
        if not missing_indices:
            return np.vstack(cached_vectors)

        model = self._load_model()
        missing_texts = [texts[index] for index in missing_indices]
        encoded = model.encode(
            missing_texts,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        encoded = np.asarray(encoded, dtype=np.float32)

        self.cache.store_batch(texts, self.model_name, encoded, missing_indices)

        if len(missing_indices) == len(texts):
            return encoded

        dim = encoded.shape[1]
        output = np.zeros((len(texts), dim), dtype=np.float32)
        for index, vector in enumerate(cached_vectors):
            if vector is not None:
                output[index] = vector

        for row, index in enumerate(missing_indices):
            output[index] = encoded[row]

        return output

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return _cosine_similarity(a, b)


def create_embedding_provider(
    config: EmbeddingConfig | None = None,
) -> SentenceTransformerEmbeddingProvider:
    """Build the default embedding provider from application settings."""
    if config is None:
        from ..config.settings import get_settings

        config = get_settings().embedding

    return SentenceTransformerEmbeddingProvider(
        model_name=config.model,
        batch_size=config.batch_size,
        cache_dir=config.cache_dir,
    )
