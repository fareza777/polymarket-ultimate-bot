#!/usr/bin/env python3
#
# POLYMARKET ULTIMATE BOT - WEB DASHBOARD
# Modern real-time web interface
#

import json
import logging
import time
from datetime import datetime
from typing import Dict
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'polymarket-ultimate-bot'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global state
dashboard_state = {
    "markets": {},
    "signals": {},
    "positions": {},
    "pnl": {"total": 0.0, "trades": 0, "win_rate": 0.0},
    "sentiment": {"fear_greed_index": 50, "label": "Neutral"},
    "system": {
        "status": "running",
        "uptime": 0,
        "last_update": None,
        "polymarket_ws": "disconnected",
        "binance_ws": "disconnected"
    }
}


def update_market_data(coin: str, timeframe: str, data: dict):
    key = f"{coin}_{timeframe}"
    dashboard_state["markets"][key] = {
        "coin": coin, "timeframe": timeframe,
        "up_price": data.get("up_price", 0),
        "down_price": data.get("down_price", 0),
        "last_update": datetime.now().isoformat()
    }
    dashboard_state["system"]["last_update"] = datetime.now().isoformat()
    try:
        socketio.emit('market_update', dashboard_state["markets"][key])
    except: pass


def update_signal(coin: str, timeframe: str, signal: dict):
    key = f"{coin}_{timeframe}"
    dashboard_state["signals"][key] = {
        "coin": coin, "timeframe": timeframe,
        "direction": signal.get("direction", "NEUTRAL"),
        "score": signal.get("score", 50),
        "confidence": signal.get("confidence", 0),
        "should_trade": signal.get("should_trade", False),
        "last_update": datetime.now().isoformat()
    }
    try:
        socketio.emit('signal_update', dashboard_state["signals"][key])
    except: pass


def update_positions(positions: dict):
    dashboard_state["positions"] = positions
    try:
        socketio.emit('positions_update', positions)
    except: pass


def update_pnl(total: float, trades: int, win_rate: float):
    dashboard_state["pnl"] = {"total": total, "trades": trades, "win_rate": win_rate}
    try:
        socketio.emit('pnl_update', dashboard_state["pnl"])
    except: pass


def update_sentiment(fear_greed_index: int, label: str):
    dashboard_state["sentiment"] = {"fear_greed_index": fear_greed_index, "label": label}
    try:
        socketio.emit('sentiment_update', dashboard_state["sentiment"])
    except: pass


def update_system_status(key: str, value: str):
    dashboard_state["system"][key] = value


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/state')
def get_state():
    return jsonify(dashboard_state)


@app.route('/api/markets')
def get_markets():
    return jsonify(dashboard_state["markets"])


@app.route('/api/signals')
def get_signals():
    return jsonify(dashboard_state["signals"])


@app.route('/api/positions')
def get_positions():
    return jsonify(dashboard_state["positions"])


@app.route('/api/pnl')
def get_pnl():
    return jsonify(dashboard_state["pnl"])


@app.route('/api/sentiment')
def get_sentiment():
    return jsonify(dashboard_state["sentiment"])


@socketio.on('connect')
def handle_connect():
    emit('connected', {'message': 'Connected'})
    emit('full_state', dashboard_state)


def run_dashboard(host: str = "0.0.0.0", port: int = 5000):
    print(f"Starting web dashboard on http://localhost:{port}")
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    run_dashboard()