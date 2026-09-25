import os
import html
import time
import threading
from datetime import datetime, timezone

import requests
import feedparser
from flask import Flask, request, jsonify


# ============================================================
# SIDESHIFT AI
# Complete single-file Telegram crypto analysis bot
# ============================================================

app = Flask(__name__)


# ============================================================
# ENVIRONMENT
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Optional Telegram channel for FREE signals.
FREE_SIGNAL_CHAT_ID = os.getenv("FREE_SIGNAL_CHAT_ID", "")

# Optional Telegram channel for recurring news.
NEWS_CHAT_ID = os.getenv("NEWS_CHAT_ID", "")

CMC_API_KEY = os.getenv("CMC_API_KEY", "")

PORT = int(os.getenv("PORT", "8080"))

REQUEST_TIMEOUT = 15

# How often the background engine checks the market.
SIGNAL_SCAN_INTERVAL = int(
    os.getenv("SIGNAL_SCAN_INTERVAL", "30")
) * 60

# Maximum free signals per UTC day.
MAX_FREE_SIGNALS_PER_DAY = int(
    os.getenv("MAX_FREE_SIGNALS_PER_DAY", "3")
)

# Minimum score required before a free signal can be sent.
MIN_SIGNAL_SCORE = float(
    os.getenv("MIN_SIGNAL_SCORE", "7.0")
)

# Minimum minutes between signals for the same coin.
SIGNAL_COOLDOWN_MINUTES = int(
    os.getenv("SIGNAL_COOLDOWN_MINUTES", "180")
)

# News interval.
NEWS_INTERVAL = int(
    os.getenv("NEWS_INTERVAL", "360"
)
) * 60


TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)


# ============================================================
# MARKET PROVIDERS
#
# Primary:
#   Coinbase
#
# Secondary:
#   Kraken
#
# Tertiary:
#   Binance
#
# Price fallback:
#   CoinMarketCap
#
# The bot does NOT depend exclusively on Binance.
# ============================================================

COINBASE_CANDLES_URL = (
    "https://api.exchange.coinbase.com/products/{product}/candles"
)

KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

CMC_PRICE_URL = (
    "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
)


# ============================================================
# COINS
# ============================================================

COINS = {
    "BTC": {
        "coinbase": "BTC-USD",
        "kraken": "XBTUSD",
        "binance": "BTCUSDT",
        "cmc": "BTC",
    },
    "ETH": {
        "coinbase": "ETH-USD",
        "kraken": "ETHUSD",
        "binance": "ETHUSDT",
        "cmc": "ETH",
    },
    "SOL": {
        "coinbase": "SOL-USD",
        "kraken": "SOLUSD",
        "binance": "SOLUSDT",
        "cmc": "SOL",
    },
    "XRP": {
        "coinbase": "XRP-USD",
        "kraken": "XRPUSD",
        "binance": "XRPUSDT",
        "cmc": "XRP",
    },
    "AVAX": {
        "coinbase": "AVAX-USD",
        "kraken": "AVAXUSD",
        "binance": "AVAXUSDT",
        "cmc": "AVAX",
    },
    "DOGE": {
        "coinbase": "DOGE-USD",
        "kraken": "DOGEUSD",
        "binance": "DOGEUSDT",
        "cmc": "DOGE",
    },
    "LINK": {
        "coinbase": "LINK-USD",
        "kraken": "LINKUSD",
        "binance": "LINKUSDT",
        "cmc": "LINK",
    },
    "ADA": {
        "coinbase": "ADA-USD",
        "kraken": "ADAUSD",
        "binance": "ADAUSDT",
        "cmc": "ADA",
    },
    "SHIB": {
        "coinbase": "SHIB-USD",
        "kraken": "SHIBUSD",
        "binance": "SHIBUSDT",
        "cmc": "SHIB",
    },
    "SUI": {
        "coinbase": "SUI-USD",
        "kraken": "SUIUSD",
        "binance": "SUIUSDT",
        "cmc": "SUI",
    },
    "PEPE": {
        "coinbase": "PEPE-USD",
        "kraken": "PEPEUSD",
        "binance": "PEPEUSDT",
        "cmc": "PEPE",
    },
    "PENGU": {
        "coinbase": "PENGU-USD",
        "kraken": "PENGUUSD",
        "binance": "PENGUUSDT",
        "cmc": "PENGU",
    },
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": {
        "coinbase": 300,
        "kraken": 5,
        "binance": "5m",
        "weight": 0.8,
    },
    "15m": {
        "coinbase": 900,
        "kraken": 15,
        "binance": "15m",
        "weight": 1.0,
    },
    "1h": {
        "coinbase": 3600,
        "kraken": 60,
        "binance": "1h",
        "weight": 1.2,
    },
    "4h": {
        "coinbase": 21600,
        "kraken": 240,
        "binance": "4h",
        "weight": 1.5,
    },
    "1D": {
        "coinbase": 86400,
        "kraken": 1440,
        "binance": "1d",
        "weight": 1.7,
    },
}


# ============================================================
# STATE
# ============================================================

TRADINGVIEW_CACHE = {}

SIGNAL_STATE = {
    "date": None,
    "sent_today": 0,
    "last_signal": {},
}

STATE_LOCK = threading.Lock()

BACKGROUND_STARTED = False


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message, chat_id, keyboard=None):
    if not TELEGRAM_API or not chat_id:
        print("Telegram unavailable: token/chat_id missing")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if keyboard:
        payload["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=15,
        )

        print(
            "TELEGRAM:",
            response.status_code,
            response.text[:300],
        )

        return response.ok

    except Exception as exc:
        print("TELEGRAM ERROR:", repr(exc))
        return False


def answer_callback(callback_id):
    if not callback_id or not TELEGRAM_API:
        return

    try:
        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id
            },
            timeout=10,
        )
    except Exception as exc:
        print("CALLBACK ERROR:", repr(exc))


# ============================================================
# TELEGRAM MENUS
# ============================================================

def main_menu():
    rows = []

    coins = list(COINS.keys())

    for i in range(0, len(coins), 2):
        row = []

        for coin in coins[i:i + 2]:
            row.append({
                "text": f"📊 {coin}",
                "callback_data": f"scan_{coin}",
            })

        rows.append(row)

    rows.extend([
        [
            {
                "text": "🟢 Join Free Signals",
                "callback_data": "free_signals",
            },
            {
                "text": "👑 Join VIP",
                "callback_data": "vip",
            },
        ],
        [
            {
                "text": "🔎 Scan a Coin",
                "callback_data": "scan_menu",
            },
            {
                "text": "📰 Crypto News",
                "callback_data": "news_all",
            },
        ],
        [
            {
                "text": "ℹ️ How It Works",
                "callback_data": "help",
            }
        ],
    ])

    return rows


def scan_menu():
    return [
        [
            {
                "text": "🔎 Scan Another Coin",
                "callback_data": "scan_menu",
            }
        ],
        [
            {
                "text": "📰 News",
                "callback_data": "news_all",
            },
            {
                "text": "👑 VIP",
                "callback_data": "vip",
            },
        ],
        [
            {
                "text": "⬅️ Main Menu",
                "callback_data": "main_menu",
            }
        ],
    ]


# ============================================================
# MATH
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def ema(values, period):
    if len(values) < period:
        return [None] * len(values)

    multiplier = 2 / (period + 1)

    result = [None] * len(values)

    previous = sum(values[:period]) / period

    result[period - 1] = previous

    for i in range(period, len(values)):
        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

    return result


def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]

        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (
            avg_gain * (period - 1)
            + gains[i]
        ) / period

        avg_loss = (
            avg_loss * (period - 1)
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def calculate_atr(candles, period=14):
    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):
        candle = candles[i]

        previous_close = candles[i - 1]["close"]

        tr = max(
            candle["high"] - candle["low"],
            abs(
                candle["high"]
                - previous_close
            ),
            abs(
                candle["low"]
                - previous_close
            ),
        )

        true_ranges.append(tr)

    atr = sum(
        true_ranges[:period]
    ) / period

    for i in range(period, len(true_ranges)):
        atr = (
            atr * (period - 1)
            + true_ranges[i]
        ) / period

    return atr


def calculate_macd(closes):
    if len(closes) < 50:
        return None

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)

    macd_values = []

    for i in range(len(closes)):
        if (
            ema12[i] is not None
            and ema26[i] is not None
        ):
            macd_values.append(
                ema12[i] - ema26[i]
            )

    if len(macd_values) < 9:
        return None

    signal_values = ema(
        macd_values,
        9,
    )

    if signal_values[-1] is None:
        return None

    value = macd_values[-1]
    signal = signal_values[-1]

    return {
        "value": value,
        "signal": signal,
        "histogram": value - signal,
    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_coinbase(rows):
    candles = []

    for row in rows:
        try:
            candles.append({
                "timestamp": int(row[0]) * 1000,
                "low": float(row[1]),
                "high": float(row[2]),
                "open": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        except Exception:
            continue

    candles.sort(
        key=lambda item: item["timestamp"]
    )

    return candles


def normalize_kraken(rows):
    candles = []

    for row in rows:
        try:
            candles.append({
                "timestamp": int(float(row[0])) * 1000,
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[6]),
            })
        except Exception:
            continue

    candles.sort(
        key=lambda item: item["timestamp"]
    )

    return candles


def normalize_binance(rows):
    candles = []

    for row in rows:
        try:
            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        except Exception:
            continue

    candles.sort(
        key=lambda item: item["timestamp"]
    )

    return candles


# ============================================================
# PROVIDER 1 — COINBASE
# ============================================================

def get_coinbase_candles(
    product,
    granularity,
    limit=200,
):
    try:
        response = requests.get(
            COINBASE_CANDLES_URL.format(
                product=product
            ),
            params={
                "granularity": granularity,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "SideShiftAI/3.0"
            },
        )

        if response.status_code != 200:
            print(
                "COINBASE ERROR:",
                product,
                granularity,
                response.status_code,
            )
            return []

        data = response.json()

        if not isinstance(data, list):
            return []

        candles = normalize_coinbase(data)

        return candles[-limit:]

    except Exception as exc:
        print(
            "COINBASE REQUEST ERROR:",
            repr(exc),
        )
        return []


# ============================================================
# PROVIDER 2 — KRAKEN
# ============================================================

def get_kraken_candles(
    pair,
    interval,
):
    try:
        response = requests.get(
            KRAKEN_OHLC_URL,
            params={
                "pair": pair,
                "interval": interval,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "SideShiftAI/3.0"
            },
        )

        if response.status_code != 200:
            print(
                "KRAKEN ERROR:",
                pair,
                interval,
                response.status_code,
            )
            return []

        payload = response.json()

        if payload.get("error"):
            print(
                "KRAKEN API ERROR:",
                payload["error"],
            )
            return []

        result = payload.get(
            "result",
            {},
        )

        rows = None

        for key, value in result.items():
            if key != "last":
                rows = value
                break

        if not rows:
            return []

        return normalize_kraken(rows)

    except Exception as exc:
        print(
            "KRAKEN REQUEST ERROR:",
            repr(exc),
        )
        return []


# ============================================================
# PROVIDER 3 — BINANCE
# ============================================================

def get_binance_candles(
    symbol,
    interval,
    limit=200,
):
    try:
        response = requests.get(
            BINANCE_KLINES_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "SideShiftAI/3.0"
            },
        )

        if response.status_code != 200:
            print(
                "BINANCE ERROR:",
                symbol,
                interval,
                response.status_code,
            )
            return []

        data = response.json()

        if not isinstance(data, list):
            return []

        return normalize_binance(data)

    except Exception as exc:
        print(
            "BINANCE REQUEST ERROR:",
            repr(exc),
        )
        return []


# ============================================================
# PROVIDER ROUTER
# ============================================================

def get_market_candles(
    coin,
    timeframe,
):
    config = COINS[coin]
    tf = TIMEFRAMES[timeframe]

    # --------------------------------------------------------
    # 1. Coinbase
    # --------------------------------------------------------

    candles = get_coinbase_candles(
        config["coinbase"],
        tf["coinbase"],
    )

    if len(candles) >= 60:
        return candles, "Coinbase"

    # --------------------------------------------------------
    # 2. Kraken
    # --------------------------------------------------------

    candles = get_kraken_candles(
        config["kraken"],
        tf["kraken"],
    )

    if len(candles) >= 60:
        return candles, "Kraken"

    # --------------------------------------------------------
    # 3. Binance
    #
    # Used only as a tertiary fallback.
    # --------------------------------------------------------

    candles = get_binance_candles(
        config["binance"],
        tf["binance"],
    )

    if len(candles) >= 60:
        return candles, "Binance"

    return [], None


# ============================================================
# CMC PRICE FALLBACK
# ============================================================

def get_cmc_price(symbol):
    if not CMC_API_KEY:
        return None

    try:
        response = requests.get(
            CMC_PRICE_URL,
            params={
                "symbol": symbol,
                "convert": "USD",
            },
            headers={
                "X-CMC_PRO_API_KEY": CMC_API_KEY,
                "User-Agent": "SideShiftAI/3.0",
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            return None

        payload = response.json()

        data = payload.get(
            "data",
            {},
        )

        coin = data.get(symbol)

        if not coin:
            return None

        return (
            coin[0]
            .get("quote", {})
            .get("USD", {})
            .get("price")
        )

    except Exception as exc:
        print(
            "CMC ERROR:",
            repr(exc),
        )
        return None


# ============================================================
# MARKET STRUCTURE
# ============================================================

def pivot_points(
    candles,
    left=3,
    right=3,
):
    highs = []
    lows = []

    if len(candles) < 20:
        return highs, lows

    for i in range(
        left,
        len(candles) - right,
    ):
        high = candles[i]["high"]
        low = candles[i]["low"]

        nearby = candles[
            i - left:i + right + 1
        ]

        if high == max(
            c["high"] for c in nearby
        ):
            highs.append((i, high))

        if low == min(
            c["low"] for c in nearby
        ):
            lows.append((i, low))

    return highs, lows


def calculate_structure(candles):
    recent = candles[-100:]

    highs, lows = pivot_points(recent)

    if len(highs) < 2 or len(lows) < 2:
        return {
            "label": "Unknown",
            "score": 0,
            "support": None,
            "resistance": None,
        }

    previous_high = highs[-2][1]
    latest_high = highs[-1][1]

    previous_low = lows[-2][1]
    latest_low = lows[-1][1]

    higher_high = latest_high > previous_high
    higher_low = latest_low > previous_low

    lower_high = latest_high < previous_high
    lower_low = latest_low < previous_low

    if higher_high and higher_low:
        label = "Bullish Structure"
        score = 3

    elif lower_high and lower_low:
        label = "Bearish Structure"
        score = -3

    elif higher_high or higher_low:
        label = "Bullish Lean"
        score = 1

    elif lower_high or lower_low:
        label = "Bearish Lean"
        score = -1

    else:
        label = "Mixed / Sideways"
        score = 0

    return {
        "label": label,
        "score": score,
        "support": latest_low,
        "resistance": latest_high,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(candles):
    if len(candles) < 60:
        return {
            "valid": False,
            "direction": "Data Unavailable",
            "score": 0,
        }

    closes = [
        c["close"]
        for c in candles
    ]

    price = closes[-1]

    ema20_series = ema(
        closes,
        20,
    )

    ema50_series = ema(
        closes,
        50,
    )

    ema200_series = ema(
        closes,
        200,
    )

    ema20 = ema20_series[-1]
    ema50 = ema50_series[-1]

    ema200 = (
        ema200_series[-1]
        if ema200_series[-1] is not None
        else None
    )

    score = 0

    evidence = []

    # --------------------------------------------------------
    # EMA TREND
    # --------------------------------------------------------

    if ema20 is not None:
        if price > ema20:
            score += 1
            evidence.append(
                "price_above_ema20"
            )
        else:
            score -= 1
            evidence.append(
                "price_below_ema20"
            )

    if ema20 is not None and ema50 is not None:
        if ema20 > ema50:
            score += 2
            evidence.append(
                "ema20_above_ema50"
            )
        else:
            score -= 2
            evidence.append(
                "ema20_below_ema50"
            )

    long_ema = (
        ema200
        if ema200 is not None
        else ema50
    )

    if long_ema is not None:
        if price > long_ema:
            score += 2
            evidence.append(
                "price_above_long_ema"
            )
        else:
            score -= 2
            evidence.append(
                "price_below_long_ema"
            )

    # --------------------------------------------------------
    # EMA SLOPE
    # --------------------------------------------------------

    if (
        len(ema20_series) >= 8
        and ema20_series[-8] is not None
    ):
        if (
            ema20_series[-1]
            > ema20_series[-8]
        ):
            score += 1
            evidence.append(
                "ema20_rising"
            )

        elif (
            ema20_series[-1]
            < ema20_series[-8]
        ):
            score -= 1
            evidence.append(
                "ema20_falling"
            )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = calculate_rsi(closes)

    if rsi is not None:

        if 55 <= rsi <= 70:
            score += 2
            evidence.append(
                "rsi_bullish"
            )

        elif 30 <= rsi <= 45:
            score -= 2
            evidence.append(
                "rsi_bearish"
            )

        elif rsi > 75:
            # Avoid blindly calling extreme RSI bullish.
            score -= 1
            evidence.append(
                "rsi_extreme_high"
            )

        elif rsi < 25:
            score += 1
            evidence.append(
                "rsi_extreme_low"
            )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    macd = calculate_macd(closes)

    if macd:

        if macd["histogram"] > 0:
            score += 2
            evidence.append(
                "macd_positive"
            )

        elif macd["histogram"] < 0:
            score -= 2
            evidence.append(
                "macd_negative"
            )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if len(closes) >= 11:

        previous = closes[-11]

        if previous != 0:

            momentum = (
                (price - previous)
                / previous
            ) * 100

        else:
            momentum = 0

    else:
        momentum = 0

    if momentum >= 0.5:
        score += 2
        evidence.append(
            "momentum_up"
        )

    elif momentum >= 0.15:
        score += 1
        evidence.append(
            "momentum_up_weak"
        )

    elif momentum <= -0.5:
        score -= 2
        evidence.append(
            "momentum_down"
        )

    elif momentum <= -0.15:
        score -= 1
        evidence.append(
            "momentum_down_weak"
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    recent_volume = [
        c["volume"]
        for c in candles[-21:-1]
    ]

    average_volume = (
        sum(recent_volume)
        / len(recent_volume)
        if recent_volume
        else 0
    )

    volume_ratio = (
        candles[-1]["volume"]
        / average_volume
        if average_volume
        else None
    )

    if volume_ratio is not None:

        if volume_ratio >= 1.25:

            candle_move = (
                candles[-1]["close"]
                - candles[-1]["open"]
            )

            if candle_move > 0:
                score += 1
                evidence.append(
                    "volume_confirms_up"
                )

            elif candle_move < 0:
                score -= 1
                evidence.append(
                    "volume_confirms_down"
                )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = calculate_atr(candles)

    atr_percent = (
        (atr / price) * 100
        if atr and price
        else None
    )

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    structure = calculate_structure(
        candles
    )

    score += structure["score"]

    evidence.append(
        structure["label"]
    )

    # --------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------

    if score >= 8:
        direction = "Strong Bullish"

    elif score >= 4:
        direction = "Bullish"

    elif score >= 2:
        direction = "Bullish Lean"

    elif score <= -8:
        direction = "Strong Bearish"

    elif score <= -4:
        direction = "Bearish"

    elif score <= -2:
        direction = "Bearish Lean"

    else:
        direction = "Consolidation"

    # --------------------------------------------------------
    # VOLUME LABEL
    # --------------------------------------------------------

    if volume_ratio is None:
        volume_label = "Unknown"

    elif volume_ratio >= 1.75:
        volume_label = "Very High"

    elif volume_ratio >= 1.25:
        volume_label = "Above Average"

    elif volume_ratio >= 0.80:
        volume_label = "Normal"

    else:
        volume_label = "Below Average"

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    if atr_percent is None:
        volatility = "Unknown"

    elif atr_percent >= 4:
        volatility = "Very High"

    elif atr_percent >= 2:
        volatility = "High"

    elif atr_percent >= 0.75:
        volatility = "Moderate"

    else:
        volatility = "Low"

    return {
        "valid": True,
        "direction": direction,
        "score": score,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi,
        "macd": macd,
        "momentum_pct": momentum,
        "volume_ratio": volume_ratio,
        "volume": volume_label,
        "atr_percent": atr_percent,
        "volatility": volatility,
        "structure": structure["label"],
        "support": structure["support"],
        "resistance": structure["resistance"],
        "evidence": evidence,
    }


# ============================================================
# TRADINGVIEW
# ============================================================

def tv_key(symbol, timeframe):
    return (
        f"{symbol.upper()}:{timeframe}"
    )


def get_tv_signal(
    symbol,
    timeframe,
):
    item = TRADINGVIEW_CACHE.get(
        tv_key(
            symbol,
            timeframe,
        )
    )

    if not item:
        return None

    # TradingView data expires after 2 hours.
    if (
        time.time()
        - item["received_at"]
        > 7200
    ):
        return None

    return item["data"]


def apply_tradingview(
    result,
    tv,
):
    if not tv:
        return result

    signal = str(
        tv.get("signal", "")
    ).upper()

    if signal in (
        "BUY",
        "LONG",
        "BULLISH",
    ):
        result["score"] += 2

    elif signal in (
        "SELL",
        "SHORT",
        "BEARISH",
    ):
        result["score"] -= 2

    result["tradingview"] = {
        "signal": signal or "N/A",
        "received": True,
    }

    return result


# ============================================================
# COMPLETE COIN SCAN
# ============================================================

def scan_coin(coin):
    if coin not in COINS:
        return None

    timeframe_results = {}

    providers = {}

    price = None

    for timeframe in TIMEFRAMES:

        candles, provider = get_market_candles(
            coin,
            timeframe,
        )

        providers[timeframe] = (
            provider or "Unavailable"
        )

        result = analyze_timeframe(
            candles
        )

        if result.get("valid"):

            price = result["price"]

            tv = get_tv_signal(
                coin,
                timeframe,
            )

            result = apply_tradingview(
                result,
                tv,
            )

        timeframe_results[
            timeframe
        ] = result

    valid_results = [
        result
        for result in timeframe_results.values()
        if result.get("valid")
    ]

    if price is None:
        price = get_cmc_price(
            COINS[coin]["cmc"]
        )

    # --------------------------------------------------------
    # NO DATA
    # --------------------------------------------------------

    if not valid_results:

        return {
            "coin": coin,
            "price": price,
            "timeframes": timeframe_results,
            "providers": providers,
            "valid_count": 0,
            "total_count": len(TIMEFRAMES),
            "overall": {
                "label": "Data Unavailable",
                "score": 0,
                "confidence": 0,
            },
            "data_quality": "Insufficient",
            "signal": None,
        }

    # --------------------------------------------------------
    # WEIGHTED SCORE
    # --------------------------------------------------------

    weighted_score = 0

    total_weight = 0

    for timeframe, result in (
        timeframe_results.items()
    ):

        if not result.get("valid"):
            continue

        weight = TIMEFRAMES[
            timeframe
        ]["weight"]

        weighted_score += (
            result["score"]
            * weight
        )

        total_weight += weight

    average_score = (
        weighted_score / total_weight
        if total_weight
        else 0
    )

    # --------------------------------------------------------
    # TIMEFRAME AGREEMENT
    # --------------------------------------------------------

    bullish = sum(
        1
        for result in valid_results
        if "Bullish"
        in result["direction"]
    )

    bearish = sum(
        1
        for result in valid_results
        if "Bearish"
        in result["direction"]
    )

    total = len(valid_results)

    bullish_ratio = (
        bullish / total
        if total
        else 0
    )

    bearish_ratio = (
        bearish / total
        if total
        else 0
    )

    # --------------------------------------------------------
    # OVERALL DIRECTION
    # --------------------------------------------------------

    if (
        bullish_ratio >= 0.75
        and average_score >= 4
    ):
        overall_label = "Bullish"

    elif (
        bearish_ratio >= 0.75
        and average_score <= -4
    ):
        overall_label = "Bearish"

    elif (
        bullish_ratio >= 0.60
        and average_score >= 2.5
    ):
        overall_label = "Bullish Lean"

    elif (
        bearish_ratio >= 0.60
        and average_score <= -2.5
    ):
        overall_label = "Bearish Lean"

    elif max(
        bullish_ratio,
        bearish_ratio,
    ) < 0.50:
        overall_label = "Indecisive"

    else:
        overall_label = "Consolidation"

    # --------------------------------------------------------
    # CONFIDENCE
    #
    # This is an analysis-strength score.
    # It is NOT a probability of profit.
    # --------------------------------------------------------

    confidence = clamp(
        (
            abs(average_score)
            / 12
        ) * 100,
        0,
        100,
    )

    # Agreement bonus.
    agreement = max(
        bullish_ratio,
        bearish_ratio,
    )

    confidence *= (
        0.70
        + 0.30 * agreement
    )

    confidence = clamp(
        confidence,
        0,
        100,
    )

    # --------------------------------------------------------
    # CONDITIONS
    # --------------------------------------------------------

    rsi_values = [
        result["rsi"]
        for result in valid_results
        if result.get("rsi") is not None
    ]

    average_rsi = (
        sum(rsi_values)
        / len(rsi_values)
        if rsi_values
        else None
    )

    volume_labels = [
        result["volume"]
        for result in valid_results
    ]

    if "Very High" in volume_labels:
        volume = "Very High"

    elif "Above Average" in volume_labels:
        volume = "Above Average"

    elif "Normal" in volume_labels:
        volume = "Normal"

    elif "Below Average" in volume_labels:
        volume = "Below Average"

    else:
        volume = "Unknown"

    volatility_labels = [
        result["volatility"]
        for result in valid_results
    ]

    if "Very High" in volatility_labels:
        volatility = "Very High"

    elif "High" in volatility_labels:
        volatility = "High"

    elif "Moderate" in volatility_labels:
        volatility = "Moderate"

    elif "Low" in volatility_labels:
        volatility = "Low"

    else:
        volatility = "Unknown"

    structures = [
        result["structure"]
        for result in valid_results
    ]

    bullish_structure = sum(
        1
        for value in structures
        if "Bullish" in value
    )

    bearish_structure = sum(
        1
        for value in structures
        if "Bearish" in value
    )

    if bullish_structure > bearish_structure:
        structure = "Bullish"

    elif bearish_structure > bullish_structure:
        structure = "Bearish"

    else:
        structure = "Mixed / Sideways"

    # --------------------------------------------------------
    # SIGNAL ENGINE
    # --------------------------------------------------------

    signal = build_signal(
        coin=coin,
        label=overall_label,
        score=average_score,
        confidence=confidence,
        agreement=agreement,
        valid_count=len(valid_results),
        total_count=len(TIMEFRAMES),
        structure=structure,
        volatility=volatility,
    )

    return {
        "coin": coin,
        "price": price,
        "timeframes": timeframe_results,
        "providers": providers,
        "valid_count": len(valid_results),
        "total_count": len(TIMEFRAMES),
        "overall": {
            "label": overall_label,
            "score": average_score,
            "confidence": confidence,
        },
        "data_quality": (
            "Excellent"
            if len(valid_results) == 5
            else "Good"
            if len(valid_results) >= 4
            else "Partial"
            if len(valid_results) >= 3
            else "Insufficient"
        ),
        "average_rsi": average_rsi,
        "volume": volume,
        "volatility": volatility,
        "structure": structure,
        "signal": signal,
    }


# ============================================================
# SIGNAL ENGINE
# ============================================================

def build_signal(
    coin,
    label,
    score,
    confidence,
    agreement,
    valid_count,
    total_count,
    structure,
    volatility,
):
    # Never produce a signal from partial/weak data.

    if valid_count < 4:
        return None

    # Strong timeframe agreement required.

    if agreement < 0.75:
        return None

    # Minimum analysis strength.

    if confidence < 65:
        return None

    # Strong directional score required.

    if abs(score) < MIN_SIGNAL_SCORE:
        return None

    if label == "Bullish":
        direction = "CALL / LONG"

    elif label == "Bearish":
        direction = "PUT / SHORT"

    else:
        return None

    # Avoid issuing signals during very high volatility.
    if volatility == "Very High":
        return None

    # Structure must agree.

    if direction == "CALL / LONG":
        if structure != "Bullish":
            return None

    if direction == "PUT / SHORT":
        if structure != "Bearish":
            return None

    return {
        "coin": coin,
        "direction": direction,
        "score": round(score, 2),
        "analysis_strength": round(
            confidence,
            1,
        ),
        "agreement": round(
            agreement * 100,
            1,
        ),
        "quality": "HIGH-CONFLUENCE",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }


# ============================================================
# DISPLAY
# ============================================================

def format_price(price):
    if price is None:
        return "Unavailable"

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    if price >= 0.01:
        return f"${price:,.6f}"

    return f"${price:,.10f}"


def direction_emoji(direction):
    if "Bullish" in direction:
        return "🟢"

    if "Bearish" in direction:
        return "🔴"

    if direction in (
        "Consolidation",
        "Indecisive",
    ):
        return "🟡"

    return "⚪"


def build_interpretation(analysis):
    label = analysis[
        "overall"
    ]["label"]

    if label == "Bullish":
        return (
            "Multiple timeframes are aligned "
            "to the bullish side."
        )

    if label == "Bearish":
        return (
            "Multiple timeframes are aligned "
            "to the bearish side."
        )

    if label == "Bullish Lean":
        return (
            "Bullish evidence exists, but "
            "alignment is not strong enough "
            "for a high-confluence signal."
        )

    if label == "Bearish Lean":
        return (
            "Bearish evidence exists, but "
            "alignment is not strong enough "
            "for a high-confluence signal."
        )

    if label == "Consolidation":
        return (
            "The market is relatively balanced "
            "and lacks strong directional alignment."
        )

    if label == "Indecisive":
        return (
            "The timeframes are conflicting."
        )

    return (
        "There is not enough reliable market "
        "data to form a directional conclusion."
    )


def build_scan_message(analysis):
    coin = analysis["coin"]

    overall = analysis["overall"]

    label = overall["label"]

    message = (
        f"<b>🔎 {coin} MARKET ANALYSIS</b>\n\n"
        f"💰 <b>Price:</b> "
        f"{format_price(analysis['price'])}\n\n"
        f"{direction_emoji(label)} "
        f"<b>Overall:</b> {label}\n"
        f"🎯 <b>Analysis Strength:</b> "
        f"{overall['confidence']:.0f}%\n"
        f"📡 <b>Data Quality:</b> "
        f"{analysis['data_quality']} "
        f"({analysis['valid_count']}/"
        f"{analysis['total_count']})\n\n"
        "<b>📊 TIMEFRAME ALIGNMENT</b>\n"
    )

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        direction = result.get(
            "direction",
            "Data Unavailable",
        )

        provider = analysis[
            "providers"
        ].get(
            timeframe,
            "Unavailable",
        )

        message += (
            f"{direction_emoji(direction)} "
            f"<b>{timeframe}</b>: "
            f"{html.escape(direction)}"
            f" — {html.escape(provider)}\n"
        )

    avg_rsi = analysis.get(
        "average_rsi"
    )

    rsi_text = (
        f"{avg_rsi:.1f}"
        if avg_rsi is not None
        else "Unavailable"
    )

    message += (
        "\n<b>📈 MARKET CONDITIONS</b>\n"
        f"📉 RSI: {rsi_text}\n"
        f"📦 Volume: "
        f"{analysis['volume']}\n"
        f"🌊 Volatility: "
        f"{analysis['volatility']}\n"
        f"🧱 Structure: "
        f"{analysis['structure']}\n\n"
        "<b>🧠 INTERPRETATION</b>\n"
        f"{build_interpretation(analysis)}\n\n"
        "<i>Analysis only. "
        "No market outcome is guaranteed.</i>"
    )

    return message


# ============================================================
# FREE SIGNAL MESSAGE
# ============================================================

def build_signal_message(
    analysis,
):
    signal = analysis["signal"]

    if not signal:
        return None

    coin = analysis["coin"]

    price = format_price(
        analysis["price"]
    )

    direction = signal[
        "direction"
    ]

    if direction == "CALL / LONG":
        emoji = "🟢"

    else:
        emoji = "🔴"

    return (
        "<b>🚨 SIDESHIFT AI — FREE SIGNAL</b>\n\n"
        f"{emoji} <b>{coin}</b>\n"
        f"📍 <b>Direction:</b> "
        f"{direction}\n"
        f"💰 <b>Current Price:</b> "
        f"{price}\n\n"
        f"🎯 <b>Analysis Strength:</b> "
        f"{signal['analysis_strength']:.0f}%\n"
        f"📊 <b>Timeframe Agreement:</b> "
        f"{signal['agreement']:.0f}%\n"
        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}\n"
        f"🌊 <b>Volatility:</b> "
        f"{analysis['volatility']}\n\n"
        "<b>⚠️ HIGH-CONFLUENCE SETUP</b>\n\n"
        "<i>This is market analysis, not a "
        "guarantee of profit. Manage risk.</i>"
    )


# ============================================================
# FREE SIGNAL STATE
# ============================================================

def reset_signal_day():
    today = datetime.now(
        timezone.utc
    ).date().isoformat()

    with STATE_LOCK:

        if SIGNAL_STATE["date"] != today:
            SIGNAL_STATE["date"] = today
            SIGNAL_STATE["sent_today"] = 0
            SIGNAL_STATE["last_signal"] = {}


def signal_is_on_cooldown(coin):
    reset_signal_day()

    with STATE_LOCK:

        last = SIGNAL_STATE[
            "last_signal"
        ].get(coin)

        if not last:
            return False

        elapsed = (
            time.time()
            - last
        )

        return (
            elapsed
            < SIGNAL_COOLDOWN_MINUTES * 60
        )


def mark_signal_sent(coin):
    reset_signal_day()

    with STATE_LOCK:

        SIGNAL_STATE[
            "sent_today"
        ] += 1

        SIGNAL_STATE[
            "last_signal"
        ][coin] = time.time()


def can_send_free_signal():
    reset_signal_day()

    with STATE_LOCK:
        return (
            SIGNAL_STATE[
                "sent_today"
            ]
            < MAX_FREE_SIGNALS_PER_DAY
        )


# ============================================================
# FIND BEST SIGNAL
# ============================================================

def find_best_signal():
    best = None

    print(
        "=============================="
    )

    print(
        "SIDESHIFT: scanning market..."
    )

    print(
        "=============================="
    )

    for coin in COINS:

        try:

            if signal_is_on_cooldown(
                coin
            ):
                continue

            analysis = scan_coin(
                coin
            )

            if not analysis:
                continue

            signal = analysis.get(
                "signal"
            )

            if not signal:
                continue

            if (
                best is None
                or signal[
                    "analysis_strength"
                ]
                > best["signal"][
                    "analysis_strength"
                ]
            ):
                best = analysis

        except Exception as exc:

            print(
                "SIGNAL SCAN ERROR:",
                coin,
                repr(exc),
            )

    if best:
        print(
            "BEST SIGNAL:",
            best["coin"],
            best["signal"],
        )

    else:
        print(
            "NO HIGH-CONFLUENCE SIGNAL."
        )

    return best


# ============================================================
# BACKGROUND SIGNAL ENGINE
# ============================================================

def signal_loop():
    print(
        "SideShift signal engine started."
    )

    while True:

        try:

            if FREE_SIGNAL_CHAT_ID:

                if can_send_free_signal():

                    best = find_best_signal()

                    if best:

                        message = (
                            build_signal_message(
                                best
                            )
                        )

                        if message:

                            sent = send_telegram(
                                message,
                                FREE_SIGNAL_CHAT_ID,
                            )

                            if sent:

                                mark_signal_sent(
                                    best["coin"]
                                )

                                print(
                                    "FREE SIGNAL SENT:",
                                    best["coin"],
                                )

                else:

                    print(
                        "Daily free signal limit reached."
                    )

            else:

                print(
                    "FREE_SIGNAL_CHAT_ID "
                    "not configured."
                )

        except Exception as exc:

            print(
                "SIGNAL LOOP ERROR:",
                repr(exc),
            )

        time.sleep(
            SIGNAL_SCAN_INTERVAL
        )


# ============================================================
# NEWS
# ============================================================

def get_crypto_news():
    feed_url = (
        "https://news.google.com/rss/search?"
        "q=cryptocurrency+crypto+bitcoin+ethereum"
        "&hl=en-US&gl=US&ceid=US:en"
    )

    articles = []

    try:

        feed = feedparser.parse(
            feed_url
        )

        for item in feed.entries[:10]:

            title = item.get(
                "title",
                "",
            )

            link = item.get(
                "link",
                "",
            )

            published = item.get(
                "published",
                "",
            )

            if title and link:

                articles.append(
                    (
                        html.unescape(title),
                        link,
                        published,
                    )
                )

    except Exception as exc:

        print(
            "NEWS ERROR:",
            repr(exc),
        )

    if not articles:

        return (
            "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
            "No current headlines available."
        )

    message = (
        "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
    )

    for number, (
        title,
        link,
        published,
    ) in enumerate(
        articles,
        1,
    ):

        message += (
            f"<b>{number}.</b> "
            f'<a href="{html.escape(link, quote=True)}">'
            f"{html.escape(title)}</a>\n"
        )

        if published:
            message += (
                f"<i>{html.escape(published)}</i>\n"
            )

        message += "\n"

    return message


def news_loop():
    print(
        "SideShift news engine started."
    )

    while True:

        try:

            if NEWS_CHAT_ID:

                news = get_crypto_news()

                send_telegram(
                    news,
                    NEWS_CHAT_ID,
                )

            else:

                print(
                    "NEWS_CHAT_ID not configured."
                )

        except Exception as exc:

            print(
                "NEWS LOOP ERROR:",
                repr(exc),
            )

        time.sleep(
            NEWS_INTERVAL
        )


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    return send_telegram(
        (
            "<b>🤖 SIDESHIFT AI</b>\n\n"
            "24/7 crypto market analysis engine.\n\n"
            "<b>Market engine:</b>\n"
            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR volatility\n"
            "🧱 Market structure\n"
            "⏱ Multi-timeframe alignment\n\n"
            "<b>Market data:</b>\n"
            "1️⃣ Coinbase\n"
            "2️⃣ Kraken\n"
            "3️⃣ Binance fallback\n\n"
            "The engine does not assume a trade "
            "when market data is insufficient."
        ),
        chat_id,
        main_menu(),
    )


def send_help(chat_id):

    return send_telegram(
        (
            "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"
            "SideShift analyzes multiple "
            "cryptocurrencies across several "
            "timeframes.\n\n"
            "It checks trend, momentum, RSI, "
            "MACD, volume, volatility and "
            "market structure.\n\n"
            "The signal engine requires "
            "multiple conditions to agree "
            "before producing a signal.\n\n"
            "If the data is weak or conflicting, "
            "the engine can return NO SIGNAL."
        ),
        chat_id,
        main_menu(),
    )


def send_free_info(chat_id):

    return send_telegram(
        (
            "<b>🟢 SIDESHIFT AI FREE SIGNALS</b>\n\n"
            "The free channel receives a limited "
            "number of high-confluence setups.\n\n"
            "The engine scans the supported market "
            "automatically and selects the strongest "
            "qualifying setup.\n\n"
            "No signal is forced when market "
            "conditions do not meet the rules."
        ),
        chat_id,
        main_menu(),
    )


def send_vip(chat_id):

    return send_telegram(
        (
            "<b>👑 SIDESHIFT AI VIP</b>\n\n"
            "VIP signal features are being built.\n\n"
            "The current engine already supports "
            "multi-timeframe market analysis and "
            "high-confluence signal detection."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# MANUAL SCAN
# ============================================================

def perform_scan(
    coin,
    chat_id,
):

    if coin not in COINS:

        send_telegram(
            "❌ Unsupported cryptocurrency.",
            chat_id,
            main_menu(),
        )

        return

    send_telegram(
        (
            f"<b>🔎 SCANNING {coin}</b>\n\n"
            "Collecting market data...\n"
            "Checking multiple providers...\n"
            "Analyzing 5m / 15m / 1h / 4h / 1D...\n"
            "Checking trend...\n"
            "Checking momentum...\n"
            "Checking structure..."
        ),
        chat_id,
    )

    try:

        analysis = scan_coin(
            coin
        )

        if not analysis:

            send_telegram(
                "⚠️ Scan failed.",
                chat_id,
                scan_menu(),
            )

            return

        send_telegram(
            build_scan_message(
                analysis
            ),
            chat_id,
            scan_menu(),
        )

    except Exception as exc:

        print(
            "MANUAL SCAN ERROR:",
            repr(exc),
        )

        send_telegram(
            (
                "<b>⚠️ SCAN ERROR</b>\n\n"
                "The scanner encountered an "
                "internal error.\n\n"
                "No signal was assumed."
            ),
            chat_id,
            scan_menu(),
        )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/telegram-webhook",
    methods=["POST"],
)
def telegram_webhook():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        print(
            "TELEGRAM UPDATE:",
            str(data)[:1000],
        )

        # ----------------------------------------------------
        # NORMAL MESSAGE
        # ----------------------------------------------------

        message = data.get(
            "message"
        )

        if message:

            chat_id = (
                message
                .get("chat", {})
                .get("id")
            )

            text = (
                message.get("text")
                or ""
            ).strip()

            if not chat_id:
                return jsonify({
                    "ok": True
                })

            if text.startswith(
                "/start"
            ):

                send_welcome(
                    chat_id
                )

            elif text.startswith(
                "/help"
            ):

                send_help(
                    chat_id
                )

            elif text.startswith(
                "/news"
            ):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

            elif text.lower().startswith(
                "/scan"
            ):

                parts = text.split()

                if len(parts) < 2:

                    send_telegram(
                        (
                            "<b>📊 SCAN</b>\n\n"
                            "Example:\n"
                            "/scan BTC"
                        ),
                        chat_id,
                        main_menu(),
                    )

                else:

                    coin = (
                        parts[1]
                        .upper()
                    )

                    perform_scan(
                        coin,
                        chat_id,
                    )

            else:

                send_telegram(
                    (
                        "Use /start to open "
                        "SideShift AI."
                    ),
                    chat_id,
                    main_menu(),
                )

            return jsonify({
                "ok": True
            })

        # ----------------------------------------------------
        # BUTTON CALLBACK
        # ----------------------------------------------------

        callback = data.get(
            "callback_query"
        )

        if callback:

            callback_id = callback.get(
                "id"
            )

            callback_data = callback.get(
                "data",
                "",
            )

            chat_id = (
                callback
                .get("message", {})
                .get("chat", {})
                .get("id")
            )

            answer_callback(
                callback_id
            )

            print(
                "BUTTON:",
                callback_data,
            )

            # IMPORTANT:
            # scan_menu must be checked
            # before scan_*.

            if callback_data == "scan_menu":

                send_telegram(
                    (
                        "<b>📊 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency "
                        "to analyze."
                    ),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            if callback_data.startswith(
                "scan_"
            ):

                coin = (
                    callback_data
                    .replace(
                        "scan_",
                        "",
                        1,
                    )
                    .upper()
                )

                perform_scan(
                    coin,
                    chat_id,
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "main_menu":

                send_welcome(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "news_all":

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "help":

                send_help(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "free_signals":

                send_free_info(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "vip":

                send_vip(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            return jsonify({
                "ok": True
            })

        return jsonify({
            "ok": True
        })

    except Exception as exc:

        print(
            "TELEGRAM WEBHOOK ERROR:",
            repr(exc),
        )

        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 500


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"],
)
def tradingview_webhook():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        if (
            WEBHOOK_SECRET
            and data.get("secret")
            != WEBHOOK_SECRET
        ):
            return jsonify({
                "error": "Unauthorized"
            }), 401

        symbol = str(
            data.get(
                "symbol",
                "",
            )
        ).upper()

        timeframe = str(
            data.get(
                "timeframe",
                "",
            )
        ).strip()

        # Normalize symbols.

        symbol = (
            symbol
            .replace(".P", "")
            .replace("/", "")
        )

        if symbol.endswith(
            "USDT"
        ):
            symbol = symbol[:-4]

        elif symbol.endswith(
            "USD"
        ):
            symbol = symbol[:-3]

        if symbol not in COINS:

            return jsonify({
                "error": "Unsupported symbol",
                "symbol": symbol,
            }), 400

        if timeframe not in TIMEFRAMES:

            return jsonify({
                "error": "Unsupported timeframe",
                "timeframe": timeframe,
            }), 400

        TRADINGVIEW_CACHE[
            tv_key(
                symbol,
                timeframe,
            )
        ] = {
            "received_at": time.time(),
            "data": data,
        }

        print(
            "TRADINGVIEW CACHED:",
            symbol,
            timeframe,
        )

        return jsonify({
            "status": "cached",
            "symbol": symbol,
            "timeframe": timeframe,
        })

    except Exception as exc:

        print(
            "TRADINGVIEW ERROR:",
            repr(exc),
        )

        return jsonify({
            "error": str(exc)
        }), 500


# ============================================================
# HEALTH
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def home():

    return jsonify({
        "status": "online",
        "bot": "SideShift AI",
        "version": "3.0",
        "market_engine": "online",
        "signal_engine": (
            "enabled"
            if FREE_SIGNAL_CHAT_ID
            else "not configured"
        ),
        "news_engine": (
            "enabled"
            if NEWS_CHAT_ID
            else "manual only"
        ),
        "providers": [
            "Coinbase",
            "Kraken",
            "Binance fallback",
        ],
        "coins": list(
            COINS.keys()
        ),
        "timeframes": list(
            TIMEFRAMES.keys()
        ),
    })


@app.route(
    "/test-market/<coin>",
    methods=["GET"],
)
def test_market(coin):

    coin = coin.upper()

    if coin not in COINS:

        return jsonify({
            "error": "Unsupported coin",
            "supported": list(
                COINS.keys()
            ),
        }), 400

    try:

        analysis = scan_coin(
            coin
        )

        return jsonify(
            analysis
        )

    except Exception as exc:

        return jsonify({
            "error": str(exc)
        }), 500


@app.route(
    "/health",
    methods=["GET"],
)
def health():

    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
    })


# ============================================================
# TELEGRAM WEBHOOK SETUP
# ============================================================

def setup_telegram_webhook():

    if (
        not TELEGRAM_BOT_TOKEN
        or not RAILWAY_PUBLIC_DOMAIN
    ):

        print(
            "Webhook setup skipped:"
            " missing token or domain."
        )

        return False

    webhook_url = (
        f"https://"
        f"{RAILWAY_PUBLIC_DOMAIN}"
        f"/telegram-webhook"
    )

    try:

        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": [
                    "message",
                    "callback_query",
                ],
                "drop_pending_updates": True,
            },
            timeout=15,
        )

        print(
            "WEBHOOK SETUP:",
            response.status_code,
            response.text,
        )

        return response.ok

    except Exception as exc:

        print(
            "WEBHOOK SETUP ERROR:",
            repr(exc),
        )

        return False


# ============================================================
# BACKGROUND STARTUP
# ============================================================

def start_background_engines():

    global BACKGROUND_STARTED

    if BACKGROUND_STARTED:
        return

    BACKGROUND_STARTED = True

    # Free signal engine.

    if FREE_SIGNAL_CHAT_ID:

        signal_thread = threading.Thread(
            target=signal_loop,
            daemon=True,
        )

        signal_thread.start()

    # Recurring news engine.

    if NEWS_CHAT_ID:

        news_thread = threading.Thread(
            target=news_loop,
            daemon=True,
        )

        news_thread.start()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "SideShift AI 3.0 starting..."
    )

    print(
        "========================================"
    )

    print(
        "Telegram:",
        "FOUND"
        if TELEGRAM_BOT_TOKEN
        else "MISSING",
    )

    print(
        "Railway domain:",
        RAILWAY_PUBLIC_DOMAIN
        or "MISSING",
    )

    print(
        "Free signal channel:",
        "FOUND"
        if FREE_SIGNAL_CHAT_ID
        else "NOT CONFIGURED",
    )

    print(
        "News channel:",
        "FOUND"
        if NEWS_CHAT_ID
        else "NOT CONFIGURED",
    )

    print(
        "CMC:",
        "FOUND"
        if CMC_API_KEY
        else "NOT SET",
    )

    print(
        "Market providers:",
        "Coinbase -> Kraken -> Binance"
    )

    setup_telegram_webhook()

    start_background_engines()

    app.run(
        host="0.0.0.0",
        port=PORT,
    )