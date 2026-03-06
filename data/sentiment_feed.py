# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - SENTIMENT FEED
# Social and news sentiment analysis
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

import requests
import urllib3

# Suppress SSL warnings (caused by Windows schannel certificate revocation check)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class SentimentData:
    """Sentiment analysis data"""
    fear_greed_index: int = 50
    fear_greed_label: str = "Neutral"
    fear_greed_updated: Optional[datetime] = None
    twitter_sentiment: float = 0.0
    reddit_sentiment: float = 0.0
    news_sentiment: float = 0.0
    combined_score: float = 50.0

    @property
    def direction(self) -> str:
        if self.combined_score >= 60:
            return "BULLISH"
        elif self.combined_score <= 40:
            return "BEARISH"
        return "NEUTRAL"


class SentimentFeed:
    """Fetches and aggregates sentiment data from multiple sources"""

    FEAR_GREED_API = "https://api.alternative.me/fng/"

    def __init__(self):
        self.data = SentimentData()
        self._running = False
        self._session = requests.Session()
        self._session.verify = False  # Disable SSL verification

    async def start(self):
        """Start sentiment feed"""
        self._running = True
        await self.fetch_all()
        asyncio.create_task(self._update_loop())
        logger.info("SentimentFeed started (SSL verification disabled)")

    async def stop(self):
        """Stop sentiment feed"""
        self._running = False
        self._session.close()

    async def _update_loop(self):
        """Periodic update loop"""
        while self._running:
            await asyncio.sleep(3600)
            await self.fetch_all()

    async def fetch_all(self) -> SentimentData:
        """Fetch all sentiment data"""
        await self.fetch_fear_greed()
        self._calculate_combined()
        return self.data

    async def fetch_fear_greed(self) -> Optional[int]:
        """Fetch Fear & Greed Index"""
        try:
            resp = self._session.get(
                self.FEAR_GREED_API,
                params={"limit": 1},
                timeout=15
            )

            if resp.status_code != 200:
                logger.warning(f"Fear & Greed API error: HTTP {resp.status_code}")
                return None

            data = resp.json()
            if not data.get("data"):
                return None

            fg_data = data["data"][0]
            self.data.fear_greed_index = int(fg_data["value"])
            self.data.fear_greed_label = fg_data["value_classification"]
            self.data.fear_greed_updated = datetime.now()

            logger.info(f"Fear & Greed: {self.data.fear_greed_index} ({self.data.fear_greed_label})")
            return self.data.fear_greed_index

        except Exception as e:
            logger.warning(f"Error fetching Fear & Greed: {e}")
            return None

    def _calculate_combined(self):
        """Calculate combined sentiment score"""
        score = self.data.fear_greed_index

        if self.data.twitter_sentiment != 0:
            score += self.data.twitter_sentiment * 10

        if self.data.news_sentiment != 0:
            score += self.data.news_sentiment * 10

        self.data.combined_score = max(0, min(100, score))

    def get_score(self) -> float:
        return self.data.combined_score

    def get_direction(self) -> str:
        return self.data.direction

    def is_extreme_fear(self) -> bool:
        return self.data.fear_greed_index <= 25

    def is_extreme_greed(self) -> bool:
        return self.data.fear_greed_index >= 75


class SentimentAnalyzer:
    """Analyzes sentiment for trading signals"""

    def __init__(self, feed: SentimentFeed):
        self.feed = feed

    def get_trading_signal(self) -> Dict:
        score = self.feed.get_score()
        direction = self.feed.get_direction()

        if self.feed.is_extreme_fear():
            confidence = 0.8
            signal_direction = "BULLISH"
            signal_score = 80
        elif self.feed.is_extreme_greed():
            confidence = 0.8
            signal_direction = "BEARISH"
            signal_score = 20
        else:
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
        return self.feed.is_extreme_fear() or self.feed.is_extreme_greed()