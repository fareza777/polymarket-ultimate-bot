# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - PORTFOLIO MANAGER
# Portfolio-level risk and position management
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PortfolioStats:
    """Portfolio statistics"""
    total_balance: float = 0.0
    total_exposure: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_positions: int = 0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0


class PortfolioManager:
    """
    Manages portfolio-level risk and positions
    """

    def __init__(self, config: Dict):
        self.config = config

        # Limits
        self.max_total_exposure = config.get("max_total_exposure", 200.0)
        self.max_per_coin_exposure = config.get("max_per_coin_exposure", 75.0)
        self.max_positions_per_coin = config.get("max_positions_per_coin", 2)

        # State
        self.positions: Dict[str, Dict] = {}  # key -> position data
        self.balance = 0.0
        self.daily_pnl = 0.0

    def update_balance(self, balance: float):
        """Update total balance"""
        self.balance = balance

    def add_position(self, key: str, position_data: Dict):
        """Add a position to portfolio"""
        self.positions[key] = position_data

    def remove_position(self, key: str):
        """Remove a position from portfolio"""
        if key in self.positions:
            del self.positions[key]

    def get_total_exposure(self) -> float:
        """Get total portfolio exposure"""
        return sum(
            p.get("position_size", 0)
            for p in self.positions.values()
        )

    def get_coin_exposure(self, coin: str) -> float:
        """Get exposure for a specific coin"""
        return sum(
            p.get("position_size", 0)
            for key, p in self.positions.items()
            if key.startswith(f"{coin}_")
        )

    def can_add_position(
        self,
        coin: str,
        position_size: float
    ) -> tuple:
        """
        Check if a new position can be added

        Returns:
            (can_add, reason)
        """
        # Check total exposure
        current_exposure = self.get_total_exposure()
        if current_exposure + position_size > self.max_total_exposure:
            return False, f"Would exceed max total exposure"

        # Check per-coin exposure
        coin_exposure = self.get_coin_exposure(coin)
        if coin_exposure + position_size > self.max_per_coin_exposure:
            return False, f"Would exceed max {coin} exposure"

        # Check positions per coin
        coin_positions = sum(1 for k in self.positions if k.startswith(f"{coin}_"))
        if coin_positions >= self.max_positions_per_coin:
            return False, f"Max positions for {coin} reached"

        return True, "OK"

    def get_stats(self) -> PortfolioStats:
        """Get portfolio statistics"""
        return PortfolioStats(
            total_balance=self.balance,
            total_exposure=self.get_total_exposure(),
            open_positions=len(self.positions),
            daily_pnl=self.daily_pnl
        )

    def get_summary(self) -> Dict:
        """Get portfolio summary"""
        stats = self.get_stats()
        return {
            "total_balance": f"${stats.total_balance:.2f}",
            "total_exposure": f"${stats.total_exposure:.2f}",
            "exposure_limit": f"${self.max_total_exposure:.2f}",
            "open_positions": stats.open_positions,
            "daily_pnl": f"${self.daily_pnl:.2f}"
        }