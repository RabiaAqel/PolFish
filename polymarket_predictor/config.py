"""Configuration for the Polymarket Predictor module."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SEEDS_DIR = Path("/tmp/polymarket_seeds")

# Ensure dirs exist
DATA_DIR.mkdir(exist_ok=True)
SEEDS_DIR.mkdir(exist_ok=True)

# MiroFish API
MIROFISH_API_URL = os.environ.get("MIROFISH_API_URL", "http://localhost:5001/api")

# Polymarket API (no auth needed for read-only)
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"

# Simulation defaults
DEFAULT_MAX_ROUNDS = int(os.environ.get("MAX_SIMULATION_ROUNDS", os.environ.get("PREDICTOR_MAX_ROUNDS", "40")))
DEFAULT_VARIANTS = int(os.environ.get("PREDICTOR_VARIANTS", "3"))

# Signal thresholds
MIN_EDGE_THRESHOLD = float(os.environ.get("PREDICTOR_MIN_EDGE", "0.10"))  # 10% edge
MIN_VOLUME_THRESHOLD = float(os.environ.get("PREDICTOR_MIN_VOLUME", "10000"))  # $10k volume

# Template agent injection cap (organic + templates = total agent count)
# For rapid calibration: MAX_TEMPLATE_AGENTS=5
# For standard runs: MAX_TEMPLATE_AGENTS=15 (default)
# For WEEX-scale simulation: MAX_TEMPLATE_AGENTS=170
# Total agents = organic (from graph) + templates
MAX_TEMPLATE_AGENTS = int(os.environ.get("MAX_TEMPLATE_AGENTS", "15"))

# LLM (for prediction extraction fallback)
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")

# ---------------------------------------------------------------------------
# Supported providers (all OpenAI-compatible except Claude which needs adapter)
# ---------------------------------------------------------------------------
PROVIDER_DEFAULTS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "env_key": "LLM_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GEMINI_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
    "ollama": {
        "base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "env_key": "OLLAMA_API_KEY",  # Ollama doesn't need a key, but field required
    },
}

# Model pricing database (per 1M tokens: input / output)
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00, "provider": "openai"},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "provider": "openai"},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28, "provider": "deepseek"},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19, "provider": "deepseek"},
    # Gemini
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30, "provider": "gemini"},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60, "provider": "gemini"},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00, "provider": "gemini"},
    # Deprecated aliases (retiring June 2026) — kept for backward compat
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30, "provider": "gemini"},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30, "provider": "gemini"},
    # Anthropic (Claude)
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "provider": "anthropic"},
    "claude-haiku-3.5": {"input": 0.80, "output": 4.00, "provider": "anthropic"},
    # Mistral
    "mistral-small-latest": {"input": 0.10, "output": 0.30, "provider": "mistral"},
    "mistral-large-latest": {"input": 2.00, "output": 6.00, "provider": "mistral"},
    # Groq (hosted open-source, very fast)
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79, "provider": "groq"},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08, "provider": "groq"},
    # Ollama (local models, free)
    "llama3.1:8b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
    "llama3.1:70b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
    "mistral:7b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
    "qwen2.5:14b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
    "qwen2.5:72b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
    "deepseek-r1:8b": {"input": 0.0, "output": 0.0, "provider": "ollama"},
}


def _resolve_provider(model: str) -> dict:
    """Look up provider defaults for a model."""
    info = MODEL_PRICING.get(model, {})
    provider = info.get("provider", "openai")
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["openai"])


def _stage_cfg(env_prefix: str, default_model: str) -> dict:
    """Build a stage config from env vars with smart defaults."""
    model = os.environ.get(f"{env_prefix}_MODEL", default_model)
    provider = _resolve_provider(model)
    pricing = MODEL_PRICING.get(model, {"input": 2.50, "output": 10.00})
    return {
        "model": model,
        "api_key": os.environ.get(f"{env_prefix}_API_KEY", os.environ.get(provider["env_key"], "")),
        "base_url": os.environ.get(f"{env_prefix}_BASE_URL", provider["base_url"]),
        "provider": pricing.get("provider", "openai"),
        "price_input": pricing.get("input", 2.50),
        "price_output": pricing.get("output", 10.00),
    }


# ---------------------------------------------------------------------------
# Pipeline presets — switch with one env var: PIPELINE_PRESET
#
# Set PIPELINE_PRESET in .env to one of:
#   "balanced"  — DeepSeek prep + Gemini 2.5 Flash-Lite profiles + GPT-4o sim/report (~$0.42)
#   "budget"    — DeepSeek prep + GPT-4o-mini sim/report (~$0.03)
#   "premium"   — DeepSeek prep + Gemini profiles + Claude sim + GPT-4o report (~$0.54)
#   "cheapest"  — All DeepSeek (~$0.02)
#   "best"      — All GPT-4o (~$0.58)
#   "gemini"    — All Gemini 2.5 Flash (~$0.03)
#   "custom"    — Uses per-stage env vars (ONTOLOGY_MODEL, etc.)
# ---------------------------------------------------------------------------
_PRESETS = {
    "balanced": {
        "ontology": "deepseek-chat",
        "graph": "deepseek-chat",
        "profiles": "gemini-2.5-flash-lite",
        "simulation": "gpt-4o",
        "report": "gpt-4o",
    },
    "budget": {
        "ontology": "deepseek-chat",
        "graph": "deepseek-chat",
        "profiles": "deepseek-chat",
        "simulation": "gpt-4o-mini",
        "report": "gpt-4o-mini",
    },
    "premium": {
        "ontology": "deepseek-chat",
        "graph": "deepseek-chat",
        "profiles": "gemini-2.5-flash-lite",
        "simulation": "claude-sonnet-4-20250514",
        "report": "gpt-4o",
    },
    "cheapest": {
        "ontology": "deepseek-chat",
        "graph": "deepseek-chat",
        "profiles": "deepseek-chat",
        "simulation": "deepseek-chat",
        "report": "deepseek-chat",
    },
    "best": {
        "ontology": "gpt-4o",
        "graph": "gpt-4o",
        "profiles": "gpt-4o",
        "simulation": "gpt-4o",
        "report": "gpt-4o",
    },
    "gemini": {
        "ontology": "gemini-2.5-flash",
        "graph": "gemini-2.5-flash",
        "profiles": "gemini-2.5-flash-lite",
        "simulation": "gemini-2.5-flash",
        "report": "gemini-2.5-flash",
    },
    "local": {
        "ontology": "llama3.1:8b",
        "graph": "llama3.1:8b",
        "profiles": "llama3.1:8b",
        "simulation": "llama3.1:8b",
        "report": "llama3.1:8b",
    },
    "hybrid_local": {
        "ontology": "llama3.1:8b",
        "graph": "llama3.1:8b",
        "profiles": "llama3.1:8b",
        "simulation": "llama3.1:8b",
        "report": "gpt-4o",
    },
    "max_local": {
        "ontology": "llama3.1:8b",
        "graph": "llama3.1:8b",
        "profiles": "llama3.1:8b",
        "simulation": "llama3.1:8b",
        "report": "deepseek-chat",
    },
}

PIPELINE_PRESET = os.environ.get("PIPELINE_PRESET", "balanced")


def _build_pipeline_models() -> dict:
    """Build PIPELINE_MODELS from preset or custom per-stage env vars."""
    preset_name = PIPELINE_PRESET.lower().strip()
    preset = _PRESETS.get(preset_name)

    if preset_name == "custom" or preset is None:
        # Full custom: each stage from its own env var
        fallback = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
        return {
            "ontology":   _stage_cfg("ONTOLOGY",   os.environ.get("ONTOLOGY_MODEL", fallback)),
            "graph":      _stage_cfg("GRAPH",      os.environ.get("GRAPH_MODEL", fallback)),
            "profiles":   _stage_cfg("PROFILES",   os.environ.get("PROFILES_MODEL", fallback)),
            "simulation": _stage_cfg("SIMULATION", os.environ.get("SIMULATION_MODEL", fallback)),
            "report":     _stage_cfg("REPORT",     os.environ.get("REPORT_MODEL", fallback)),
        }

    # Preset-based: use preset defaults, but allow per-stage overrides
    return {
        stage: _stage_cfg(stage.upper(), os.environ.get(f"{stage.upper()}_MODEL", model))
        for stage, model in preset.items()
    }


PIPELINE_MODELS = _build_pipeline_models()

# Fallback: use the main LLM config if no stage-specific config
DEFAULT_MODEL = os.environ.get("LLM_MODEL_NAME", "gpt-4o")
DEFAULT_API_KEY = os.environ.get("LLM_API_KEY", "")
DEFAULT_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")


def get_stage_config(stage: str) -> dict:
    """Get model config for a pipeline stage. Falls back to default LLM config."""
    cfg = PIPELINE_MODELS.get(stage, {})
    api_key = cfg.get("api_key") or DEFAULT_API_KEY
    base_url = cfg.get("base_url") or DEFAULT_BASE_URL

    # Ollama doesn't need an API key, but the OpenAI client requires a non-empty string
    if cfg.get("provider") == "ollama":
        api_key = api_key or "ollama"

    return {
        "model": cfg.get("model") or DEFAULT_MODEL,
        "api_key": api_key,
        "base_url": base_url,
        "price_input": cfg.get("price_input", 2.50),
        "price_output": cfg.get("price_output", 10.00),
    }
