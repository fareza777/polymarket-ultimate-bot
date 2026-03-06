# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - POSITION MANAGER
# Track and manage open positions
# ═══════════════════════════════════════════════════════════════

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from core.constants import Direction, PositionStatus

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open trading position"""
    id: str
    coin: str
    timeframe: str
    direction: Direction
    entry_price: float
    shares: float
    entry_time: float
    condition_id: str
    token_id: str

    # Exit parameters
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    max_hold_time: datetime = None

    # Status
    status: PositionStatus = PositionStatus.OPEN
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""

    def __post_init__(self):
        if self.max_hold_time is None:
            self.max_hold_time = datetime.now() + timedelta(minutes=30)

    @property
    def age_seconds(self) -> float:
        """Position age in seconds"""
        if self.exit_time:
            return self.exit_time - self.entry_time
        return time.time() - self.entry_time

    @property
    def is_expired(self) -> bool:
        """Check if position exceeded max hold time"""
        return datetime.now() > self.max_hold_time

    @property
    def position_size(self) -> float:
        """Total position value"""
        return self.entry_price * self.shares

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "coin": self.coin,
            "timeframe": self.timeframe,
            "direction": str(self.direction),
            "entry_price": self.entry_price,
            "shares": self.shares,
            "position_size": self.position_size,
            "age_seconds": self.age_seconds,
            "status": str(self.status),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct
        }


@dataclass
class TradeStats:
    """Trading statistics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0


class PositionManager:
    """
    Manages all open positions and trade history
    """

    def __init__(self, config: Dict):
        self.config = config

        # Position settings
        self.stop_loss_pct = config.get("stop_loss_pct", 0.15)
        self.take_profit_pct = config.get("take_profit_pct", 0.30)
        self.max_hold_time_seconds = config.get("max_hold_time_seconds", 1800)
        self.min_hold_time_seconds = config.get("min_hold_time_seconds", 60)

        # Cooldowns
        self.cooldown_after_win = config.get("cooldown_after_win", 300)
        self.cooldown_after_loss = config.get("cooldown_after_loss", 600)

        # State
        self.open_positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self.stats = TradeStats()

        self.last_win_time: Optional[float] = None
        self.last_loss_time: Optional[float] = None

    def create_position(
        self,
        coin: str,
        timeframe: str,
        direction: Direction,
        entry_price: float,
        shares: float,
        condition_id: str,
        token_id: str
    ) -> Position:
        """Create a new position"""
        position_id = f"{coin}_{timeframe}_{int(time.time())}"

        # Calculate exit prices
        stop_loss, take_profit = self._calculate_exit_prices(entry_price, direction)

        position = Position(
            id=position_id,
            coin=coin,
            timeframe=timeframe,
            direction=direction,
            entry_price=entry_price,
            shares=shares,
            entry_time=time.time(),
            condition_id=condition_id,
            token_id=token_id,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            max_hold_time=datetime.now() + timedelta(seconds=self.max_hold_time_seconds)
        )

        key = f"{coin}_{timeframe}"
        self.open_positions[key] = position

        logger.info(f"📊 Position created: {position_id}")
        logger.info(f"   Entry: ${entry_price:.4f} | Shares: {shares:.2f} | Size: ${position.position_size:.2f}")
        logger.info(f"   SL: ${stop_loss:.4f} | TP: ${take_profit:.4f}")

        return position

    def _calculate_exit_prices(
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

    def check_exit_conditions(self, position: Position, current_price: float) -> Optional[str]:
        """
        Check if position should be exited

        Returns:
            Exit reason or None
        """
        # Check time-based exit
        if position.is_expired:
            return "max_hold_time"

        # Check minimum hold time
        if position.age_seconds < self.min_hold_time_seconds:
            return None

        # Check price-based exits
        if position.direction == Direction.BULLISH:
            if current_price <= position.stop_loss_price:
                return "stop_loss"
            elif current_price >= position.take_profit_price:
                return "take_profit"
        else:
            if current_price >= position.stop_loss_price:
                return "stop_loss"
            elif current_price <= position.take_profit_price:
                return "take_profit"

        return None

    def close_position(
        self,
        position_key: str,
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[Position]:
        """Close an open position"""
        if position_key not in self.open_positions:
            logger.warning(f"Position not found: {position_key}")
            return None

        position = self.open_positions[position_key]

        # Calculate PnL
        if position.direction == Direction.BULLISH:
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - exit_price) / position.entry_price

        pnl = pnl_pct * position.entry_price * position.shares

        # Update position
        position.exit_price = exit_price
        position.exit_time = time.time()
        position.pnl = pnl
        position.pnl_pct = pnl_pct
        position.exit_reason = reason

        # Update status
        if reason == "take_profit":
            position.status = PositionStatus.TAKEN_PROFIT
        elif reason == "stop_loss":
            position.status = PositionStatus.STOPPED
        else:
            position.status = PositionStatus.CLOSED

        # Update stats
        self._update_stats(position)

        # Move to closed
        self.closed_positions.append(position)
        del self.open_positions[position_key]

        pnl_sign = "+" if pnl >= 0 else ""
        logger.info(f"🔒 Position closed: {position.id}")
        logger.info(f"   Exit: ${exit_price:.4f} | PnL: {pnl_sign}${pnl:.2f} ({pnl_pct * 100:.2f}%) | Reason: {reason}")

        return position

    def _update_stats(self, position: Position):
        """Update trading statistics"""
        self.stats.total_trades += 1
        self.stats.total_pnl += position.pnl

        if position.pnl > 0:
            self.stats.winning_trades += 1
            self.last_win_time = position.exit_time
        else:
            self.stats.losing_trades += 1
            self.last_loss_time = position.exit_time

        # Update win rate
        if self.stats.total_trades > 0:
            self.stats.win_rate = self.stats.winning_trades / self.stats.total_trades

    def can_enter_trade(self, coin: str, timeframe: str) -> Tuple[bool, str]:
        """
        Check if we can enter a new trade

        Returns:
            (can_enter, reason)
        """
        # Check cooldown after win
        if self.last_win_time:
            time_since = time.time() - self.last_win_time
            if time_since < self.cooldown_after_win:
                remaining = self.cooldown_after_win - time_since
                return False, f"Cooldown after win ({remaining:.0f}s remaining)"

        # Check cooldown after loss
        if self.last_loss_time:
            time_since = time.time() - self.last_loss_time
            if time_since < self.cooldown_after_loss:
                remaining = self.cooldown_after_loss - time_since
                return False, f"Cooldown after loss ({remaining:.0f}s remaining)"

        # Check if already have position
        key = f"{coin}_{timeframe}"
        if key in self.open_positions:
            return False, f"Already have position for {coin} {timeframe}"

        # Check max concurrent positions
        if len(self.open_positions) >= 5:
            return False, "Max concurrent positions reached (5)"

        return True, "OK"

    def get_total_exposure(self) -> float:
        """Get total exposure from open positions"""
        return sum(p.position_size for p in self.open_positions.values())

    def get_stats_summary(self) -> Dict:
        """Get trading statistics summary"""
        return {
            "total_trades": self.stats.total_trades,
            "winning_trades": self.stats.winning_trades,
            "losing_trades": self.stats.losing_trades,
            "win_rate": f"{self.stats.win_rate * 100:.1f}%",
            "total_pnl": f"${self.stats.total_pnl:.2f}",
            "open_positions": len(self.open_positions),
            "total_exposure": f"${self.get_total_exposure():.2f}"
        }


# Import Tuple for type hints
from typing import Tuple