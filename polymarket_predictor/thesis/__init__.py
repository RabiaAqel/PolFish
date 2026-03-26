"""Multi-tier market thesis system.

Groups related Polymarket markets (date tiers, price tiers, stage tiers)
and applies a single thesis prediction across all tiers, avoiding redundant
deep predictions for each individual market.
"""

from polymarket_predictor.thesis.grouper import MarketGrouper, MarketGroup
from polymarket_predictor.thesis.applier import ThesisApplier

__all__ = ["MarketGrouper", "ThesisApplier", "MarketGroup"]
