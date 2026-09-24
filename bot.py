import os
import html
import math
import time
import requests
import feedparser

from flask import Flask, request, jsonify

app = Flask(__name__)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API = None

if TELEGRAM_BOT_TOKEN:
    TELEGRAM_API = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    )


# ============================================================
# MARKET DATA PROVIDERS
# ============================================================

BINANCE_KLINES_URL = (
    "https://api.binance.com/api/v3/klines"
)

BYBIT_KLINES_URL = (
    "https://api.bybit.com/v5/market/kline"
)

REQUEST_TIMEOUT = 12


# ============================================================
# SUPPORTED COINS
# ============================================================

COINS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "PENGU": "PENGUUSDT",
    "AVAX": "AVAXUSDT",
    "SHIB": "SHIBUSDT",
    "DOGE": "DOGEUSDT",
    "LINK": "LINKUSDT",
    "ADA": "ADAUSDT",
    "SUI": "SUIUSDT",
    "PEPE": "PEPEUSDT",
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": {
        "binance": "5m",
        "bybit": "5",
        "limit": 150,
        "weight": 1.0,
    },
    "15m": {
        "binance": "15m",
        "bybit": "15",
        "limit": 150,
        "weight": 1.0,
    },
    "1h": {
        "binance": "1h",
        "bybit": "60",
        "limit": 150,
        "weight": 1.2,
    },
    "4h": {
        "binance": "4h",
        "bybit": "240",
        "limit": 150,
        "weight": 1.4,
    },
    "1D": {
        "binance": "1d",
        "bybit": "D",
        "limit": 150,
        "weight": 1.6,
    },
}


# ============================================================
# TELEGRAM MESSAGE SENDER
# ============================================================

def send_telegram(message, chat_id, keyboard=None):

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_API:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing.")
        return False

    if not chat_id:
        print("ERROR: Telegram chat ID is missing.")
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
            "TELEGRAM SEND:",
            response.status_code,
            response.text,
        )

        return response.ok

    except Exception as e:

        print("TELEGRAM SEND ERROR:", e)

        return False


# ============================================================
# TELEGRAM CALLBACK ACK
# ============================================================

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

    except Exception as e:

        print(
            "CALLBACK ACK ERROR:",
            e
        )


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    return [
        [
            {"text": "📊 BTC", "callback_data": "scan_BTC"},
            {"text": "📊 ETH", "callback_data": "scan_ETH"},
        ],
        [
            {"text": "📊 SOL", "callback_data": "scan_SOL"},
            {"text": "📊 XRP", "callback_data": "scan_XRP"},
        ],
        [
            {"text": "📊 PENGU", "callback_data": "scan_PENGU"},
            {"text": "📊 AVAX", "callback_data": "scan_AVAX"},
        ],
        [
            {"text": "📊 SHIB", "callback_data": "scan_SHIB"},
            {"text": "📊 DOGE", "callback_data": "scan_DOGE"},
        ],
        [
            {"text": "📊 LINK", "callback_data": "scan_LINK"},
            {"text": "📊 ADA", "callback_data": "scan_ADA"},
        ],
        [
            {"text": "📊 SUI", "callback_data": "scan_SUI"},
            {"text": "📊 PEPE", "callback_data": "scan_PEPE"},
        ],
        [
            {"text": "📰 Crypto News", "callback_data": "news_all"},
        ],
        [
            {"text": "ℹ️ How It Works", "callback_data": "help"},
        ],
    ]


# ============================================================
# AFTER-SCAN MENU
# ============================================================

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
# WELCOME
# ============================================================

def send_welcome(chat_id):

    message = (
        "<b>🤖 SIDESHIFT AI</b>\n\n"
        "Welcome to SideShift AI.\n\n"
        "Use the scanner to analyze the current market "
        "condition of supported cryptocurrencies.\n\n"
        "<b>The scanner analyzes:</b>\n"
        "📊 Trend\n"
        "⚡ Momentum\n"
        "📈 RSI\n"
        "📦 Volume\n"
        "🌊 Volatility\n"
        "🧱 Market Structure\n"
        "⏱ 5m • 15m • 1h • 4h • 1D\n\n"
        "This scanner describes market conditions. "
        "It does not automatically create a trade entry."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu(),
    )


# ============================================================
# HELP
# ============================================================

def send_help(chat_id):

    message = (
        "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"
        "Select a cryptocurrency and the scanner "
        "reviews multiple timeframes.\n\n"

        "<b>📊 Trend</b>\n"
        "Measures directional movement using price "
        "and moving-average relationships.\n\n"

        "<b>⚡ Momentum</b>\n"
        "Measures whether buying or selling pressure "
        "is strengthening or weakening.\n\n"

        "<b>📈 RSI</b>\n"
        "Helps identify momentum conditions and "
        "potentially stretched price movement.\n\n"

        "<b>📦 Volume</b>\n"
        "Compares current volume with recent average volume.\n\n"

        "<b>🌊 Volatility</b>\n"
        "Measures how aggressively price is moving.\n\n"

        "<b>🧱 Market Structure</b>\n"
        "Looks for higher highs, higher lows, lower highs "
        "and lower lows.\n\n"

        "<b>⏱ Multiple Timeframes</b>\n"
        "5m • 15m • 1h • 4h • 1D\n\n"

        "The scanner can describe conditions as:\n"
        "🟢 Bullish\n"
        "🔴 Bearish\n"
        "🟡 Consolidation\n"
        "⚪ Indecisive\n\n"

        "<b>Important:</b> Market analysis is not a guarantee "
        "of future price movement."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu(),
    )


# ============================================================
# BASIC MATH
# ============================================================

def safe_float(value, default=0.0):

    try:
        result = float(value)

        if math.isfinite(result):
            return result

        return default

    except Exception:

        return default


def clamp(value, minimum, maximum):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if not values:
        return []

    if len(values) < period:
        return [None] * len(values)

    multiplier = 2 / (period + 1)

    result = [None] * len(values)

    initial = sum(
        values[:period]
    ) / period

    result[period - 1] = initial

    previous = initial

    for i in range(period, len(values)):

        current = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = current

        previous = current

    return result


# ============================================================
# SMA
# ============================================================

def sma(values, period):

    if len(values) < period:
        return None

    return (
        sum(values[-period:]) /
        period
    )


# ============================================================
# RSI
# ============================================================

def calculate_rsi(closes, period=14):

    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(closes)):

        change = closes[i] - closes[i - 1]

        if change >= 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period]) /
        period
    )

    avg_loss = (
        sum(losses[:period]) /
        period
    )

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1)
             + gains[i])
            / period
        )

        avg_loss = (
            (avg_loss * (period - 1)
             + losses[i])
            / period
        )

    if avg_loss == 0:

        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    atr = (
        sum(true_ranges[:period]) /
        period
    )

    for i in range(period, len(true_ranges)):

        atr = (
            (atr * (period - 1)
             + true_ranges[i])
            / period
        )

    return atr


# ============================================================
# MACD
# ============================================================

def calculate_macd(closes):

    if len(closes) < 35:
        return None, None

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
        return None, None

    signal_values = ema(
        macd_values,
        9,
    )

    macd_current = macd_values[-1]
    signal_current = signal_values[-1]

    if signal_current is None:
        return macd_current, None

    return (
        macd_current,
        signal_current,
    )


# ============================================================
# CANDLE DATA NORMALIZATION
# ============================================================

def normalize_binance(data):

    candles = []

    for row in data:

        try:

            candles.append(
                {
                    "timestamp": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )

        except Exception:

            continue

    return candles


def normalize_bybit(data):

    candles = []

    for row in data:

        try:

            candles.append(
                {
                    "timestamp": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
            )

        except Exception:

            continue

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    return candles


# ============================================================
# BINANCE DATA
# ============================================================

def get_binance_candles(symbol, interval, limit):

    try:

        response = requests.get(
            BINANCE_KLINES_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                "BINANCE ERROR:",
                symbol,
                interval,
                response.status_code,
                response.text[:300],
            )

            return []

        data = response.json()

        if not isinstance(data, list):

            return []

        candles = normalize_binance(data)

        return candles

    except Exception as e:

        print(
            "BINANCE REQUEST ERROR:",
            symbol,
            interval,
            e,
        )

        return []


# ============================================================
# BYBIT FALLBACK
# ============================================================

def get_bybit_candles(symbol, interval, limit):

    try:

        response = requests.get(
            BYBIT_KLINES_URL,
            params={
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                "BYBIT ERROR:",
                symbol,
                interval,
                response.status_code,
            )

            return []

        payload = response.json()

        result = payload.get(
            "result",
            {},
        )

        rows = result.get(
            "list",
            [],
        )

        if not rows:
            return []

        return normalize_bybit(rows)

    except Exception as e:

        print(
            "BYBIT REQUEST ERROR:",
            symbol,
            interval,
            e,
        )

        return []


# ============================================================
# GET MARKET CANDLES
# ============================================================

def get_market_candles(symbol, timeframe):

    config = TIMEFRAMES[timeframe]

    # --------------------------------------------------------
    # PRIMARY PROVIDER
    # --------------------------------------------------------

    candles = get_binance_candles(
        symbol,
        config["binance"],
        config["limit"],
    )

    if len(candles) >= 60:

        return candles, "Binance"

    # --------------------------------------------------------
    # FALLBACK PROVIDER
    # --------------------------------------------------------

    candles = get_bybit_candles(
        symbol,
        config["bybit"],
        config["limit"],
    )

    if len(candles) >= 60:

        return candles, "Bybit"

    return [], None


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_structure(candles):

    if len(candles) < 30:

        return {
            "label": "Unknown",
            "score": 0,
        }

    recent = candles[-30:]

    closes = [
        x["close"]
        for x in recent
    ]

    highs = [
        x["high"]
        for x in recent
    ]

    lows = [
        x["low"]
        for x in recent
    ]

    midpoint = len(recent) // 2

    first_half_high = max(
        highs[:midpoint]
    )

    second_half_high = max(
        highs[midpoint:]
    )

    first_half_low = min(
        lows[:midpoint]
    )

    second_half_low = min(
        lows[midpoint:]
    )

    higher_high = (
        second_half_high >
        first_half_high
    )

    higher_low = (
        second_half_low >
        first_half_low
    )

    lower_high = (
        second_half_high <
        first_half_high
    )

    lower_low = (
        second_half_low <
        first_half_low
    )

    if higher_high and higher_low:

        return {
            "label": "Bullish Structure",
            "score": 2,
        }

    if lower_high and lower_low:

        return {
            "label": "Bearish Structure",
            "score": -2,
        }

    if higher_high and not lower_low:

        return {
            "label": "Bullish Lean",
            "score": 1,
        }

    if lower_low and not higher_high:

        return {
            "label": "Bearish Lean",
            "score": -1,
        }

    return {
        "label": "Sideways / Mixed",
        "score": 0,
    }


# ============================================================
# TREND ANALYSIS
# ============================================================

def calculate_trend(closes):

    if len(closes) < 60:

        return {
            "label": "Unknown",
            "score": 0,
            "ema20": None,
            "ema50": None,
        }

    ema20_values = ema(
        closes,
        20,
    )

    ema50_values = ema(
        closes,
        50,
    )

    ema20_current = ema20_values[-1]
    ema50_current = ema50_values[-1]

    if (
        ema20_current is None
        or ema50_current is None
    ):

        return {
            "label": "Unknown",
            "score": 0,
            "ema20": None,
            "ema50": None,
        }

    current_price = closes[-1]

    # --------------------------------------------------------
    # EMA SLOPE
    # --------------------------------------------------------

    previous_ema20 = ema20_values[-6]

    slope = 0

    if previous_ema20:

        slope = (
            ema20_current -
            previous_ema20
        )

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 0

    if current_price > ema20_current:
        score += 1

    else:
        score -= 1

    if ema20_current > ema50_current:
        score += 2

    else:
        score -= 2

    if slope > 0:
        score += 1

    elif slope < 0:
        score -= 1

    if score >= 3:

        label = "Bullish"

    elif score <= -3:

        label = "Bearish"

    else:

        label = "Neutral"

    return {
        "label": label,
        "score": score,
        "ema20": ema20_current,
        "ema50": ema50_current,
    }


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(
    closes,
    rsi_value,
    macd_value,
    macd_signal,
):

    if len(closes) < 30:

        return {
            "label": "Unknown",
            "score": 0,
        }

    score = 0

    # --------------------------------------------------------
    # SHORT-TERM PRICE MOMENTUM
    # --------------------------------------------------------

    previous = closes[-11]

    current = closes[-1]

    if previous != 0:

        percent_change = (
            (current - previous)
            / previous
        ) * 100

    else:

        percent_change = 0

    if percent_change > 0.5:

        score += 2

    elif percent_change > 0.15:

        score += 1

    elif percent_change < -0.5:

        score -= 2

    elif percent_change < -0.15:

        score -= 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi_value is not None:

        if rsi_value >= 60:

            score += 1

        elif rsi_value <= 40:

            score -= 1

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if (
        macd_value is not None
        and macd_signal is not None
    ):

        if macd_value > macd_signal:

            score += 1

        elif macd_value < macd_signal:

            score -= 1

    if score >= 3:

        label = "Strong Bullish"

    elif score >= 1:

        label = "Bullish"

    elif score <= -3:

        label = "Strong Bearish"

    elif score <= -1:

        label = "Bearish"

    else:

        label = "Neutral"

    return {
        "label": label,
        "score": score,
    }


# ============================================================
# VOLUME
# ============================================================

def calculate_volume(candles):

    if len(candles) < 25:

        return {
            "label": "Unknown",
            "ratio": None,
        }

    recent_volumes = [
        x["volume"]
        for x in candles[-21:-1]
    ]

    current_volume = candles[-1]["volume"]

    average_volume = (
        sum(recent_volumes)
        / len(recent_volumes)
    )

    if average_volume <= 0:

        return {
            "label": "Unknown",
            "ratio": None,
        }

    ratio = (
        current_volume /
        average_volume
    )

    if ratio >= 1.75:

        label = "Very High"

    elif ratio >= 1.25:

        label = "Above Average"

    elif ratio >= 0.80:

        label = "Normal"

    else:

        label = "Below Average"

    return {
        "label": label,
        "ratio": ratio,
    }


# ============================================================
# VOLATILITY
# ============================================================

def calculate_volatility(
    candles,
    atr_value,
):

    if (
        not candles
        or atr_value is None
    ):

        return {
            "label": "Unknown",
            "atr_percent": None,
        }

    price = candles[-1]["close"]

    if price <= 0:

        return {
            "label": "Unknown",
            "atr_percent": None,
        }

    atr_percent = (
        atr_value /
        price
    ) * 100

    if atr_percent >= 4:

        label = "Very High"

    elif atr_percent >= 2:

        label = "High"

    elif atr_percent >= 0.75:

        label = "Moderate"

    else:

        label = "Low"

    return {
        "label": label,
        "atr_percent": atr_percent,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(candles):

    if len(candles) < 60:

        return {
            "valid": False,
            "trend": "Data Unavailable",
            "trend_score": 0,
            "momentum": "Data Unavailable",
            "momentum_score": 0,
            "rsi": None,
            "volume": "Unknown",
            "volume_ratio": None,
            "volatility": "Unknown",
            "atr_percent": None,
            "structure": "Unknown",
            "structure_score": 0,
        }

    closes = [
        x["close"]
        for x in candles
    ]

    trend = calculate_trend(
        closes
    )

    rsi_value = calculate_rsi(
        closes
    )

    macd_value, macd_signal = (
        calculate_macd(
            closes
        )
    )

    momentum = calculate_momentum(
        closes,
        rsi_value,
        macd_value,
        macd_signal,
    )

    volume = calculate_volume(
        candles
    )

    atr_value = calculate_atr(
        candles
    )

    volatility = calculate_volatility(
        candles,
        atr_value,
    )

    structure = calculate_structure(
        candles
    )

    # --------------------------------------------------------
    # FINAL TIMEFRAME SCORE
    # --------------------------------------------------------

    score = (
        trend["score"] * 1.5
        + momentum["score"]
        + structure["score"]
    )

    # RSI adjustment
    if rsi_value is not None:

        if rsi_value >= 55:

            score += 0.5

        elif rsi_value <= 45:

            score -= 0.5

    if score >= 4:

        direction = "Bullish"

    elif score <= -4:

        direction = "Bearish"

    elif score >= 1.5:

        direction = "Bullish Lean"

    elif score <= -1.5:

        direction = "Bearish Lean"

    else:

        direction = "Consolidation"

    return {
        "valid": True,
        "trend": trend["label"],
        "trend_score": trend["score"],
        "momentum": momentum["label"],
        "momentum_score": momentum["score"],
        "rsi": rsi_value,
        "volume": volume["label"],
        "volume_ratio": volume["ratio"],
        "volatility": volatility["label"],
        "atr_percent": volatility["atr_percent"],
        "structure": structure["label"],
        "structure_score": structure["score"],
        "score": score,
        "direction": direction,
    }


# ============================================================
# OVERALL MARKET DIRECTION
# ============================================================

def determine_overall_direction(results):

    valid_results = []

    for timeframe, result in results.items():

        if result.get("valid"):

            valid_results.append(
                (
                    timeframe,
                    result,
                )
            )

    if not valid_results:

        return {
            "label": "Data Unavailable",
            "score": 0,
            "confidence": 0,
        }

    weighted_score = 0
    total_weight = 0

    for timeframe, result in valid_results:

        weight = TIMEFRAMES[
            timeframe
        ]["weight"]

        weighted_score += (
            result["score"]
            * weight
        )

        total_weight += weight

    if total_weight == 0:

        return {
            "label": "Indecisive",
            "score": 0,
            "confidence": 0,
        }

    average_score = (
        weighted_score /
        total_weight
    )

    # --------------------------------------------------------
    # COUNT DIRECTIONS
    # --------------------------------------------------------

    bullish_count = 0
    bearish_count = 0
    consolidation_count = 0

    for _, result in valid_results:

        direction = result[
            "direction"
        ]

        if "Bullish" in direction:

            bullish_count += 1

        elif "Bearish" in direction:

            bearish_count += 1

        else:

            consolidation_count += 1

    total = len(valid_results)

    bullish_ratio = (
        bullish_count / total
    )

    bearish_ratio = (
        bearish_count / total
    )

    # --------------------------------------------------------
    # OVERALL CLASSIFICATION
    # --------------------------------------------------------

    if (
        average_score >= 3
        and bullish_ratio >= 0.60
    ):

        label = "Bullish"

    elif (
        average_score <= -3
        and bearish_ratio >= 0.60
    ):

        label = "Bearish"

    elif (
        bullish_ratio >= 0.50
        and average_score > 1
    ):

        label = "Bullish Lean"

    elif (
        bearish_ratio >= 0.50
        and average_score < -1
    ):

        label = "Bearish Lean"

    elif consolidation_count >= (
        total * 0.60
    ):

        label = "Consolidation"

    else:

        label = "Indecisive"

    confidence = (
        abs(average_score) / 7
    ) * 100

    confidence = clamp(
        confidence,
        0,
        100,
    )

    return {
        "label": label,
        "score": average_score,
        "confidence": confidence,
    }


# ============================================================
# PRICE FORMAT
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


# ============================================================
# RSI FORMAT
# ============================================================

def format_rsi(value):

    if value is None:

        return "Unavailable"

    return f"{value:.1f}"


# ============================================================
# DIRECTION EMOJI
# ============================================================

def direction_emoji(direction):

    if direction == "Bullish":

        return "🟢"

    if direction == "Bearish":

        return "🔴"

    if direction == "Bullish Lean":

        return "🟢"

    if direction == "Bearish Lean":

        return "🔴"

    if direction == "Consolidation":

        return "🟡"

    if direction == "Indecisive":

        return "⚪"

    return "⚠️"


# ============================================================
# TIMEFRAME EMOJI
# ============================================================

def timeframe_emoji(direction):

    return direction_emoji(
        direction
    )


# ============================================================
# BUILD MARKET ANALYSIS
# ============================================================

def scan_coin(coin):

    if coin not in COINS:

        return None

    symbol = COINS[coin]

    timeframe_results = {}

    providers = {}

    price = None

    # --------------------------------------------------------
    # FETCH EVERY TIMEFRAME
    # --------------------------------------------------------

    for timeframe in TIMEFRAMES:

        candles, provider = (
            get_market_candles(
                symbol,
                timeframe,
            )
        )

        if candles:

            price = candles[-1]["close"]

        result = analyze_timeframe(
            candles
        )

        timeframe_results[
            timeframe
        ] = result

        providers[
            timeframe
        ] = provider

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    overall = (
        determine_overall_direction(
            timeframe_results
        )
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    valid_count = sum(
        1
        for result in timeframe_results.values()
        if result.get("valid")
    )

    total_count = len(
        timeframe_results
    )

    if valid_count == total_count:

        data_quality = "Excellent"

    elif valid_count >= 4:

        data_quality = "Good"

    elif valid_count >= 3:

        data_quality = "Partial"

    else:

        data_quality = "Insufficient"

    # --------------------------------------------------------
    # AGGREGATE CONDITIONS
    # --------------------------------------------------------

    valid = [
        result
        for result in timeframe_results.values()
        if result.get("valid")
    ]

    rsi_values = [
        result["rsi"]
        for result in valid
        if result.get("rsi") is not None
    ]

    volume_labels = [
        result["volume"]
        for result in valid
    ]

    volatility_labels = [
        result["volatility"]
        for result in valid
    ]

    structure_scores = [
        result["structure_score"]
        for result in valid
    ]

    average_rsi = None

    if rsi_values:

        average_rsi = (
            sum(rsi_values)
            / len(rsi_values)
        )

    if structure_scores:

        average_structure = (
            sum(structure_scores)
            / len(structure_scores)
        )

    else:

        average_structure = 0

    if average_structure >= 1.2:

        structure_label = "Bullish"

    elif average_structure <= -1.2:

        structure_label = "Bearish"

    elif average_structure > 0.3:

        structure_label = "Bullish Lean"

    elif average_structure < -0.3:

        structure_label = "Bearish Lean"

    else:

        structure_label = "Mixed / Sideways"

    # --------------------------------------------------------
    # VOLUME SUMMARY
    # --------------------------------------------------------

    if "Very High" in volume_labels:

        volume_summary = "Very High"

    elif "Above Average" in volume_labels:

        volume_summary = "Above Average"

    elif "Normal" in volume_labels:

        volume_summary = "Normal"

    elif "Below Average" in volume_labels:

        volume_summary = "Below Average"

    else:

        volume_summary = "Unknown"

    # --------------------------------------------------------
    # VOLATILITY SUMMARY
    # --------------------------------------------------------

    if "Very High" in volatility_labels:

        volatility_summary = "Very High"

    elif "High" in volatility_labels:

        volatility_summary = "High"

    elif "Moderate" in volatility_labels:

        volatility_summary = "Moderate"

    elif "Low" in volatility_labels:

        volatility_summary = "Low"

    else:

        volatility_summary = "Unknown"

    return {
        "coin": coin,
        "symbol": symbol,
        "price": price,
        "timeframes": timeframe_results,
        "providers": providers,
        "overall": overall,
        "data_quality": data_quality,
        "valid_count": valid_count,
        "total_count": total_count,
        "average_rsi": average_rsi,
        "volume": volume_summary,
        "volatility": volatility_summary,
        "structure": structure_label,
    }


# ============================================================
# MARKET INTERPRETATION
# ============================================================

def build_interpretation(analysis):

    overall = analysis["overall"]["label"]

    valid_count = analysis[
        "valid_count"
    ]

    total_count = analysis[
        "total_count"
    ]

    if valid_count == 0:

        return (
            "Reliable market data could not be obtained "
            "for the requested timeframes."
        )

    if overall == "Bullish":

        return (
            "Price structure and momentum are currently "
            "leaning bullish across multiple timeframes. "
            "This describes the current market condition "
            "and does not guarantee continued upside."
        )

    if overall == "Bearish":

        return (
            "Price structure and momentum are currently "
            "leaning bearish across multiple timeframes. "
            "This describes the current market condition "
            "and does not guarantee continued downside."
        )

    if overall == "Bullish Lean":

        return (
            "The market is showing a bullish lean, but "
            "the available timeframes are not uniformly "
            "aligned."
        )

    if overall == "Bearish Lean":

        return (
            "The market is showing a bearish lean, but "
            "the available timeframes are not uniformly "
            "aligned."
        )

    if overall == "Consolidation":

        return (
            "Price action is relatively balanced. "
            "The market is showing consolidation rather "
            "than a strong directional move."
        )

    return (
        "The market is showing mixed conditions across "
        "the analyzed timeframes. Direction is currently "
        "indecisive."
    )


# ============================================================
# BUILD TELEGRAM SCAN MESSAGE
# ============================================================

def build_scan_message(analysis):

    coin = analysis["coin"]

    price = format_price(
        analysis["price"]
    )

    overall = analysis[
        "overall"
    ]

    overall_label = overall[
        "label"
    ]

    overall_score = overall[
        "score"
    ]

    confidence = overall[
        "confidence"
    ]

    average_rsi = format_rsi(
        analysis["average_rsi"]
    )

    quality = analysis[
        "data_quality"
    ]

    volume = analysis[
        "volume"
    ]

    volatility = analysis[
        "volatility"
    ]

    structure = analysis[
        "structure"
    ]

    message = (
        f"<b>🔎 {coin} MARKET ANALYSIS</b>\n\n"

        f"💰 <b>Price:</b> {price}\n\n"

        f"{direction_emoji(overall_label)} "
        f"<b>Overall Direction:</b> "
        f"{overall_label}\n"

        f"🎯 <b>Analysis Strength:</b> "
        f"{confidence:.0f}%\n\n"

        f"📊 <b>MULTI-TIMEFRAME ANALYSIS</b>\n"
    )

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        direction = result.get(
            "direction",
            "Data Unavailable",
        )

        emoji = timeframe_emoji(
            direction
        )

        message += (
            f"{emoji} <b>{timeframe}:</b> "
            f"{direction}\n"
        )

    message += (
        "\n"
        "📈 <b>MARKET CONDITIONS</b>\n"
        f"⚡ <b>Momentum:</b> "
        f"{overall_label}\n"
        f"📉 <b>Average RSI:</b> "
        f"{average_rsi}\n"
        f"📦 <b>Volume:</b> "
        f"{volume}\n"
        f"🌊 <b>Volatility:</b> "
        f"{volatility}\n"
        f"🧱 <b>Structure:</b> "
        f"{structure}\n\n"
    )

    message += (
        "🧠 <b>MARKET INTERPRETATION</b>\n"
        f"{build_interpretation(analysis)}\n\n"
    )

    message += (
        f"📡 <b>Data Quality:</b> {quality} "
        f"({analysis['valid_count']}/"
        f"{analysis['total_count']} timeframes)\n\n"
    )

    message += (
        "⚪ <b>This is market analysis, "
        "not a trade-entry signal.</b>\n\n"
        "For entry-focused signals, use the "
        "SideShift AI signal channels."
    )

    return message


# ============================================================
# SCAN PROCESS
# ============================================================

def perform_scan(coin, chat_id):

    symbol = COINS.get(coin)

    if not symbol:

        send_telegram(
            "❌ That cryptocurrency is not currently supported.",
            chat_id,
            main_menu(),
        )

        return

    # --------------------------------------------------------
    # SCANNING MESSAGE
    # --------------------------------------------------------

    send_telegram(
        (
            f"<b>🔎 Scanning {symbol}...</b>\n\n"
            "Analyzing:\n"
            "📊 Trend\n"
            "⚡ Momentum\n"
            "📈 RSI\n"
            "📦 Volume\n"
            "🌊 Volatility\n"
            "🧱 Market Structure\n"
            "⏱ 5m • 15m • 1h • 4h • 1D"
        ),
        chat_id,
    )

    try:

        analysis = scan_coin(
            coin
        )

        if not analysis:

            raise Exception(
                "Unable to create analysis."
            )

        message = build_scan_message(
            analysis
        )

        send_telegram(
            message,
            chat_id,
            scan_menu(),
        )

    except Exception as e:

        print(
            "SCAN ERROR:",
            coin,
            e,
        )

        send_telegram(
            (
                f"<b>⚠️ {coin} SCAN ERROR</b>\n\n"
                "The scanner could not complete the "
                "market analysis right now.\n\n"
                "No market direction was assumed."
            ),
            chat_id,
            scan_menu(),
        )


# ============================================================
# CRYPTO NEWS
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

        for item in feed.entries[:8]:

            title = item.get(
                "title",
                "",
            )

            link = item.get(
                "link",
                "",
            )

            if title:

                articles.append(
                    (
                        html.unescape(
                            title
                        ),
                        link,
                    )
                )

    except Exception as e:

        print(
            "NEWS ERROR:",
            e,
        )

    if not articles:

        return (
            "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
            "No current headlines were available."
        )

    message = (
        "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
    )

    for number, article in enumerate(
        articles,
        start=1,
    ):

        title, link = article

        safe_title = html.escape(
            title
        )

        safe_link = html.escape(
            link,
            quote=True,
        )

        message += (
            f"<b>{number}.</b> "
            f"<a href=\"{safe_link}\">"
            f"{safe_title}"
            f"</a>\n\n"
        )

    return message


# ============================================================
# VIP PLACEHOLDER
# ============================================================

def send_vip(chat_id):

    message = (
        "<b>👑 SIDESHIFT AI VIP</b>\n\n"
        "VIP access will provide access to "
        "the separate signal system when it is "
        "fully configured.\n\n"
        "The public scanner is for market analysis "
        "and does not provide trade-entry signals."
    )

    send_telegram(
        message,
        chat_id,
        main_menu(),
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

        data = request.get_json(
            silent=True
        )

        print(
            "========================================"
        )

        print(
            "TELEGRAM UPDATE RECEIVED"
        )

        print(data)

        print(
            "========================================"
        )

        if not data:

            return jsonify({
                "ok": True
            })

        # ====================================================
        # NORMAL MESSAGE
        # ====================================================

        message = data.get(
            "message"
        )

        if message:

            chat = message.get(
                "chat",
                {},
            )

            chat_id = chat.get(
                "id"
            )

            text = message.get(
                "text",
                "",
            )

            if not chat_id:

                return jsonify({
                    "ok": True
                })

            if not text:

                return jsonify({
                    "ok": True
                })

            text = text.strip()

            print(
                f"Telegram message "
                f"from {chat_id}: {text}"
            )

            # ------------------------------------------------
            # START
            # ------------------------------------------------

            if text.startswith(
                "/start"
            ):

                send_welcome(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # HELP
            # ------------------------------------------------

            if text.startswith(
                "/help"
            ):

                send_help(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if text.startswith(
                "/news"
            ):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            if text.lower().startswith(
                "/scan"
            ):

                parts = text.split()

                if len(parts) < 2:

                    send_telegram(
                        (
                            "<b>📊 SCAN</b>\n\n"
                            "Please choose a cryptocurrency.\n\n"
                            "Example:\n"
                            "/scan BTC\n"
                            "/scan ETH\n"
                            "/scan XRP"
                        ),
                        chat_id,
                        main_menu(),
                    )

                    return jsonify({
                        "ok": True
                    })

                coin = parts[1].upper()

                if coin not in COINS:

                    send_telegram(
                        (
                            "❌ That coin is not "
                            "currently supported."
                        ),
                        chat_id,
                        main_menu(),
                    )

                    return jsonify({
                        "ok": True
                    })

                perform_scan(
                    coin,
                    chat_id,
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            send_telegram(
                (
                    "Use /start to open the "
                    "SideShift AI menu."
                ),
                chat_id,
                main_menu(),
            )

            return jsonify({
                "ok": True
            })

        # ====================================================
        # CALLBACK QUERY
        # ====================================================

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

            callback_message = (
                callback.get(
                    "message",
                    {},
                )
            )

            callback_chat = (
                callback_message.get(
                    "chat",
                    {},
                )
            )

            chat_id = callback_chat.get(
                "id"
            )

            print(
                "BUTTON:",
                callback_data,
            )

            answer_callback(
                callback_id
            )

            # ------------------------------------------------
            # COIN SCAN
            # ------------------------------------------------

            if callback_data.startswith(
                "scan_"
            ):

                coin = callback_data.replace(
                    "scan_",
                    "",
                )

                if coin in COINS:

                    perform_scan(
                        coin,
                        chat_id,
                    )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # MAIN MENU
            # ------------------------------------------------

            if callback_data == "main_menu":

                send_welcome(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # SCAN MENU
            # ------------------------------------------------

            if callback_data == "scan_menu":

                send_telegram(
                    (
                        "<b>📊 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency to "
                        "analyze."
                    ),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if callback_data == "news_all":

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # HELP
            # ------------------------------------------------

            if callback_data == "help":

                send_help(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # VIP
            # ------------------------------------------------

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

    except Exception as e:

        print(
            "TELEGRAM WEBHOOK ERROR:",
            e,
        )

        return jsonify({
            "ok": False,
            "error": str(e),
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

        data = request.get_json(
            silent=True
        )

        print(
            "TRADINGVIEW SIGNAL:",
            data,
        )

        if not data:

            return jsonify({
                "error": "No JSON received"
            }), 400

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        if WEBHOOK_SECRET:

            incoming_secret = data.get(
                "secret"
            )

            if (
                incoming_secret
                != WEBHOOK_SECRET
            ):

                print(
                    "Unauthorized TradingView request."
                )

                return jsonify({
                    "error": "Unauthorized"
                }), 401

        # ----------------------------------------------------
        # SIGNAL DATA
        # ----------------------------------------------------

        symbol = data.get(
            "symbol",
            "UNKNOWN",
        )

        signal = str(
            data.get(
                "signal",
                "NO TRADE",
            )
        ).upper()

        timeframe = data.get(
            "timeframe",
            "N/A",
        )

        entry = data.get(
            "entry",
            "N/A",
        )

        stop_loss = data.get(
            "stop_loss",
            "N/A",
        )

        tp1 = data.get(
            "tp1",
            "N/A",
        )

        tp2 = data.get(
            "tp2",
            "N/A",
        )

        tp3 = data.get(
            "tp3",
            "N/A",
        )

        # ----------------------------------------------------
        # SIGNAL EMOJI
        # ----------------------------------------------------

        if signal == "LONG":

            emoji = "🟢"

        elif signal == "SHORT":

            emoji = "🔴"

        else:

            emoji = "⚪"

        # ----------------------------------------------------
        # SIGNAL MESSAGE
        # ----------------------------------------------------

        signal_message = (
            f"<b>{emoji} {html.escape(signal)}</b>\n\n"
            f"<b>{html.escape(str(symbol))}</b>\n"
            f"⏱ Timeframe: "
            f"{html.escape(str(timeframe))}\n\n"
            f"Entry: {html.escape(str(entry))}\n"
            f"Stop Loss: "
            f"{html.escape(str(stop_loss))}\n\n"
            f"TP1: {html.escape(str(tp1))}\n"
            f"TP2: {html.escape(str(tp2))}\n"
            f"TP3: {html.escape(str(tp3))}"
        )

        # ----------------------------------------------------
        # SEND
        # ----------------------------------------------------

        if TELEGRAM_CHAT_ID:

            send_telegram(
                signal_message,
                TELEGRAM_CHAT_ID,
            )

        else:

            print(
                "WARNING: TELEGRAM_CHAT_ID "
                "is not configured."
            )

        return jsonify({
            "status": "signal received",
            "symbol": symbol,
            "signal": signal,
        })

    except Exception as e:

        print(
            "TRADINGVIEW WEBHOOK ERROR:",
            e,
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def home():

    return jsonify({
        "status": "online",
        "bot": "SideShift AI",
        "telegram_webhook": "/telegram-webhook",
        "tradingview_webhook": "/webhook",
        "coins": list(
            COINS.keys()
        ),
        "timeframes": list(
            TIMEFRAMES.keys()
        ),
    })


# ============================================================
# MARKET TEST ENDPOINT
# ============================================================

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

    analysis = scan_coin(
        coin
    )

    if not analysis:

        return jsonify({
            "error": "Analysis failed"
        }), 500

    return jsonify(
        analysis
    )


# ============================================================
# TELEGRAM WEBHOOK SETUP
# ============================================================

def setup_telegram_webhook():

    if not TELEGRAM_BOT_TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN is missing."
        )

        return False

    if not RAILWAY_PUBLIC_DOMAIN:

        print(
            "ERROR: RAILWAY_PUBLIC_DOMAIN is missing."
        )

        return False

    webhook_url = (
        f"https://{RAILWAY_PUBLIC_DOMAIN}"
        "/telegram-webhook"
    )

    print(
        "SETTING TELEGRAM WEBHOOK:",
        webhook_url,
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

    except Exception as e:

        print(
            "WEBHOOK SETUP ERROR:",
            e,
        )

        return False


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "SideShift AI starting..."
    )

    print(
        "========================================"
    )

    if TELEGRAM_BOT_TOKEN:

        print(
            "Telegram token: FOUND"
        )

    else:

        print(
            "Telegram token: MISSING"
        )

    if RAILWAY_PUBLIC_DOMAIN:

        print(
            "Railway domain:",
            RAILWAY_PUBLIC_DOMAIN,
        )

    else:

        print(
            "Railway domain: MISSING"
        )

    if TELEGRAM_CHAT_ID:

        print(
            "Telegram chat ID: FOUND"
        )

    else:

        print(
            "Telegram chat ID: MISSING"
        )

    setup_telegram_webhook()

    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )