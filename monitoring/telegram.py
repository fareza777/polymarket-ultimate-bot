# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - TELEGRAM NOTIFIER
# Send trading alerts to Telegram
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Optional
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram notification system

    Sends alerts for:
    - Trade entries
    - Trade exits
    - Strong signals
    - Error notifications
    """

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = bool(bot_token and chat_id)

        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize session"""
        if self.enabled:
            self._session = aiohttp.ClientSession()
            logger.info("Telegram notifier started")

    async def stop(self):
        """Close session"""
        if self._session:
            await self._session.close()

    async def send_message(self, text: str, silent: bool = False) -> bool:
        """
        Send a message to Telegram

        Args:
            text: Message text (supports Markdown)
            silent: Send without notification

        Returns:
            True if successful
        """
        if not self.enabled or not self._session:
            return False

        url = self.API_URL.format(token=self.bot_token)

        try:
            async with self._session.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_notification": silent
                },
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return True
                else:
                    error = await resp.text()
                    logger.error(f"Telegram error: {error}")
                    return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def send_trade_entry(
        self,
        coin: str,
        timeframe: str,
        direction: str,
        score: float,
        entry_price: float,
        shares: float,
        position_size: float,
        stop_loss: float,
        take_profit: float
    ):
        """Send trade entry notification"""
        emoji = "🚀" if direction == "BULLISH" else "📉"

        text = (
            f"{emoji} *NEW TRADE*\n\n"
            f"📊 `{coin} {timeframe}`\n"
            f"Direction: *{direction}*\n"
            f"Score: `{score:.0f}/100`\n\n"
            f"💰 Entry: `${entry_price:.4f}`\n"
            f"Shares: `{shares:.2f}`\n"
            f"Size: `${position_size:.2f}`\n\n"
            f"🛑 SL: `${stop_loss:.4f}`\n"
            f"✅ TP: `${take_profit:.4f}`"
        )

        await self.send_message(text)

    async def send_trade_exit(
        self,
        coin: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str
    ):
        """Send trade exit notification"""
        emoji = "✅" if pnl >= 0 else "❌"
        pnl_sign = "+" if pnl >= 0 else ""

        text = (
            f"{emoji} *POSITION CLOSED*\n\n"
            f"📊 `{coin} {timeframe}`\n"
            f"Reason: `{reason}`\n\n"
            f"💰 Entry: `${entry_price:.4f}`\n"
            f"Exit: `${exit_price:.4f}`\n\n"
            f"PnL: `{pnl_sign}${pnl:.2f}` ({pnl_sign}{pnl_pct * 100:.2f}%)"
        )

        await self.send_message(text)

    async def send_strong_signal(
        self,
        coin: str,
        timeframe: str,
        direction: str,
        score: float,
        signals: list
    ):
        """Send strong signal alert"""
        emoji = "🔥" if direction == "BULLISH" else "⚠️"

        signals_text = "\n".join(f"• `{s}`" for s in signals[:5])

        text = (
            f"{emoji} *STRONG SIGNAL*\n\n"
            f"📊 `{coin} {timeframe}`\n"
            f"Direction: *{direction}*\n"
            f"Score: `{score:.0f}/100`\n\n"
            f"Signals:\n{signals_text}"
        )

        await self.send_message(text)

    async def send_error(self, error_message: str):
        """Send error notification"""
        text = f"🚨 *ERROR*\n\n`{error_message}`"
        await self.send_message(text)

    async def send_daily_summary(
        self,
        total_trades: int,
        winning_trades: int,
        total_pnl: float,
        win_rate: float
    ):
        """Send daily trading summary"""
        pnl_sign = "+" if total_pnl >= 0 else ""

        text = (
            f"📊 *DAILY SUMMARY*\n\n"
            f"Total Trades: `{total_trades}`\n"
            f"Winning: `{winning_trades}`\n"
            f"Win Rate: `{win_rate * 100:.1f}%`\n\n"
            f"💰 PnL: `{pnl_sign}${total_pnl:.2f}`"
        )

        await self.send_message(text, silent=True)