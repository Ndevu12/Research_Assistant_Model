# -*- coding: utf-8 -*-
"""Core pipeline infrastructure."""

from .context import PipelineContext, ResearchSession, StageResult
from .events import PipelineEventBus, StageEventCollector, get_event_bus
from .metrics import PipelineMetrics
from .pipeline import PipelineStage, ResearchPipeline, ResearchPipelineResult
from .registry import PluginRegistry, bootstrap_default_plugins, get_registry, register_retrieval_provider, register_stage

__all__ = [
    "PipelineContext",
    "PipelineEventBus",
    "PipelineMetrics",
    "PipelineStage",
    "PluginRegistry",
    "ResearchPipeline",
    "ResearchPipelineResult",
    "ResearchSession",
    "StageEventCollector",
    "StageResult",
    "bootstrap_default_plugins",
    "get_event_bus",
    "get_registry",
    "register_retrieval_provider",
    "register_stage",
]
