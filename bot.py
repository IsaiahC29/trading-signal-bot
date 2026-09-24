import os
import html
import requests
import feedparser
import statistics
import time

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
# SUPPORTED COINS
# ============================================================

COINS = {
    "BTC": {
        "coinbase": "BTC-USD",
        "kraken": "XBTUSD"
    },

    "ETH": {
        "coinbase": "ETH-USD",
        "kraken": "ETHUSD"
    },

    "SOL": {
        "coinbase": "SOL-USD",
        "kraken": "SOLUSD"
    },

    "XRP": {
        "coinbase": "XRP-USD",
        "kraken": "XRPUSD"
    },

    "PENGU": {
        "coinbase": "PENGU-USD",
        "kraken": "PENGUUSD"
    },

    "AVAX": {
        "coinbase": "AVAX-USD",
        "kraken": "AVAXUSD"
    },

    "SHIB": {
        "coinbase": "SHIB-USD",
        "kraken": "SHIBUSD"
    },

    "DOGE": {
        "coinbase": "DOGE-USD",
        "kraken": "DOGEUSD"
    },

    "LINK": {
        "coinbase": "LINK-USD",
        "kraken": "LINKUSD"
    },

    "ADA": {
        "coinbase": "ADA-USD",
        "kraken": "ADAUSD"
    },

    "SUI": {
        "coinbase": "SUI-USD",
        "kraken": "SUIUSD"
    },

    "PEPE": {
        "coinbase": "PEPE-USD",
        "kraken": "PEPEUSD"
    }
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 21600
}


# ============================================================
# TELEGRAM
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
            timeout=15
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
        "🤖 <b>SIDESHIFT AI</b>\n\n"

        "Welcome to SideShift AI.\n\n"

        "This bot analyzes cryptocurrency markets "
        "using real-time market data and multiple "
        "technical factors.\n\n"

        "📊 <b>Market Scanner</b>\n"
        "Analyze trend, momentum, volume, volatility, "
        "market structure and multiple timeframes.\n\n"

        "The scanner can identify conditions such as:\n"
        "🟢 Bullish\n"
        "🔴 Bearish\n"
        "🟠 Consolidation\n"
        "🟡 Indecisive\n"
        "⚡ High Volatility\n\n"

        "Select a cryptocurrency below."
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
        "🤖 <b>SIDESHIFT AI HELP</b>\n\n"

        "/start — Open the main menu\n"
        "/scan BTC — Scan Bitcoin\n"
        "/scan ETH — Scan Ethereum\n"
        "/scan XRP — Scan XRP\n"
        "/news — Crypto news\n\n"

        "The market scanner describes current market "
        "conditions. A market scan does not automatically "
        "mean a trade setup exists."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# COINBASE MARKET DATA
# ============================================================

def get_coinbase_candles(product_id, granularity):

    url = (
        f"https://api.exchange.coinbase.com/"
        f"products/{product_id}/candles"
    )

    params = {
        "granularity": granularity
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15,
            headers={
                "User-Agent": "SideShift-AI"
            }
        )

        if not response.ok:

            print(
                "COINBASE ERROR:",
                response.status_code,
                response.text
            )

            return []

        data = response.json()

        if not isinstance(data, list):
            return []

        candles = []

        for row in data:

            if len(row) < 6:
                continue

            candles.append({
                "time": row[0],
                "low": float(row[1]),
                "high": float(row[2]),
                "open": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        candles.sort(
            key=lambda x: x["time"]
        )

        return candles

    except Exception as e:

        print(
            "COINBASE REQUEST ERROR:",
            e
        )

        return []


# ============================================================
# KRAKEN MARKET DATA
# ============================================================

def get_kraken_candles(pair, interval):

    url = (
        "https://api.kraken.com/0/public/OHLC"
    )

    params = {
        "pair": pair,
        "interval": interval
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15,
            headers={
                "User-Agent": "SideShift-AI"
            }
        )

        if not response.ok:

            print(
                "KRAKEN ERROR:",
                response.status_code,
                response.text
            )

            return []

        data = response.json()

        if data.get("error"):
            print(
                "KRAKEN API ERROR:",
                data.get("error")
            )
            return []

        result = data.get("result", {})

        pair_keys = [
            key for key in result.keys()
            if key != "last"
        ]

        if not pair_keys:
            return []

        rows = result[pair_keys[0]]

        candles = []

        for row in rows:

            if len(row) < 7:
                continue

            candles.append({
                "time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[6])
            })

        candles.sort(
            key=lambda x: x["time"]
        )

        return candles

    except Exception as e:

        print(
            "KRAKEN REQUEST ERROR:",
            e
        )

        return []


# ============================================================
# MARKET DATA ROUTER
# ============================================================

def get_market_data(coin, timeframe):

    if coin not in COINS:
        return []

    coin_data = COINS[coin]

    granularity = TIMEFRAMES[timeframe]

    # --------------------------------------------------------
    # PRIMARY SOURCE: COINBASE
    # --------------------------------------------------------

    candles = get_coinbase_candles(
        coin_data["coinbase"],
        granularity
    )

    if len(candles) >= 60:

        print(
            f"{coin} {timeframe}: "
            f"Coinbase data received "
            f"({len(candles)} candles)"
        )

        return candles

    # --------------------------------------------------------
    # BACKUP SOURCE: KRAKEN
    # --------------------------------------------------------

    kraken_intervals = {
        "5m": 5,
        "15m": 15,
        "1h": 60,
        "4h": 240
    }

    candles = get_kraken_candles(
        coin_data["kraken"],
        kraken_intervals[timeframe]
    )

    if len(candles) >= 60:

        print(
            f"{coin} {timeframe}: "
            f"Kraken backup data received "
            f"({len(candles)} candles)"
        )

        return candles

    print(
        f"{coin} {timeframe}: "
        "INSUFFICIENT MARKET DATA"
    )

    return []


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        ema = (
            price - ema
        ) * multiplier + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i] -
            values[i - 1]
        )

        if change > 0:

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
            (avg_gain * (period - 1)) +
            gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1)) +
            losses[i]
        ) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# ATR / VOLATILITY
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"] -
            current["low"],

            abs(
                current["high"] -
                previous["close"]
            ),

            abs(
                current["low"] -
                previous["close"]
            )
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    return (
        sum(
            true_ranges[-period:]
        ) / period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def determine_structure(candles):

    if len(candles) < 20:
        return "Unknown"

    recent = candles[-20:]

    highs = [
        candle["high"]
        for candle in recent
    ]

    lows = [
        candle["low"]
        for candle in recent
    ]

    first_half_high = max(
        highs[:10]
    )

    second_half_high = max(
        highs[10:]
    )

    first_half_low = min(
        lows[:10]
    )

    second_half_low = min(
        lows[10:]
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
        return "Higher Highs / Higher Lows"

    if lower_highs and lower_lows:
        return "Lower Highs / Lower Lows"

    return "Mixed / Sideways"


# ============================================================
# ANALYZE ONE TIMEFRAME
# ============================================================

def analyze_timeframe(candles):

    if len(candles) < 60:
        return None

    closes = [
        c["close"]
        for c in candles
    ]

    volumes = [
        c["volume"]
        for c in candles
    ]

    price = closes[-1]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    rsi = calculate_rsi(
        closes,
        14
    )

    atr = calculate_atr(
        candles,
        14
    )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    lookback = min(
        10,
        len(closes) - 1
    )

    old_price = closes[
        -lookback - 1
    ]

    momentum_pct = (
        (price - old_price)
        / old_price
    ) * 100

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    recent_volume = (
        sum(volumes[-10:]) /
        10
    )

    previous_volume = (
        sum(volumes[-30:-10]) /
        20
    )

    if previous_volume > 0:

        volume_ratio = (
            recent_volume /
            previous_volume
        )

    else:

        volume_ratio = 1

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    if atr and price:

        atr_pct = (
            atr /
            price
        ) * 100

    else:

        atr_pct = 0

    # --------------------------------------------------------
    # TREND SCORE
    # --------------------------------------------------------

    score = 0

    if ema20 and ema50:

        if price > ema20:
            score += 1
        else:
            score -= 1

        if ema20 > ema50:
            score += 2
        else:
            score -= 2

    if momentum_pct > 0.15:
        score += 1

    elif momentum_pct < -0.15:
        score -= 1

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if score >= 3:

        trend = "Bullish"

    elif score <= -3:

        trend = "Bearish"

    else:

        trend = "Neutral"

    # --------------------------------------------------------
    # MOMENTUM DESCRIPTION
    # --------------------------------------------------------

    if momentum_pct >= 1:

        momentum = "Strong Positive"

    elif momentum_pct >= 0.25:

        momentum = "Positive"

    elif momentum_pct <= -1:

        momentum = "Strong Negative"

    elif momentum_pct <= -0.25:

        momentum = "Negative"

    else:

        momentum = "Weak / Flat"

    # --------------------------------------------------------
    # VOLUME DESCRIPTION
    # --------------------------------------------------------

    if volume_ratio >= 1.5:

        volume_status = "Strongly Increasing"

    elif volume_ratio >= 1.15:

        volume_status = "Increasing"

    elif volume_ratio <= 0.75:

        volume_status = "Decreasing"

    else:

        volume_status = "Normal"

    # --------------------------------------------------------
    # VOLATILITY DESCRIPTION
    # --------------------------------------------------------

    if atr_pct >= 3:

        volatility = "Very High"

    elif atr_pct >= 1.5:

        volatility = "High"

    elif atr_pct >= 0.7:

        volatility = "Moderate"

    else:

        volatility = "Low"

    structure = determine_structure(
        candles
    )

    return {
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "momentum_pct": momentum_pct,
        "momentum": momentum,
        "volume_ratio": volume_ratio,
        "volume": volume_status,
        "atr_pct": atr_pct,
        "volatility": volatility,
        "trend": trend,
        "structure": structure,
        "score": score
    }


# ============================================================
# OVERALL MARKET CONDITION
# ============================================================

def determine_overall_condition(results):

    valid = [
        result
        for result in results.values()
        if result
    ]

    if not valid:
        return "Unavailable"

    scores = [
        result["score"]
        for result in valid
    ]

    average_score = (
        sum(scores) /
        len(scores)
    )

    # --------------------------------------------------------
    # MULTI-TIMEFRAME TREND
    # --------------------------------------------------------

    bullish_count = sum(
        1
        for result in valid
        if result["trend"] == "Bullish"
    )

    bearish_count = sum(
        1
        for result in valid
        if result["trend"] == "Bearish"
    )

    # --------------------------------------------------------
    # CONSOLIDATION
    # --------------------------------------------------------

    if (
        abs(average_score) < 1
        and
        bullish_count <= 1
        and
        bearish_count <= 1
    ):

        return "🟠 Consolidation"

    if average_score >= 2:

        return "🟢 Bullish"

    if average_score <= -2:

        return "🔴 Bearish"

    return "🟡 Indecisive"


# ============================================================
# FULL COIN SCAN
# ============================================================

def scan_coin(coin):

    print(
        "========================================"
    )

    print(
        f"STARTING MARKET SCAN: {coin}"
    )

    print(
        "========================================"
    )

    results = {}

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h"
    ]:

        candles = get_market_data(
            coin,
            timeframe
        )

        if candles:

            analysis = analyze_timeframe(
                candles
            )

            results[timeframe] = analysis

        else:

            results[timeframe] = None

        # Small pause to avoid hammering APIs
        time.sleep(0.15)

    valid_results = [
        value
        for value in results.values()
        if value
    ]

    if not valid_results:

        return None

    condition = determine_overall_condition(
        results
    )

    latest = valid_results[-1]

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    available_timeframes = [
        timeframe
        for timeframe, result
        in results.items()
        if result
    ]

    if len(available_timeframes) == 4:

        data_quality = "Excellent"

    elif len(available_timeframes) >= 3:

        data_quality = "Good"

    elif len(available_timeframes) >= 2:

        data_quality = "Limited"

    else:

        data_quality = "Insufficient"

    return {
        "coin": coin,
        "condition": condition,
        "results": results,
        "latest": latest,
        "available_timeframes":
            available_timeframes,
        "data_quality":
            data_quality
    }


# ============================================================
# FORMAT MARKET SCAN
# ============================================================

def format_market_scan(scan):

    coin = scan["coin"]

    condition = scan["condition"]

    latest = scan["latest"]

    results = scan["results"]

    price = latest["price"]

    rsi = latest["rsi"]

    if rsi is None:
        rsi_text = "N/A"
    else:
        rsi_text = f"{rsi:.1f}"

    message = (
        f"🔎 <b>{coin} MARKET ANALYSIS</b>\n\n"

        f"💰 Price: ${price:,.6f}\n\n"

        f"<b>Overall Condition:</b>\n"
        f"{condition}\n\n"

        f"<b>Multi-Timeframe Trend</b>\n"
    )

    # --------------------------------------------------------
    # TIMEFRAMES
    # --------------------------------------------------------

    timeframe_labels = {
        "5m": "5 Minute",
        "15m": "15 Minute",
        "1h": "1 Hour",
        "4h": "4 Hour"
    }

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h"
    ]:

        result = results.get(
            timeframe
        )

        label = timeframe_labels[
            timeframe
        ]

        if result:

            message += (
                f"• {label}: "
                f"{result['trend']}\n"
            )

        else:

            message += (
                f"• {label}: "
                f"Unavailable\n"
            )

    message += "\n"

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    message += (
        f"⚡ <b>Momentum:</b> "
        f"{latest['momentum']}\n"
        f"📈 <b>RSI:</b> {rsi_text}\n"
        f"📊 <b>Volume:</b> "
        f"{latest['volume']}\n"
        f"🌊 <b>Volatility:</b> "
        f"{latest['volatility']}\n"
        f"🏗 <b>Structure:</b> "
        f"{latest['structure']}\n\n"
    )

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    message += (
        f"📡 <b>Data Quality:</b> "
        f"{scan['data_quality']}\n"
        f"⏱ <b>Timeframes Available:</b> "
        f"{', '.join(scan['available_timeframes'])}\n\n"
    )

    # --------------------------------------------------------
    # INTERPRETATION
    # --------------------------------------------------------

    if condition == "🟢 Bullish":

        interpretation = (
            "Market structure and momentum are "
            "currently leaning bullish across "
            "multiple timeframes."
        )

    elif condition == "🔴 Bearish":

        interpretation = (
            "Market structure and momentum are "
            "currently leaning bearish across "
            "multiple timeframes."
        )

    elif condition == "🟠 Consolidation":

        interpretation = (
            "Price is showing relatively sideways "
            "behavior. Momentum is not strongly "
            "favoring either direction."
        )

    else:

        interpretation = (
            "The market is showing mixed conditions. "
            "Different timeframes are not strongly "
            "aligned."
        )

    message += (
        f"🧠 <b>Market Interpretation</b>\n"
        f"{interpretation}\n\n"
    )

    # --------------------------------------------------------
    # IMPORTANT
    # --------------------------------------------------------

    message += (
        "ℹ️ <b>Scanner only</b>\n"
        "This analysis describes current market "
        "conditions. It does not automatically "
        "mean a qualifying trade setup exists."
    )

    return message


# ============================================================
# SCAN COIN AND SEND RESULT
# ============================================================

def perform_scan(
    coin,
    chat_id
):

    # --------------------------------------------------------
    # FIRST MESSAGE
    # --------------------------------------------------------

    send_telegram(
        f"🔎 <b>Scanning {coin}/USDT...</b>\n\n"
        "Analyzing multiple timeframes,\n"
        "trend, momentum, volume,\n"
        "structure and volatility.",
        chat_id
    )

    # --------------------------------------------------------
    # ACTUAL SCAN
    # --------------------------------------------------------

    scan = scan_coin(
        coin
    )

    # --------------------------------------------------------
    # FAILURE
    # --------------------------------------------------------

    if not scan:

        send_telegram(
            f"⚠️ <b>{coin} MARKET DATA</b>\n\n"
            "The market-data providers did not "
            "return enough reliable information "
            "to complete the scan.\n\n"
            "No market conclusion was generated.\n\n"
            "Please try again shortly.",
            chat_id,
            main_menu()
        )

        return

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    message = format_market_scan(
        scan
    )

    send_telegram(
        message,
        chat_id,
        main_menu()
    )


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
                        "❌ That coin is not "
                        "currently supported.",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                perform_scan(
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
            # COIN SCAN
            # ------------------------------------------------

            if callback_data.startswith(
                "scan_"
            ):

                coin = callback_data.replace(
                    "scan_",
                    ""
                ).upper()

                if coin in COINS:

                    perform_scan(
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

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        if WEBHOOK_SECRET:

            incoming_secret = data.get(
                "secret"
            )

            if incoming_secret != WEBHOOK_SECRET:

                return jsonify({
                    "error": "Unauthorized"
                }), 401

        # ----------------------------------------------------
        # SIGNAL DATA
        # ----------------------------------------------------

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
            f"{emoji} <b>{signal}</b>\n\n"
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
            "status":
                "signal received",
            "symbol":
                symbol,
            "signal":
                signal
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
                        html.unescape(
                            title
                        ),
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
            "📰 <b>CRYPTO NEWS</b>\n\n"
            "No current headlines were available."
        )

    message = (
        "📰 <b>CRYPTO MARKET NEWS</b>\n\n"
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
        "telegram_webhook":
            "/telegram-webhook",
        "tradingview_webhook":
            "/webhook",
        "coins":
            list(COINS.keys()),
        "market_data":
            "Coinbase + Kraken"
    })


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
        webhook_url
    )

    try:

        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={
                "url":
                    webhook_url,
                "allowed_updates": [
                    "message",
                    "callback_query"
                ],
                "drop_pending_updates":
                    True
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