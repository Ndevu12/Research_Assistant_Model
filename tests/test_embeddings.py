# -*- coding: utf-8 -*-
"""Tests for embedding cache and provider behavior."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.embeddings.cache import EmbeddingCache
from src.embeddings.sentence_transformers import SentenceTransformerEmbeddingProvider


class TestEmbeddingCache:
    def test_round_trip(self, tmp_path) -> None:
        cache = EmbeddingCache(tmp_path)
        vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        cache.set("hello world", "test-model", vector)
        loaded = cache.get("hello world", "test-model")

        assert loaded is not None
        np.testing.assert_array_equal(loaded, vector)

    def test_cache_key_is_model_specific(self, tmp_path) -> None:
        cache = EmbeddingCache(tmp_path)
        vector_a = np.array([1.0, 0.0], dtype=np.float32)
        vector_b = np.array([0.0, 1.0], dtype=np.float32)

        cache.set("same text", "model-a", vector_a)
        cache.set("same text", "model-b", vector_b)

        np.testing.assert_array_equal(cache.get("same text", "model-a"), vector_a)
        np.testing.assert_array_equal(cache.get("same text", "model-b"), vector_b)

    def test_partition_hits(self, tmp_path) -> None:
        cache = EmbeddingCache(tmp_path)
        cache.set("cached", "model", np.array([1.0], dtype=np.float32))

        vectors, missing = cache.partition_hits(["cached", "new"], "model")

        assert vectors[0] is not None
        assert vectors[1] is None
        assert missing == [1]


class TestSentenceTransformerEmbeddingProvider:
    def test_embed_texts_uses_cache(self, tmp_path) -> None:
        provider = SentenceTransformerEmbeddingProvider(
            model_name="test-model",
            batch_size=2,
            cache_dir=str(tmp_path),
        )
        fake_vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)

        with patch.object(provider, "_load_model") as load_model:
            mock_model = MagicMock()
            mock_model.encode.return_value = fake_vectors
            load_model.return_value = mock_model

            first = provider.embed_texts(["alpha", "beta"])
            second = provider.embed_texts(["alpha", "beta"])

        np.testing.assert_array_equal(first, fake_vectors)
        np.testing.assert_array_equal(second, fake_vectors)
        mock_model.encode.assert_called_once()

    def test_similarity(self) -> None:
        provider = SentenceTransformerEmbeddingProvider(cache_dir="data/embeddings")
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([1.0, 0.0], dtype=np.float32)
        c = np.array([0.0, 1.0], dtype=np.float32)

        assert provider.similarity(a, b) == pytest.approx(1.0)
        assert provider.similarity(a, c) == pytest.approx(0.0)

    def test_embed_texts_empty(self, tmp_path) -> None:
        provider = SentenceTransformerEmbeddingProvider(cache_dir=str(tmp_path))

        result = provider.embed_texts([])

        assert result.shape == (0, 0)
