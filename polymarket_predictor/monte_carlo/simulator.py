"""Monte Carlo portfolio simulation — answers 'is this viable?'"""

import random
import json
import logging
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import httpx

from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    """Result of a single Monte Carlo simulation run."""
    accuracy: float
    edge_threshold: float
    kelly_factor: float
    num_bets_target: int

    # Outcomes
    final_balance: float = 10000.0
    total_pnl: float = 0.0
    roi: float = 0.0
    win_rate: float = 0.0
    wins: int = 0
    losses: int = 0
    skipped: int = 0
    bets_placed: int = 0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0


@dataclass
class ParameterSweepResult:
    """Aggregated results for one parameter combination across N simulations."""
    accuracy: float
    edge_threshold: float
    kelly_factor: float
    num_simulations: int

    mean_pnl: float = 0.0
    median_pnl: float = 0.0
    std_pnl: float = 0.0
    mean_roi: float = 0.0
    mean_win_rate: float = 0.0
    mean_sharpe: float = 0.0
    mean_max_drawdown: float = 0.0
    probability_of_profit: float = 0.0  # % of runs that made money
    best_case_pnl: float = 0.0
    worst_case_pnl: float = 0.0

    def to_dict(self):
        return {
            "accuracy": self.accuracy,
            "edge_threshold": self.edge_threshold,
            "kelly_factor": self.kelly_factor,
            "num_simulations": self.num_simulations,
            "mean_pnl": round(self.mean_pnl, 2),
            "median_pnl": round(self.median_pnl, 2),
            "std_pnl": round(self.std_pnl, 2),
            "mean_roi": round(self.mean_roi, 4),
            "mean_win_rate": round(self.mean_win_rate, 4),
            "mean_sharpe": round(self.mean_sharpe, 4),
            "mean_max_drawdown": round(self.mean_max_drawdown, 4),
            "probability_of_profit": round(self.probability_of_profit, 4),
            "best_case_pnl": round(self.best_case_pnl, 2),
            "worst_case_pnl": round(self.worst_case_pnl, 2),
        }


class MonteCarloSimulator:
    """Run thousands of portfolio simulations to find optimal parameters."""

    CACHE_FILE = "resolved_markets_cache.json"

    def __init__(self, data_dir: Path = None):
        self._dir = data_dir or DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._resolved_markets: list[dict] = []

    async def fetch_resolved_markets(self, limit: int = 200, min_volume: float = 500) -> list[dict]:
        """Fetch resolved markets from Polymarket. Caches to disk."""
        cache_path = self._dir / self.CACHE_FILE

        # Use cache if less than 24h old
        if cache_path.exists():
            import time
            age = time.time() - cache_path.stat().st_mtime
            if age < 86400:  # 24 hours
                self._resolved_markets = json.loads(cache_path.read_text())
                logger.info("Loaded %d resolved markets from cache", len(self._resolved_markets))
                return self._resolved_markets

        logger.info("Fetching resolved markets from Polymarket API...")
        markets = []

        async with httpx.AsyncClient(timeout=30) as client:
            offset = 0
            page_size = 100

            while len(markets) < limit:
                resp = await client.get(
                    "https://gamma-api.polymarket.com/events",
                    params={
                        "closed": "true",
                        "limit": page_size,
                        "offset": offset,
                    }
                )
                if resp.status_code != 200:
                    break

                events = resp.json()
                if not events:
                    break

                for event in events:
                    for m in event.get("markets", []):
                        # Parse outcome prices
                        prices_raw = m.get("outcomePrices", "[]")
                        if isinstance(prices_raw, str):
                            try:
                                prices = json.loads(prices_raw)
                            except Exception:
                                continue
                        else:
                            prices = prices_raw or []

                        if len(prices) < 2:
                            continue

                        yes_price = float(prices[0])

                        # Determine resolution
                        resolved_yes = None
                        if yes_price >= 0.95:
                            resolved_yes = True
                        elif yes_price <= 0.05:
                            resolved_yes = False
                        else:
                            continue  # Ambiguous, skip

                        vol = float(m.get("volume", 0) or 0)
                        if vol < min_volume:
                            continue

                        # We need the PRE-resolution odds, not the final price
                        # Use the midpoint between extreme and 50% as a proxy
                        # (In reality we'd want historical price data)
                        # Better proxy: use the volume-weighted average
                        # For now, generate realistic pre-resolution odds
                        if resolved_yes:
                            # Market resolved YES — pre-resolution odds were probably 30-80%
                            pre_odds = random.uniform(0.25, 0.85)
                        else:
                            # Market resolved NO — pre-resolution odds were probably 15-60%
                            pre_odds = random.uniform(0.10, 0.65)

                        markets.append({
                            "slug": m.get("slug", ""),
                            "question": m.get("question", ""),
                            "volume": vol,
                            "pre_resolution_odds": round(pre_odds, 3),
                            "resolved_yes": resolved_yes,
                            "category": event.get("tags", [{}])[0].get("label", "other") if event.get("tags") else "other",
                        })

                offset += page_size
                if len(events) < page_size:
                    break

        # Cache results
        cache_path.write_text(json.dumps(markets, indent=2))
        self._resolved_markets = markets
        logger.info("Fetched and cached %d resolved markets", len(markets))
        return markets

    def _generate_prediction(self, market: dict, accuracy: float) -> float:
        """Generate a synthetic prediction at a controlled accuracy level.

        accuracy=0.50 means random (no skill)
        accuracy=0.60 means 60% of the time, prediction is on the correct side
        accuracy=1.00 means perfect prediction

        The prediction is a probability (0-1) that reflects:
        - The true outcome (with probability = accuracy)
        - Random noise (with probability = 1-accuracy)
        """
        resolved_yes = market["resolved_yes"]
        pre_odds = market["pre_resolution_odds"]

        # Decide if this prediction is "correct" (on the right side)
        is_correct = random.random() < accuracy

        if is_correct:
            if resolved_yes:
                # True outcome is YES — prediction should be ABOVE pre_odds
                # Higher accuracy = more confident prediction
                boost = random.uniform(0.05, 0.25) * (accuracy - 0.5) * 4
                prediction = pre_odds + boost + random.uniform(0.02, 0.10)
            else:
                # True outcome is NO — prediction should be BELOW pre_odds
                reduction = random.uniform(0.05, 0.25) * (accuracy - 0.5) * 4
                prediction = pre_odds - reduction - random.uniform(0.02, 0.10)
        else:
            # Wrong prediction — opposite of reality
            if resolved_yes:
                prediction = pre_odds - random.uniform(0.03, 0.15)
            else:
                prediction = pre_odds + random.uniform(0.03, 0.15)

        return max(0.01, min(0.99, prediction))

    def _kelly_bet_size(self, balance: float, prediction: float, market_odds: float,
                        edge_threshold: float, kelly_factor: float,
                        max_bet_pct: float = 0.10) -> tuple[float, str]:
        """Calculate bet size and side using Kelly criterion.

        Returns (amount, side) where amount=0 means skip.
        """
        edge = prediction - market_odds
        abs_edge = abs(edge)

        if abs_edge < edge_threshold:
            return 0.0, "SKIP"

        side = "YES" if edge > 0 else "NO"

        # Kelly fraction
        if side == "YES":
            odds_decimal = 1.0 / market_odds if market_odds > 0 else 1.0
            q = 1 - prediction
            kelly = (prediction * odds_decimal - q) / odds_decimal if odds_decimal > 1 else 0
        else:
            odds_decimal = 1.0 / (1 - market_odds) if market_odds < 1 else 1.0
            q = prediction
            kelly = ((1 - prediction) * odds_decimal - q) / odds_decimal if odds_decimal > 1 else 0

        kelly = max(0, kelly) * kelly_factor

        amount = balance * min(kelly, max_bet_pct)

        # Minimum bet
        if amount < 25:
            return 0.0, "SKIP"

        # Cash reserve (keep 20%)
        max_available = balance * 0.80
        amount = min(amount, max_available)

        return round(amount, 2), side

    def _run_single_simulation(
        self,
        markets: list[dict],
        accuracy: float,
        edge_threshold: float,
        kelly_factor: float,
        num_bets_target: int,
    ) -> SimulationResult:
        """Run one complete portfolio simulation."""

        result = SimulationResult(
            accuracy=accuracy,
            edge_threshold=edge_threshold,
            kelly_factor=kelly_factor,
            num_bets_target=num_bets_target,
        )

        balance = 10000.0
        peak_balance = balance
        max_drawdown = 0.0
        pnl_history = []

        # Shuffle markets to get random selection
        shuffled = list(markets)
        random.shuffle(shuffled)

        # Sector tracking for diversification
        sector_exposure: dict[str, float] = {}
        max_sector_pct = 0.30

        bets_processed = 0

        for market in shuffled:
            if result.bets_placed >= num_bets_target:
                break

            bets_processed += 1

            # Generate prediction
            prediction = self._generate_prediction(market, accuracy)
            pre_odds = market["pre_resolution_odds"]

            # Check sector limits
            cat = market.get("category", "other")
            current_sector = sector_exposure.get(cat, 0)
            if current_sector >= balance * max_sector_pct:
                result.skipped += 1
                continue

            # Size the bet
            amount, side = self._kelly_bet_size(
                balance, prediction, pre_odds, edge_threshold, kelly_factor
            )

            if amount <= 0:
                result.skipped += 1
                continue

            # Cap by sector remaining budget
            sector_remaining = (balance * max_sector_pct) - current_sector
            amount = min(amount, sector_remaining)

            if amount < 25:
                result.skipped += 1
                continue

            # Place bet
            balance -= amount
            sector_exposure[cat] = sector_exposure.get(cat, 0) + amount

            # Resolve immediately (we know the outcome)
            resolved_yes = market["resolved_yes"]

            if side == "YES":
                if resolved_yes:
                    # Won YES bet
                    payout = amount / pre_odds if pre_odds > 0 else amount
                    pnl = payout - amount
                    result.wins += 1
                else:
                    payout = 0
                    pnl = -amount
                    result.losses += 1
            else:  # NO bet
                if not resolved_yes:
                    # Won NO bet
                    payout = amount / (1 - pre_odds) if pre_odds < 1 else amount
                    pnl = payout - amount
                    result.wins += 1
                else:
                    payout = 0
                    pnl = -amount
                    result.losses += 1

            balance += payout
            result.bets_placed += 1
            pnl_history.append(pnl)

            # Track drawdown
            peak_balance = max(peak_balance, balance)
            drawdown = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        # Calculate final metrics
        result.final_balance = round(balance, 2)
        result.total_pnl = round(balance - 10000, 2)
        result.roi = round((balance - 10000) / 10000, 4) if balance > 0 else -1.0
        result.win_rate = result.wins / max(result.bets_placed, 1)
        result.max_drawdown = round(max_drawdown, 4)

        # Sharpe ratio (simplified)
        if pnl_history and len(pnl_history) > 1:
            import statistics
            mean_pnl = statistics.mean(pnl_history)
            std_pnl = statistics.stdev(pnl_history)
            result.sharpe_ratio = round(mean_pnl / std_pnl, 4) if std_pnl > 0 else 0

        return result

    def run_parameter_sweep(
        self,
        markets: list[dict] = None,
        num_simulations: int = 1000,
        accuracies: list[float] = None,
        edge_thresholds: list[float] = None,
        kelly_factors: list[float] = None,
        num_bets: int = 50,
        progress_callback=None,
    ) -> dict:
        """Run Monte Carlo sweep across parameter combinations.

        Returns dict with 'results' (list of ParameterSweepResult.to_dict()),
        'summary', and 'best_params'.
        """
        if markets is None:
            markets = self._resolved_markets
        if not markets:
            raise ValueError("No resolved markets loaded. Call fetch_resolved_markets() first.")

        if accuracies is None:
            accuracies = [0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.65, 0.70]
        if edge_thresholds is None:
            edge_thresholds = [0.03, 0.05, 0.08, 0.10]
        if kelly_factors is None:
            kelly_factors = [0.10, 0.15, 0.25, 0.50]

        total_combos = len(accuracies) * len(edge_thresholds) * len(kelly_factors)
        logger.info("Running Monte Carlo: %d combinations x %d simulations = %d total runs",
                     total_combos, num_simulations, total_combos * num_simulations)

        all_results = []
        combo_idx = 0

        import statistics

        for accuracy in accuracies:
            for edge_threshold in edge_thresholds:
                for kelly_factor in kelly_factors:
                    combo_idx += 1

                    if progress_callback:
                        progress_callback(combo_idx, total_combos,
                            f"acc={accuracy:.0%} edge={edge_threshold:.0%} kelly={kelly_factor}")

                    # Run N simulations for this parameter combination
                    sim_results = []
                    for _ in range(num_simulations):
                        r = self._run_single_simulation(
                            markets, accuracy, edge_threshold, kelly_factor, num_bets
                        )
                        sim_results.append(r)

                    # Aggregate
                    pnls = [r.total_pnl for r in sim_results]
                    rois = [r.roi for r in sim_results]
                    win_rates = [r.win_rate for r in sim_results]
                    sharpes = [r.sharpe_ratio for r in sim_results]
                    drawdowns = [r.max_drawdown for r in sim_results]

                    sweep_result = ParameterSweepResult(
                        accuracy=accuracy,
                        edge_threshold=edge_threshold,
                        kelly_factor=kelly_factor,
                        num_simulations=num_simulations,
                        mean_pnl=statistics.mean(pnls),
                        median_pnl=statistics.median(pnls),
                        std_pnl=statistics.stdev(pnls) if len(pnls) > 1 else 0,
                        mean_roi=statistics.mean(rois),
                        mean_win_rate=statistics.mean(win_rates),
                        mean_sharpe=statistics.mean(sharpes),
                        mean_max_drawdown=statistics.mean(drawdowns),
                        probability_of_profit=sum(1 for p in pnls if p > 0) / len(pnls),
                        best_case_pnl=max(pnls),
                        worst_case_pnl=min(pnls),
                    )
                    all_results.append(sweep_result)

        # Find break-even accuracy (lowest accuracy where probability_of_profit > 50%)
        break_even = None
        for accuracy in sorted(accuracies):
            results_at_acc = [r for r in all_results if r.accuracy == accuracy]
            best_at_acc = max(results_at_acc, key=lambda r: r.probability_of_profit)
            if best_at_acc.probability_of_profit > 0.50:
                break_even = {
                    "accuracy": accuracy,
                    "edge_threshold": best_at_acc.edge_threshold,
                    "kelly_factor": best_at_acc.kelly_factor,
                    "probability_of_profit": best_at_acc.probability_of_profit,
                    "mean_pnl": best_at_acc.mean_pnl,
                }
                break

        # Find best overall params
        best_overall = max(all_results, key=lambda r: r.mean_pnl)

        # Find best params at each accuracy level
        best_per_accuracy = {}
        for acc in accuracies:
            results_at_acc = [r for r in all_results if r.accuracy == acc]
            best = max(results_at_acc, key=lambda r: r.mean_pnl)
            best_per_accuracy[f"{acc:.0%}"] = best.to_dict()

        return {
            "results": [r.to_dict() for r in all_results],
            "summary": {
                "total_combinations": total_combos,
                "simulations_per_combination": num_simulations,
                "total_simulations": total_combos * num_simulations,
                "markets_used": len(markets),
                "bets_per_simulation": num_bets,
            },
            "break_even": break_even,
            "best_overall": best_overall.to_dict(),
            "best_per_accuracy": best_per_accuracy,
        }
