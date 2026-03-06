# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - EXECUTOR
# Polymarket CLOB order execution
# ═══════════════════════════════════════════════════════════════

import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Any

import aiohttp

from core.constants import OrderSide, OrderStatus
from core.exceptions import ExecutionError, APIError

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Result of order placement"""
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    price: float = 0.0
    shares: float = 0.0
    status: OrderStatus = OrderStatus.PENDING

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "message": self.message,
            "price": self.price,
            "shares": self.shares,
            "status": str(self.status)
        }


class PolymarketExecutor:
    """
    Executes orders on Polymarket CLOB API

    Supports:
    - Market orders (buy/sell)
    - Limit orders
    - Order cancellation
    - Balance checking
    """

    CLOB_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.api_passphrase = config.get("api_passphrase", "")
        self.private_key = config.get("private_key", "")
        self.proxy_wallet = config.get("proxy_wallet", "")
        self.simulation_mode = config.get("simulation_mode", True)

        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize session"""
        self._session = aiohttp.ClientSession(headers={
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

        if self.api_key:
            self._session.headers.update({
                "POLYMARKET-API-KEY": self.api_key
            })

    async def stop(self):
        """Close session"""
        if self._session:
            await self._session.close()

    async def get_mid_price(self, token_id: str) -> Optional[float]:
        """Get mid price for a token"""
        try:
            url = f"{self.CLOB_URL}/book"
            params = {"token_id": token_id}

            async with self._session.get(url, params=params, timeout=5) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])

                if not bids or not asks:
                    return None

                best_bid = float(bids[0]["price"])
                best_ask = float(asks[0]["price"])

                return (best_bid + best_ask) / 2

        except Exception as e:
            logger.error(f"Error getting mid price: {e}")
            return None

    async def place_order(
        self,
        token_id: str,
        side: OrderSide,
        price: float,
        shares: float,
        condition_id: str
    ) -> OrderResult:
        """
        Place an order on Polymarket

        Args:
            token_id: Token ID (Up or Down contract)
            side: BUY or SELL
            price: Order price (0-1)
            shares: Number of shares
            condition_id: Market condition ID

        Returns:
            OrderResult
        """
        if self.simulation_mode:
            logger.info(f"🧪 SIMULATION: Would place {side.value} order")
            logger.info(f"   Token: {token_id[:24]}... | Price: ${price:.4f} | Shares: {shares:.2f}")
            return OrderResult(
                success=True,
                order_id=f"sim_{int(time.time())}",
                message="Simulation mode - no real order",
                price=price,
                shares=shares,
                status=OrderStatus.FILLED
            )

        try:
            order_data = {
                "order": {
                    "token_id": token_id,
                    "side": side.value,
                    "price": str(price),
                    "size": str(shares),
                    "expiration": "0",
                    "signature_type": 2
                }
            }

            url = f"{self.CLOB_URL}/order"
            async with self._session.post(url, json=order_data, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    order_id = data.get("orderID", data.get("id", "unknown"))

                    logger.info(f"✅ Order placed: {order_id}")
                    return OrderResult(
                        success=True,
                        order_id=order_id,
                        message="Order placed",
                        price=price,
                        shares=shares,
                        status=OrderStatus.OPEN
                    )
                else:
                    error = await resp.text()
                    logger.error(f"❌ Order failed: {resp.status} - {error}")
                    return OrderResult(
                        success=False,
                        message=f"Order failed: {error}",
                        status=OrderStatus.FAILED
                    )

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return OrderResult(
                success=False,
                message=str(e),
                status=OrderStatus.FAILED
            )

    async def buy_up_contract(
        self,
        condition_id: str,
        token_id: str,
        shares: float,
        max_price: Optional[float] = None
    ) -> OrderResult:
        """Buy UP contract (bullish position)"""
        price = max_price or await self.get_mid_price(token_id)
        if price is None:
            return OrderResult(success=False, message="Could not get price")

        logger.info(f"📈 Buying UP: {token_id[:24]}... @ ${price:.4f}")
        return await self.place_order(token_id, OrderSide.BUY, price, shares, condition_id)

    async def buy_down_contract(
        self,
        condition_id: str,
        token_id: str,
        shares: float,
        max_price: Optional[float] = None
    ) -> OrderResult:
        """Buy DOWN contract (bearish position)"""
        price = max_price or await self.get_mid_price(token_id)
        if price is None:
            return OrderResult(success=False, message="Could not get price")

        logger.info(f"📉 Buying DOWN: {token_id[:24]}... @ ${price:.4f}")
        return await self.place_order(token_id, OrderSide.BUY, price, shares, condition_id)

    async def sell_position(
        self,
        token_id: str,
        shares: float,
        min_price: Optional[float] = None
    ) -> OrderResult:
        """Sell a position (exit trade)"""
        price = min_price or await self.get_mid_price(token_id)
        if price is None:
            return OrderResult(success=False, message="Could not get price")

        logger.info(f"💰 Selling: {token_id[:24]}... @ ${price:.4f}")
        return await self.place_order(token_id, OrderSide.SELL, price, shares, token_id)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if self.simulation_mode:
            logger.info(f"🧪 SIMULATION: Would cancel order {order_id}")
            return True

        try:
            url = f"{self.CLOB_URL}/order"
            payload = {"orderID": order_id}

            async with self._session.delete(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"✅ Order cancelled: {order_id}")
                    return True
                else:
                    logger.error(f"❌ Cancel failed: {resp.status}")
                    return False

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def check_balance(self) -> Optional[Dict]:
        """Check account balance"""
        try:
            url = f"{self.CLOB_URL}/balance"
            # USDC on Polygon
            params = {"asset_id": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"}

            async with self._session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None

        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            return None