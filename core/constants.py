# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - CONSTANTS & ENUMS
# ═══════════════════════════════════════════════════════════════

from enum import Enum, auto
from typing import Dict, List


class Direction(Enum):
    """Trading direction"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"

    def __str__(self):
        return self.value

    @property
    def emoji(self) -> str:
        if self == Direction.BULLISH:
            return "🚀"
        elif self == Direction.BEARISH:
            return "📉"
        return "➖"


class PositionStatus(Enum):
    """Position status"""
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"
    TAKEN_PROFIT = "taken_profit"
    LIQUIDATED = "liquidated"

    def __str__(self):
        return self.value


class OrderSide(Enum):
    """Order side (buy/sell)"""
    BUY = "BUY"
    SELL = "SELL"

    def __str__(self):
        return self.value


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"

    def __str__(self):
        return self.value


class TimeFrame(Enum):
    """Trading timeframes"""
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    DAILY = "daily"

    def __str__(self):
        return self.value

    @property
    def seconds(self) -> int:
        """Return timeframe in seconds"""
        mapping = {
            TimeFrame.M5: 300,
            TimeFrame.M15: 900,
            TimeFrame.H1: 3600,
            TimeFrame.H4: 14400,
            TimeFrame.DAILY: 86400
        }
        return mapping[self]

    @property
    def binance_interval(self) -> str:
        """Return Binance kline interval"""
        return self.value


class Coin(Enum):
    """Supported cryptocurrencies"""
    BTC = "BTC"
    ETH = "ETH"
    SOL = "SOL"
    XRP = "XRP"

    def __str__(self):
        return self.value

    @property
    def binance_symbol(self) -> str:
        """Return Binance trading pair"""
        return f"{self.value}USDT"

    @property
    def polymarket_slug(self) -> str:
        """Return Polymarket slug"""
        slugs = {
            Coin.BTC: "bitcoin",
            Coin.ETH: "ethereum",
            Coin.SOL: "solana",
            Coin.XRP: "ripple-xrp"
        }
        return slugs[self]


class StrategyType(Enum):
    """Strategy types"""
    SIGNAL = "signal"           # Binance signal-based
    ARBITRAGE = "arbitrage"     # Cross-timeframe arbitrage
    SENTIMENT = "sentiment"     # Social/news sentiment
    COMBINED = "combined"       # Multi-strategy combination

    def __str__(self):
        return self.value


class SignalStrength(Enum):
    """Signal strength levels"""
    VERY_STRONG = "very_strong"  # >= 85 or <= 15
    STRONG = "strong"            # >= 75 or <= 25
    MODERATE = "moderate"        # >= 70 or <= 30
    WEAK = "weak"                # >= 60 or <= 40
    NONE = "none"                # Neutral

    def __str__(self):
        return self.value


# ═══════════════════════════════════════════════════════════════
# INDICATOR CONSTANTS
# ═══════════════════════════════════════════════════════════════

# RSI
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# EMA
EMA_SHORT = 5
EMA_LONG = 20

# Order Book
OBI_BAND_PCT = 0.5  # 0.5% band around mid
OBI_THRESH = 0.05   # 5% imbalance threshold

# Depth bands
DEPTH_BANDS = [0.1, 0.5, 1.0]  # Percentage bands

# Wall detection
WALL_MULT = 3.0  # Multiple of average volume

# CVD windows
CVD_WINDOWS = [60, 180, 300]  # 1m, 3m, 5m in seconds
DELTA_WINDOW = 60  # 1 minute

# Volume Profile
VP_BINS = 20
VP_SHOW = 12  # Number of bars to show

# Heikin Ashi
HA_COUNT = 8  # Number of HA candles to display

# Trade TTL
TRADE_TTL = 300  # 5 minutes
KLINE_MAX = 200
KLINE_BOOT = 100

# Signal refresh intervals
REFRESH_5M = 2.0
REFRESH = 3.0


# ═══════════════════════════════════════════════════════════════
# BIAS SCORE WEIGHTS
# ═══════════════════════════════════════════════════════════════

BIAS_WEIGHTS: Dict[str, int] = {
    "ema": 8,
    "obi": 8,
    "macd": 6,
    "cvd": 6,
    "ha": 6,
    "vwap": 6,
    "rsi": 6,
    "poc": 6,
    "walls": 4
}


# ═══════════════════════════════════════════════════════════════
# POLYMARKET CONSTANTS
# ═══════════════════════════════════════════════════════════════

# Supported coins and timeframes for trading
SUPPORTED_COINS = ["BTC", "ETH", "SOL", "XRP"]
SUPPORTED_TIMEFRAMES = ["5m", "15m", "1h"]

# USDC address on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"

# Minimum trade amounts
MIN_TRADE_USDC = 5.0
MAX_PRICE = 0.99
MIN_PRICE = 0.01


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def get_signal_strength(score: float, direction: Direction) -> SignalStrength:
    """
    Determine signal strength based on score and direction

    Args:
        score: Bias score (0-100)
        direction: Trading direction

    Returns:
        SignalStrength enum value
    """
    if direction == Direction.BULLISH:
        if score >= 85:
            return SignalStrength.VERY_STRONG
        elif score >= 75:
            return SignalStrength.STRONG
        elif score >= 70:
            return SignalStrength.MODERATE
        elif score >= 60:
            return SignalStrength.WEAK
    elif direction == Direction.BEARISH:
        if score <= 15:
            return SignalStrength.VERY_STRONG
        elif score <= 25:
            return SignalStrength.STRONG
        elif score <= 30:
            return SignalStrength.MODERATE
        elif score <= 40:
            return SignalStrength.WEAK

    return SignalStrength.NONE


def score_to_direction(score: float) -> Direction:
    """
    Convert bias score to direction

    Args:
        score: Bias score (0-100)

    Returns:
        Direction enum value
    """
    if score > 60:
        return Direction.BULLISH
    elif score < 40:
        return Direction.BEARISH
    return Direction.NEUTRAL