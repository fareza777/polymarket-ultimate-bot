# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - CUSTOM EXCEPTIONS
# ═══════════════════════════════════════════════════════════════

from typing import Optional, Any


class PolymarketBotError(Exception):
    """Base exception for Polymarket Bot"""

    def __init__(self, message: str, details: Optional[Any] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConfigurationError(PolymarketBotError):
    """Configuration related errors"""
    pass


class ExecutionError(PolymarketBotError):
    """Trade execution errors"""

    def __init__(self, message: str, order_id: Optional[str] = None, details: Optional[Any] = None):
        self.order_id = order_id
        super().__init__(message, details)

    def __str__(self):
        base = super().__str__()
        if self.order_id:
            return f"[Order: {self.order_id}] {base}"
        return base


class RiskError(PolymarketBotError):
    """Risk management errors"""
    pass


class DataFeedError(PolymarketBotError):
    """Data feed connection errors"""

    def __init__(self, source: str, message: str, details: Optional[Any] = None):
        self.source = source
        super().__init__(f"[{source}] {message}", details)


class StrategyError(PolymarketBotError):
    """Strategy calculation errors"""

    def __init__(self, strategy_name: str, message: str, details: Optional[Any] = None):
        self.strategy_name = strategy_name
        super().__init__(f"[{strategy_name}] {message}", details)


class OrderError(PolymarketBotError):
    """Order related errors"""

    def __init__(self, message: str, order_id: Optional[str] = None,
                 side: Optional[str] = None, token_id: Optional[str] = None):
        self.order_id = order_id
        self.side = side
        self.token_id = token_id
        super().__init__(message)

    def __str__(self):
        parts = []
        if self.order_id:
            parts.append(f"order_id={self.order_id}")
        if self.side:
            parts.append(f"side={self.side}")
        if self.token_id:
            parts.append(f"token={self.token_id[:16]}...")
        details = ", ".join(parts) if parts else None
        if details:
            return f"{self.message} ({details})"
        return self.message


class PositionError(PolymarketBotError):
    """Position management errors"""
    pass


class InsufficientBalanceError(RiskError):
    """Insufficient balance for trade"""
    pass


class MaxExposureError(RiskError):
    """Maximum exposure limit reached"""

    def __init__(self, current: float, max_allowed: float):
        self.current = current
        self.max_allowed = max_allowed
        super().__init__(f"Max exposure reached: {current:.2f} / {max_allowed:.2f}")


class CooldownError(RiskError):
    """Trading in cooldown period"""

    def __init__(self, remaining_seconds: float, reason: str):
        self.remaining_seconds = remaining_seconds
        self.reason = reason
        super().__init__(f"Cooldown active: {remaining_seconds:.0f}s remaining ({reason})")


class MarketNotFoundError(PolymarketBotError):
    """Market not found on Polymarket"""

    def __init__(self, coin: str, timeframe: str):
        self.coin = coin
        self.timeframe = timeframe
        super().__init__(f"No active market for {coin} {timeframe}")


class APIError(PolymarketBotError):
    """API related errors"""

    def __init__(self, api_name: str, status_code: int, message: str):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(f"[{api_name}] HTTP {status_code}: {message}")


class AuthenticationError(APIError):
    """Authentication failed"""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded"""

    def __init__(self, api_name: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(api_name, 429, "Rate limit exceeded")


class ValidationError(PolymarketBotError):
    """Input validation errors"""
    pass