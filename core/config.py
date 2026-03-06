# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - CONFIGURATION
# ═══════════════════════════════════════════════════════════════

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


@dataclass
class PolymarketConfig:
    """Polymarket API configuration"""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    private_key: str = ""
    proxy_wallet: str = ""
    signature_type: int = 2

    # API URLs
    clob_url: str = "https://clob.polymarket.com"
    gamma_url: str = "https://gamma-api.polymarket.com"
    ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

    def __post_init__(self):
        self.api_key = os.getenv("POLYMARKET_API_KEY", "")
        self.api_secret = os.getenv("POLYMARKET_API_SECRET", "")
        self.api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE", "")
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY", "")
        self.proxy_wallet = os.getenv("POLYMARKET_PROXY_WALLET", "")
        self.signature_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "2"))


@dataclass
class BinanceConfig:
    """Binance API configuration"""
    rest_url: str = "https://api.binance.com"
    ws_url: str = "wss://stream.binance.com:9443/stream"

    # Supported coins and timeframes
    coins: List[str] = field(default_factory=lambda: ["BTC", "ETH", "SOL", "XRP"])
    timeframes: List[str] = field(default_factory=lambda: ["5m", "15m", "1h"])

    # Coin mappings
    binance_symbols: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "BTCUSDT",
        "ETH": "ETHUSDT",
        "SOL": "SOLUSDT",
        "XRP": "XRPUSDT"
    })

    polymarket_slugs: Dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "XRP": "ripple-xrp"
    })


@dataclass
class StrategyConfig:
    """Strategy configuration"""
    # Strategy weights (should sum to 1.0)
    signal_weight: float = 0.50
    arbitrage_weight: float = 0.30
    sentiment_weight: float = 0.20

    # Signal strategy thresholds
    entry_bullish_threshold: int = 70
    entry_bearish_threshold: int = 30
    strong_signal_threshold: int = 85
    exit_threshold: int = 50

    # Arbitrage settings
    arbitrage_min_spread: float = 0.05  # 5% minimum spread
    arbitrage_max_position: float = 20.0

    # Sentiment settings
    fear_greed_weight: float = 0.5
    social_weight: float = 0.3
    news_weight: float = 0.2

    def __post_init__(self):
        self.signal_weight = float(os.getenv("SIGNAL_STRATEGY_WEIGHT", "0.50"))
        self.arbitrage_weight = float(os.getenv("ARBITRAGE_STRATEGY_WEIGHT", "0.30"))
        self.sentiment_weight = float(os.getenv("SENTIMENT_STRATEGY_WEIGHT", "0.20"))
        self.entry_bullish_threshold = int(os.getenv("ENTRY_BULLISH_THRESHOLD", "70"))
        self.entry_bearish_threshold = int(os.getenv("ENTRY_BEARISH_THRESHOLD", "30"))
        self.strong_signal_threshold = int(os.getenv("STRONG_SIGNAL_THRESHOLD", "85"))
        self.arbitrage_min_spread = float(os.getenv("ARBITRAGE_MIN_SPREAD", "0.05"))
        self.arbitrage_max_position = float(os.getenv("ARBITRAGE_MAX_POSITION", "20.0"))


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position sizing
    base_position_size: float = 10.0
    max_position_size: float = 50.0
    max_total_exposure: float = 200.0
    max_concurrent_positions: int = 5
    strong_signal_multiplier: float = 2.0

    # Stop loss & take profit
    stop_loss_pct: float = 0.15  # 15%
    take_profit_pct: float = 0.30  # 30%
    trailing_stop: bool = False
    trailing_stop_pct: float = 0.10

    # Time limits
    max_hold_time_seconds: int = 1800  # 30 minutes
    min_hold_time_seconds: int = 60  # 1 minute

    # Cooldowns
    cooldown_after_win: int = 300  # 5 minutes
    cooldown_after_loss: int = 600  # 10 minutes

    # Market filters
    min_liquidity: float = 1000.0
    max_spread: float = 0.05

    def __post_init__(self):
        self.base_position_size = float(os.getenv("BASE_POSITION_SIZE", "10.0"))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", "50.0"))
        self.max_total_exposure = float(os.getenv("MAX_TOTAL_EXPOSURE", "200.0"))
        self.stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "0.15"))
        self.take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "0.30"))
        self.max_hold_time_seconds = int(os.getenv("MAX_HOLD_TIME_SECONDS", "1800"))
        self.min_hold_time_seconds = int(os.getenv("MIN_HOLD_TIME_SECONDS", "60"))
        self.cooldown_after_win = int(os.getenv("COOLDOWN_AFTER_WIN", "300"))
        self.cooldown_after_loss = int(os.getenv("COOLDOWN_AFTER_LOSS", "600"))


@dataclass
class TelegramConfig:
    """Telegram notification configuration"""
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = False

    # Alert thresholds
    strong_bull_threshold: int = 78
    strong_bear_threshold: int = 22

    # Anti-spam
    anti_spam_strong_sec: int = 180
    anti_spam_change_sec: int = 300

    def __post_init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)


@dataclass
class SentimentConfig:
    """Sentiment API configuration"""
    # Fear & Greed Index
    fear_greed_api_url: str = "https://api.alternative.me/fng/"

    # Twitter/X (optional)
    twitter_bearer_token: str = ""
    twitter_enabled: bool = False

    # News API (optional)
    news_api_key: str = ""
    news_enabled: bool = False

    def __post_init__(self):
        self.twitter_bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")
        self.twitter_enabled = bool(self.twitter_bearer_token)
        self.news_api_key = os.getenv("NEWS_API_KEY", "")
        self.news_enabled = bool(self.news_api_key)


@dataclass
class Config:
    """Main configuration class"""
    # Mode
    simulation_mode: bool = True
    debug_mode: bool = False
    log_level: str = "INFO"
    log_file: str = "polymarket_bot.log"

    # Sub-configurations
    polymarket: PolymarketConfig = field(default_factory=PolymarketConfig)
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    sentiment: SentimentConfig = field(default_factory=SentimentConfig)

    def __post_init__(self):
        self.simulation_mode = os.getenv("SIMULATION_MODE", "true").lower() == "true"
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file = os.getenv("LOG_FILE", "polymarket_bot.log")

    def validate(self) -> List[str]:
        """Validate configuration, return list of errors"""
        errors = []

        if not self.simulation_mode:
            if not self.polymarket.api_key:
                errors.append("POLYMARKET_API_KEY required for live trading")
            if not self.polymarket.api_secret:
                errors.append("POLYMARKET_API_SECRET required for live trading")
            if not self.polymarket.private_key:
                errors.append("POLYMARKET_PRIVATE_KEY required for live trading")

        if self.strategy.signal_weight + self.strategy.arbitrage_weight + self.strategy.sentiment_weight != 1.0:
            errors.append("Strategy weights must sum to 1.0")

        if self.risk.stop_loss_pct <= 0 or self.risk.stop_loss_pct > 0.5:
            errors.append("STOP_LOSS_PCT must be between 0 and 0.5")

        if self.risk.take_profit_pct <= 0 or self.risk.take_profit_pct > 1.0:
            errors.append("TAKE_PROFIT_PCT must be between 0 and 1.0")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "simulation_mode": self.simulation_mode,
            "debug_mode": self.debug_mode,
            "log_level": self.log_level,
            "polymarket": {
                "clob_url": self.polymarket.clob_url,
                "gamma_url": self.polymarket.gamma_url,
            },
            "strategy": {
                "signal_weight": self.strategy.signal_weight,
                "arbitrage_weight": self.strategy.arbitrage_weight,
                "sentiment_weight": self.strategy.sentiment_weight,
            },
            "risk": {
                "base_position_size": self.risk.base_position_size,
                "max_position_size": self.risk.max_position_size,
                "max_total_exposure": self.risk.max_total_exposure,
            }
        }


# Singleton instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get configuration singleton"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment"""
    global _config
    _config = Config()
    return _config