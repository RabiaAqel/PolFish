"""Hybrid LLM client factory — creates per-stage LLM clients from PolFish pipeline config."""

import logging
from typing import Optional
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

# Cache to avoid creating duplicate clients
_client_cache: dict[str, LLMClient] = {}


def get_llm_for_stage(stage: str) -> LLMClient:
    """Get an LLMClient configured for a specific pipeline stage.

    Reads from polymarket_predictor.config.PIPELINE_MODELS if available,
    otherwise falls back to the default MiroFish LLM config.

    Stages: ontology, graph, profiles, simulation, report
    """
    if stage in _client_cache:
        return _client_cache[stage]

    try:
        from polymarket_predictor.config import get_stage_config
        cfg = get_stage_config(stage)

        if cfg.get("api_key"):
            client = LLMClient(
                api_key=cfg["api_key"],
                base_url=cfg["base_url"],
                model=cfg["model"],
            )
            logger.info("Hybrid LLM [%s]: %s via %s", stage, cfg["model"], cfg["base_url"][:40])
            _client_cache[stage] = client
            return client
    except Exception as e:
        logger.debug("Hybrid config not available for stage '%s': %s", stage, e)

    # Fallback to default
    client = LLMClient()
    _client_cache[stage] = client
    return client


def clear_cache():
    """Clear cached clients (useful for testing or config reload)."""
    _client_cache.clear()
