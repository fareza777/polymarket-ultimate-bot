# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - MARKET DISCOVERY
# Auto-discover active Polymarket markets
# ═══════════════════════════════════════════════════════════════

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import urllib3

# Suppress SSL warnings (caused by Windows schannel certificate revocation check)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class Market:
    """Represents a Polymarket market"""
    condition_id: str
    slug: str
    question: str
    coin: str
    timeframe: str
    up_token_id: str
    down_token_id: str
    end_timestamp: int
    active: bool = True

    @property
    def time_remaining(self) -> int:
        return max(0, self.end_timestamp - int(time.time()))

    @property
    def key(self) -> str:
        return f"{self.coin}_{self.timeframe}"


class MarketDiscovery:
    """Discovers and tracks active Polymarket crypto markets"""

    GAMMA_URL = "https://gamma-api.polymarket.com"

    COIN_SLUGS = {
        "BTC": "btc",
        "ETH": "eth",
        "SOL": "sol",
        "XRP": "xrp"
    }

    SUPPORTED_COINS = ["BTC", "ETH", "SOL", "XRP"]
    SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h"]

    def __init__(self):
        self.markets: Dict[str, Market] = {}
        # Create session with SSL verification disabled
        self._session = requests.Session()
        self._session.verify = False

    async def start(self):
        """Initialize"""
        logger.info("MarketDiscovery initialized (SSL verification disabled)")

    async def stop(self):
        """Cleanup"""
        self._session.close()

    def _build_slug(self, coin: str, timeframe: str) -> Optional[str]:
        """Build market slug based on coin and timeframe"""
        coin_slug = self.COIN_SLUGS.get(coin.upper())
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

    async def fetch_market(self, coin: str, timeframe: str) -> Optional[Market]:
        """Fetch market info for a specific coin/timeframe"""
        slug = self._build_slug(coin, timeframe)
        if not slug:
            return None

        try:
            url = f"{self.GAMMA_URL}/events"
            params = {"slug": slug, "limit": 1}

            resp = self._session.get(url, params=params, timeout=15)

            if resp.status_code != 200:
                logger.debug(f"Market not found: {slug} (HTTP {resp.status_code})")
                return None

            data = resp.json()
            if not data:
                return None

            event = data[0]
            if event.get("ticker") != slug:
                return None

            markets = event.get("markets", [])
            if not markets:
                return None

            market_data = markets[0]
            token_ids = json.loads(market_data.get("clobTokenIds", "[]"))

            if len(token_ids) != 2:
                return None

            market = Market(
                condition_id=market_data.get("conditionId", ""),
                slug=slug,
                question=market_data.get("question", ""),
                coin=coin.upper(),
                timeframe=timeframe,
                up_token_id=token_ids[0],
                down_token_id=token_ids[1],
                end_timestamp=market_data.get("end_date_iso", 0) // 1000,
                active=market_data.get("active", True)
            )

            self.markets[market.key] = market
            logger.info(f"Found market: {market.key}")
            return market

        except Exception as e:
            logger.debug(f"Error fetching market {coin} {timeframe}: {e}")
            return None

    async def discover_all(self) -> Dict[str, Market]:
        """Discover all active markets"""
        logger.info("Discovering all markets...")

        tasks = [self.fetch_market(coin, tf) for coin in self.SUPPORTED_COINS for tf in self.SUPPORTED_TIMEFRAMES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        discovered = {r.key: r for r in results if isinstance(r, Market)}
        logger.info(f"Discovered {len(discovered)} active markets")
        return discovered

    async def refresh_market(self, key: str) -> Optional[Market]:
        """Refresh a specific market by key"""
        if "_" not in key:
            return None
        coin, tf = key.split("_", 1)
        return await self.fetch_market(coin, tf)

    def get_market(self, key: str) -> Optional[Market]:
        """Get cached market by key"""
        return self.markets.get(key)

    def get_market_by_token(self, token_id: str) -> Optional[Market]:
        """Find market by token ID"""
        for market in self.markets.values():
            if market.up_token_id == token_id or market.down_token_id == token_id:
                return market
        return None

    def get_active_markets(self) -> List[Market]:
        """Get list of all active markets"""
        return [m for m in self.markets.values() if m.active]

    def get_markets_by_coin(self, coin: str) -> List[Market]:
        """Get all markets for a specific coin"""
        return [m for m in self.markets.values() if m.coin == coin.upper()]

    def get_markets_by_timeframe(self, timeframe: str) -> List[Market]:
        """Get all markets for a specific timeframe"""
        return [m for m in self.markets.values() if m.timeframe == timeframe]