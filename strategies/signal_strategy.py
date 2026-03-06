# ═══════════════════════════════════════════════════════════════
# POLYMARKET ULTIMATE BOT - SIGNAL STRATEGY
# Binance-based signal generation strategy
# ═══════════════════════════════════════════════════════════════

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .base import BaseStrategy, StrategyResult
from core.constants import (
    Direction, StrategyType,
    BIAS_WEIGHTS, RSI_OVERBOUGHT, RSI_OVERSOLD,
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    EMA_SHORT, EMA_LONG
)

logger = logging.getLogger(__name__)


class SignalStrategy(BaseStrategy):
    """
    Signal-based trading strategy using Binance order flow

    Indicators used:
    - Order Book Imbalance (OBI)
    - Cumulative Volume Delta (CVD)
    - RSI, MACD, VWAP
    - EMA crossovers
    - Heikin Ashi patterns
    - Volume Profile POC
    - Buy/Sell Walls
    """

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)

        # Thresholds
        self.entry_bullish_threshold = self.config.get("entry_bullish_threshold", 70)
        self.entry_bearish_threshold = self.config.get("entry_bearish_threshold", 30)
        self.strong_signal_threshold = self.config.get("strong_signal_threshold", 85)

        # Bias weights
        self.weights = BIAS_WEIGHTS.copy()

    def get_name(self) -> str:
        return "SignalStrategy"

    def get_type(self) -> StrategyType:
        return StrategyType.SIGNAL

    async def analyze(self, data: Dict[str, Any]) -> StrategyResult:
        """
        Analyze market data and generate signals

        Args:
            data: Must contain 'binance_state' with orderbook, trades, klines

        Returns:
            StrategyResult with bias score and direction
        """
        state = data.get("binance_state")
        if not state:
            raise ValueError("binance_state required in data")

        coin = data.get("coin", "")
        timeframe = data.get("timeframe", "5m")

        # Calculate all indicators
        indicators = self._calculate_indicators(state)

        # Calculate bias score
        bias_score = self._calculate_bias_score(state, indicators)

        # Determine direction
        direction = self._score_to_direction(bias_score)

        # Generate signals list
        signals = self._generate_signals(state, indicators)

        # Calculate confidence
        confidence = self._calculate_confidence(bias_score, indicators)

        return self._create_result(
            score=bias_score,
            direction=direction,
            confidence=confidence,
            signals=signals,
            indicators=indicators,
            coin=coin,
            timeframe=timeframe
        )

    def _calculate_indicators(self, state) -> Dict[str, Any]:
        """Calculate all technical indicators"""
        indicators = {}

        # Order Book Imbalance
        indicators["obi"] = self._calc_obi(state)

        # CVD
        indicators["cvd_1m"] = self._calc_cvd(state, 60)
        indicators["cvd_5m"] = self._calc_cvd(state, 300)

        # RSI
        indicators["rsi"] = self._calc_rsi(state)

        # MACD
        macd, signal, hist = self._calc_macd(state)
        indicators["macd"] = macd
        indicators["macd_signal"] = signal
        indicators["macd_hist"] = hist

        # VWAP
        indicators["vwap"] = self._calc_vwap(state)

        # EMA
        ema_s, ema_l = self._calc_ema(state)
        indicators["ema_short"] = ema_s
        indicators["ema_long"] = ema_l

        # Heikin Ashi
        indicators["ha"] = self._calc_heikin_ashi(state)

        # Volume Profile POC
        indicators["poc"] = self._calc_poc(state)

        # Walls
        indicators["buy_walls"], indicators["sell_walls"] = self._calc_walls(state)

        return indicators

    def _calc_obi(self, state) -> float:
        """Calculate Order Book Imbalance"""
        if not state.mid_price or not state.bids or not state.asks:
            return 0.0

        band = state.mid_price * 0.5 / 100  # 0.5% band

        bid_vol = sum(q for p, q in state.bids if p >= state.mid_price - band)
        ask_vol = sum(q for p, q in state.asks if p <= state.mid_price + band)

        total = bid_vol + ask_vol
        if total == 0:
            return 0.0

        return (bid_vol - ask_vol) / total

    def _calc_cvd(self, state, window_seconds: int) -> float:
        """Calculate Cumulative Volume Delta"""
        import time
        cutoff = time.time() - window_seconds

        return sum(
            t.price * t.quantity * (1 if t.is_buy else -1)
            for t in state.trades
            if t.timestamp >= cutoff
        )

    def _calc_rsi(self, state) -> Optional[float]:
        """Calculate RSI"""
        if len(state.klines) < RSI_PERIOD + 1:
            return None

        closes = [k.close for k in state.klines]
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        gains = [max(c, 0) for c in changes[:RSI_PERIOD]]
        losses = [abs(min(c, 0)) for c in changes[:RSI_PERIOD]]

        avg_gain = sum(gains) / RSI_PERIOD
        avg_loss = sum(losses) / RSI_PERIOD

        for c in changes[RSI_PERIOD:]:
            avg_gain = (avg_gain * (RSI_PERIOD - 1) + max(c, 0)) / RSI_PERIOD
            avg_loss = (avg_loss * (RSI_PERIOD - 1) + abs(min(c, 0))) / RSI_PERIOD

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1 + rs))

    def _calc_macd(self, state) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate MACD"""
        if len(state.klines) < MACD_SLOW:
            return None, None, None

        closes = [k.close for k in state.klines]

        # Calculate EMAs
        ema_fast = self._calc_ema_series(closes, MACD_FAST)
        ema_slow = self._calc_ema_series(closes, MACD_SLOW)

        if ema_fast is None or ema_slow is None:
            return None, None, None

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line (EMA of MACD)
        # Simplified - just return the histogram
        return macd_line, None, macd_line

    def _calc_ema_series(self, values: List[float], period: int) -> Optional[float]:
        """Calculate EMA for a series"""
        if len(values) < period:
            return None

        multiplier = 2.0 / (period + 1)
        ema = sum(values[:period]) / period

        for v in values[period:]:
            ema = v * multiplier + ema * (1 - multiplier)

        return ema

    def _calc_vwap(self, state) -> float:
        """Calculate VWAP"""
        if not state.klines:
            return 0.0

        total_value = sum(
            (k.high + k.low + k.close) / 3 * k.volume
            for k in state.klines
        )
        total_volume = sum(k.volume for k in state.klines)

        return total_value / total_volume if total_volume > 0 else 0.0

    def _calc_ema(self, state) -> Tuple[Optional[float], Optional[float]]:
        """Calculate short and long EMA"""
        if len(state.klines) < EMA_LONG:
            return None, None

        closes = [k.close for k in state.klines]
        ema_short = self._calc_ema_series(closes, EMA_SHORT)
        ema_long = self._calc_ema_series(closes, EMA_LONG)

        return ema_short, ema_long

    def _calc_heikin_ashi(self, state) -> List[Dict]:
        """Calculate Heikin Ashi candles"""
        if not state.klines:
            return []

        ha = []
        for i, k in enumerate(state.klines):
            close = (k.open + k.high + k.low + k.close) / 4
            if i == 0:
                open_price = (k.open + k.close) / 2
            else:
                open_price = (ha[i - 1]["open"] + ha[i - 1]["close"]) / 2

            ha.append({
                "open": open_price,
                "close": close,
                "green": close >= open_price
            })

        return ha[-8:]  # Return last 8

    def _calc_poc(self, state) -> float:
        """Calculate Volume Profile POC"""
        if not state.klines:
            return 0.0

        # Simplified POC - use VWAP
        return self._calc_vwap(state)

    def _calc_walls(self, state) -> Tuple[List, List]:
        """Calculate buy/sell walls"""
        if not state.bids or not state.asks:
            return [], []

        all_vols = [q for _, q in state.bids] + [q for _, q in state.asks]
        if not all_vols:
            return [], []

        avg = sum(all_vols) / len(all_vols)
        threshold = avg * 3.0  # 3x average = wall

        buy_walls = [(p, q) for p, q in state.bids if q >= threshold]
        sell_walls = [(p, q) for p, q in state.asks if q >= threshold]

        return buy_walls, sell_walls

    def _calculate_bias_score(self, state, indicators: Dict) -> float:
        """
        Calculate bias score (-100 to +100)

        Uses weighted sum of all indicators
        """
        total = 0.0
        W = self.weights

        # EMA cross
        ema_s = indicators.get("ema_short")
        ema_l = indicators.get("ema_long")
        if ema_s and ema_l:
            total += W["ema"] if ema_s > ema_l else -W["ema"]

        # OBI
        obi = indicators.get("obi", 0)
        total += obi * W["obi"]

        # MACD
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None:
            total += W["macd"] if macd_hist > 0 else -W["macd"]

        # CVD
        cvd5 = indicators.get("cvd_5m", 0)
        if cvd5 != 0:
            total += W["cvd"] if cvd5 > 0 else -W["cvd"]

        # Heikin Ashi streak
        ha = indicators.get("ha", [])
        if ha:
            streak = 0
            for c in reversed(ha[-3:]):
                if c["green"]:
                    if streak >= 0:
                        streak += 1
                    else:
                        break
                else:
                    if streak <= 0:
                        streak -= 1
                    else:
                        break
            total += max(-W["ha"], min(W["ha"], streak * (W["ha"] / 3)))

        # VWAP
        vwap = indicators.get("vwap", 0)
        if vwap and state.mid_price:
            total += W["vwap"] if state.mid_price > vwap else -W["vwap"]

        # RSI
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi <= RSI_OVERSOLD:
                total += W["rsi"]
            elif rsi >= RSI_OVERBOUGHT:
                total -= W["rsi"]
            elif rsi < 50:
                total += W["rsi"] * (50 - rsi) / 20
            else:
                total -= W["rsi"] * (rsi - 50) / 20

        # POC
        poc = indicators.get("poc", 0)
        if poc and state.mid_price:
            total += W["poc"] if state.mid_price > poc else -W["poc"]

        # Walls
        buy_walls = indicators.get("buy_walls", [])
        sell_walls = indicators.get("sell_walls", [])
        wall_pts = (min(len(buy_walls), 2) - min(len(sell_walls), 2)) * 2
        total += max(-W["walls"], min(W["walls"], wall_pts))

        # Normalize to -100 to +100
        max_possible = sum(W.values())
        raw = (total / max_possible) * 100

        return max(-100.0, min(100.0, raw))

    def _score_to_direction(self, score: float) -> Direction:
        """Convert bias score to direction"""
        if score > 60:
            return Direction.BULLISH
        elif score < 40:
            return Direction.BEARISH
        return Direction.NEUTRAL

    def _generate_signals(self, state, indicators: Dict) -> List[str]:
        """Generate human-readable signals"""
        signals = []

        # OBI
        obi = indicators.get("obi", 0)
        if abs(obi) > 0.05:
            direction = "BULLISH" if obi > 0 else "BEARISH"
            signals.append(f"OBI → {direction} ({obi * 100:+.1f}%)")

        # CVD
        cvd5 = indicators.get("cvd_5m", 0)
        if cvd5 != 0:
            direction = "buy pressure" if cvd5 > 0 else "sell pressure"
            signals.append(f"CVD 5m → {direction}")

        # RSI
        rsi = indicators.get("rsi")
        if rsi is not None:
            if rsi >= RSI_OVERBOUGHT:
                signals.append(f"RSI → overbought ({rsi:.0f})")
            elif rsi <= RSI_OVERSOLD:
                signals.append(f"RSI → oversold ({rsi:.0f})")

        # MACD
        macd_hist = indicators.get("macd_hist")
        if macd_hist is not None:
            direction = "bullish" if macd_hist > 0 else "bearish"
            signals.append(f"MACD hist → {direction}")

        # EMA
        ema_s = indicators.get("ema_short")
        ema_l = indicators.get("ema_long")
        if ema_s and ema_l:
            cross = "golden cross" if ema_s > ema_l else "death cross"
            signals.append(f"EMA → {cross}")

        # Walls
        buy_walls = indicators.get("buy_walls", [])
        sell_walls = indicators.get("sell_walls", [])
        if buy_walls:
            signals.append(f"BUY wall × {len(buy_walls)}")
        if sell_walls:
            signals.append(f"SELL wall × {len(sell_walls)}")

        return signals

    def _calculate_confidence(self, score: float, indicators: Dict) -> float:
        """Calculate confidence based on signal agreement"""
        # More extreme scores = higher confidence
        extremity = abs(score - 50) / 50

        # Count agreeing indicators
        agreeing = 0
        total = 0

        if score > 50:  # Bullish
            if indicators.get("obi", 0) > 0:
                agreeing += 1
            if indicators.get("cvd_5m", 0) > 0:
                agreeing += 1
            if indicators.get("macd_hist", 0) > 0:
                agreeing += 1
            total += 3
        else:  # Bearish
            if indicators.get("obi", 0) < 0:
                agreeing += 1
            if indicators.get("cvd_5m", 0) < 0:
                agreeing += 1
            if indicators.get("macd_hist", 0) < 0:
                agreeing += 1
            total += 3

        agreement = agreeing / max(total, 1)

        # Combine
        confidence = (extremity * 0.5 + agreement * 0.5)

        return min(1.0, max(0.0, confidence))