#!/usr/bin/env python3
# 
# POLYMARKET ULTIMATE BOT - MAIN ENTRY POINT
# 

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config, Config
from core.constants import Direction, StrategyType
from core.exceptions import PolymarketBotError

from data.binance_feed import BinanceFeed, MultiBinanceFeed
from data.polymarket_feed import PolymarketFeed
from data.market_discovery import MarketDiscovery
from data.sentiment_feed import SentimentFeed

from strategies.combined import CombinedStrategy

from execution.executor import PolymarketExecutor
from execution.position_manager import PositionManager
from execution.paper_trader import PaperTrader

from risk.risk_manager import RiskManager

from monitoring.logger import setup_logger
from monitoring.telegram import TelegramNotifier
from monitoring.dashboard import Dashboard

# Setup logger
logger = setup_logger(
    name="polymarket_bot",
    level="INFO",
    log_file="polymarket_bot.log"
)


class PolymarketUltimateBot:
    """
    Main bot orchestrator

    Coordinates:
    - Data feeds (Binance, Polymarket, Sentiment)
    - Strategy execution
    - Risk management
    - Order execution
    - Monitoring & alerts
    """

    def __init__(self, config: Config):
        self.config = config

        # Trading mode
        self.simulation_mode = config.simulation_mode

        # Components
        self.binance_feeds: Dict[str, BinanceFeed] = {}
        self.polymarket_feed: Optional[PolymarketFeed] = None
        self.market_discovery: Optional[MarketDiscovery] = None
        self.sentiment_feed: Optional[SentimentFeed] = None

        self.strategy: Optional[CombinedStrategy] = None
        self.risk_manager: Optional[RiskManager] = None
        self.position_manager: Optional[PositionManager] = None
        self.executor: Optional[PolymarketExecutor] = None
        self.paper_trader: Optional[PaperTrader] = None

        self.telegram: Optional[TelegramNotifier] = None
        self.dashboard: Optional[Dashboard] = None

        # State
        self._running = False
        self._tasks = []

        logger.info(f"[BOT] Polymarket Ultimate Bot initialized")
        logger.info(f"   Mode: {'SIMULATION' if self.simulation_mode else 'LIVE'}")

    async def start(self):
        """Start the bot"""
        logger.info("[START] Starting Polymarket Ultimate Bot...")

        self._running = True

        # Initialize components
        await self._init_feeds()
        await self._init_strategy()
        self._init_risk()
        await self._init_execution()
        await self._init_monitoring()

        # Start main trading loop
        await self._run()

    async def stop(self):
        """Stop the bot"""
        logger.info("[STOP] Stopping Polymarket Ultimate Bot...")
        self._running = False

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Stop components
        if self.polymarket_feed:
            await self.polymarket_feed.stop()
        if self.sentiment_feed:
            await self.sentiment_feed.stop()
        if self.executor:
            await self.executor.stop()
        if self.telegram:
            await self.telegram.stop()
        if self.dashboard:
            await self.dashboard.stop()

        logger.info("Bot stopped")

    async def _init_feeds(self):
        """Initialize data feeds"""
        logger.info("[FEED] Initializing data feeds...")

        # Binance feeds
        for coin in self.config.binance.coins:
            for tf in self.config.binance.timeframes:
                key = f"{coin}_{tf}"
                feed = BinanceFeed(
                    symbol=self.config.binance.binance_symbols[coin],
                    timeframe=tf
                )
                self.binance_feeds[key] = feed

        # Polymarket feed
        self.polymarket_feed = PolymarketFeed()
        await self.polymarket_feed.start()

        # Market discovery
        self.market_discovery = MarketDiscovery()
        await self.market_discovery.start()

        # Discover markets
        markets = await self.market_discovery.discover_all()
        logger.info(f"Found {len(markets)} active markets")

        # Register markets with Polymarket feed
        for key, market in markets.items():
            self.polymarket_feed.register_market(
                condition_id=market.condition_id,
                up_token_id=market.up_token_id,
                down_token_id=market.down_token_id,
                slug=market.slug
            )

        # Now connect WebSocket with registered markets
        await self.polymarket_feed.connect_ws()

        # Sentiment feed
        self.sentiment_feed = SentimentFeed()
        await self.sentiment_feed.start()

        logger.info("[OK] Data feeds initialized")

    async def _init_strategy(self):
        """Initialize strategy"""
        logger.info("[STRATEGY] Initializing strategy...")

        self.strategy = CombinedStrategy({
            "signal_weight": self.config.strategy.signal_weight,
            "arbitrage_weight": self.config.strategy.arbitrage_weight,
            "sentiment_weight": self.config.strategy.sentiment_weight,
            "entry_bullish_threshold": self.config.strategy.entry_bullish_threshold,
            "entry_bearish_threshold": self.config.strategy.entry_bearish_threshold
        })

        logger.info("[OK] Strategy initialized")

    def _init_risk(self):
        """Initialize risk management"""
        logger.info("[RISK] Initializing risk management...")

        self.risk_manager = RiskManager({
            "base_position_size": self.config.risk.base_position_size,
            "max_position_size": self.config.risk.max_position_size,
            "max_total_exposure": self.config.risk.max_total_exposure,
            "stop_loss_pct": self.config.risk.stop_loss_pct,
            "take_profit_pct": self.config.risk.take_profit_pct
        })

        self.position_manager = PositionManager({
            "stop_loss_pct": self.config.risk.stop_loss_pct,
            "take_profit_pct": self.config.risk.take_profit_pct,
            "max_hold_time_seconds": self.config.risk.max_hold_time_seconds
        })

        logger.info("[OK] Risk management initialized")

    async def _init_execution(self):
        """Initialize execution"""
        logger.info("[EXEC] Initializing execution...")

        if self.simulation_mode:
            self.paper_trader = PaperTrader({
                "initial_balance": 1000.0,
                "stop_loss_pct": self.config.risk.stop_loss_pct,
                "take_profit_pct": self.config.risk.take_profit_pct
            })
            await self.paper_trader.start()
            logger.info("[PAPER] Paper trading mode enabled")
        else:
            self.executor = PolymarketExecutor({
                "api_key": self.config.polymarket.api_key,
                "api_secret": self.config.polymarket.api_secret,
                "api_passphrase": self.config.polymarket.api_passphrase,
                "private_key": self.config.polymarket.private_key,
                "proxy_wallet": self.config.polymarket.proxy_wallet,
                "simulation_mode": False
            })
            await self.executor.start()
            logger.info("[LIVE] LIVE trading mode enabled")

        logger.info("[OK] Execution initialized")

    async def _init_monitoring(self):
        """Initialize monitoring"""
        logger.info("[MONITOR] Initializing monitoring...")

        # Telegram
        if self.config.telegram.enabled:
            self.telegram = TelegramNotifier(
                bot_token=self.config.telegram.bot_token,
                chat_id=self.config.telegram.chat_id
            )
            await self.telegram.start()
            logger.info("Telegram notifications enabled")

        # Dashboard
        self.dashboard = Dashboard()
        await self.dashboard.start()

        logger.info("[OK] Monitoring initialized")

    async def _run(self):
        """Main trading loop"""
        logger.info("[LOOP] Starting trading loop...")

        # Give Polymarket WS time to establish connection first
        logger.info("Waiting for Polymarket WS to connect...")
        await asyncio.sleep(3)

        # Start Binance feeds with timeout protection
        feed_tasks = []
        for key, feed in self.binance_feeds.items():
            task = asyncio.create_task(self._safe_start_feed(feed, key))
            feed_tasks.append(task)

        # Start dashboard refresh
        dashboard_task = asyncio.create_task(self.dashboard.run_live())

        # Main loop
        while self._running:
            try:
                # Process each market
                for key in self.binance_feeds:
                    await self._process_market(key)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5)

    async def _safe_start_feed(self, feed, key: str):
        """Start a feed with error handling"""
        try:
            await asyncio.wait_for(feed.start(), timeout=30)
        except asyncio.TimeoutError:
            logger.warning(f"Feed {key} startup timed out (likely geo-blocked)")
        except Exception as e:
            logger.warning(f"Feed {key} error: {e}")

    async def _process_market(self, key: str):
        """Process a single market"""
        parts = key.split("_")
        coin = parts[0]
        timeframe = parts[1] if len(parts) > 1 else "5m"

        # Get market info
        market = self.market_discovery.get_market(key)
        if not market:
            return

        # Get binance state
        feed = self.binance_feeds.get(key)
        if not feed or not feed.state.mid_price:
            return

        # Get Polymarket prices
        prices = self.polymarket_feed.get_market_prices(market.condition_id)
        if not prices or not prices.is_valid:
            return

        # Update dashboard
        self.dashboard.update_market_data(coin, timeframe, {
            "up_price": prices.up_price,
            "down_price": prices.down_price
        })

        # Prepare data for strategy
        data = {
            "coin": coin,
            "timeframe": timeframe,
            "binance_state": feed.state,
            "market_prices": prices,
            "sentiment": self.sentiment_feed.data if self.sentiment_feed else None
        }

        # Run strategy
        result = await self.strategy.analyze(data)

        # Update dashboard
        self.dashboard.update_signal(coin, timeframe, result.to_dict())

        # Check if we should trade
        if result.should_trade:
            await self._execute_trade(coin, timeframe, result, market, prices)

        # Check existing positions for exit
        await self._check_exits(coin, timeframe, prices)

    async def _execute_trade(self, coin: str, timeframe: str, result, market, prices):
        """Execute a trade based on signal"""
        # Check if we can trade
        can_trade, reason = self.position_manager.can_enter_trade(coin, timeframe)
        if not can_trade:
            logger.debug(f"Cannot trade: {reason}")
            return

        # Calculate position size
        if result.direction == Direction.BULLISH:
            entry_price = prices.up_price
            token_id = market.up_token_id
        else:
            entry_price = prices.down_price
            token_id = market.down_token_id

        position_size = self.risk_manager.calculate_position_size(
            result.score,
            result.direction,
            entry_price,
            result.is_strong
        )

        if position_size < 5:  # Minimum $5
            logger.debug(f"Position size too small: ${position_size:.2f}")
            return

        shares = position_size / entry_price

        logger.info(f"[SIGNAL] TRADE SIGNAL: {coin} {timeframe}")
        logger.info(f"   Direction: {result.direction} | Score: {result.score:.0f}")
        logger.info(f"   Size: ${position_size:.2f} | Shares: {shares:.2f}")

        # Execute
        if self.simulation_mode:
            position = self.paper_trader.create_position(
                coin=coin,
                timeframe=timeframe,
                direction=result.direction,
                entry_price=entry_price,
                shares=shares,
                condition_id=market.condition_id,
                token_id=token_id
            )
        else:
            order_result = await self.executor.buy_up_contract(
                condition_id=market.condition_id,
                token_id=token_id,
                shares=shares
            )

            if order_result.success:
                position = self.position_manager.create_position(
                    coin=coin,
                    timeframe=timeframe,
                    direction=result.direction,
                    entry_price=entry_price,
                    shares=shares,
                    condition_id=market.condition_id,
                    token_id=token_id
                )

        # Send notification
        if self.telegram and position:
            await self.telegram.send_trade_entry(
                coin=coin,
                timeframe=timeframe,
                direction=str(result.direction),
                score=result.score,
                entry_price=entry_price,
                shares=shares,
                position_size=position_size,
                stop_loss=position.stop_loss_price,
                take_profit=position.take_profit_price
            )

    async def _check_exits(self, coin: str, timeframe: str, prices):
        """Check if positions should be exited"""
        key = f"{coin}_{timeframe}"

        position = self.position_manager.open_positions.get(key)
        if not position:
            return

        # Get current price
        if position.direction == Direction.BULLISH:
            current_price = prices.up_price
        else:
            current_price = prices.down_price

        # Check exit conditions
        exit_reason = self.position_manager.check_exit_conditions(position, current_price)

        if exit_reason:
            if self.simulation_mode:
                closed = self.paper_trader.close_position(key, current_price, exit_reason)
            else:
                # Execute sell
                sell_result = await self.executor.sell_position(
                    token_id=position.token_id,
                    shares=position.shares
                )

                if sell_result.success:
                    closed = self.position_manager.close_position(key, current_price, exit_reason)

            # Send notification
            if self.telegram and closed:
                await self.telegram.send_trade_exit(
                    coin=coin,
                    timeframe=timeframe,
                    direction=str(closed.direction),
                    entry_price=closed.entry_price,
                    exit_price=closed.exit_price,
                    pnl=closed.pnl,
                    pnl_pct=closed.pnl_pct,
                    reason=exit_reason
                )


async def main():
    """Main entry point"""
    # Load configuration
    config = get_config()

    # Validate
    errors = config.validate()
    if errors:
        logger.error("Configuration errors:")
        for error in errors:
            logger.error(f"  - {error}")
        if not config.simulation_mode:
            sys.exit(1)

    # Create bot
    bot = PolymarketUltimateBot(config)

    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(bot.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())