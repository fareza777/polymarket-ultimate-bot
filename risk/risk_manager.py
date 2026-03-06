# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - RISK MANAGER
# Advanced risk management and position sizing
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from core.constants import Direction, SignalStrength

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    """Risk assessment for a potential trade"""
    can_trade: bool
    position_size: float
    stop_loss_price: float
    take_profit_price: float
    risk_amount: float
    risk_reward_ratio: float
    reason: str = ""


class RiskManager:
    """
    Advanced risk management

    Features:
    - Dynamic position sizing
    - Risk per trade limits
    - Portfolio exposure management
    - Win/loss streak handling
    """

    def __init__(self, config: Dict):
        self.config = config

        # Position sizing
        self.base_position_size = config.get("base_position_size", 10.0)
        self.max_position_size = config.get("max_position_size", 50.0)
        self.max_total_exposure = config.get("max_total_exposure", 200.0)
        self.max_concurrent_positions = config.get("max_concurrent_positions", 5)

        # Risk parameters
        self.risk_per_trade_pct = config.get("risk_per_trade_pct", 0.02)  # 2% per trade
        self.stop_loss_pct = config.get("stop_loss_pct", 0.15)
        self.take_profit_pct = config.get("take_profit_pct", 0.30)

        # Streak handling
        self.reduce_on_loss_streak = config.get("reduce_on_loss_streak", True)
        self.loss_streak_count = 0
        self.win_streak_count = 0

        # State
        self.current_exposure = 0.0
        self.account_balance = 1000.0  # Will be updated

    def update_balance(self, balance: float):
        """Update account balance"""
        self.account_balance = balance

    def calculate_position_size(
        self,
        signal_score: float,
        direction: Direction,
        entry_price: float,
        is_strong_signal: bool = False
    ) -> float:
        """
        Calculate optimal position size

        Args:
            signal_score: Signal confidence score (0-100)
            direction: Trade direction
            entry_price: Entry price
            is_strong_signal: Whether this is a strong signal

        Returns:
            Position size in USDC
        """
        # Base size from config
        size = self.base_position_size

        # Scale by signal strength
        extremity = abs(signal_score - 50)
        if extremity >= 35:  # Very strong (>= 85 or <= 15)
            size *= 1.5
        elif extremity >= 20:  # Strong (>= 70 or <= 30)
            size *= 1.2

        # Strong signal multiplier
        if is_strong_signal:
            size *= 2.0

        # Adjust for loss streak
        if self.reduce_on_loss_streak and self.loss_streak_count >= 3:
            reduction = 0.5 ** (self.loss_streak_count - 2)  # Exponential reduction
            size *= reduction
            logger.warning(f"Reducing position size due to {self.loss_streak_count} loss streak")

        # Risk-based cap (max risk = 2% of account)
        max_risk = self.account_balance * self.risk_per_trade_pct
        max_size_by_risk = max_risk / self.stop_loss_pct
        size = min(size, max_size_by_risk)

        # Cap at max position size
        size = min(size, self.max_position_size)

        # Check total exposure
        remaining_exposure = self.max_total_exposure - self.current_exposure
        if size > remaining_exposure:
            size = max(0, remaining_exposure)

        return round(size, 2)

    def calculate_exit_prices(
        self,
        entry_price: float,
        direction: Direction
    ) -> Tuple[float, float]:
        """Calculate stop loss and take profit prices"""
        if direction == Direction.BULLISH:
            stop_loss = entry_price * (1 - self.stop_loss_pct)
            take_profit = entry_price * (1 + self.take_profit_pct)
        else:
            stop_loss = entry_price * (1 + self.stop_loss_pct)
            take_profit = entry_price * (1 - self.take_profit_pct)

        # Clamp to valid range
        stop_loss = max(0.01, min(0.99, stop_loss))
        take_profit = max(0.01, min(0.99, take_profit))

        return stop_loss, take_profit

    def assess_trade(
        self,
        coin: str,
        timeframe: str,
        direction: Direction,
        entry_price: float,
        signal_score: float,
        is_strong_signal: bool,
        current_positions: int,
        current_exposure: float
    ) -> RiskAssessment:
        """
        Assess a potential trade

        Returns:
            RiskAssessment with trade parameters
        """
        # Update exposure tracking
        self.current_exposure = current_exposure

        # Check if we can trade
        can_trade, reason = self._check_can_trade(
            coin, timeframe, current_positions, current_exposure
        )

        if not can_trade:
            return RiskAssessment(
                can_trade=False,
                position_size=0,
                stop_loss_price=0,
                take_profit_price=0,
                risk_amount=0,
                risk_reward_ratio=0,
                reason=reason
            )

        # Calculate position size
        position_size = self.calculate_position_size(
            signal_score, direction, entry_price, is_strong_signal
        )

        # Calculate exit prices
        stop_loss, take_profit = self.calculate_exit_prices(entry_price, direction)

        # Calculate risk
        risk_amount = position_size * self.stop_loss_pct
        reward_amount = position_size * self.take_profit_pct
        risk_reward = reward_amount / risk_amount if risk_amount > 0 else 0

        return RiskAssessment(
            can_trade=True,
            position_size=position_size,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            risk_amount=risk_amount,
            risk_reward_ratio=risk_reward,
            reason="OK"
        )

    def _check_can_trade(
        self,
        coin: str,
        timeframe: str,
        current_positions: int,
        current_exposure: float
    ) -> Tuple[bool, str]:
        """Check if trading is allowed"""
        # Check max positions
        if current_positions >= self.max_concurrent_positions:
            return False, f"Max positions reached ({current_positions}/{self.max_concurrent_positions})"

        # Check max exposure
        if current_exposure >= self.max_total_exposure:
            return False, f"Max exposure reached (${current_exposure:.2f}/${self.max_total_exposure:.2f})"

        return True, "OK"

    def record_trade_result(self, pnl: float):
        """Record trade result for streak tracking"""
        if pnl > 0:
            self.win_streak_count += 1
            self.loss_streak_count = 0
        else:
            self.loss_streak_count += 1
            self.win_streak_count = 0

    def get_risk_summary(self) -> Dict:
        """Get risk management summary"""
        return {
            "account_balance": f"${self.account_balance:.2f}",
            "current_exposure": f"${self.current_exposure:.2f}",
            "max_exposure": f"${self.max_total_exposure:.2f}",
            "base_position": f"${self.base_position_size:.2f}",
            "max_position": f"${self.max_position_size:.2f}",
            "stop_loss": f"{self.stop_loss_pct * 100:.0f}%",
            "take_profit": f"{self.take_profit_pct * 100:.0f}%",
            "win_streak": self.win_streak_count,
            "loss_streak": self.loss_streak_count
        }


# Import Tuple for type hints
from typing import Tuple