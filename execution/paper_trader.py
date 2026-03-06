# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - PAPER TRADER
# Simulation mode for testing strategies
# ═══════════════════════════════════════════════════════════════

import logging
import time
from typing import Dict, Optional
from datetime import datetime

from .position_manager import PositionManager, Position
from .executor import OrderResult
from core.constants import Direction, OrderSide

logger = logging.getLogger(__name__)


class PaperTrader:
    """
    Paper trading (simulation) mode

    Simulates order execution without real API calls
    """

    def __init__(self, config: Dict):
        self.config = config
        self.simulation_mode = True

        # Virtual balance
        self.initial_balance = config.get("initial_balance", 1000.0)
        self.balance = self.initial_balance

        # Position manager
        self.position_manager = PositionManager(config)

        # Trade history
        self.trade_history = []

        logger.info(f"📝 PaperTrader initialized with ${self.balance:.2f}")

    async def start(self):
        """Start paper trader"""
        logger.info("PaperTrader started (Simulation Mode)")

    async def stop(self):
        """Stop paper trader"""
        logger.info("PaperTrader stopped")

    async def get_balance(self) -> float:
        """Get current virtual balance"""
        return self.balance

    async def place_order(
        self,
        token_id: str,
        side: OrderSide,
        price: float,
        shares: float
    ) -> OrderResult:
        """Simulate placing an order"""
        order_id = f"paper_{int(time.time() * 1000)}"

        if side == OrderSide.BUY:
            # Check if we have enough balance
            cost = price * shares
            if cost > self.balance:
                return OrderResult(
                    success=False,
                    message=f"Insufficient balance: ${self.balance:.2f} < ${cost:.2f}"
                )

            # Deduct from balance
            self.balance -= cost
            logger.info(f"📝 PAPER BUY: {shares:.2f} shares @ ${price:.4f} = ${cost:.2f}")
            logger.info(f"   Balance: ${self.balance:.2f}")

        else:  # SELL
            # Add to balance
            revenue = price * shares
            self.balance += revenue
            logger.info(f"📝 PAPER SELL: {shares:.2f} shares @ ${price:.4f} = ${revenue:.2f}")
            logger.info(f"   Balance: ${self.balance:.2f}")

        # Record trade
        self.trade_history.append({
            "order_id": order_id,
            "token_id": token_id,
            "side": side.value,
            "price": price,
            "shares": shares,
            "timestamp": time.time(),
            "balance": self.balance
        })

        return OrderResult(
            success=True,
            order_id=order_id,
            message="Paper order executed",
            price=price,
            shares=shares
        )

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
        """Create a simulated position"""
        return self.position_manager.create_position(
            coin=coin,
            timeframe=timeframe,
            direction=direction,
            entry_price=entry_price,
            shares=shares,
            condition_id=condition_id,
            token_id=token_id
        )

    def close_position(
        self,
        position_key: str,
        exit_price: float,
        reason: str = "manual"
    ) -> Optional[Position]:
        """Close a simulated position"""
        position = self.position_manager.close_position(position_key, exit_price, reason)

        if position:
            # Update balance
            if position.direction == Direction.BULLISH:
                revenue = exit_price * position.shares
            else:
                # For bearish, we sell the down contract
                revenue = exit_price * position.shares

            self.balance += revenue

            pnl_sign = "+" if position.pnl >= 0 else ""
            logger.info(f"📝 PAPER CLOSE: {position.id}")
            logger.info(f"   PnL: {pnl_sign}${position.pnl:.2f} ({position.pnl_pct * 100:.2f}%)")
            logger.info(f"   Balance: ${self.balance:.2f}")

        return position

    def get_pnl(self) -> float:
        """Get total PnL"""
        return self.balance - self.initial_balance

    def get_pnl_pct(self) -> float:
        """Get PnL as percentage"""
        return (self.balance - self.initial_balance) / self.initial_balance * 100

    def get_summary(self) -> Dict:
        """Get trading summary"""
        stats = self.position_manager.get_stats_summary()
        return {
            "mode": "PAPER_TRADING",
            "initial_balance": f"${self.initial_balance:.2f}",
            "current_balance": f"${self.balance:.2f}",
            "pnl": f"${self.get_pnl():.2f}",
            "pnl_pct": f"{self.get_pnl_pct():.2f}%",
            **stats
        }

    def reset(self):
        """Reset paper trader"""
        self.balance = self.initial_balance
        self.trade_history = []
        self.position_manager = PositionManager(self.config)
        logger.info(f"📝 PaperTrader reset to ${self.balance:.2f}")