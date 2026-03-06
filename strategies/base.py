# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - BASE STRATEGY
# Abstract base class for all trading strategies
# ═══════════════════════════════════════════════════════════════

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.constants import Direction, SignalStrength, StrategyType
from core.exceptions import StrategyError

logger = logging.getLogger(__name__)


@dataclass
class StrategyResult:
    """Result from strategy analysis"""
    # Core signals
    score: float  # 0-100
    direction: Direction
    strength: SignalStrength
    confidence: float  # 0.0-1.0

    # Strategy info
    strategy_name: str
    strategy_type: StrategyType

    # Details
    signals: List[str] = field(default_factory=list)
    indicators: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)

    # Market info
    coin: str = ""
    timeframe: str = ""

    # Trade parameters
    suggested_position_size: Optional[float] = None
    suggested_entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    @property
    def should_trade(self) -> bool:
        """Whether this signal should trigger a trade"""
        return (
            self.direction != Direction.NEUTRAL and
            self.confidence >= 0.5 and
            self.strength not in [SignalStrength.NONE, SignalStrength.WEAK]
        )

    @property
    def is_strong(self) -> bool:
        """Whether this is a strong signal"""
        return self.strength in [SignalStrength.STRONG, SignalStrength.VERY_STRONG]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "score": self.score,
            "direction": str(self.direction),
            "strength": str(self.strength),
            "confidence": self.confidence,
            "strategy_name": self.strategy_name,
            "signals": self.signals,
            "should_trade": self.should_trade,
            "is_strong": self.is_strong,
            "timestamp": self.timestamp.isoformat(),
            "coin": self.coin,
            "timeframe": self.timeframe
        }


class BaseStrategy(ABC):
    """
    Abstract base class for trading strategies

    All strategies must implement:
    - analyze(): Main analysis method
    - get_name(): Return strategy name
    - get_type(): Return strategy type
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._last_result: Optional[StrategyResult] = None
        self._history: List[StrategyResult] = []

    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> StrategyResult:
        """
        Analyze market data and return strategy result

        Args:
            data: Market data dictionary containing:
                - binance_state: BinanceState object
                - market_prices: MarketPrices object
                - sentiment: Optional SentimentData
                - historical_prices: Optional price history

        Returns:
            StrategyResult with signals and recommendations
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name"""
        pass

    @abstractmethod
    def get_type(self) -> StrategyType:
        """Return strategy type"""
        pass

    def get_last_result(self) -> Optional[StrategyResult]:
        """Get last analysis result"""
        return self._last_result

    def get_history(self, limit: int = 100) -> List[StrategyResult]:
        """Get analysis history"""
        return self._history[-limit:]

    def _store_result(self, result: StrategyResult):
        """Store result in history"""
        self._last_result = result
        self._history.append(result)

        # Limit history size
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

    def _create_result(
        self,
        score: float,
        direction: Direction,
        confidence: float,
        signals: List[str],
        indicators: Dict[str, Any],
        coin: str = "",
        timeframe: str = ""
    ) -> StrategyResult:
        """
        Create a strategy result with proper strength calculation
        """
        from core.constants import get_signal_strength

        strength = get_signal_strength(score, direction)

        result = StrategyResult(
            score=score,
            direction=direction,
            strength=strength,
            confidence=confidence,
            strategy_name=self.get_name(),
            strategy_type=self.get_type(),
            signals=signals,
            indicators=indicators,
            coin=coin,
            timeframe=timeframe
        )

        self._store_result(result)
        return result

    def calculate_position_size(
        self,
        base_size: float,
        max_size: float,
        strong_multiplier: float = 2.0
    ) -> float:
        """
        Calculate position size based on signal strength

        Args:
            base_size: Base position size
            max_size: Maximum position size
            strong_multiplier: Multiplier for strong signals

        Returns:
            Calculated position size
        """
        if not self._last_result:
            return base_size

        size = base_size

        # Scale by confidence
        size *= self._last_result.confidence

        # Scale by score extremity
        score = self._last_result.score
        if score >= 80 or score <= 20:
            size *= 1.5
        elif score >= 70 or score <= 30:
            size *= 1.2

        # Strong signal multiplier
        if self._last_result.is_strong:
            size *= strong_multiplier

        return min(size, max_size)

    def reset(self):
        """Reset strategy state"""
        self._last_result = None
        self._history = []