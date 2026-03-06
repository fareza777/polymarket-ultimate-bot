# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - BINANCE DATA FEED
# Real-time market data from Binance via WebSocket
# ═══════════════════════════════════════════════════════════════

import asyncio
import json
import time
import logging
import os
import ssl
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime

import aiohttp
import requests
import urllib3
import websockets

# Suppress SSL warnings (caused by Avast Web Shield intercepting HTTPS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    bids: List[Tuple[float, float]] = field(default_factory=list)
    asks: List[Tuple[float, float]] = field(default_factory=list)
    mid_price: float = 0.0
    trades: List[Trade] = field(default_factory=list)
    klines: List[Kline] = field(default_factory=list)
    current_kline: Optional[Kline] = None
    symbol: str = ""
    timeframe: str = "5m"
    last_update: float = 0.0

    @property
    def spread(self) -> float:
        if self.bids and self.asks:
            return self.asks[0][0] - self.bids[0][0]
        return 0.0

    @property
    def spread_pct(self) -> float:
        if self.mid_price > 0:
            return (self.spread / self.mid_price) * 100
        return 0.0


class BinanceFeed:
    """Binance WebSocket feed manager"""

    REST_URL = "https://api.binance.com"
    WS_URL = "wss://stream.binance.com:9443/stream"

    def __init__(self, symbol: str, timeframe: str = "5m", api_key: str = None):
        self.symbol = symbol.upper()
        self.timeframe = timeframe
        self.state = BinanceState(symbol=self.symbol, timeframe=self.timeframe)
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")

        self._ws = None
        self._running = False
        self._reconnect_delay = 1
        self._max_reconnect_delay = 30

        # SSL context (skip verification for Avast)
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        logger.info(f"BinanceFeed initialized: {self.symbol} {self.timeframe}")

    async def start(self):
        """Start the WebSocket feed"""
        self._running = True
        await self._bootstrap_klines()
        asyncio.create_task(self._poll_orderbook())
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
            params = {"symbol": self.symbol, "interval": self.timeframe, "limit": 100}

            # Use requests with verify=False (like old bot)
            resp = requests.get(url, params=params, timeout=10, verify=False)

            if resp.status_code == 200:
                data = resp.json()
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
                logger.warning(f"Failed to bootstrap klines: HTTP {resp.status_code}")
                self._generate_synthetic_klines()

        except Exception as e:
            logger.warning(f"Error bootstrapping klines: {e}")
            self._generate_synthetic_klines()

    def _generate_synthetic_klines(self):
        """Generate synthetic klines for testing"""
        import random
        base_price = 50000.0 if "BTC" in self.symbol else 3000.0
        now = time.time()

        for i in range(100):
            ts = now - (100 - i) * 300
            change = random.uniform(-0.02, 0.02)
            o = base_price * (1 + random.uniform(-0.01, 0.01))
            c = o * (1 + change)
            h = max(o, c) * (1 + random.uniform(0, 0.005))
            l = min(o, c) * (1 - random.uniform(0, 0.005))
            v = random.uniform(100, 1000)

            self.state.klines.append(Kline(ts, o, h, l, c, v, True))

        logger.info(f"Generated {len(self.state.klines)} synthetic klines")

    async def _poll_orderbook(self):
        """Poll order book via REST API"""
        url = f"{self.REST_URL}/api/v3/depth"

        while self._running:
            try:
                resp = requests.get(
                    url,
                    params={"symbol": self.symbol, "limit": 20},
                    timeout=3,
                    verify=False
                )

                if resp.status_code == 200:
                    data = resp.json()
                    self.state.bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
                    self.state.asks = [(float(p), float(q)) for p, q in data.get("asks", [])]

                    if self.state.bids and self.state.asks:
                        self.state.mid_price = (self.state.bids[0][0] + self.state.asks[0][0]) / 2
                        self.state.last_update = time.time()

            except Exception:
                pass

            await asyncio.sleep(2)

    async def _connect_ws(self):
        """Connect to Binance WebSocket"""
        symbol_lower = self.symbol.lower()
        streams = "/".join([f"{symbol_lower}@trade", f"{symbol_lower}@kline_{self.timeframe}"])
        ws_url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        while self._running:
            try:
                logger.info(f"Connecting to Binance WS: {self.symbol}")
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10,
                    ssl=self._ssl_context
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1
                    logger.info(f"Binance WS connected: {self.symbol}")

                    while self._running:
                        try:
                            data = json.loads(await ws.recv())
                            await self._handle_message(data)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Binance WS connection closed")
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
        self.state.trades.append(trade)
        cutoff = time.time() - 300
        self.state.trades = [t for t in self.state.trades if t.timestamp >= cutoff]

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
            self.state.klines = self.state.klines[-200:]

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

        return (bid_vol - ask_vol) / total if total else 0.0


class MultiBinanceFeed:
    """Manages multiple Binance feeds"""

    def __init__(self, symbols: List[str], timeframe: str = "5m", api_key: str = None):
        self.feeds = {s: BinanceFeed(s, timeframe, api_key) for s in symbols}

    async def start(self):
        await asyncio.gather(*[f.start() for f in self.feeds.values()], return_exceptions=True)

    async def stop(self):
        await asyncio.gather(*[f.stop() for f in self.feeds.values()], return_exceptions=True)

    def get_state(self, symbol: str) -> Optional[BinanceState]:
        return self.feeds.get(symbol, BinanceState()).state if symbol in self.feeds else None

    def get_all_states(self) -> Dict[str, BinanceState]:
        return {s: f.state for s, f in self.feeds.items()}