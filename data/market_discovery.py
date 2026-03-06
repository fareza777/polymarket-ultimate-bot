# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - MARKET DISCOVERY
# Auto-discover active Polymarket markets
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

import aiohttp

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
        """Seconds remaining until market closes"""
        return max(0, self.end_timestamp - int(time.time()))

    @property
    def key(self) -> str:
        """Unique key for this market"""
        return f"{self.coin}_{self.timeframe}"


class MarketDiscovery:
    """
    Discovers and tracks active Polymarket crypto markets
    """

    GAMMA_URL = "https://gamma-api.polymarket.com"

    COIN_SLUGS = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "XRP": "ripple-xrp"
    }

    SUPPORTED_COINS = ["BTC", "ETH", "SOL", "XRP"]
    SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h"]

    def __init__(self):
        self.markets: Dict[str, Market] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize session"""
        self._session = aiohttp.ClientSession()

    async def stop(self):
        """Close session"""
        if self._session:
            await self._session.close()

    def _build_slug(self, coin: str, timeframe: str) -> Optional[str]:
        """Build market slug based on coin and timeframe"""
        coin_slug = self.COIN_SLUGS.get(coin.upper())
        if not coin_slug:
            return None

        now_ts = int(time.time())

        if timeframe == "5m":
            # 5 minute markets
            ts = (now_ts // 300) * 300
            return f"{coin_slug}-updown-5m-{ts}"
        elif timeframe == "15m":
            # 15 minute markets
            ts = (now_ts // 900) * 900
            return f"{coin_slug}-updown-15m-{ts}"
        elif timeframe == "1h":
            # 1 hour markets (actually 4h on Polymarket)
            ts = ((now_ts - 3600) // 14400) * 14400 + 3600
            return f"{coin_slug}-updown-4h-{ts}"

        return None

    async def fetch_market(self, coin: str, timeframe: str) -> Optional[Market]:
        """
        Fetch market info for a specific coin/timeframe

        Args:
            coin: BTC, ETH, SOL, XRP
            timeframe: 5m, 15m, 1h

        Returns:
            Market object or None
        """
        slug = self._build_slug(coin, timeframe)
        if not slug:
            return None

        try:
            url = f"{self.GAMMA_URL}/events"
            params = {"slug": slug, "limit": 1}

            async with self._session.get(url, params=params, timeout=10) as resp:
                if resp.status != 200:
                    logger.debug(f"Market not found: {slug} (HTTP {resp.status})")
                    return None

                data = await resp.json()
                if not data:
                    logger.debug(f"No data for market: {slug}")
                    return None

                event = data[0]

                # Verify slug matches
                if event.get("ticker") != slug:
                    logger.debug(f"Slug mismatch: {event.get('ticker')} != {slug}")
                    return None

                # Extract market data
                markets = event.get("markets", [])
                if not markets:
                    return None

                market_data = markets[0]

                # Get token IDs
                import json
                token_ids = json.loads(market_data.get("clobTokenIds", "[]"))
                if len(token_ids) != 2:
                    logger.warning(f"Invalid token IDs for {slug}")
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

                # Cache it
                self.markets[market.key] = market
                logger.info(f"Found market: {market.key} -> {slug}")

                return market

        except asyncio.TimeoutError:
            logger.warning(f"Timeout fetching market: {slug}")
            return None
        except Exception as e:
            logger.error(f"Error fetching market {coin} {timeframe}: {e}")
            return None

    async def discover_all(self) -> Dict[str, Market]:
        """
        Discover all active markets for supported coins/timeframes

        Returns:
            Dictionary of key -> Market
        """
        logger.info("Discovering all markets...")

        tasks = []
        for coin in self.SUPPORTED_COINS:
            for tf in self.SUPPORTED_TIMEFRAMES:
                tasks.append(self.fetch_market(coin, tf))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        discovered = {}
        for result in results:
            if isinstance(result, Market):
                discovered[result.key] = result

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