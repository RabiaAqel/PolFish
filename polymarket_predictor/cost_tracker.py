"""Track OpenAI API token usage and compute costs across pipeline steps."""

from dataclasses import dataclass, field
from typing import Any
import threading
import logging

logger = logging.getLogger(__name__)

# GPT-4o pricing (per 1M tokens) as of 2024
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o-2024-11-20": {"input": 2.50, "output": 10.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
}
DEFAULT_PRICING = {"input": 2.50, "output": 10.00}  # Assume GPT-4o


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    step: str = ""  # Which pipeline step (ontology, graph, simulation, report)


@dataclass
class CostReport:
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    steps: list = field(default_factory=list)  # List of {step, tokens, cost}
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "steps": self.steps,
            "model": self.model,
        }


class CostTracker:
    """Thread-safe tracker that accumulates token usage across pipeline steps."""

    def __init__(self, model: str = "gpt-4o"):
        self._model = model
        self._usages: list[TokenUsage] = []
        self._lock = threading.Lock()
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        self._input_price = pricing["input"]
        self._output_price = pricing["output"]

    def record(self, prompt_tokens: int, completion_tokens: int, total_tokens: int = 0, step: str = ""):
        """Record token usage from a single API call."""
        if total_tokens == 0:
            total_tokens = prompt_tokens + completion_tokens
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            step=step,
        )
        with self._lock:
            self._usages.append(usage)
        logger.debug("Token usage [%s]: %d prompt + %d completion = %d total",
                     step, prompt_tokens, completion_tokens, total_tokens)

    def get_report(self) -> CostReport:
        """Generate a cost report from all recorded usages."""
        with self._lock:
            usages = list(self._usages)

        # Aggregate by step
        step_totals: dict[str, dict] = {}
        total_prompt = 0
        total_completion = 0

        for u in usages:
            total_prompt += u.prompt_tokens
            total_completion += u.completion_tokens
            step = u.step or "unknown"
            if step not in step_totals:
                step_totals[step] = {"prompt": 0, "completion": 0}
            step_totals[step]["prompt"] += u.prompt_tokens
            step_totals[step]["completion"] += u.completion_tokens

        total_cost = (total_prompt * self._input_price + total_completion * self._output_price) / 1_000_000

        steps = []
        for step_name, tokens in step_totals.items():
            step_cost = (tokens["prompt"] * self._input_price + tokens["completion"] * self._output_price) / 1_000_000
            steps.append({
                "step": step_name,
                "prompt_tokens": tokens["prompt"],
                "completion_tokens": tokens["completion"],
                "total_tokens": tokens["prompt"] + tokens["completion"],
                "cost_usd": round(step_cost, 4),
            })

        return CostReport(
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_prompt + total_completion,
            total_cost_usd=total_cost,
            steps=steps,
            model=self._model,
        )

    def reset(self):
        with self._lock:
            self._usages.clear()


# Global tracker instance for the current pipeline run
_current_tracker: CostTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> CostTracker | None:
    return _current_tracker


def set_tracker(tracker: CostTracker | None):
    global _current_tracker
    with _tracker_lock:
        _current_tracker = tracker
