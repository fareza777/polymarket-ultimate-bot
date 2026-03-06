# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - ARBITRAGE STRATEGY
# Cross-timeframe arbitrage detection
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .base import BaseStrategy, StrategyResult
from core.constants import Direction, StrategyType

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity"""
    coin: str
    tf1: str  # Timeframe 1
    tf2: str  # Timeframe 2
    price1: float  # Price in timeframe 1
    price2: float  # Price in timeframe 2
    spread: float  # Price difference
    spread_pct: float  # Spread as percentage
    direction: str  # "buy_tf1_sell_tf2" or vice versa
    expected_profit: float
    confidence: float


class ArbitrageStrategy(BaseStrategy):
    """
    Arbitrage strategy detecting price discrepancies

    Strategies:
    1. Cross-timeframe arbitrage (5m vs 15m vs 1h)
    2. Price discrepancy between contracts
    3. Funding rate arbitrage (if available)
    """

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)

        # Minimum spread to trigger (5%)
        self.min_spread = self.config.get("min_spread", 0.05)
        # Maximum position for arbitrage
        self.max_position = self.config.get("max_position", 20.0)

        # Timeframes to compare
        self.timeframes = ["5m", "15m", "1h"]

    def get_name(self) -> str:
        return "ArbitrageStrategy"

    def get_type(self) -> StrategyType:
        return StrategyType.ARBITRAGE

    async def analyze(self, data: Dict[str, Any]) -> StrategyResult:
        """
        Analyze for arbitrage opportunities

        Args:
            data: Must contain 'market_prices' for multiple timeframes

        Returns:
            StrategyResult with arbitrage signals
        """
        coin = data.get("coin", "")

        # Get prices for all timeframes
        prices_by_tf = data.get("prices_by_timeframe", {})

        if len(prices_by_tf) < 2:
            # Not enough data for arbitrage
            return self._create_result(
                score=50.0,  # Neutral
                direction=Direction.NEUTRAL,
                confidence=0.0,
                signals=["Insufficient data for arbitrage"],
                indicators={},
                coin=coin,
                timeframe="multi"
            )

        # Find arbitrage opportunities
        opportunities = self._find_opportunities(coin, prices_by_tf)

        if not opportunities:
            return self._create_result(
                score=50.0,
                direction=Direction.NEUTRAL,
                confidence=0.0,
                signals=["No arbitrage opportunities"],
                indicators={"opportunities": []},
                coin=coin,
                timeframe="multi"
            )

        # Use best opportunity
        best = opportunities[0]

        # Convert to strategy result
        if best.direction == "buy_up":
            direction = Direction.BULLISH
            score = 50 + (best.spread_pct * 100)
        else:
            direction = Direction.BEARISH
            score = 50 - (best.spread_pct * 100)

        signals = [
            f"Arbitrage: {best.tf1} vs {best.tf2}",
            f"Spread: {best.spread_pct * 100:.2f}%",
            f"Expected profit: ${best.expected_profit:.2f}"
        ]

        return self._create_result(
            score=max(0, min(100, score)),
            direction=direction,
            confidence=best.confidence,
            signals=signals,
            indicators={
                "opportunities": [o.__dict__ for o in opportunities],
                "best_spread": best.spread_pct
            },
            coin=coin,
            timeframe=f"{best.tf1}_vs_{best.tf2}"
        )

    def _find_opportunities(
        self,
        coin: str,
        prices_by_tf: Dict[str, Dict]
    ) -> List[ArbitrageOpportunity]:
        """Find arbitrage opportunities across timeframes"""
        opportunities = []

        # Compare each pair of timeframes
        tfs = list(prices_by_tf.keys())

        for i, tf1 in enumerate(tfs):
            for tf2 in tfs[i + 1:]:
                p1 = prices_by_tf.get(tf1, {})
                p2 = prices_by_tf.get(tf2, {})

                up1 = p1.get("up_price", 0)
                up2 = p2.get("up_price", 0)

                if up1 <= 0 or up2 <= 0:
                    continue

                # Calculate spread
                spread = abs(up1 - up2)
                spread_pct = spread / min(up1, up2)

                # Check if spread is significant
                if spread_pct < self.min_spread:
                    continue

                # Determine direction
                if up1 < up2:
                    # Buy TF1 Up, it's cheaper
                    direction = "buy_up"
                    expected_profit = (up2 - up1) * self.max_position / up1
                else:
                    # Buy TF2 Up, it's cheaper
                    direction = "sell_up"
                    expected_profit = (up1 - up2) * self.max_position / up2

                # Calculate confidence based on spread
                confidence = min(1.0, spread_pct / 0.10)  # Max at 10% spread

                opp = ArbitrageOpportunity(
                    coin=coin,
                    tf1=tf1,
                    tf2=tf2,
                    price1=up1,
                    price2=up2,
                    spread=spread,
                    spread_pct=spread_pct,
                    direction=direction,
                    expected_profit=expected_profit,
                    confidence=confidence
                )

                opportunities.append(opp)

        # Sort by expected profit
        opportunities.sort(key=lambda x: x.expected_profit, reverse=True)

        return opportunities

    def check_arbitrage(
        self,
        price_5m: float,
        price_15m: float,
        price_1h: float
    ) -> Optional[Dict]:
        """
        Quick check for arbitrage between timeframes

        Returns:
            Dict with arbitrage info or None
        """
        prices = {
            "5m": {"up_price": price_5m},
            "15m": {"up_price": price_15m},
            "1h": {"up_price": price_1h}
        }

        opportunities = self._find_opportunities("BTC", prices)

        if opportunities:
            return opportunities[0].__dict__
        return None


# Import dataclass
from dataclasses import dataclass