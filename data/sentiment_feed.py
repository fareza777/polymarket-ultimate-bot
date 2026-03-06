# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - SENTIMENT FEED
# Social and news sentiment analysis
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class SentimentData:
    """Sentiment analysis data"""
    # Fear & Greed Index (0-100)
    fear_greed_index: int = 50
    fear_greed_label: str = "Neutral"
    fear_greed_updated: Optional[datetime] = None

    # Social sentiment (optional)
    twitter_sentiment: float = 0.0  # -1 to +1
    reddit_sentiment: float = 0.0

    # News sentiment (optional)
    news_sentiment: float = 0.0

    # Combined score
    combined_score: float = 50.0  # 0-100

    @property
    def direction(self) -> str:
        """Get overall sentiment direction"""
        if self.combined_score >= 60:
            return "BULLISH"
        elif self.combined_score <= 40:
            return "BEARISH"
        return "NEUTRAL"


class SentimentFeed:
    """
    Fetches and aggregates sentiment data from multiple sources
    """

    FEAR_GREED_API = "https://api.alternative.me/fng/"

    def __init__(self):
        self.data = SentimentData()
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

        # Cache
        self._last_fear_greed_update: Optional[datetime] = None

    async def start(self):
        """Start sentiment feed"""
        self._running = True
        self._session = aiohttp.ClientSession()

        # Initial fetch
        await self.fetch_all()

        # Start periodic updates
        asyncio.create_task(self._update_loop())

    async def stop(self):
        """Stop sentiment feed"""
        self._running = False
        if self._session:
            await self._session.close()

    async def _update_loop(self):
        """Periodic update loop"""
        while self._running:
            await asyncio.sleep(3600)  # Update every hour
            await self.fetch_all()

    async def fetch_all(self) -> SentimentData:
        """Fetch all sentiment data"""
        await asyncio.gather(
            self.fetch_fear_greed(),
            # Add more sources here
        )

        self._calculate_combined()
        return self.data

    async def fetch_fear_greed(self) -> Optional[int]:
        """
        Fetch Fear & Greed Index

        Returns:
            Index value (0-100) or None
        """
        try:
            async with self._session.get(
                self.FEAR_GREED_API,
                params={"limit": 1},
                timeout=10
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Fear & Greed API error: HTTP {resp.status}")
                    return None

                data = await resp.json()
                if not data.get("data"):
                    return None

                fg_data = data["data"][0]
                self.data.fear_greed_index = int(fg_data["value"])
                self.data.fear_greed_label = fg_data["value_classification"]
                self.data.fear_greed_updated = datetime.now()

                logger.info(f"Fear & Greed: {self.data.fear_greed_index} ({self.data.fear_greed_label})")
                return self.data.fear_greed_index

        except Exception as e:
            logger.error(f"Error fetching Fear & Greed: {e}")
            return None

    def _calculate_combined(self):
        """Calculate combined sentiment score"""
        # Base: Fear & Greed (already 0-100)
        score = self.data.fear_greed_index

        # Adjust for social sentiment if available
        if self.data.twitter_sentiment != 0:
            # Convert -1/+1 to adjustment
            adjustment = self.data.twitter_sentiment * 10
            score += adjustment

        # Adjust for news sentiment if available
        if self.data.news_sentiment != 0:
            adjustment = self.data.news_sentiment * 10
            score += adjustment

        # Clamp to 0-100
        self.data.combined_score = max(0, min(100, score))

    def get_score(self) -> float:
        """Get combined sentiment score (0-100)"""
        return self.data.combined_score

    def get_direction(self) -> str:
        """Get sentiment direction"""
        return self.data.direction

    def is_extreme_fear(self) -> bool:
        """Check if in extreme fear zone"""
        return self.data.fear_greed_index <= 25

    def is_extreme_greed(self) -> bool:
        """Check if in extreme greed zone"""
        return self.data.fear_greed_index >= 75


# ═══════════════════════════════════════════════════════════════
# SENTIMENT ANALYZER (for strategy use)
# ═══════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """
    Analyzes sentiment for trading signals
    """

    def __init__(self, feed: SentimentFeed):
        self.feed = feed

    def get_trading_signal(self) -> Dict:
        """
        Get trading signal based on sentiment

        Returns:
            Dict with score, direction, and confidence
        """
        score = self.feed.get_score()
        direction = self.feed.get_direction()

        # Calculate confidence based on extremity
        # Extreme readings = higher confidence
        if self.feed.is_extreme_fear():
            # Extreme fear = contrarian bullish
            confidence = 0.8
            signal_direction = "BULLISH"
            signal_score = 80
        elif self.feed.is_extreme_greed():
            # Extreme greed = contrarian bearish
            confidence = 0.8
            signal_direction = "BEARISH"
            signal_score = 20
        else:
            # Neutral zone
            confidence = 0.4
            signal_direction = direction
            signal_score = score

        return {
            "score": signal_score,
            "direction": signal_direction,
            "confidence": confidence,
            "fear_greed_index": self.feed.data.fear_greed_index,
            "fear_greed_label": self.feed.data.fear_greed_label
        }

    def should_trade(self) -> bool:
        """
        Determine if sentiment supports trading

        Only trade on extreme readings
        """
        return self.feed.is_extreme_fear() or self.feed.is_extreme_greed()