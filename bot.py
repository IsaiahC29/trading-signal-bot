import os
import html
import requests
import feedparser
import numpy as np
import pandas as pd

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
# MARKET DATA
# ============================================================

BYBIT_API = "https://api.bybit.com"

# We use Bybit public market data.
# No trading account or API key is required for these endpoints.

MARKET_CATEGORY = "spot"

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


TIMEFRAMES = {
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1D": "D",
}


# ============================================================
# TELEGRAM MESSAGE
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
        "text": message
    }

    if keyboard:
        payload["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    try:

        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=20
        )

        print(
            "TELEGRAM SEND:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:

        print("TELEGRAM SEND ERROR:", e)

        return False


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    return [
        [
            {"text": "📊 BTC", "callback_data": "scan_BTC"},
            {"text": "📊 ETH", "callback_data": "scan_ETH"}
        ],
        [
            {"text": "📊 SOL", "callback_data": "scan_SOL"},
            {"text": "📊 XRP", "callback_data": "scan_XRP"}
        ],
        [
            {"text": "📊 PENGU", "callback_data": "scan_PENGU"},
            {"text": "📊 AVAX", "callback_data": "scan_AVAX"}
        ],
        [
            {"text": "📊 SHIB", "callback_data": "scan_SHIB"},
            {"text": "📊 DOGE", "callback_data": "scan_DOGE"}
        ],
        [
            {"text": "📊 LINK", "callback_data": "scan_LINK"},
            {"text": "📊 ADA", "callback_data": "scan_ADA"}
        ],
        [
            {"text": "📊 SUI", "callback_data": "scan_SUI"},
            {"text": "📊 PEPE", "callback_data": "scan_PEPE"}
        ],
        [
            {"text": "📰 Crypto News", "callback_data": "news_all"}
        ],
        [
            {"text": "ℹ️ Help", "callback_data": "help"}
        ]
    ]


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    message = (
        "🤖 SIDESHIFT AI\n\n"
        "Welcome to SideShift AI.\n\n"
        "Use the scanner to analyze the current market "
        "direction of supported cryptocurrencies.\n\n"

        "The scanner evaluates:\n"
        "📊 Trend\n"
        "⚡ Momentum\n"
        "📈 RSI & MACD\n"
        "📦 Volume\n"
        "🌊 Volatility\n"
        "🧱 Market Structure\n"
        "📐 Price Slope\n\n"

        "Multi-timeframe analysis:\n"
        "5m • 15m • 1h • 4h • 1D\n\n"

        "The scanner describes whether the market is "
        "Bullish, Bearish, Consolidating, or Indecisive.\n\n"

        "⚠️ Market analysis is not a guarantee of future results "
        "and is not financial advice."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# HELP
# ============================================================

def send_help(chat_id):

    message = (
        "ℹ️ SIDESHIFT AI — HOW IT WORKS\n\n"

        "Select a cryptocurrency to request a market scan.\n\n"

        "The scanner analyzes multiple independent factors "
        "instead of relying on a single indicator.\n\n"

        "📊 Trend\n"
        "⚡ Momentum\n"
        "📈 RSI\n"
        "📉 MACD\n"
        "📦 Volume\n"
        "🌊 Volatility\n"
        "🧱 Market Structure\n"
        "📐 Price Slope\n\n"

        "Timeframes:\n"
        "5m • 15m • 1h • 4h • 1D\n\n"

        "The scanner is designed to describe the current "
        "market condition. It does not automatically mean "
        "that a trade should be taken."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# BYBIT MARKET DATA
# ============================================================

def get_market_candles(symbol, interval, limit=250):

    url = f"{BYBIT_API}/v5/market/kline"

    params = {
        "category": MARKET_CATEGORY,
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        if data.get("retCode") != 0:

            print(
                "BYBIT ERROR:",
                symbol,
                interval,
                data
            )

            return None

        rows = data.get(
            "result",
            {}
        ).get(
            "list",
            []
        )

        if not rows:

            return None

        # Bybit returns newest first.
        rows = list(reversed(rows))

        candles = []

        for row in rows:

            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        df = pd.DataFrame(candles)

        if len(df) < 80:

            print(
                "NOT ENOUGH CANDLES:",
                symbol,
                interval,
                len(df)
            )

            return None

        return df

    except Exception as e:

        print(
            "MARKET DATA ERROR:",
            symbol,
            interval,
            e
        )

        return None


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def calculate_indicators(df):

    df = df.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    df["ema20"] = close.ewm(
        span=20,
        adjust=False
    ).mean()

    df["ema50"] = close.ewm(
        span=50,
        adjust=False
    ).mean()

    df["ema200"] = close.ewm(
        span=200,
        adjust=False
    ).mean()

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    df["rsi"] = 100 - (
        100 / (1 + rs)
    )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    df["macd"] = ema12 - ema26

    df["macd_signal"] = df["macd"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["macd_hist"] = (
        df["macd"] -
        df["macd_signal"]
    )

    # --------------------------------------------------------
    # TRUE RANGE / ATR
    # --------------------------------------------------------

    previous_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high -
        previous_close
    ).abs()

    tr3 = (
        low -
        previous_close
    ).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    df["atr"] = true_range.rolling(
        14
    ).mean()

    df["atr_percent"] = (
        df["atr"] /
        close
    ) * 100

    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    up_move = high.diff()

    down_move = -low.diff()

    plus_dm = np.where(
        (up_move > down_move) &
        (up_move > 0),
        up_move,
        0
    )

    minus_dm = np.where(
        (down_move > up_move) &
        (down_move > 0),
        down_move,
        0
    )

    tr14 = true_range.rolling(
        14
    ).sum()

    plus_di = (
        100 *
        pd.Series(
            plus_dm,
            index=df.index
        ).rolling(14).sum() /
        tr14
    )

    minus_di = (
        100 *
        pd.Series(
            minus_dm,
            index=df.index
        ).rolling(14).sum() /
        tr14
    )

    dx = (
        (
            plus_di -
            minus_di
        ).abs() /
        (
            plus_di +
            minus_di
        ).replace(0, np.nan)
    ) * 100

    df["adx"] = dx.rolling(
        14
    ).mean()

    df["plus_di"] = plus_di
    df["minus_di"] = minus_di

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    df["volume_avg"] = volume.rolling(
        20
    ).mean()

    df["volume_ratio"] = (
        volume /
        df["volume_avg"]
    )

    # --------------------------------------------------------
    # PRICE SLOPE
    # --------------------------------------------------------

    lookback = 30

    slopes = []

    for i in range(len(df)):

        if i < lookback:

            slopes.append(np.nan)

            continue

        prices = close.iloc[
            i - lookback:i
        ].values

        x = np.arange(
            len(prices)
        )

        slope = np.polyfit(
            x,
            prices,
            1
        )[0]

        average_price = np.mean(
            prices
        )

        if average_price == 0:

            slopes.append(0)

        else:

            normalized = (
                slope /
                average_price
            ) * 100

            slopes.append(
                normalized
            )

    df["slope"] = slopes

    return df


# ============================================================
# MARKET STRUCTURE
# ============================================================

def determine_structure(df):

    recent = df.tail(30)

    highs = recent["high"].values
    lows = recent["low"].values

    midpoint = len(recent) // 2

    first_half_high = np.max(
        highs[:midpoint]
    )

    second_half_high = np.max(
        highs[midpoint:]
    )

    first_half_low = np.min(
        lows[:midpoint]
    )

    second_half_low = np.min(
        lows[midpoint:]
    )

    higher_highs = (
        second_half_high >
        first_half_high
    )

    higher_lows = (
        second_half_low >
        first_half_low
    )

    lower_highs = (
        second_half_high <
        first_half_high
    )

    lower_lows = (
        second_half_low <
        first_half_low
    )

    if higher_highs and higher_lows:

        return "Bullish Structure"

    if lower_highs and lower_lows:

        return "Bearish Structure"

    if (
        higher_highs and
        lower_lows
    ) or (
        lower_highs and
        higher_lows
    ):

        return "Mixed Structure"

    return "Sideways Structure"


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(df):

    if df is None:

        return {
            "status": "Data Unavailable"
        }

    df = calculate_indicators(df)

    latest = df.iloc[-1]

    required_values = [
        latest["close"],
        latest["ema20"],
        latest["ema50"],
        latest["ema200"],
        latest["rsi"],
        latest["macd"],
        latest["macd_signal"],
        latest["adx"],
        latest["volume_ratio"],
        latest["atr_percent"],
        latest["slope"]
    ]

    if any(
        pd.isna(value)
        for value in required_values
    ):

        return {
            "status": "Insufficient Data"
        }

    bullish = 0
    bearish = 0
    neutral = 0

    # --------------------------------------------------------
    # EMA TREND
    # --------------------------------------------------------

    if (
        latest["ema20"] >
        latest["ema50"] >
        latest["ema200"]
    ):

        bullish += 3

    elif (
        latest["ema20"] <
        latest["ema50"] <
        latest["ema200"]
    ):

        bearish += 3

    else:

        if latest["ema20"] > latest["ema50"]:

            bullish += 1

        elif latest["ema20"] < latest["ema50"]:

            bearish += 1

        else:

            neutral += 1

    # --------------------------------------------------------
    # PRICE VS EMA
    # --------------------------------------------------------

    if latest["close"] > latest["ema50"]:

        bullish += 1

    elif latest["close"] < latest["ema50"]:

        bearish += 1

    else:

        neutral += 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = latest["rsi"]

    if rsi >= 55:

        bullish += 2

    elif rsi <= 45:

        bearish += 2

    else:

        neutral += 2

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if (
        latest["macd"] >
        latest["macd_signal"] and
        latest["macd_hist"] > 0
    ):

        bullish += 2

    elif (
        latest["macd"] <
        latest["macd_signal"] and
        latest["macd_hist"] < 0
    ):

        bearish += 2

    else:

        neutral += 1

    # --------------------------------------------------------
    # ADX + DIRECTIONAL MOVEMENT
    # --------------------------------------------------------

    adx = latest["adx"]

    if adx >= 25:

        if latest["plus_di"] > latest["minus_di"]:

            bullish += 2

        elif latest["minus_di"] > latest["plus_di"]:

            bearish += 2

        else:

            neutral += 1

    else:

        neutral += 2

    # --------------------------------------------------------
    # PRICE SLOPE
    # --------------------------------------------------------

    slope = latest["slope"]

    if slope > 0.015:

        bullish += 2

    elif slope < -0.015:

        bearish += 2

    else:

        neutral += 1

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    structure = determine_structure(
        df
    )

    if structure == "Bullish Structure":

        bullish += 3

    elif structure == "Bearish Structure":

        bearish += 3

    elif structure == "Sideways Structure":

        neutral += 2

    else:

        neutral += 1

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    volume_ratio = latest["volume_ratio"]

    if volume_ratio >= 1.20:

        if bullish > bearish:

            bullish += 1

        elif bearish > bullish:

            bearish += 1

    # --------------------------------------------------------
    # DETERMINE DIRECTION
    # --------------------------------------------------------

    total_directional = (
        bullish +
        bearish +
        neutral
    )

    if total_directional == 0:

        return {
            "status": "Insufficient Data"
        }

    difference = bullish - bearish

    # Strong directional conditions
    if (
        bullish >= bearish + 4 and
        bullish >= neutral
    ):

        direction = "Bullish"

    elif (
        bearish >= bullish + 4 and
        bearish >= neutral
    ):

        direction = "Bearish"

    # Clear but less extreme direction
    elif (
        bullish > bearish and
        bullish >= neutral + 1
    ):

        direction = "Bullish"

    elif (
        bearish > bullish and
        bearish >= neutral + 1
    ):

        direction = "Bearish"

    # Strongly balanced / sideways
    elif neutral >= bullish and neutral >= bearish:

        direction = "Consolidation"

    else:

        direction = "Indecisive"

    # --------------------------------------------------------
    # MOMENTUM DESCRIPTION
    # --------------------------------------------------------

    momentum_value = difference

    if momentum_value >= 6:

        momentum = "Strong Bullish"

    elif momentum_value >= 2:

        momentum = "Bullish"

    elif momentum_value <= -6:

        momentum = "Strong Bearish"

    elif momentum_value <= -2:

        momentum = "Bearish"

    else:

        momentum = "Neutral / Mixed"

    # --------------------------------------------------------
    # VOLUME DESCRIPTION
    # --------------------------------------------------------

    if volume_ratio >= 1.50:

        volume_description = "High"

    elif volume_ratio >= 1.10:

        volume_description = "Above Average"

    elif volume_ratio >= 0.80:

        volume_description = "Normal"

    else:

        volume_description = "Below Average"

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    atr_percent = latest["atr_percent"]

    if atr_percent >= 3:

        volatility = "High"

    elif atr_percent >= 1.5:

        volatility = "Moderate"

    else:

        volatility = "Low"

    return {
        "status": "OK",
        "direction": direction,
        "bullish_score": bullish,
        "bearish_score": bearish,
        "neutral_score": neutral,
        "momentum": momentum,
        "rsi": float(latest["rsi"]),
        "volume": volume_description,
        "volume_ratio": float(volume_ratio),
        "volatility": volatility,
        "atr_percent": float(atr_percent),
        "structure": structure,
        "adx": float(adx),
        "slope": float(slope)
    }


# ============================================================
# OVERALL MULTI-TIMEFRAME ANALYSIS
# ============================================================

def determine_overall_direction(results):

    weights = {
        "5m": 1.0,
        "15m": 1.2,
        "1h": 1.5,
        "4h": 2.0,
        "1D": 2.5
    }

    weighted_bullish = 0
    weighted_bearish = 0
    weighted_neutral = 0

    available = 0

    for timeframe, result in results.items():

        if result.get("status") != "OK":

            continue

        weight = weights.get(
            timeframe,
            1
        )

        weighted_bullish += (
            result["bullish_score"] *
            weight
        )

        weighted_bearish += (
            result["bearish_score"] *
            weight
        )

        weighted_neutral += (
            result["neutral_score"] *
            weight
        )

        available += 1

    if available < 3:

        return (
            "Insufficient Data",
            0
        )

    total = (
        weighted_bullish +
        weighted_bearish +
        weighted_neutral
    )

    if total <= 0:

        return (
            "Indecisive",
            0
        )

    directional_difference = (
        weighted_bullish -
        weighted_bearish
    )

    strength = abs(
        directional_difference
    ) / total * 100

    # --------------------------------------------------------
    # OVERALL CLASSIFICATION
    # --------------------------------------------------------

    if (
        weighted_bullish >
        weighted_bearish * 1.18 and
        weighted_bullish >
        weighted_neutral
    ):

        direction = "Bullish"

    elif (
        weighted_bearish >
        weighted_bullish * 1.18 and
        weighted_bearish >
        weighted_neutral
    ):

        direction = "Bearish"

    elif weighted_neutral > (
        weighted_bullish +
        weighted_bearish
    ) / 2:

        direction = "Consolidation"

    else:

        direction = "Indecisive"

    return (
        direction,
        round(strength, 1)
    )


# ============================================================
# MARKET INTERPRETATION
# ============================================================

def build_market_interpretation(
    coin,
    overall,
    results
):

    valid_results = {
        tf: result
        for tf, result in results.items()
        if result.get("status") == "OK"
    }

    if not valid_results:

        return (
            "Reliable market data was not available "
            "for enough timeframes to describe the "
            "current market condition."
        )

    bullish_count = sum(
        1
        for result in valid_results.values()
        if result["direction"] == "Bullish"
    )

    bearish_count = sum(
        1
        for result in valid_results.values()
        if result["direction"] == "Bearish"
    )

    consolidation_count = sum(
        1
        for result in valid_results.values()
        if result["direction"] == "Consolidation"
    )

    if overall == "Bullish":

        if bearish_count > 0:

            return (
                f"{coin} is showing an overall bullish "
                f"structure across the available timeframes. "
                f"Some shorter timeframes may still be "
                f"pulling back or moving against the broader "
                f"direction."
            )

        return (
            f"{coin} is showing bullish conditions across "
            f"multiple timeframes, supported by trend, "
            f"momentum and market structure."
        )

    if overall == "Bearish":

        if bullish_count > 0:

            return (
                f"{coin} is showing an overall bearish "
                f"structure across the available timeframes. "
                f"Some shorter timeframes may still be "
                f"moving against the broader direction."
            )

        return (
            f"{coin} is showing bearish conditions across "
            f"multiple timeframes, supported by trend, "
            f"momentum and market structure."
        )

    if overall == "Consolidation":

        return (
            f"{coin} is currently showing consolidation. "
            f"Price movement is relatively balanced and "
            f"the available indicators do not show enough "
            f"directional agreement for a clear bullish "
            f"or bearish trend."
        )

    return (
        f"{coin} is showing mixed conditions. "
        f"Bullish and bearish evidence are competing "
        f"across the available timeframes, so the current "
        f"direction is not clearly established."
    )


# ============================================================
# FORMAT MARKET ANALYSIS
# ============================================================

def format_market_analysis(
    coin,
    symbol,
    price,
    overall,
    strength,
    results
):

    direction_icons = {
        "Bullish": "🟢",
        "Bearish": "🔴",
        "Consolidation": "🟡",
        "Indecisive": "⚪",
        "Insufficient Data": "⚠️"
    }

    overall_icon = direction_icons.get(
        overall,
        "⚪"
    )

    message = (
        f"🔎 {coin} MARKET ANALYSIS\n\n"
        f"💰 Price: ${price:,.8f}\n\n"
        f"{overall_icon} Overall Direction: {overall}\n"
    )

    if strength > 0:

        message += (
            f"📊 Directional Strength: {strength:.1f}%\n"
        )

    message += (
        "\n"
        "📊 MULTI-TIMEFRAME ANALYSIS\n"
    )

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h",
        "1D"
    ]:

        result = results.get(
            timeframe,
            {}
        )

        status = result.get(
            "status"
        )

        if status != "OK":

            message += (
                f"{timeframe}: ⚠️ "
                f"{status}\n"
            )

            continue

        direction = result["direction"]

        icon = direction_icons.get(
            direction,
            "⚪"
        )

        message += (
            f"{timeframe}: "
            f"{icon} {direction}\n"
        )

    # --------------------------------------------------------
    # CURRENT CONDITIONS
    # --------------------------------------------------------

    valid = [
        result
        for result in results.values()
        if result.get("status") == "OK"
    ]

    if valid:

        latest = valid[-1]

        average_rsi = np.mean([
            result["rsi"]
            for result in valid
        ])

        average_adx = np.mean([
            result["adx"]
            for result in valid
        ])

        strongest_momentum = max(
            valid,
            key=lambda x: abs(
                x["bullish_score"] -
                x["bearish_score"]
            )
        )

        message += (
            "\n"
            "📈 MARKET CONDITIONS\n"
            f"⚡ Momentum: "
            f"{strongest_momentum['momentum']}\n"
            f"📊 Average RSI: {average_rsi:.1f}\n"
            f"📦 Volume: "
            f"{latest['volume']}\n"
            f"🌊 Volatility: "
            f"{latest['volatility']}\n"
            f"🧱 Structure: "
            f"{latest['structure']}\n"
            f"📐 Average ADX: "
            f"{average_adx:.1f}\n"
        )

    interpretation = build_market_interpretation(
        coin,
        overall,
        results
    )

    message += (
        "\n"
        "🧠 MARKET INTERPRETATION\n"
        f"{interpretation}\n\n"
        "⚪ This is market analysis, not a trade-entry "
        "signal.\n\n"
        "📌 The scanner evaluates current market data. "
        "It does not guarantee future price movement."
    )

    return message


# ============================================================
# COMPLETE COIN SCAN
# ============================================================

def scan_coin(coin):

    if coin not in COINS:

        return None, (
            "That cryptocurrency is not supported."
        )

    symbol = COINS[coin]

    timeframe_results = {}

    price = None

    # --------------------------------------------------------
    # SCAN EVERY TIMEFRAME
    # --------------------------------------------------------

    for timeframe, interval in TIMEFRAMES.items():

        print(
            f"SCANNING {coin} "
            f"{timeframe} "
            f"{symbol}"
        )

        df = get_market_candles(
            symbol,
            interval,
            250
        )

        if df is not None:

            if price is None:

                price = float(
                    df["close"].iloc[-1]
                )

            result = analyze_timeframe(
                df
            )

        else:

            result = {
                "status":
                "Data Unavailable"
            }

        timeframe_results[
            timeframe
        ] = result

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    overall, strength = (
        determine_overall_direction(
            timeframe_results
        )
    )

    if price is None:

        return None, (
            f"⚠️ {coin} SCAN\n\n"
            "Reliable market data could not be "
            "retrieved for this asset right now.\n\n"
            "The scanner will not invent a market "
            "direction when valid data is unavailable."
        )

    message = format_market_analysis(
        coin,
        symbol,
        price,
        overall,
        strength,
        timeframe_results
    )

    return message, None


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/telegram-webhook",
    methods=["POST"]
)
def telegram_webhook():

    try:

        data = request.get_json(
            silent=True
        )

        print("========================================")
        print("TELEGRAM UPDATE RECEIVED")
        print(data)
        print("========================================")

        if not data:

            return jsonify({
                "ok": True
            })

        # ====================================================
        # NORMAL TELEGRAM MESSAGE
        # ====================================================

        message = data.get(
            "message"
        )

        if message:

            chat = message.get(
                "chat",
                {}
            )

            chat_id = chat.get(
                "id"
            )

            text = message.get(
                "text",
                ""
            )

            if not text:

                return jsonify({
                    "ok": True
                })

            text = text.strip()

            if not chat_id:

                return jsonify({
                    "ok": True
                })

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

                news = get_crypto_news()

                send_telegram(
                    news,
                    chat_id,
                    main_menu()
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
                        "📊 Please choose a coin.\n\n"
                        "Example:\n"
                        "/scan BTC\n"
                        "/scan ETH\n"
                        "/scan XRP",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                coin = parts[1].upper()

                if coin not in COINS:

                    send_telegram(
                        "❌ That coin is not currently supported.",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                send_scan(
                    coin,
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            send_telegram(
                "Use /start to open the menu.",
                chat_id,
                main_menu()
            )

            return jsonify({
                "ok": True
            })

        # ====================================================
        # TELEGRAM BUTTON PRESS
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
                ""
            )

            callback_message = callback.get(
                "message",
                {}
            )

            callback_chat = callback_message.get(
                "chat",
                {}
            )

            chat_id = callback_chat.get(
                "id"
            )

            print(
                "BUTTON:",
                callback_data
            )

            # ------------------------------------------------
            # ACKNOWLEDGE BUTTON
            # ------------------------------------------------

            if callback_id and TELEGRAM_API:

                try:

                    requests.post(
                        f"{TELEGRAM_API}/answerCallbackQuery",
                        json={
                            "callback_query_id":
                            callback_id
                        },
                        timeout=10
                    )

                except Exception as e:

                    print(
                        "CALLBACK ACK ERROR:",
                        e
                    )

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            if callback_data.startswith(
                "scan_"
            ):

                coin = callback_data.replace(
                    "scan_",
                    ""
                )

                if coin in COINS:

                    send_scan(
                        coin,
                        chat_id
                    )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if callback_data == "news_all":

                news = get_crypto_news()

                send_telegram(
                    news,
                    chat_id,
                    main_menu()
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

            return jsonify({
                "ok": True
            })

        return jsonify({
            "ok": True
        })

    except Exception as e:

        print(
            "TELEGRAM WEBHOOK ERROR:",
            e
        )

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500


# ============================================================
# SEND SCAN
# ============================================================

def send_scan(
    coin,
    chat_id
):

    symbol = COINS[coin]

    # --------------------------------------------------------
    # SCANNING MESSAGE
    # --------------------------------------------------------

    send_telegram(
        (
            f"🔎 Scanning {symbol}...\n\n"
            "Analyzing:\n"
            "📊 Trend\n"
            "⚡ Momentum\n"
            "📈 RSI\n"
            "📉 MACD\n"
            "📦 Volume\n"
            "🌊 Volatility\n"
            "🧱 Market Structure\n"
            "📐 Price Slope\n\n"
            "⏱ Timeframes:\n"
            "5m • 15m • 1h • 4h • 1D"
        ),
        chat_id
    )

    # --------------------------------------------------------
    # PERFORM ACTUAL SCAN
    # --------------------------------------------------------

    message, error = scan_coin(
        coin
    )

    if error:

        send_telegram(
            error,
            chat_id,
            main_menu()
        )

        return

    send_telegram(
        message,
        chat_id,
        main_menu()
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
                ""
            )

            link = item.get(
                "link",
                ""
            )

            if title:

                articles.append(
                    (
                        html.unescape(title),
                        link
                    )
                )

    except Exception as e:

        print(
            "NEWS ERROR:",
            e
        )

    if not articles:

        return (
            "📰 Crypto News\n\n"
            "No current headlines were available."
        )

    message = (
        "📰 CRYPTO MARKET NEWS\n\n"
    )

    for number, article in enumerate(
        articles,
        start=1
    ):

        title, link = article

        message += (
            f"{number}. {title}\n"
            f"{link}\n\n"
        )

    return message


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"]
)
def tradingview_webhook():

    try:

        data = request.get_json(
            silent=True
        )

        print(
            "TRADINGVIEW SIGNAL:",
            data
        )

        if not data:

            return jsonify({
                "error": "No JSON received"
            }), 400

        if WEBHOOK_SECRET:

            incoming_secret = data.get(
                "secret"
            )

            if incoming_secret != WEBHOOK_SECRET:

                return jsonify({
                    "error": "Unauthorized"
                }), 401

        symbol = data.get(
            "symbol",
            "UNKNOWN"
        )

        signal = str(
            data.get(
                "signal",
                "NO TRADE"
            )
        ).upper()

        timeframe = data.get(
            "timeframe",
            "N/A"
        )

        entry = data.get(
            "entry",
            "N/A"
        )

        stop_loss = data.get(
            "stop_loss",
            "N/A"
        )

        tp1 = data.get(
            "tp1",
            "N/A"
        )

        tp2 = data.get(
            "tp2",
            "N/A"
        )

        tp3 = data.get(
            "tp3",
            "N/A"
        )

        if signal == "LONG":

            emoji = "🟢"

        elif signal == "SHORT":

            emoji = "🔴"

        else:

            emoji = "⚪"

        signal_message = (
            f"{emoji} {signal}\n\n"
            f"{symbol}\n"
            f"⏱ Timeframe: {timeframe}\n\n"
            f"Entry: {entry}\n"
            f"Stop Loss: {stop_loss}\n\n"
            f"TP1: {tp1}\n"
            f"TP2: {tp2}\n"
            f"TP3: {tp3}"
        )

        if TELEGRAM_CHAT_ID:

            send_telegram(
                signal_message,
                TELEGRAM_CHAT_ID
            )

        return jsonify({
            "status": "signal received",
            "symbol": symbol,
            "signal": signal
        })

    except Exception as e:

        print(
            "TRADINGVIEW WEBHOOK ERROR:",
            e
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({
        "status": "online",
        "bot": "SideShift AI",
        "market_data": "Bybit Public API",
        "telegram_webhook":
            "/telegram-webhook",
        "tradingview_webhook":
            "/webhook",
        "coins":
            list(COINS.keys()),
        "timeframes":
            list(TIMEFRAMES.keys())
    })


# ============================================================
# SET TELEGRAM WEBHOOK
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
        webhook_url
    )

    try:

        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": [
                    "message",
                    "callback_query"
                ],
                "drop_pending_updates": True
            },
            timeout=15
        )

        print(
            "WEBHOOK SETUP:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:

        print(
            "WEBHOOK SETUP ERROR:",
            e
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
            RAILWAY_PUBLIC_DOMAIN
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

    print(
        "Market data provider: Bybit"
    )

    print(
        "Timeframes: 5m, 15m, 1h, 4h, 1D"
    )

    setup_telegram_webhook()

    port = int(
        os.getenv(
            "PORT",
            "8080"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )