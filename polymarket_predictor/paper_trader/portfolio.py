"""Paper trading portfolio for simulated Polymarket betting.

Tracks virtual bets, computes P&L, and persists state to a JSONL file.
"""

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class BetRecord:
    """A single paper bet."""

    market_id: str
    slug: str
    question: str
    side: str              # "YES" or "NO"
    amount: float          # dollars wagered
    odds: float            # decimal odds at time of bet (0-1 probability)
    placed_at: str = ""
    closes_at: str = ""    # Market end date (ISO 8601)
    resolved: bool = False
    outcome_yes: Optional[bool] = None
    payout: float = 0.0
    pnl: float = 0.0
    resolved_at: str = ""
    bet_id: str = ""
    # Extra metadata for UI display
    prediction: float = 0.0       # predicted probability (0-1)
    edge: float = 0.0             # abs(prediction - odds)
    confidence: str = ""          # "high", "medium", "low"
    mode: str = "quick"           # "quick" or "deep"
    kelly_fraction: float = 0.0   # Kelly fraction used
    cost_usd: float = 0.0         # API cost for deep predictions

    def __post_init__(self) -> None:
        if not self.placed_at:
            self.placed_at = datetime.utcnow().isoformat()
        if not self.bet_id:
            ts = self.placed_at.replace(":", "").replace("-", "").replace(".", "")
            self.bet_id = f"{self.market_id}_{ts}"


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class PaperPortfolio:
    """Simulated portfolio that tracks paper bets with JSONL persistence."""

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        data_dir: Optional[Path] = None,
    ) -> None:
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "portfolio.jsonl"
        self._initial_balance = initial_balance
        self._bets: list[BetRecord] = []
        self._cash: float = initial_balance
        self._load()

    # -- persistence --------------------------------------------------------

    def _load(self) -> None:
        """Load existing bets from the JSONL file and reconstruct cash."""
        if not self._file.exists():
            logger.info("No portfolio file found — starting fresh at $%.2f", self._initial_balance)
            return

        bets: list[BetRecord] = []
        for lineno, line in enumerate(self._file.read_text().strip().split("\n"), 1):
            if not line:
                continue
            try:
                data = json.loads(line)
                bets.append(BetRecord(**data))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Skipping corrupt line %d in %s: %s", lineno, self._file, exc)

        self._bets = bets
        # Reconstruct cash balance from history
        cash = self._initial_balance
        for bet in self._bets:
            cash -= bet.amount
            if bet.resolved:
                cash += bet.payout
        self._cash = cash
        logger.info(
            "Loaded %d bets from %s — balance $%.2f",
            len(self._bets),
            self._file,
            self._cash,
        )

    def _save(self) -> None:
        """Rewrite the full JSONL file from in-memory state."""
        with open(self._file, "w") as fh:
            for bet in self._bets:
                fh.write(json.dumps(asdict(bet)) + "\n")

    def _append(self, bet: BetRecord) -> None:
        """Append a single bet to the file (fast path for new bets)."""
        with open(self._file, "a") as fh:
            fh.write(json.dumps(asdict(bet)) + "\n")

    # -- properties ---------------------------------------------------------

    @property
    def balance(self) -> float:
        """Current available cash."""
        return self._cash

    @property
    def total_value(self) -> float:
        """Cash plus unrealised value of open positions.

        Open positions are valued at their wagered amount (conservative).
        """
        open_value = sum(b.amount for b in self._bets if not b.resolved)
        return self._cash + open_value

    # -- betting ------------------------------------------------------------

    def place_bet(
        self,
        market_id: str,
        slug: str,
        question: str,
        side: str,
        amount: float,
        odds: float,
        closes_at: str = "",
        prediction: float = 0.0,
        edge: float = 0.0,
        confidence: str = "",
        mode: str = "quick",
        kelly_fraction: float = 0.0,
        cost_usd: float = 0.0,
    ) -> BetRecord:
        """Record a new paper bet and deduct from balance.

        Args:
            market_id: Polymarket condition ID.
            slug: Market slug for display.
            question: Human-readable market question.
            side: ``"YES"`` or ``"NO"``.
            amount: Dollar amount to wager.
            odds: Decimal probability (0-1) at time of bet.

        Returns:
            The created :class:`BetRecord`.

        Raises:
            ValueError: If balance is insufficient or inputs are invalid.
        """
        side = side.upper()
        if side not in ("YES", "NO"):
            raise ValueError(f"side must be 'YES' or 'NO', got '{side}'")
        if amount <= 0:
            raise ValueError(f"amount must be positive, got {amount}")
        if not 0 < odds < 1:
            raise ValueError(f"odds must be between 0 and 1 exclusive, got {odds}")
        if amount > self._cash:
            raise ValueError(
                f"Insufficient balance: need ${amount:.2f} but only ${self._cash:.2f} available"
            )

        bet = BetRecord(
            market_id=market_id,
            slug=slug,
            question=question,
            side=side,
            amount=amount,
            odds=odds,
            closes_at=closes_at,
            prediction=prediction,
            edge=edge,
            confidence=confidence,
            mode=mode,
            kelly_fraction=kelly_fraction,
            cost_usd=cost_usd,
        )
        self._cash -= amount
        self._bets.append(bet)
        self._append(bet)

        logger.info(
            "Placed %s bet of $%.2f on '%s' at %.1f%% odds — balance $%.2f",
            side,
            amount,
            slug,
            odds * 100,
            self._cash,
        )
        return bet

    def resolve_bet(self, market_id: str, outcome_yes: bool) -> list[BetRecord]:
        """Resolve all open bets for a market.

        P&L logic:
        - Bet YES and resolved YES: payout = amount / odds
        - Bet YES and resolved NO:  payout = 0  (lose amount)
        - Bet NO  and resolved NO:  payout = amount / (1 - odds)
        - Bet NO  and resolved YES: payout = 0  (lose amount)

        Returns:
            List of resolved :class:`BetRecord` objects.
        """
        resolved: list[BetRecord] = []
        for bet in self._bets:
            if bet.market_id != market_id or bet.resolved:
                continue

            bet.resolved = True
            bet.outcome_yes = outcome_yes
            bet.resolved_at = datetime.utcnow().isoformat()

            won = (bet.side == "YES" and outcome_yes) or (
                bet.side == "NO" and not outcome_yes
            )

            if won:
                if bet.side == "YES":
                    bet.payout = bet.amount / bet.odds
                else:
                    bet.payout = bet.amount / (1.0 - bet.odds)
            else:
                bet.payout = 0.0

            bet.pnl = bet.payout - bet.amount
            self._cash += bet.payout
            resolved.append(bet)

            logger.info(
                "Resolved bet %s — %s, payout $%.2f, P&L $%.2f",
                bet.bet_id,
                "WON" if won else "LOST",
                bet.payout,
                bet.pnl,
            )

        if resolved:
            self._save()  # rewrite to update resolved fields
        else:
            logger.warning("No open bets found for market_id=%s", market_id)

        return resolved

    # -- queries ------------------------------------------------------------

    def get_open_positions(self) -> list[BetRecord]:
        """Return all unresolved bets."""
        return [b for b in self._bets if not b.resolved]

    def get_resolved_positions(self) -> list[BetRecord]:
        """Return all resolved bets with P&L."""
        return [b for b in self._bets if b.resolved]

    def get_performance(self) -> dict:
        """Compute aggregate performance metrics.

        Returns:
            Dict with keys: total_bets, wins, losses, win_rate,
            total_pnl, roi, sharpe_ratio, max_drawdown.
        """
        resolved = self.get_resolved_positions()
        total_bets = len(resolved)

        if total_bets == 0:
            return {
                "total_bets": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "roi": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
            }

        wins = sum(1 for b in resolved if b.pnl > 0)
        losses = total_bets - wins
        total_pnl = sum(b.pnl for b in resolved)
        total_wagered = sum(b.amount for b in resolved)
        roi = (total_pnl / total_wagered) * 100 if total_wagered else 0.0

        # Sharpe ratio: mean(returns) / std(returns), annualised assuming daily bets
        returns = [b.pnl / b.amount if b.amount else 0.0 for b in resolved]
        mean_r = sum(returns) / len(returns)
        var_r = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std_r = math.sqrt(var_r) if var_r > 0 else 0.0
        sharpe = (mean_r / std_r) * math.sqrt(252) if std_r > 0 else 0.0

        # Max drawdown over cumulative P&L curve
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for bet in resolved:
            cumulative += bet.pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_bets": total_bets,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total_bets) * 100,
            "total_pnl": round(total_pnl, 2),
            "roi": round(roi, 2),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 2),
        }


# ---------------------------------------------------------------------------
# Bet sizer
# ---------------------------------------------------------------------------


class BetSizer:
    """Kelly-criterion bet sizing for paper trading."""

    @staticmethod
    def kelly_fraction(probability: float, odds: float, kelly_factor: float = 0.25) -> float:
        """Compute fractional Kelly bet size.

        Uses the formula for binary outcome bets:
            f* = (p * b - q) / b
        where b = (1/odds - 1) is the net decimal odds payout ratio,
        p = probability of winning, q = 1 - p.

        Scaled by *kelly_factor* (default quarter-Kelly) for safety.

        Args:
            probability: Estimated true probability of YES outcome (0-1).
            odds: Market implied probability / price (0-1).
            kelly_factor: Fraction of full Kelly to use.

        Returns:
            Suggested fraction of bankroll to bet (>= 0).
        """
        if not (0 < probability < 1) or not (0 < odds < 1):
            return 0.0

        # Net payout ratio for a YES bet at price `odds`:
        # You pay `odds` per share and receive 1 if correct → net gain = 1/odds - 1
        b = (1.0 / odds) - 1.0
        p = probability
        q = 1.0 - p

        f_star = (p * b - q) / b if b > 0 else 0.0
        return max(0.0, f_star * kelly_factor)

    @staticmethod
    def size_bet(
        balance: float,
        probability: float,
        market_odds: float,
        edge: float,
        confidence: str,
        max_bet_pct: float = 0.05,
        min_edge: float = 0.03,
    ) -> dict:
        """Compute the recommended bet amount.

        Args:
            balance: Current available cash.
            probability: Estimated true probability (0-1).
            market_odds: Current market price / implied probability (0-1).
            edge: Absolute edge (|probability - market_odds|).
            confidence: ``"high"``, ``"medium"``, or ``"low"``.
            max_bet_pct: Maximum fraction of balance for a single bet.
            min_edge: Minimum edge required to place a bet.

        Returns:
            Dict with: amount, side, kelly_fraction, reasoning.
            ``amount`` is 0 if the bet should be skipped.
        """
        confidence_scale = {"high": 1.0, "medium": 0.6, "low": 0.3}
        conf_factor = confidence_scale.get(confidence.lower(), 0.3)

        # Determine side
        if probability > market_odds:
            side = "YES"
            bet_prob = probability
            bet_odds = market_odds
        else:
            side = "NO"
            bet_prob = 1.0 - probability
            bet_odds = 1.0 - market_odds

        # Check minimum edge
        if edge < min_edge:
            return {
                "amount": 0.0,
                "side": side,
                "kelly_fraction": 0.0,
                "reasoning": f"Edge {edge:.1%} below minimum threshold {min_edge:.1%}",
            }

        # Kelly sizing
        kf = BetSizer.kelly_fraction(bet_prob, bet_odds)
        adjusted_kf = kf * conf_factor

        # Cap at max_bet_pct
        bet_fraction = min(adjusted_kf, max_bet_pct)
        amount = balance * bet_fraction

        # Enforce minimum bet
        min_bet = 10.0
        if amount < min_bet:
            if balance >= min_bet and edge >= min_edge:
                amount = min_bet
                reasoning = f"Kelly ${balance * adjusted_kf:.2f} below minimum — using ${min_bet:.2f}"
            else:
                return {
                    "amount": 0.0,
                    "side": side,
                    "kelly_fraction": round(adjusted_kf, 6),
                    "reasoning": f"Computed bet ${amount:.2f} below ${min_bet:.2f} minimum",
                }
        else:
            amount = round(amount, 2)
            reasoning = (
                f"Kelly fraction {kf:.4f} * confidence {conf_factor:.1f} = "
                f"{adjusted_kf:.4f} -> ${amount:.2f} "
                f"(capped at {max_bet_pct:.0%} of ${balance:.2f})"
            )

        return {
            "amount": amount,
            "side": side,
            "kelly_fraction": round(adjusted_kf, 6),
            "reasoning": reasoning,
        }
