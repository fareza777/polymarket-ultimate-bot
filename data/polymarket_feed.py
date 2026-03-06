# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - POLYMARKET DATA FEED
# Real-time prices from Polymarket CLOB
# ═══════════════════════════════════════════════════════════════

import asyncio
import json
import logging
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
import urllib3
import websockets

# Suppress SSL warnings (caused by Avast Web Shield)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class MarketPrices:
    """Current prices for a Polymarket market"""
    condition_id: str = ""
    up_token_id: str = ""
    down_token_id: str = ""
    up_price: float = 0.0
    down_price: float = 0.0
    spread: float = 0.0
    liquidity: float = 0.0
    last_update: float = 0.0

    @property
    def is_valid(self) -> bool:
        return self.up_price > 0 and self.down_price > 0

    @property
    def total_odds(self) -> float:
        return self.up_price + self.down_price


@dataclass
class MarketInfo:
    """Market information from Gamma API"""
    condition_id: str
    question: str
    slug: str
    end_time: datetime
    up_token_id: str
    down_token_id: str
    active: bool = True


class PolymarketFeed:
    """Polymarket WebSocket feed for real-time prices"""

    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __init__(self):
        self.prices: Dict[str, MarketPrices] = {}
        self.markets: Dict[str, MarketInfo] = {}
        self._ws = None
        self._running = False
        self._session = requests.Session()

        # SSL context for WebSocket
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        logger.info("PolymarketFeed initialized")

    async def start(self):
        """Start the feed"""
        self._running = True
        asyncio.create_task(self._connect_ws())

    async def stop(self):
        """Stop the feed"""
        self._running = False
        if self._ws:
            await self._ws.close()
        self._session.close()
        logger.info("PolymarketFeed stopped")

    async def fetch_market(self, coin: str, timeframe: str) -> Optional[MarketInfo]:
        """Fetch market info for a coin/timeframe"""
        slug = self._build_slug(coin, timeframe)
        if not slug:
            return None

        try:
            url = f"{self.GAMMA_URL}/events"
            params = {"slug": slug, "limit": 1}

            resp = self._session.get(url, params=params, timeout=10, verify=False)

            if resp.status_code != 200:
                return None

            data = resp.json()
            if not data or data[0].get("ticker") != slug:
                return None

            event = data[0]
            market = event.get("markets", [{}])[0]
            token_ids = json.loads(market.get("clobTokenIds", "[]"))

            if len(token_ids) != 2:
                return None

            info = MarketInfo(
                condition_id=market.get("conditionId", ""),
                question=market.get("question", ""),
                slug=slug,
                end_time=datetime.fromtimestamp(
                    market.get("end_date_iso", 0) / 1000,
                    tz=timezone.utc
                ),
                up_token_id=token_ids[0],
                down_token_id=token_ids[1]
            )

            self.markets[info.condition_id] = info

            self.prices[info.up_token_id] = MarketPrices(
                condition_id=info.condition_id,
                up_token_id=info.up_token_id,
                down_token_id=info.down_token_id
            )
            self.prices[info.down_token_id] = MarketPrices(
                condition_id=info.condition_id,
                up_token_id=info.up_token_id,
                down_token_id=info.down_token_id
            )

            return info

        except Exception as e:
            logger.debug(f"Error fetching market {coin} {timeframe}: {e}")
            return None

    def _build_slug(self, coin: str, timeframe: str) -> Optional[str]:
        """Build Polymarket slug for coin/timeframe"""
        coin_slugs = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
            "XRP": "ripple-xrp"
        }

        coin_slug = coin_slugs.get(coin.upper())
        if not coin_slug:
            return None

        now_ts = int(time.time())

        if timeframe == "5m":
            ts = (now_ts // 300) * 300
            return f"{coin_slug}-updown-5m-{ts}"
        elif timeframe == "15m":
            ts = (now_ts // 900) * 900
            return f"{coin_slug}-updown-15m-{ts}"
        elif timeframe == "1h":
            ts = ((now_ts - 3600) // 14400) * 14400 + 3600
            return f"{coin_slug}-updown-4h-{ts}"

        return None

    async def subscribe_market(self, condition_id: str):
        """Subscribe to market updates via WebSocket"""
        if not self._ws or condition_id not in self.markets:
            return

        market = self.markets[condition_id]
        assets = [market.up_token_id, market.down_token_id]

        await self._ws.send(json.dumps({
            "assets_ids": assets,
            "type": "market"
        }))

        logger.info(f"Subscribed to market: {condition_id[:16]}...")

    async def _connect_ws(self):
        """Connect to Polymarket WebSocket"""
        while self._running:
            try:
                logger.info("Connecting to Polymarket WS...")
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10,
                    ssl=self._ssl_context
                ) as ws:
                    self._ws = ws
                    logger.info("Polymarket WS connected")

                    for condition_id in self.markets:
                        await self.subscribe_market(condition_id)

                    while self._running:
                        try:
                            data = json.loads(await ws.recv())
                            await self._handle_message(data)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("Polymarket WS closed")
                            break

            except Exception as e:
                logger.error(f"Polymarket WS error: {e}")

            if self._running:
                await asyncio.sleep(5)

    async def _handle_message(self, data: Dict):
        """Handle WebSocket message"""
        if isinstance(data, list):
            for entry in data:
                await self._process_price_update(entry)
        elif isinstance(data, dict) and data.get("event_type") == "price_change":
            for change in data.get("price_changes", []):
                await self._process_price_change(change)

    async def _process_price_update(self, data: Dict):
        """Process price update from WS"""
        asset_id = data.get("asset_id")
        asks = data.get("asks", [])

        if asset_id and asks:
            price = min(float(a["price"]) for a in asks)
            self._update_price(asset_id, price)

    async def _process_price_change(self, data: Dict):
        """Process price change event"""
        asset_id = data.get("asset_id")
        best_ask = data.get("best_ask")

        if asset_id and best_ask:
            self._update_price(asset_id, float(best_ask))

    def _update_price(self, token_id: str, price: float):
        """Update price for a token"""
        if token_id not in self.prices:
            return

        price_obj = self.prices[token_id]
        price_obj.last_update = time.time()

        if token_id == price_obj.up_token_id:
            price_obj.up_price = price
        elif token_id == price_obj.down_token_id:
            price_obj.down_price = price

    def get_price(self, token_id: str) -> Optional[float]:
        """Get current price for a token"""
        if token_id in self.prices:
            price_obj = self.prices[token_id]
            if token_id == price_obj.up_token_id:
                return price_obj.up_price
            else:
                return price_obj.down_price
        return None

    def get_market_prices(self, condition_id: str) -> Optional[MarketPrices]:
        """Get prices for a market"""
        if condition_id in self.markets:
            market = self.markets[condition_id]
            if market.up_token_id in self.prices:
                return self.prices[market.up_token_id]
        return None


class MarketDiscovery:
    """Discovers and tracks active Polymarket markets"""

    SUPPORTED_COINS = ["BTC", "ETH", "SOL", "XRP"]
    SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h"]

    def __init__(self, feed: PolymarketFeed):
        self.feed = feed
        self.active_markets: Dict[str, MarketInfo] = {}

    async def discover_all(self) -> Dict[str, MarketInfo]:
        """Discover all active markets"""
        for coin in self.SUPPORTED_COINS:
            for tf in self.SUPPORTED_TIMEFRAMES:
                key = f"{coin}_{tf}"
                market = await self.feed.fetch_market(coin, tf)
                if market:
                    self.active_markets[key] = market
                    logger.info(f"Found market: {key}")

        return self.active_markets

    async def refresh_market(self, coin: str, timeframe: str) -> Optional[MarketInfo]:
        """Refresh a specific market"""
        market = await self.feed.fetch_market(coin, timeframe)
        if market:
            key = f"{coin}_{timeframe}"
            self.active_markets[key] = market
        return market

    def get_market(self, coin: str, timeframe: str) -> Optional[MarketInfo]:
        """Get cached market info"""
        return self.active_markets.get(f"{coin}_{timeframe}")