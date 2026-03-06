# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - SENTIMENT STRATEGY
# Social and news sentiment based trading
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseStrategy, StrategyResult
from core.constants import Direction, StrategyType

logger = logging.getLogger(__name__)


class SentimentStrategy(BaseStrategy):
    """
    Sentiment-based trading strategy

    Uses:
    - Fear & Greed Index
    - Social media sentiment (optional)
    - News sentiment (optional)

    Strategy:
    - Extreme fear (F&G <= 25) = Contrarian bullish
    - Extreme greed (F&G >= 75) = Contrarian bearish
    """

    # Fear & Greed thresholds
    EXTREME_FEAR = 25
    EXTREME_GREED = 75
    FEAR = 40
    GREED = 60

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)

        self.use_contrarian = self.config.get("use_contrarian", True)

    def get_name(self) -> str:
        return "SentimentStrategy"

    def get_type(self) -> StrategyType:
        return StrategyType.SENTIMENT

    async def analyze(self, data: Dict[str, Any]) -> StrategyResult:
        """
        Analyze sentiment data

        Args:
            data: Must contain 'sentiment' with SentimentData

        Returns:
            StrategyResult with sentiment signals
        """
        sentiment = data.get("sentiment")
        coin = data.get("coin", "")

        if not sentiment:
            return self._create_result(
                score=50.0,
                direction=Direction.NEUTRAL,
                confidence=0.0,
                signals=["No sentiment data available"],
                indicators={},
                coin=coin,
                timeframe="sentiment"
            )

        # Get Fear & Greed
        fg_index = sentiment.fear_greed_index
        fg_label = sentiment.fear_greed_label

        # Determine direction based on contrarian strategy
        if self.use_contrarian:
            direction, score, confidence = self._contrarian_signal(fg_index)
        else:
            direction, score, confidence = self._momentum_signal(fg_index)

        # Generate signals
        signals = [
            f"Fear & Greed: {fg_index} ({fg_label})",
            f"Strategy: {'Contrarian' if self.use_contrarian else 'Momentum'}",
            f"Signal: {direction.value}"
        ]

        return self._create_result(
            score=score,
            direction=direction,
            confidence=confidence,
            signals=signals,
            indicators={
                "fear_greed_index": fg_index,
                "fear_greed_label": fg_label,
                "combined_score": sentiment.combined_score
            },
            coin=coin,
            timeframe="sentiment"
        )

    def _contrarian_signal(self, fg_index: int) -> tuple:
        """
        Contrarian strategy: buy fear, sell greed

        Returns:
            (direction, score, confidence)
        """
        if fg_index <= self.EXTREME_FEAR:
            # Extreme fear = strong bullish contrarian
            return Direction.BULLISH, 85.0, 0.8

        elif fg_index <= self.FEAR:
            # Fear = bullish contrarian
            score = 60 + (self.FEAR - fg_index)
            return Direction.BULLISH, score, 0.6

        elif fg_index >= self.EXTREME_GREED:
            # Extreme greed = strong bearish contrarian
            return Direction.BEARISH, 15.0, 0.8

        elif fg_index >= self.GREED:
            # Greed = bearish contrarian
            score = 40 - (fg_index - self.GREED)
            return Direction.BEARISH, score, 0.6

        else:
            # Neutral zone
            return Direction.NEUTRAL, 50.0, 0.3

    def _momentum_signal(self, fg_index: int) -> tuple:
        """
        Momentum strategy: follow the trend

        Returns:
            (direction, score, confidence)
        """
        if fg_index >= self.GREED:
            # Greed = bullish momentum
            score = 50 + (fg_index - 50)
            return Direction.BULLISH, score, 0.6

        elif fg_index <= self.FEAR:
            # Fear = bearish momentum
            score = 50 - (50 - fg_index)
            return Direction.BEARISH, score, 0.6

        else:
            # Neutral
            return Direction.NEUTRAL, 50.0, 0.3

    def should_trade_sentiment(self, fg_index: int) -> bool:
        """
        Check if sentiment supports trading

        Only trade on extreme readings
        """
        return fg_index <= self.EXTREME_FEAR or fg_index >= self.EXTREME_GREED