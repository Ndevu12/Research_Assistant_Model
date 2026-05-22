# -*- coding: utf-8 -*-
"""Disk cache for embedding vectors keyed by text hash."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np


class EmbeddingCache:
    """Persist embedding vectors on disk to avoid recomputation."""

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_key(self, text: str, model: str) -> str:
        """Return a stable hash key for ``text`` under ``model``."""
        payload = f"{model}\0{text}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _path_for(self, text: str, model: str) -> Path:
        return self.cache_dir / f"{self.cache_key(text, model)}.npy"

    def get(self, text: str, model: str) -> np.ndarray | None:
        path = self._path_for(text, model)
        if not path.is_file():
            return None
        return np.load(path)

    def set(self, text: str, model: str, vector: np.ndarray) -> None:
        path = self._path_for(text, model)
        np.save(path, vector)

    def partition_hits(
        self,
        texts: list[str],
        model: str,
    ) -> tuple[list[np.ndarray | None], list[int]]:
        """Split ``texts`` into cached vectors and indices needing encoding."""
        cached: list[np.ndarray | None] = []
        missing_indices: list[int] = []

        for index, text in enumerate(texts):
            vector = self.get(text, model)
            cached.append(vector)
            if vector is None:
                missing_indices.append(index)

        return cached, missing_indices

    def store_batch(
        self,
        texts: list[str],
        model: str,
        vectors: np.ndarray,
        indices: list[int],
    ) -> None:
        """Write freshly encoded vectors for ``indices`` into the cache."""
        for row, index in enumerate(indices):
            self.set(texts[index], model, vectors[row])
