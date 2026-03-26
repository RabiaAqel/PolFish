"""Prediction cost calculator — estimates and tracks costs across pipeline stages."""

from dataclasses import dataclass, field
from polymarket_predictor.config import PIPELINE_MODELS, MODEL_PRICING, PIPELINE_PRESET, _PRESETS, get_stage_config


@dataclass
class StageEstimate:
    stage: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float


@dataclass
class PredictionCostEstimate:
    stages: list[StageEstimate]
    total_estimated_cost_usd: float
    total_estimated_tokens: int
    model_breakdown: dict  # model_name -> cost

    def to_dict(self) -> dict:
        return {
            "total_cost_usd": round(self.total_estimated_cost_usd, 4),
            "total_tokens": self.total_estimated_tokens,
            "stages": [
                {
                    "stage": s.stage,
                    "model": s.model,
                    "input_tokens": s.estimated_input_tokens,
                    "output_tokens": s.estimated_output_tokens,
                    "cost_usd": round(s.estimated_cost_usd, 4),
                }
                for s in self.stages
            ],
            "model_breakdown": {k: round(v, 4) for k, v in self.model_breakdown.items()},
        }


class CostCalculator:
    """Estimate and compare prediction costs across different model configurations."""

    # Average token usage per stage (based on observed MiroFish runs)
    DEFAULT_TOKEN_ESTIMATES = {
        "ontology": {"input": 3000, "output": 2000},
        "graph": {"input": 8000, "output": 4000},
        "profiles": {"input": 5000, "output": 6000},
        "simulation": {"input": 40000, "output": 20000},  # 15 rounds x agents
        "report": {"input": 15000, "output": 8000},
    }

    def estimate_prediction_cost(self, rounds: int = 15, agents: int = 10) -> PredictionCostEstimate:
        """Estimate cost for a single deep prediction with current config."""
        stages = []
        total_cost = 0.0
        total_tokens = 0
        model_costs = {}

        for stage_name, defaults in self.DEFAULT_TOKEN_ESTIMATES.items():
            cfg = get_stage_config(stage_name)

            # Scale simulation tokens by rounds and agents
            input_tokens = defaults["input"]
            output_tokens = defaults["output"]
            if stage_name == "simulation":
                input_tokens = int(input_tokens * (rounds / 15) * (agents / 10))
                output_tokens = int(output_tokens * (rounds / 15) * (agents / 10))

            cost = (input_tokens * cfg["price_input"] + output_tokens * cfg["price_output"]) / 1_000_000

            stages.append(StageEstimate(
                stage=stage_name,
                model=cfg["model"],
                estimated_input_tokens=input_tokens,
                estimated_output_tokens=output_tokens,
                estimated_cost_usd=cost,
            ))

            total_cost += cost
            total_tokens += input_tokens + output_tokens
            model_costs[cfg["model"]] = model_costs.get(cfg["model"], 0) + cost

        return PredictionCostEstimate(
            stages=stages,
            total_estimated_cost_usd=total_cost,
            total_estimated_tokens=total_tokens,
            model_breakdown=model_costs,
        )

    def _all_same_model_cost(self, model: str, rounds: int = 15, agents: int = 10) -> float:
        """Estimate cost if all stages used the same model."""
        pricing = MODEL_PRICING.get(model, {"input": 2.50, "output": 10.00})
        total = 0.0
        for stage_name, defaults in self.DEFAULT_TOKEN_ESTIMATES.items():
            inp = defaults["input"]
            out = defaults["output"]
            if stage_name == "simulation":
                inp = int(inp * (rounds / 15) * (agents / 10))
                out = int(out * (rounds / 15) * (agents / 10))
            total += (inp * pricing["input"] + out * pricing["output"]) / 1_000_000
        return total

    def compare_configurations(self, rounds: int = 15, agents: int = 10) -> dict:
        """Compare cost of current hybrid config vs various alternatives."""
        current = self.estimate_prediction_cost(rounds, agents)

        alternatives = {
            "all_gpt4o": {"cost_usd": round(self._all_same_model_cost("gpt-4o", rounds, agents), 4), "model": "gpt-4o", "label": "All GPT-4o"},
            "all_gpt4o_mini": {"cost_usd": round(self._all_same_model_cost("gpt-4o-mini", rounds, agents), 4), "model": "gpt-4o-mini", "label": "All GPT-4o Mini"},
            "all_deepseek": {"cost_usd": round(self._all_same_model_cost("deepseek-chat", rounds, agents), 4), "model": "deepseek-chat", "label": "All DeepSeek V3"},
            "all_gemini_flash": {"cost_usd": round(self._all_same_model_cost("gemini-2.5-flash-lite", rounds, agents), 4), "model": "gemini-2.5-flash-lite", "label": "All Gemini Flash-Lite"},
            "all_gemini_pro": {"cost_usd": round(self._all_same_model_cost("gemini-2.5-pro", rounds, agents), 4), "model": "gemini-2.5-pro", "label": "All Gemini Pro"},
            "all_claude_sonnet": {"cost_usd": round(self._all_same_model_cost("claude-sonnet-4-20250514", rounds, agents), 4), "model": "claude-sonnet-4-20250514", "label": "All Claude Sonnet"},
            "all_mistral_small": {"cost_usd": round(self._all_same_model_cost("mistral-small-latest", rounds, agents), 4), "model": "mistral-small-latest", "label": "All Mistral Small"},
        }

        # Build presets from the actual config presets
        _preset_labels = {
            "balanced": "Balanced (recommended)",
            "budget": "Budget",
            "premium": "Premium (Claude reasoning)",
            "cheapest": "Cheapest (all DeepSeek)",
            "best": "Best Quality (all GPT-4o)",
            "gemini": "Gemini (all Gemini Flash)",
        }
        _preset_descriptions = {
            "balanced": "DeepSeek prep + Gemini profiles + GPT-4o sim/report",
            "budget": "DeepSeek prep + GPT-4o-mini sim/report",
            "premium": "DeepSeek prep + Gemini profiles + Claude sim + GPT-4o report",
            "cheapest": "All DeepSeek V3 — minimum cost",
            "best": "All GPT-4o — maximum quality",
            "gemini": "All Gemini Flash — fast and cheap",
        }

        presets = {}
        for preset_key, stages in _PRESETS.items():
            cost = 0.0
            for stage_name, model in stages.items():
                pricing = MODEL_PRICING.get(model, {"input": 2.50, "output": 10.00})
                defaults = self.DEFAULT_TOKEN_ESTIMATES[stage_name]
                inp = defaults["input"]
                out = defaults["output"]
                if stage_name == "simulation":
                    inp = int(inp * (rounds / 15) * (agents / 10))
                    out = int(out * (rounds / 15) * (agents / 10))
                cost += (inp * pricing["input"] + out * pricing["output"]) / 1_000_000
            presets[preset_key] = {
                "label": _preset_labels.get(preset_key, preset_key),
                "description": _preset_descriptions.get(preset_key, ""),
                "stages": stages,
                "cost_usd": round(cost, 4),
                "cost_50": round(cost * 50, 2),
                "active": preset_key == PIPELINE_PRESET.lower().strip(),
            }

        gpt4o_cost = alternatives["all_gpt4o"]["cost_usd"]
        savings_vs_gpt4o = ((gpt4o_cost - current.total_estimated_cost_usd) / gpt4o_cost * 100) if gpt4o_cost > 0 else 0

        return {
            "current_hybrid": current.to_dict(),
            "alternatives": alternatives,
            "presets": presets,
            "savings_vs_gpt4o_percent": round(savings_vs_gpt4o, 1),
            "cost_for_50_predictions": round(current.total_estimated_cost_usd * 50, 2),
            "active_preset": PIPELINE_PRESET.lower().strip(),
            "available_models": {k: {"input": v["input"], "output": v["output"], "provider": v["provider"]} for k, v in MODEL_PRICING.items()},
        }

    def estimate_batch_cost(self, num_predictions: int, rounds: int = 15, agents: int = 10) -> dict:
        """Estimate cost for a batch of predictions."""
        single = self.estimate_prediction_cost(rounds, agents)
        return {
            "per_prediction": round(single.total_estimated_cost_usd, 4),
            "total": round(single.total_estimated_cost_usd * num_predictions, 2),
            "num_predictions": num_predictions,
            "stages": single.to_dict()["stages"],
        }
