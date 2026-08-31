# -*- coding: utf-8 -*-
"""Application settings with YAML defaults and environment overrides."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _default_config_dir() -> Path:
    return _project_root() / "config"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Load and merge YAML configuration files from the config directory."""
    directory = config_dir or _default_config_dir()
    merged: dict[str, Any] = {}

    default_path = directory / "default.yaml"
    if default_path.is_file():
        with default_path.open(encoding="utf-8") as handle:
            merged = yaml.safe_load(handle) or {}

    overlay_files = [
        ("llm", directory / "models.yaml"),
        ("ranking", directory / "ranking.yaml"),
        ("retrieval", directory / "providers.yaml"),
    ]
    for section, path in overlay_files:
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            overlay = yaml.safe_load(handle) or {}
        if section in merged:
            merged[section] = _deep_merge(merged[section], overlay)
        else:
            merged[section] = overlay

    return merged


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "auto"
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    temperature: float = 0.2
    timeout_seconds: int = 120


class EmbeddingConfig(BaseModel):
    model: str = "BAAI/bge-small-en-v1.5"
    batch_size: int = 32
    cache_dir: str = "data/embeddings"


class RankingWeights(BaseModel):
    semantic_relevance: float = 0.20
    citation_count: float = 0.08
    recency: float = 0.08
    venue_quality: float = 0.10
    abstract_completeness: float = 0.10
    keyword_overlap: float = 0.10
    author_prominence: float = 0.05
    embedding_similarity: float = 0.30


class RankingConfig(BaseModel):
    top_k: int = 25
    weights: RankingWeights = Field(default_factory=RankingWeights)
    domain_penalty_multiplier: float = 0.5
    outlier_embedding_gap: float = 0.12
    keyword_collision_max_sim: float = 0.40
    canonical_boost: float = 0.0


LlmMode = Literal["auto", "on", "off"]


class QueryExpansionConfig(BaseModel):
    llm_mode: LlmMode = "auto"
    llm_enabled: bool = False
    max_variants: int = 5
    max_sub_questions: int = 3


class DeduplicationConfig(BaseModel):
    enabled: bool = True
    enable_embedding_dedup: bool = True
    embedding_similarity_threshold: float = 0.92


class ClusteringConfig(BaseModel):
    min_cluster_size: int = 2
    min_samples: int = 1
    noise_merge_threshold: float = 0.5
    max_macro_clusters: int = 4


class RelevanceScoringConfig(BaseModel):
    min_rank_score: float = 0.25
    min_embedding_similarity: float = 0.35
    require_all_concepts: bool = True
    min_papers: int = 5
    concept_match_mode: str = "any_group"
    adaptive_embedding: bool = True
    keep_percentile: float = 25.0
    gap_from_top: float = 0.12


class ProviderConfig(BaseModel):
    enabled: bool = True
    limit: int = 8


class RetrievalConfig(BaseModel):
    concurrency_limit: int = 4
    per_provider_limit: int = 8
    providers: dict[str, ProviderConfig] = Field(
        default_factory=lambda: {
            "openalex": ProviderConfig(),
            "semantic_scholar": ProviderConfig(),
            "arxiv": ProviderConfig(enabled=False),
            "crossref": ProviderConfig(enabled=False),
            "pubmed": ProviderConfig(enabled=False),
            "core": ProviderConfig(enabled=False),
            "dblp": ProviderConfig(enabled=False),
        }
    )


class SnowballConfig(BaseModel):
    """Citation-graph expansion around top-ranked papers."""

    enabled: bool = True
    max_seed_papers: int = 5
    per_seed_citations: int = 5
    max_reference_fetch: int = 25
    max_new_papers: int = 30
    request_timeout_seconds: int = 30


class PipelineConfig(BaseModel):
    continue_on_stage_failure: bool = True
    stage_timeout_seconds: int = 300
    synthesis_timeout_seconds: int = 600
    stream_progress: bool = True
    debug: bool = False
    enabled_stages: dict[str, bool] = Field(
        default_factory=lambda: {
            "query_understanding": True,
            "query_expansion": True,
            "retrieval": True,
            "deduplication": True,
            "ranking": True,
            "snowball": True,
            "relevance_scoring": True,
            "clustering": True,
            "synthesis": True,
            "gap_analysis": True,
            "citation_export": True,
            "report_generation": True,
        }
    )


class MemoryConfig(BaseModel):
    db_path: str = "data/research.db"
    cache_enabled: bool = False


class SynthesisConfig(BaseModel):
    llm_mode: LlmMode = "auto"
    llm_enabled: bool = False
    max_llm_papers: int = 3
    extraction_max_retries: int = 0
    collective_max_retries: int = 0
    concurrency: int = 2
    circuit_breaker_failures: int = 2


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Load settings from merged YAML files."""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        config_dir: Path | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self.config_dir = config_dir

    def get_field_value(
        self,
        field: Any,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        config_dir = self.config_dir
        if config_dir is None:
            config_path = os.environ.get("RA_CONFIG_DIR")
            config_dir = Path(config_path) if config_path else _default_config_dir()
        return load_yaml_config(config_dir)


class AppSettings(BaseSettings):
    """Root application settings.

    Precedence (highest to lowest):
    1. Explicit constructor kwargs
    2. Environment variables (``RA_`` prefix, nested via ``__``)
    3. Merged YAML files in ``config/``
    4. Field defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="RA_",
        env_nested_delimiter="__",
        env_file=_project_root() / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    query_expansion: QueryExpansionConfig = Field(default_factory=QueryExpansionConfig)
    deduplication: DeduplicationConfig = Field(default_factory=DeduplicationConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    relevance_scoring: RelevanceScoringConfig = Field(default_factory=RelevanceScoringConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    snowball: SnowballConfig = Field(default_factory=SnowballConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_dir = None
        config_path = os.environ.get("RA_CONFIG_DIR")
        if config_path:
            config_dir = Path(config_path)

        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlSettingsSource(settings_cls, config_dir=config_dir),
        )

    @classmethod
    def from_yaml(cls, config_dir: Path | None = None, **overrides: Any) -> AppSettings:
        """Load settings from YAML with optional explicit overrides.

        Precedence: constructor overrides > process environment > YAML > defaults.

        Unlike :meth:`AppSettings`, this loader skips the project ``.env`` file so
        isolated YAML directories (for example in tests) are not affected by local
        developer overrides.
        """
        resolved_dir = config_dir or _default_config_dir()

        class _ConfiguredSettings(cls):
            @classmethod
            def settings_customise_sources(
                cls,
                settings_cls: type[BaseSettings],
                init_settings: PydanticBaseSettingsSource,
                env_settings: PydanticBaseSettingsSource,
                dotenv_settings: PydanticBaseSettingsSource,
                file_secret_settings: PydanticBaseSettingsSource,
            ) -> tuple[PydanticBaseSettingsSource, ...]:
                return (
                    init_settings,
                    env_settings,
                    YamlSettingsSource(settings_cls, config_dir=resolved_dir),
                )

        return _ConfiguredSettings(**overrides)

    @property
    def debug_enabled(self) -> bool:
        """True when verbose pipeline debugging is enabled."""
        env_debug = os.environ.get("RA_DEBUG", "").lower() in {"1", "true", "yes"}
        return self.pipeline.debug or env_debug


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Return cached application settings."""
    return AppSettings()
