# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - COMBINED STRATEGY
# Multi-strategy combination with weighted signals
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .base import BaseStrategy, StrategyResult
from .signal_strategy import SignalStrategy
from .arbitrage import ArbitrageStrategy
from .sentiment import SentimentStrategy
from core.constants import Direction, StrategyType

logger = logging.getLogger(__name__)


class CombinedStrategy(BaseStrategy):
    """
    Combined multi-strategy approach

    Weights:
    - Signal Strategy: 50%
    - Arbitrage Strategy: 30%
    - Sentiment Strategy: 20%

    Total score is weighted combination of all strategies
    """

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)

        # Strategy weights (should sum to 1.0)
        self.signal_weight = self.config.get("signal_weight", 0.50)
        self.arbitrage_weight = self.config.get("arbitrage_weight", 0.30)
        self.sentiment_weight = self.config.get("sentiment_weight", 0.20)

        # Initialize sub-strategies
        self.signal_strategy = SignalStrategy(config)
        self.arbitrage_strategy = ArbitrageStrategy(config)
        self.sentiment_strategy = SentimentStrategy(config)

        # Cache results
        self._last_signal_result: Optional[StrategyResult] = None
        self._last_arbitrage_result: Optional[StrategyResult] = None
        self._last_sentiment_result: Optional[StrategyResult] = None

    def get_name(self) -> str:
        return "CombinedStrategy"

    def get_type(self) -> StrategyType:
        return StrategyType.COMBINED

    async def analyze(self, data: Dict[str, Any]) -> StrategyResult:
        """
        Run all strategies and combine results

        Args:
            data: Market data for all strategies

        Returns:
            Combined StrategyResult
        """
        coin = data.get("coin", "")
        timeframe = data.get("timeframe", "5m")

        # Run each strategy
        results = {}

        try:
            self._last_signal_result = await self.signal_strategy.analyze(data)
            results["signal"] = self._last_signal_result
        except Exception as e:
            logger.warning(f"Signal strategy error: {e}")

        try:
            self._last_arbitrage_result = await self.arbitrage_strategy.analyze(data)
            results["arbitrage"] = self._last_arbitrage_result
        except Exception as e:
            logger.warning(f"Arbitrage strategy error: {e}")

        try:
            self._last_sentiment_result = await self.sentiment_strategy.analyze(data)
            results["sentiment"] = self._last_sentiment_result
        except Exception as e:
            logger.warning(f"Sentiment strategy error: {e}")

        # Combine scores
        combined_score, combined_direction, combined_confidence = self._combine_results(results)

        # Collect all signals
        all_signals = []
        for strategy_name, result in results.items():
            all_signals.extend([f"[{strategy_name}] {s}" for s in result.signals])

        # Collect indicators
        indicators = {
            "signal_score": results.get("signal", StrategyResult(50, Direction.NEUTRAL, None, 0, "", StrategyType.SIGNAL)).score,
            "arbitrage_score": results.get("arbitrage", StrategyResult(50, Direction.NEUTRAL, None, 0, "", StrategyType.ARBITRAGE)).score,
            "sentiment_score": results.get("sentiment", StrategyResult(50, Direction.NEUTRAL, None, 0, "", StrategyType.SENTIMENT)).score,
            "weights": {
                "signal": self.signal_weight,
                "arbitrage": self.arbitrage_weight,
                "sentiment": self.sentiment_weight
            }
        }

        return self._create_result(
            score=combined_score,
            direction=combined_direction,
            confidence=combined_confidence,
            signals=all_signals[:10],  # Limit to 10 signals
            indicators=indicators,
            coin=coin,
            timeframe=timeframe
        )

    def _combine_results(self, results: Dict[str, StrategyResult]) -> tuple:
        """
        Combine multiple strategy results into one

        Returns:
            (score, direction, confidence)
        """
        # Weight the scores
        weighted_score = 50.0  # Start neutral
        total_weight = 0.0

        # Direction votes
        direction_votes = {
            Direction.BULLISH: 0.0,
            Direction.BEARISH: 0.0,
            Direction.NEUTRAL: 0.0
        }

        # Confidence tracking
        confidences = []

        if "signal" in results:
            r = results["signal"]
            # Normalize score to 0-100 range (from -100 to +100)
            normalized = (r.score + 100) / 2 if r.score < 0 else r.score
            weighted_score += (normalized - 50) * self.signal_weight
            direction_votes[r.direction] += self.signal_weight * r.confidence
            confidences.append(r.confidence)
            total_weight += self.signal_weight

        if "arbitrage" in results:
            r = results["arbitrage"]
            if r.direction != Direction.NEUTRAL:
                weighted_score += (r.score - 50) * self.arbitrage_weight
                direction_votes[r.direction] += self.arbitrage_weight * r.confidence
                confidences.append(r.confidence)
            total_weight += self.arbitrage_weight

        if "sentiment" in results:
            r = results["sentiment"]
            if r.direction != Direction.NEUTRAL:
                weighted_score += (r.score - 50) * self.sentiment_weight
                direction_votes[r.direction] += self.sentiment_weight * r.confidence
                confidences.append(r.confidence)
            total_weight += self.sentiment_weight

        # Determine final direction
        max_vote = max(direction_votes.values())
        if max_vote > 0:
            for direction, vote in direction_votes.items():
                if vote == max_vote:
                    final_direction = direction
                    break
        else:
            final_direction = Direction.NEUTRAL

        # Average confidence
        final_confidence = sum(confidences) / len(confidences) if confidences else 0.3

        # Clamp score
        final_score = max(0, min(100, weighted_score))

        return final_score, final_direction, final_confidence

    def get_signal_result(self) -> Optional[StrategyResult]:
        """Get last signal strategy result"""
        return self._last_signal_result

    def get_arbitrage_result(self) -> Optional[StrategyResult]:
        """Get last arbitrage strategy result"""
        return self._last_arbitrage_result

    def get_sentiment_result(self) -> Optional[StrategyResult]:
        """Get last sentiment strategy result"""
        return self._last_sentiment_result

    def update_weights(self, signal: float, arbitrage: float, sentiment: float):
        """Update strategy weights"""
        total = signal + arbitrage + sentiment
        if total > 0:
            self.signal_weight = signal / total
            self.arbitrage_weight = arbitrage / total
            self.sentiment_weight = sentiment / total
            logger.info(f"Updated weights: signal={self.signal_weight:.2f}, "
                       f"arbitrage={self.arbitrage_weight:.2f}, "
                       f"sentiment={self.sentiment_weight:.2f}")