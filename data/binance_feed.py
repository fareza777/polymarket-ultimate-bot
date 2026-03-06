# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - BINANCE DATA FEED
# Real-time market data from Binance via WebSocket
# ═══════════════════════════════════════════════════════════════

import asyncio
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime

import aiohttp
import websockets

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Individual trade data"""
    timestamp: float
    price: float
    quantity: float
    is_buyer_maker: bool  # True = sell, False = buy

    @property
    def is_buy(self) -> bool:
        return not self.is_buyer_maker


@dataclass
class Kline:
    """Kline/candlestick data"""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False


@dataclass
class BinanceState:
    """State container for Binance data"""
    # Order book
    bids: List[Tuple[float, float]] = field(default_factory=list)
    asks: List[Tuple[float, float]] = field(default_factory=list)
    mid_price: float = 0.0

    # Trades
    trades: List[Trade] = field(default_factory=list)

    # Klines
    klines: List[Kline] = field(default_factory=list)
    current_kline: Optional[Kline] = None

    # Metadata
    symbol: str = ""
    timeframe: str = "5m"
    last_update: float = 0.0

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        if self.bids and self.asks:
            return self.asks[0][0] - self.bids[0][0]
        return 0.0

    @property
    def spread_pct(self) -> float:
        """Calculate spread as percentage"""
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 100
        return 0.0


class BinanceFeed:
    """
    Binance WebSocket feed manager

    Streams real-time data:
    - Order book depth
    - Trade feed
    - Kline/candlestick data
    """

    WS_URL = "wss://stream.binance.com:9443/stream"
    REST_URL = "https://api.binance.com"
    REST_TIMEOUT = 10

    def __init__(self, symbol: str, timeframe: str = "5m"):
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.state = BinanceState(symbol=self.symbol, timeframe=self.timeframe)

        self._ws = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30

        # Callbacks
        self._on_trade: Optional[Callable] = None
        self._on_kline: Optional[Callable] = None
        self._on_orderbook: Optional[Callable] = None

        logger.info(f"BinanceFeed initialized: {self.symbol} {self.timeframe}")

    def on_trade(self, callback: Callable):
        """Register trade callback"""
        self._on_trade = callback

    def on_kline(self, callback: Callable):
        """Register kline callback"""
        self._on_kline = callback

    def on_orderbook(self, callback: Callable):
        """Register orderbook callback"""
        self._on_orderbook = callback

    async def start(self):
        """Start the WebSocket feed"""
        self._running = True

        # Bootstrap historical klines
        await self._bootstrap_klines()

        # Start order book poller
        asyncio.create_task(self._poll_orderbook())

        # Start WebSocket
        await self._connect_ws()

    async def stop(self):
        """Stop the WebSocket feed"""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info(f"BinanceFeed stopped: {self.symbol}")

    async def _bootstrap_klines(self):
        """Fetch historical klines via REST API"""
        try:
            url = f"{self.REST_URL}/api/v3/klines"
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "limit": 100
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=self.REST_TIMEOUT) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.state.klines = [
                            Kline(
                                timestamp=k[0] / 1000,
                                open=float(k[1]),
                                high=float(k[2]),
                                low=float(k[3]),
                                close=float(k[4]),
                                volume=float(k[5]),
                                is_closed=True
                            )
                            for k in data
                        ]
                        logger.info(f"Bootstrapped {len(self.state.klines)} klines for {self.symbol}")
                    else:
                        logger.error(f"Failed to bootstrap klines: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Error bootstrapping klines: {e}")

    async def _poll_orderbook(self):
        """Poll order book via REST API"""
        url = f"{self.REST_URL}/api/v3/depth"
        params = {"symbol": self.symbol, "limit": 20}

        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.state.bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
                            self.state.asks = [(float(p), float(q)) for p, q in data.get("asks", [])]

                            if self.state.bids and self.state.asks:
                                self.state.mid_price = (self.state.bids[0][0] + self.state.asks[0][0]) / 2
                                self.state.last_update = time.time()

                                if self._on_orderbook:
                                    await self._safe_callback(self._on_orderbook, self.state)
            except Exception as e:
                logger.debug(f"Orderbook poll error: {e}")

            await asyncio.sleep(2)

    async def _connect_ws(self):
        """Connect to Binance WebSocket"""
        symbol_lower = self.symbol.lower()

        # Build stream names
        streams = [
            f"{symbol_lower}@trade",
            f"{symbol_lower}@kline_{self.timeframe}"
        ]
        ws_url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"

        while self._running:
            try:
                logger.info(f"Connecting to Binance WS: {self.symbol}")
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1
                    logger.info(f"Binance WS connected: {self.symbol}")

                    while self._running:
                        try:
                            data = json.loads(await ws.recv())
                            await self._handle_message(data)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning(f"Binance WS connection closed")
                            break
                        except Exception as e:
                            logger.error(f"WS message error: {e}")

            except Exception as e:
                logger.error(f"WS connection error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, self._max_reconnect_delay)

    async def _handle_message(self, data: Dict):
        """Handle incoming WebSocket message"""
        stream = data.get("stream", "")
        payload = data.get("data", {})

        if "@trade" in stream:
            await self._handle_trade(payload)
        elif "@kline" in stream:
            await self._handle_kline(payload)

    async def _handle_trade(self, data: Dict):
        """Handle trade message"""
        trade = Trade(
            timestamp=data["T"] / 1000,
            price=float(data["p"]),
            quantity=float(data["q"]),
            is_buyer_maker=data["m"]
        )

        # Add to trades list
        self.state.trades.append(trade)

        # Trim old trades (keep 5 minutes)
        cutoff = time.time() - 300
        self.state.trades = [t for t in self.state.trades if t.timestamp >= cutoff]

        if self._on_trade:
            await self._safe_callback(self._on_trade, trade)

    async def _handle_kline(self, data: Dict):
        """Handle kline message"""
        k = data["k"]
        kline = Kline(
            timestamp=k["t"] / 1000,
            open=float(k["o"]),
            high=float(k["h"]),
            low=float(k["l"]),
            close=float(k["c"]),
            volume=float(k["v"]),
            is_closed=k["x"]
        )

        self.state.current_kline = kline

        if kline.is_closed:
            self.state.klines.append(kline)
            # Keep max 200 klines
            self.state.klines = self.state.klines[-200:]

            if self._on_kline:
                await self._safe_callback(self._on_kline, kline)

    async def _safe_callback(self, callback: Callable, *args):
        """Safely execute callback"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def get_cvd(self, window_seconds: int = 300) -> float:
        """Calculate Cumulative Volume Delta"""
        cutoff = time.time() - window_seconds
        return sum(
            t.price * t.quantity * (1 if t.is_buy else -1)
            for t in self.state.trades
            if t.timestamp >= cutoff
        )

    def get_obi(self, band_pct: float = 0.5) -> float:
        """Calculate Order Book Imbalance"""
        if not self.state.mid_price or not self.state.bids or not self.state.asks:
            return 0.0

        band = self.state.mid_price * band_pct / 100

        bid_vol = sum(q for p, q in self.state.bids if p >= self.state.mid_price - band)
        ask_vol = sum(q for p, q in self.state.asks if p <= self.state.mid_price + band)

        total = bid_vol + ask_vol
        if total == 0:
            return 0.0

        return (bid_vol - ask_vol) / total


# ═══════════════════════════════════════════════════════════════
# MULTI-SYMBOL FEED MANAGER
# ═══════════════════════════════════════════════════════════════

class MultiBinanceFeed:
    """
    Manages multiple Binance feeds for different symbols
    """

    def __init__(self, symbols: List[str], timeframe: str = "5m"):
        self.symbols = symbols
        self.timeframe = timeframe
        self.feeds: Dict[str, BinanceFeed] = {}

        for symbol in symbols:
            self.feeds[symbol] = BinanceFeed(symbol, timeframe)

    async def start(self):
        """Start all feeds"""
        tasks = [feed.start() for feed in self.feeds.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self):
        """Stop all feeds"""
        tasks = [feed.stop() for feed in self.feeds.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_state(self, symbol: str) -> Optional[BinanceState]:
        """Get state for a specific symbol"""
        if symbol in self.feeds:
            return self.feeds[symbol].state
        return None

    def get_all_states(self) -> Dict[str, BinanceState]:
        """Get all states"""
        return {symbol: feed.state for symbol, feed in self.feeds.items()}