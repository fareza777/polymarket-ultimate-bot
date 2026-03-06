# 🤖 Polymarket Ultimate Bot

**Bot trading otomatis untuk Polymarket dengan strategi multi-signal, arbitrage, dan analisis sentimen.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ Fitur

### 🎯 Strategi Trading
- **Signal Strategy** - Berdasarkan data order flow Binance (OBI, CVD, RSI, MACD, VWAP, EMA)
- **Arbitrage Strategy** - Cross-timeframe arbitrage (5m vs 15m vs 1h)
- **Sentiment Strategy** - Fear & Greed Index dan sentiment analysis
- **Combined Strategy** - Kombinasi ketiga strategi dengan bobot yang bisa diatur

### 📊 Data Feeds
- Real-time Binance order book dan trade data
- Polymarket price feeds via WebSocket
- Fear & Greed Index integration
- Multi-market support (BTC, ETH, SOL, XRP)

### 🛡️ Risk Management
- Dynamic position sizing
- Stop loss dan take profit otomatis
- Max exposure limits
- Win/loss streak handling
- Cooldown periods

### 📱 Monitoring
- Terminal dashboard dengan Rich
- Telegram notifications
- Performance tracking

### 🧪 Simulation Mode
- Paper trading untuk testing
- Virtual balance tracking
- Real market data

---

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/USERNAME/polymarket-ultimate-bot.git
cd polymarket-ultimate-bot
```

### 2. Setup Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
# Copy example config
cp .env.example .env

# Edit with your settings
notepad .env  # Windows
nano .env     # Linux/Mac
```

### 5. Run Bot
```bash
# Simulation mode (paper trading)
python main.py

# Or with specific config
SIMULATION_MODE=true python main.py
```

---

## ⚙️ Konfigurasi

### Trading Mode
```env
# Paper Trading (Simulation) - AMAN untuk testing!
SIMULATION_MODE=true

# Live Trading - GUNAKAN SETELAH YAKIN!
SIMULATION_MODE=false
```

### Strategy Weights
```env
# Bobot strategi (harus total = 1.0)
SIGNAL_STRATEGY_WEIGHT=0.50    # 50% signal
ARBITRAGE_STRATEGY_WEIGHT=0.30  # 30% arbitrage
SENTIMENT_STRATEGY_WEIGHT=0.20  # 20% sentiment
```

### Position Sizing
```env
BASE_POSITION_SIZE=10.0       # Ukuran dasar ($)
MAX_POSITION_SIZE=50.0        # Maksimal per trade ($)
MAX_TOTAL_EXPOSURE=200.0      # Total exposure maksimal ($)
```

### Risk Parameters
```env
STOP_LOSS_PCT=0.15            # 15% stop loss
TAKE_PROFIT_PCT=0.30          # 30% take profit
MAX_HOLD_TIME_SECONDS=1800    # 30 menit max hold
```

### Telegram (Optional)
```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 📁 Struktur Proyek

```
polymarket-ultimate-bot/
├── core/               # Konfigurasi, constants, exceptions
├── data/               # Data feeds (Binance, Polymarket, Sentiment)
├── strategies/         # Strategi trading
├── execution/          # Order execution dan position management
├── risk/               # Risk management
├── monitoring/         # Dashboard dan Telegram
├── main.py             # Entry point
├── .env.example        # Template konfigurasi
├── requirements.txt    # Dependencies
└── README.md           # Dokumentasi
```

---

## 📈 Cara Kerja

### 1. Data Collection
- Binance WebSocket → Order book, trades, klines
- Polymarket WebSocket → Real-time prices
- Fear & Greed API → Market sentiment

### 2. Signal Generation
- **Bias Score** (-100 to +100) dari weighted indicators
- Score > 60 = BULLISH, Score < 40 = BEARISH
- Strong signals (≥85 atau ≤15) = 2x position size

### 3. Risk Assessment
- Check cooldowns
- Check exposure limits
- Calculate position size

### 4. Execution
- Paper trading (simulation) atau
- Live trading via Polymarket CLOB API

### 5. Position Management
- Monitor stop loss / take profit
- Check time-based exits
- Send notifications

---

## 📊 Dashboard

Bot menampilkan dashboard real-time di terminal:

```
╔══════════════════════════════════════════════════════════════╗
║  POLYMARKET ULTIMATE BOT  2024-01-15 10:30:00               ║
╠══════════════════════════════════════════════════════════════╣
║  📊 MARKETS                                                  ║
║  Market      Up Price   Down Price   Spread                 ║
║  BTC_5m      0.524      0.476        0.0%                   ║
║  ETH_15m     0.498      0.502        0.0%                   ║
╠══════════════════════════════════════════════════════════════╣
║  🎯 SIGNALS                                                  ║
║  Market      Direction    Score   Confidence                ║
║  BTC_5m      🚀 BULLISH   72      65%                       ║
║  ETH_15m     ➖ NEUTRAL    52      30%                       ║
╠══════════════════════════════════════════════════════════════╣
║  💼 POSITIONS                                                ║
║  ID          Direction   Entry     PnL       Age            ║
║  BTC_5m      BULLISH     $0.5200   +$2.50    5m 30s         ║
╠══════════════════════════════════════════════════════════════╣
║  📈 STATS                                                    ║
║  Total Balance: $1,025.50                                    ║
║  Total PnL: +$25.50                                          ║
║  Win Rate: 62.5%                                             ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🔔 Telegram Notifications

Bot mengirim notifikasi untuk:

### Trade Entry
```
🚀 NEW TRADE

📊 BTC 5m
Direction: BULLISH
Score: 75/100

💰 Entry: $0.5200
Shares: 19.23
Size: $10.00

🛑 SL: $0.4420
✅ TP: $0.6760
```

### Trade Exit
```
✅ POSITION CLOSED

📊 BTC 5m
Reason: take_profit

💰 Entry: $0.5200
Exit: $0.6760

PnL: +$3.00 (+30.00%)
```

---

## ⚠️ Risk Warnings

1. **Trading prediction markets berisiko tinggi** - Hanya gunakan uang yang siap hilang
2. **Simulation ≠ Live performance** - Slippage, fees, dan latency mempengaruhi hasil
3. **Bot tidak menjamin profit** - Market bisa irrational
4. **Monitor secara regular** - Jangan leave bot unattended
5. **Start small** - Mulai dengan position size minimal

---

## 🧪 Testing Checklist

Sebelum live trading, pastikan:
- [ ] Simulation mode berjalan tanpa error
- [ ] Data feeds berfungsi (Binance, Polymarket)
- [ ] Strategy signals masuk akal
- [ ] Risk management bekerja
- [ ] Telegram notifications berfungsi (jika diaktifkan)
- [ ] Tested minimal 24 jam di simulation mode

---

## 🛠️ Development

### Run Tests
```bash
pytest tests/
```

### Format Code
```bash
black .
isort .
```

### Type Check
```bash
mypy .
```

---

## 📄 License

MIT License - see LICENSE file.

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

---

## 📞 Support

- GitHub Issues: [Open an issue](https://github.com/USERNAME/polymarket-ultimate-bot/issues)
- Logs: Check `polymarket_bot.log`

---

**Happy Trading! 🚀**

*Remember: Trade responsibly and never risk more than you can afford to lose.*