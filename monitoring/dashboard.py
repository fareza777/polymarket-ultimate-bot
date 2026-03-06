# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - DASHBOARD
# Real-time terminal dashboard with Rich
# ═══════════════════════════════════════════════════════════════

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich import box as bx

logger = logging.getLogger(__name__)


class Dashboard:
    """
    Real-time terminal dashboard

    Displays:
    - Market prices
    - Trading signals
    - Open positions
    - Portfolio stats
    - Recent trades
    """

    def __init__(self):
        self.console = Console(force_terminal=True)
        self._live: Optional[Live] = None
        self._running = False

        # Data to display
        self.market_data: Dict[str, Dict] = {}
        self.signals: Dict[str, Dict] = {}
        self.positions: Dict[str, Dict] = {}
        self.stats: Dict[str, Any] = {}

    async def start(self):
        """Start dashboard"""
        self._running = True
        logger.info("Dashboard started")

    async def stop(self):
        """Stop dashboard"""
        self._running = False
        if self._live:
            self._live.stop()

    def update_market_data(self, coin: str, timeframe: str, data: Dict):
        """Update market data for display"""
        key = f"{coin}_{timeframe}"
        self.market_data[key] = data

    def update_signal(self, coin: str, timeframe: str, signal: Dict):
        """Update signal for display"""
        key = f"{coin}_{timeframe}"
        self.signals[key] = signal

    def update_positions(self, positions: Dict[str, Dict]):
        """Update positions for display"""
        self.positions = positions

    def update_stats(self, stats: Dict[str, Any]):
        """Update portfolio stats"""
        self.stats = stats

    def render(self) -> Group:
        """Render the full dashboard"""
        panels = []

        # Header
        panels.append(self._render_header())

        # Market prices
        if self.market_data:
            panels.append(self._render_markets())

        # Signals
        if self.signals:
            panels.append(self._render_signals())

        # Positions
        if self.positions:
            panels.append(self._render_positions())

        # Stats
        if self.stats:
            panels.append(self._render_stats())

        return Group(*panels)

    def _render_header(self) -> Panel:
        """Render header panel"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = Text()
        text.append("  POLYMARKET ULTIMATE BOT  ", style="bold white on dark_blue")
        text.append(f"  {now}  ", style="dim")

        return Panel(
            text,
            box=bx.DOUBLE,
            expand=True
        )

    def _render_markets(self) -> Panel:
        """Render market prices panel"""
        table = Table(box=None, expand=True, show_header=True)
        table.add_column("Market", style="bold")
        table.add_column("Up Price", justify="right")
        table.add_column("Down Price", justify="right")
        table.add_column("Spread", justify="right")

        for key, data in self.market_data.items():
            up = data.get("up_price", 0)
            down = data.get("down_price", 0)
            spread = abs(up + down - 1) * 100 if up and down else 0

            up_style = "green" if up > 0.5 else "red" if up < 0.5 else "yellow"
            down_style = "red" if up > 0.5 else "green" if up < 0.5 else "yellow"

            table.add_row(
                key,
                f"[{up_style}]{up:.3f}[/{up_style}]",
                f"[{down_style}]{down:.3f}[/{down_style}]",
                f"{spread:.1f}%"
            )

        return Panel(table, title="📊 MARKETS", box=bx.ROUNDED, expand=True)

    def _render_signals(self) -> Panel:
        """Render signals panel"""
        table = Table(box=None, expand=True, show_header=True)
        table.add_column("Market", style="bold")
        table.add_column("Direction", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Top Signals")

        for key, signal in self.signals.items():
            direction = signal.get("direction", "NEUTRAL")
            score = signal.get("score", 50)
            confidence = signal.get("confidence", 0)
            signals_list = signal.get("signals", [])

            if direction == "BULLISH":
                dir_style = "green"
                emoji = "🚀"
            elif direction == "BEARISH":
                dir_style = "red"
                emoji = "📉"
            else:
                dir_style = "yellow"
                emoji = "➖"

            top_signal = signals_list[0] if signals_list else ""

            table.add_row(
                key,
                f"[{dir_style}]{emoji} {direction}[/{dir_style}]",
                f"{score:.0f}",
                f"{confidence * 100:.0f}%",
                f"[dim]{top_signal[:30]}[/dim]" if top_signal else ""
            )

        return Panel(table, title="🎯 SIGNALS", box=bx.ROUNDED, expand=True)

    def _render_positions(self) -> Panel:
        """Render positions panel"""
        table = Table(box=None, expand=True, show_header=True)
        table.add_column("ID", style="bold")
        table.add_column("Direction", justify="center")
        table.add_column("Entry", justify="right")
        table.add_column("Size", justify="right")
        table.add_column("PnL", justify="right")
        table.add_column("Age", justify="right")

        for key, pos in self.positions.items():
            direction = pos.get("direction", "NEUTRAL")
            entry = pos.get("entry_price", 0)
            size = pos.get("position_size", 0)
            pnl = pos.get("pnl", 0)
            age = pos.get("age_seconds", 0)

            if direction == "BULLISH":
                dir_style = "green"
            else:
                dir_style = "red"

            pnl_style = "green" if pnl >= 0 else "red"
            pnl_sign = "+" if pnl >= 0 else ""

            age_str = f"{int(age // 60)}m {int(age % 60)}s"

            table.add_row(
                key,
                f"[{dir_style}]{direction}[/{dir_style}]",
                f"${entry:.4f}",
                f"${size:.2f}",
                f"[{pnl_style}]{pnl_sign}${pnl:.2f}[/{pnl_style}]",
                age_str
            )

        return Panel(table, title="💼 POSITIONS", box=bx.ROUNDED, expand=True)

    def _render_stats(self) -> Panel:
        """Render stats panel"""
        table = Table(box=None, expand=True, show_header=False)
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        for key, value in self.stats.items():
            table.add_row(key.replace("_", " ").title(), str(value))

        return Panel(table, title="📈 STATS", box=bx.ROUNDED, expand=True)

    async def run_live(self, refresh_interval: float = 2.0):
        """Run live dashboard refresh"""
        with Live(
            self.render(),
            console=self.console,
            refresh_per_second=0.5,
            transient=False
        ) as live:
            self._live = live

            while self._running:
                live.update(self.render())
                await asyncio.sleep(refresh_interval)