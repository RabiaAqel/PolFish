"""Apply a thesis prediction to individual tier markets.

Given a thesis like "ceasefire 40% likely by June" or "oil heading to $90-95 range",
compute specific predictions for each tier market.
"""

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TierPrediction:
    """Prediction for a single tier within a group."""
    market_slug: str
    question: str
    market_odds: float
    predicted_probability: float
    edge: float
    side: str  # YES or NO
    confidence: str
    reasoning: str


class ThesisApplier:
    """Apply a group thesis to individual tier markets."""

    def apply_date_thesis(
        self,
        thesis_probability: float,  # Overall probability the event happens at all
        thesis_confidence: str,
        markets: list,  # List of market objects, each with different dates
    ) -> list[TierPrediction]:
        """Apply a date-tier thesis.

        Logic: If we think the event has X% chance of EVER happening,
        then earlier dates are less likely and later dates are more likely.

        The probability accumulates over time:
        - Very near-term: low (hasn't happened yet, unlikely immediately)
        - Medium-term: building up
        - Long-term: approaches the overall probability

        Example: thesis_probability = 60% (ceasefire 60% likely eventually)
        - By April 7: ~15% (too soon)
        - By April 30: ~30%
        - By June 30: ~45%
        - By December: ~58% (approaching 60%)
        """
        predictions = []

        # Sort markets by their implied deadline (use market odds as a proxy for ordering)
        # Markets with lower odds are typically nearer-term
        sorted_markets = sorted(markets, key=lambda m: self._get_yes_price(m))

        for m in sorted_markets:
            yes_price = self._get_yes_price(m)

            # The thesis probability is the "ceiling" -- no tier can exceed it
            # Scale each tier's prediction relative to the thesis
            # If market says 30% and thesis says 60%, the market might be right
            # that it's unlikely by this specific date, but the thesis adds info
            # about the overall trajectory

            # Simple approach: adjust market odds toward thesis, weighted by distance
            # Near-term markets: stay closer to current market odds
            # Far-term markets: pull more toward thesis probability
            if yes_price < 0.15:
                # Very near-term or very unlikely -> trust market more
                prediction = yes_price * 0.7 + thesis_probability * 0.05 * 0.3
            elif yes_price > 0.70:
                # Far-term -> pull toward thesis
                prediction = yes_price * 0.5 + thesis_probability * 0.5
            else:
                # Medium-term -> blend
                prediction = yes_price * 0.4 + thesis_probability * 0.3 + yes_price * 0.3

            prediction = max(0.03, min(0.97, prediction))
            edge = prediction - yes_price
            side = "YES" if edge > 0.03 else ("NO" if edge < -0.03 else "SKIP")

            predictions.append(TierPrediction(
                market_slug=m.slug,
                question=m.question,
                market_odds=yes_price,
                predicted_probability=round(prediction, 4),
                edge=round(edge, 4),
                side=side,
                confidence=thesis_confidence,
                reasoning=f"Thesis: {thesis_probability:.0%} overall. This tier at {yes_price:.0%}, adjusted to {prediction:.0%}.",
            ))

        return predictions

    def apply_price_thesis(
        self,
        thesis_prediction: float,  # Core prediction (e.g., 0.65 = price likely goes up)
        thesis_confidence: str,
        markets: list,
    ) -> list[TierPrediction]:
        """Apply a price-tier thesis.

        Logic: If we think the asset is heading UP, then:
        - HIGH markets below current price -> high probability (YES)
        - HIGH markets near current price -> moderate
        - HIGH markets far above -> low probability
        - LOW markets -> low probability (asset going up, not down)

        The thesis_prediction is interpreted as:
        - > 0.5: bullish (price going up)
        - < 0.5: bearish (price going down)
        - = 0.5: neutral
        """
        predictions = []

        is_bullish = thesis_prediction > 0.55
        is_bearish = thesis_prediction < 0.45

        for m in markets:
            yes_price = self._get_yes_price(m)
            q = m.question.lower()

            is_high_market = "high" in q or "above" in q or "over" in q
            is_low_market = "low" in q or "below" in q or "under" in q or "dip" in q or "drop" in q

            if is_high_market:
                if is_bullish:
                    # Bullish thesis + HIGH market -> slightly increase YES probability
                    adjustment = (thesis_prediction - 0.5) * 0.3
                    prediction = yes_price + adjustment
                elif is_bearish:
                    # Bearish thesis + HIGH market -> decrease YES probability
                    adjustment = (0.5 - thesis_prediction) * 0.3
                    prediction = yes_price - adjustment
                else:
                    prediction = yes_price  # Neutral, trust market
            elif is_low_market:
                if is_bearish:
                    # Bearish thesis + LOW market -> increase YES probability (price will drop)
                    adjustment = (0.5 - thesis_prediction) * 0.3
                    prediction = yes_price + adjustment
                elif is_bullish:
                    # Bullish thesis + LOW market -> decrease YES probability
                    adjustment = (thesis_prediction - 0.5) * 0.3
                    prediction = yes_price - adjustment
                else:
                    prediction = yes_price
            else:
                # Can't determine direction from question -> use thesis directly
                prediction = thesis_prediction * 0.4 + yes_price * 0.6

            prediction = max(0.03, min(0.97, prediction))
            edge = prediction - yes_price
            side = "YES" if edge > 0.03 else ("NO" if edge < -0.03 else "SKIP")

            direction = "bullish" if is_bullish else ("bearish" if is_bearish else "neutral")
            market_type = "HIGH" if is_high_market else ("LOW" if is_low_market else "unknown")

            predictions.append(TierPrediction(
                market_slug=m.slug,
                question=m.question,
                market_odds=yes_price,
                predicted_probability=round(prediction, 4),
                edge=round(edge, 4),
                side=side,
                confidence=thesis_confidence,
                reasoning=f"Thesis: {direction} ({thesis_prediction:.0%}). {market_type} market at {yes_price:.0%}, adjusted to {prediction:.0%}.",
            ))

        return predictions

    def apply_stage_thesis(
        self,
        thesis_prediction: float,  # How strong is the candidacy overall
        thesis_confidence: str,
        markets: list,
    ) -> list[TierPrediction]:
        """Apply a stage-tier thesis (nomination -> election).

        Logic: Winning an election requires winning the nomination first.
        P(win election) <= P(win nomination).
        """
        predictions = []

        for m in markets:
            yes_price = self._get_yes_price(m)
            q = m.question.lower()

            is_nomination = "nomination" in q or "nominated" in q or "primary" in q
            is_general = "presidential election" in q or "general election" in q

            if is_nomination:
                # Nomination: use thesis more directly
                prediction = thesis_prediction * 0.6 + yes_price * 0.4
            elif is_general:
                # General election: must win nomination first, then general
                # Roughly: P(general) = P(nomination) * P(general|nomination)
                # Simplify: general is harder, so discount
                prediction = thesis_prediction * 0.4 + yes_price * 0.6
            else:
                prediction = thesis_prediction * 0.5 + yes_price * 0.5

            prediction = max(0.03, min(0.97, prediction))
            edge = prediction - yes_price
            side = "YES" if edge > 0.03 else ("NO" if edge < -0.03 else "SKIP")

            predictions.append(TierPrediction(
                market_slug=m.slug,
                question=m.question,
                market_odds=yes_price,
                predicted_probability=round(prediction, 4),
                edge=round(edge, 4),
                side=side,
                confidence=thesis_confidence,
                reasoning=f"Candidacy strength: {thesis_prediction:.0%}. Market at {yes_price:.0%}, adjusted to {prediction:.0%}.",
            ))

        return predictions

    def _get_yes_price(self, market) -> float:
        """Extract YES price from market object."""
        for o in getattr(market, 'outcomes', []):
            if isinstance(o, dict) and o.get('name', '').lower() in ('yes', 'up'):
                return float(o.get('price', 0.5))
        return 0.5
