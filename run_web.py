#!/usr/bin/env python3
#
# POLYMARKET ULTIMATE BOT - RUN WITH WEB DASHBOARD
# Runs bot + web dashboard together
#

import asyncio
import threading
import time
import logging
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.constants import Direction
from data.binance_feed import BinanceFeed
from data.polymarket_feed import PolymarketFeed
from data.market_discovery import MarketDiscovery
from data.sentiment_feed import SentimentFeed
from strategies.combined import CombinedStrategy
from execution.paper_trader import PaperTrader
from risk.risk_manager import RiskManager
from execution.position_manager import PositionManager
from monitoring.logger import setup_logger

# Web dashboard
from web_dashboard import (
    app, socketio, dashboard_state,
    update_market_data, update_signal, update_positions,
    update_pnl, update_sentiment, update_system_status
)

logger = setup_logger("polymarket_bot", "INFO", "polymarket_bot.log")


class BotWithWebDashboard:
    """Bot that updates web dashboard"""

    def __init__(self):
        self.config = get_config()
        self.running = False

        # Components
        self.polymarket_feed = None
        self.market_discovery = None
        self.sentiment_feed = None
        self.strategy = None
        self.paper_trader = None
        self.risk_manager = RiskManager({
            "base_position_size": self.config.risk.base_position_size,
            "max_position_size": self.config.risk.max_position_size,
        })
        self.position_manager = PositionManager({
            "stop_loss_pct": self.config.risk.stop_loss_pct,
            "take_profit_pct": self.config.risk.take_profit_pct,
        })

        self.binance_feeds = {}

    async def start(self):
        """Start the bot"""
        logger.info("Starting Polymarket Ultimate Bot with Web Dashboard...")
        self.running = True

        # Initialize feeds
        await self._init_feeds()
        await self._init_strategy()

        # Initialize paper trader
        self.paper_trader = PaperTrader({
            "initial_balance": 1000.0,
            "stop_loss_pct": 0.15,
            "take_profit_pct": 0.30
        })
        await self.paper_trader.start()

        update_pnl(1000.0, 0, 0.0)

        # Main loop
        await self._run_loop()

    async def _init_feeds(self):
        """Initialize data feeds"""
        logger.info("Initializing data feeds...")

        # Polymarket feed
        self.polymarket_feed = PolymarketFeed()
        await self.polymarket_feed.start()

        # Market discovery
        self.market_discovery = MarketDiscovery()
        await self.market_discovery.start()

        # Discover markets
        markets = await self.market_discovery.discover_all()
        logger.info(f"Found {len(markets)} active markets")

        # Register markets
        for key, market in markets.items():
            self.polymarket_feed.register_market(
                condition_id=market.condition_id,
                up_token_id=market.up_token_id,
                down_token_id=market.down_token_id,
                slug=market.slug
            )

        # Connect WS
        await self.polymarket_feed.connect_ws()
        update_system_status("polymarket_ws", "connected")

        # Sentiment
        self.sentiment_feed = SentimentFeed()
        await self.sentiment_feed.start()

        if self.sentiment_feed.data:
            update_sentiment(
                self.sentiment_feed.data.fear_greed_index,
                self.sentiment_feed.data.fear_greed_label
            )

        # Binance feeds
        for coin in self.config.binance.coins:
            for tf in self.config.binance.timeframes:
                key = f"{coin}_{tf}"
                self.binance_feeds[key] = BinanceFeed(
                    symbol=self.config.binance.binance_symbols[coin],
                    timeframe=tf
                )

        logger.info("Data feeds initialized")

    async def _init_strategy(self):
        """Initialize strategy"""
        self.strategy = CombinedStrategy({
            "signal_weight": 0.5,
            "arbitrage_weight": 0.3,
            "sentiment_weight": 0.2,
            "entry_bullish_threshold": 70,
            "entry_bearish_threshold": 30
        })
        logger.info("Strategy initialized")

    async def _run_loop(self):
        """Main trading loop"""
        logger.info("Starting trading loop...")

        # Start Binance feeds
        for key, feed in self.binance_feeds.items():
            asyncio.create_task(self._safe_start_feed(feed, key))

        while self.running:
            try:
                # Process markets
                for key in list(self.binance_feeds.keys()):
                    await self._process_market(key)

                # Update dashboard with positions
                if self.paper_trader:
                    positions = {}
                    # Access positions through position_manager
                    for k, pos in self.paper_trader.position_manager.open_positions.items():
                        positions[k] = {
                            "coin": pos.coin,
                            "timeframe": pos.timeframe,
                            "direction": str(pos.direction),
                            "entry_price": pos.entry_price,
                            "shares": pos.shares,
                            "pnl": pos.pnl if hasattr(pos, 'pnl') else 0
                        }
                    update_positions(positions)

                    # Update PnL from stats
                    stats = self.paper_trader.position_manager.get_stats_summary()
                    update_pnl(
                        self.paper_trader.balance,
                        stats.get("total_trades", 0),
                        stats.get("win_rate", 0.0)
                    )

                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"Error in loop: {e}")
                await asyncio.sleep(5)

    async def _safe_start_feed(self, feed, key: str):
        """Start feed with timeout"""
        try:
            await asyncio.wait_for(feed.start(), timeout=15)
        except asyncio.TimeoutError:
            logger.warning(f"Feed {key} timed out")
            update_system_status("binance_ws", "timeout")

    async def _process_market(self, key: str):
        """Process market"""
        parts = key.split("_")
        coin = parts[0]
        timeframe = parts[1] if len(parts) > 1 else "5m"

        market = self.market_discovery.get_market(key)
        if not market:
            return

        feed = self.binance_feeds.get(key)
        if not feed or not feed.state.mid_price:
            return

        prices = self.polymarket_feed.get_market_prices(market.condition_id)
        if not prices or not prices.is_valid:
            return

        # Update dashboard
        update_market_data(coin, timeframe, {
            "up_price": prices.up_price,
            "down_price": prices.down_price
        })

        # Run strategy
        data = {
            "coin": coin,
            "timeframe": timeframe,
            "binance_state": feed.state,
            "market_prices": prices,
            "sentiment": self.sentiment_feed.data if self.sentiment_feed else None
        }

        result = await self.strategy.analyze(data)

        # Update signal
        update_signal(coin, timeframe, result.to_dict())

        # Trade
        if result.should_trade:
            await self._execute_trade(coin, timeframe, result, market, prices)

    async def _execute_trade(self, coin, timeframe, result, market, prices):
        """Execute trade"""
        can_trade, reason = self.position_manager.can_enter_trade(coin, timeframe)
        if not can_trade:
            return

        if result.direction == Direction.BULLISH:
            entry_price = prices.up_price
            token_id = market.up_token_id
        else:
            entry_price = prices.down_price
            token_id = market.down_token_id

        position_size = self.risk_manager.calculate_position_size(
            result.score, result.direction, entry_price, result.is_strong
        )

        if position_size < 5:
            return

        shares = position_size / entry_price

        logger.info(f"TRADE: {coin} {timeframe} {result.direction} ${position_size:.2f}")

        if self.paper_trader:
            self.paper_trader.create_position(
                coin=coin, timeframe=timeframe,
                direction=result.direction, entry_price=entry_price,
                shares=shares, condition_id=market.condition_id, token_id=token_id
            )


def run_web_dashboard():
    """Run web dashboard in thread"""
    logger.info("Starting web dashboard on http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)


async def main():
    """Main entry"""
    # Start web dashboard in background thread
    web_thread = threading.Thread(target=run_web_dashboard, daemon=True)
    web_thread.start()

    # Wait a bit for web server to start
    await asyncio.sleep(2)

    # Start bot
    bot = BotWithWebDashboard()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Stopped by user")


if __name__ == "__main__":
    print("=" * 60)
    print("POLYMARKET ULTIMATE BOT WITH WEB DASHBOARD")
    print("=" * 60)
    print()
    print("Dashboard will be available at: http://localhost:5000")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    asyncio.run(main())