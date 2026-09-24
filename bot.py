import os
import html
import math
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
# COINGECKO IDS
# ============================================================

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "PENGU": "pudgy-penguins",
    "AVAX": "avalanche-2",
    "SHIB": "shiba-inu",
    "DOGE": "dogecoin",
    "LINK": "chainlink",
    "ADA": "cardano",
    "SUI": "sui",
    "PEPE": "pepe",
}


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "SideShiftAI/1.0",
    "Accept": "application/json",
})


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

        response = SESSION.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=15
        )

        print(
            "TELEGRAM SEND:",
            response.status_code,
            response.text[:500]
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
            {
                "text": "📊 BTC",
                "callback_data": "scan_BTC"
            },
            {
                "text": "📊 ETH",
                "callback_data": "scan_ETH"
            }
        ],
        [
            {
                "text": "📊 SOL",
                "callback_data": "scan_SOL"
            },
            {
                "text": "📊 XRP",
                "callback_data": "scan_XRP"
            }
        ],
        [
            {
                "text": "📊 PENGU",
                "callback_data": "scan_PENGU"
            },
            {
                "text": "📊 AVAX",
                "callback_data": "scan_AVAX"
            }
        ],
        [
            {
                "text": "📊 SHIB",
                "callback_data": "scan_SHIB"
            },
            {
                "text": "📊 DOGE",
                "callback_data": "scan_DOGE"
            }
        ],
        [
            {
                "text": "📊 LINK",
                "callback_data": "scan_LINK"
            },
            {
                "text": "📊 ADA",
                "callback_data": "scan_ADA"
            }
        ],
        [
            {
                "text": "📊 SUI",
                "callback_data": "scan_SUI"
            },
            {
                "text": "📊 PEPE",
                "callback_data": "scan_PEPE"
            }
        ],
        [
            {
                "text": "📰 Crypto News",
                "callback_data": "news_all"
            }
        ],
        [
            {
                "text": "ℹ️ Help",
                "callback_data": "help"
            }
        ]
    ]


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    message = (
        "🤖 SIDESHIFT AI\n\n"
        "Welcome to SideShift AI.\n\n"
        "This bot analyzes cryptocurrency markets "
        "using live market data and multiple technical "
        "confirmation factors.\n\n"
        "📊 Scan a cryptocurrency\n"
        "📈 Analyze market direction\n"
        "📰 Review current crypto news\n\n"
        "⚠️ No analysis guarantees a profitable trade. "
        "The bot will return NO QUALIFYING TRADE when "
        "conditions are not strong enough.\n\n"
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
        "🤖 SIDESHIFT AI HELP\n\n"
        "/start — Open the main menu\n"
        "/scan BTC — Scan Bitcoin\n"
        "/scan ETH — Scan Ethereum\n"
        "/scan SOL — Scan Solana\n"
        "/scan XRP — Scan XRP\n"
        "/news — Current crypto headlines\n\n"
        "The scanner checks multiple timeframes, "
        "trend, momentum, volume, volatility, "
        "structure and technical confirmation.\n\n"
        "A trade signal is only produced when "
        "the conditions meet the qualification rules."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# NUMERIC HELPERS
# ============================================================

def safe_float(value):

    try:
        return float(value)

    except Exception:
        return None


def mean(values):

    if not values:
        return None

    return sum(values) / len(values)


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema = sum(values[:period]) / period

    for price in values[period:]:

        ema = (
            (price - ema) * multiplier
        ) + ema

    return ema


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) <= period:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = values[i] - values[i - 1]

        if change >= 0:

            gains.append(change)
            losses.append(0)

        else:

            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(
        gains[:period]
    ) / period

    avg_loss = sum(
        losses[:period]
    ) / period

    for i in range(period, len(gains)):

        avg_gain = (
            ((avg_gain * (period - 1)) + gains[i])
            / period
        )

        avg_loss = (
            ((avg_loss * (period - 1)) + losses[i])
            / period
        )

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# MACD
# ============================================================

def calculate_macd(values):

    if len(values) < 35:
        return None

    ema12 = calculate_ema(
        values,
        12
    )

    ema26 = calculate_ema(
        values,
        26
    )

    if ema12 is None or ema26 is None:
        return None

    macd = ema12 - ema26

    return macd


# ============================================================
# ATR / VOLATILITY
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) <= period:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current_high = candles[i]["high"]
        current_low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        tr = max(
            current_high - current_low,
            abs(current_high - previous_close),
            abs(current_low - previous_close)
        )

        true_ranges.append(tr)

    recent = true_ranges[-period:]

    return mean(recent)


# ============================================================
# BINANCE MARKET DATA
# ============================================================

def get_binance_candles(symbol, interval, limit=200):

    url = (
        "https://api.binance.com/api/v3/klines"
    )

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=10
        )

        print(
            "BINANCE:",
            symbol,
            interval,
            response.status_code
        )

        if not response.ok:
            return []

        data = response.json()

        candles = []

        for row in data:

            candles.append({
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        return candles

    except Exception as e:

        print(
            "BINANCE ERROR:",
            symbol,
            interval,
            e
        )

        return []


# ============================================================
# BYBIT FALLBACK
# ============================================================

def get_bybit_candles(symbol, interval, limit=200):

    interval_map = {
        "15m": "15",
        "1h": "60",
        "4h": "240"
    }

    bybit_interval = interval_map.get(
        interval
    )

    if not bybit_interval:
        return []

    url = (
        "https://api.bybit.com/v5/market/kline"
    )

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": bybit_interval,
        "limit": limit
    }

    try:

        response = SESSION.get(
            url,
            params=params,
            timeout=10
        )

        print(
            "BYBIT:",
            symbol,
            interval,
            response.status_code
        )

        if not response.ok:
            return []

        data = response.json()

        if data.get("retCode") != 0:
            return []

        rows = data.get(
            "result",
            {}
        ).get(
            "list",
            []
        )

        rows = list(reversed(rows))

        candles = []

        for row in rows:

            candles.append({
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            })

        return candles

    except Exception as e:

        print(
            "BYBIT ERROR:",
            symbol,
            interval,
            e
        )

        return []


# ============================================================
# GET MARKET DATA WITH FALLBACK
# ============================================================

def get_market_candles(symbol, interval):

    candles = get_binance_candles(
        symbol,
        interval
    )

    if len(candles) >= 60:
        return candles, "Binance"

    print(
        "Binance data insufficient. "
        "Trying Bybit..."
    )

    candles = get_bybit_candles(
        symbol,
        interval
    )

    if len(candles) >= 60:
        return candles, "Bybit"

    return [], "Unavailable"


# ============================================================
# TREND ANALYSIS
# ============================================================

def determine_trend(candles):

    if len(candles) < 60:
        return "UNKNOWN"

    closes = [
        candle["close"]
        for candle in candles
    ]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    price = closes[-1]

    if not ema20 or not ema50:
        return "UNKNOWN"

    recent_high = max(
        closes[-20:]
    )

    recent_low = min(
        closes[-20:]
    )

    previous_high = max(
        closes[-40:-20]
    )

    previous_low = min(
        closes[-40:-20]
    )

    higher_structure = (
        recent_high > previous_high
        and recent_low > previous_low
    )

    lower_structure = (
        recent_high < previous_high
        and recent_low < previous_low
    )

    if (
        price > ema20
        and ema20 > ema50
        and higher_structure
    ):
        return "BULLISH"

    if (
        price < ema20
        and ema20 < ema50
        and lower_structure
    ):
        return "BEARISH"

    if (
        abs(ema20 - ema50)
        / ema50
        < 0.003
    ):
        return "CONSOLIDATION"

    return "INDECISIVE"


# ============================================================
# MARKET ANALYSIS
# ============================================================

def analyze_timeframe(candles):

    closes = [
        candle["close"]
        for candle in candles
    ]

    volumes = [
        candle["volume"]
        for candle in candles
    ]

    current_price = closes[-1]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    rsi = calculate_rsi(
        closes
    )

    macd = calculate_macd(
        closes
    )

    atr = calculate_atr(
        candles
    )

    average_volume = mean(
        volumes[-20:]
    )

    current_volume = volumes[-1]

    if average_volume:
        volume_ratio = (
            current_volume
            / average_volume
        )
    else:
        volume_ratio = None

    trend = determine_trend(
        candles
    )

    return {
        "price": current_price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "macd": macd,
        "atr": atr,
        "volume_ratio": volume_ratio,
        "trend": trend
    }


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_support_resistance(candles):

    recent = candles[-50:]

    highs = [
        candle["high"]
        for candle in recent
    ]

    lows = [
        candle["low"]
        for candle in recent
    ]

    return {
        "resistance": max(highs),
        "support": min(lows)
    }


# ============================================================
# QUALIFICATION ENGINE
# ============================================================

def qualify_trade(analysis_15m,
                  analysis_1h,
                  analysis_4h):

    bullish_points = 0
    bearish_points = 0

    # ----------------------------
    # MULTI-TIMEFRAME TREND
    # ----------------------------

    for analysis in [
        analysis_15m,
        analysis_1h,
        analysis_4h
    ]:

        if analysis["trend"] == "BULLISH":
            bullish_points += 2

        elif analysis["trend"] == "BEARISH":
            bearish_points += 2

    # ----------------------------
    # RSI
    # ----------------------------

    rsi = analysis_15m["rsi"]

    if rsi is not None:

        if 50 < rsi < 70:
            bullish_points += 1

        elif 30 < rsi < 50:
            bearish_points += 1

    # ----------------------------
    # EMA
    # ----------------------------

    price = analysis_15m["price"]
    ema20 = analysis_15m["ema20"]
    ema50 = analysis_15m["ema50"]

    if ema20 and ema50:

        if price > ema20 > ema50:
            bullish_points += 2

        elif price < ema20 < ema50:
            bearish_points += 2

    # ----------------------------
    # MACD
    # ----------------------------

    macd = analysis_15m["macd"]

    if macd is not None:

        if macd > 0:
            bullish_points += 1

        elif macd < 0:
            bearish_points += 1

    # ----------------------------
    # VOLUME
    # ----------------------------

    volume_ratio = (
        analysis_15m["volume_ratio"]
    )

    if volume_ratio:

        if volume_ratio >= 1.20:

            if bullish_points > bearish_points:
                bullish_points += 1

            elif bearish_points > bullish_points:
                bearish_points += 1

    # ----------------------------
    # DECISION
    # ----------------------------

    total_points = (
        bullish_points
        + bearish_points
    )

    if total_points == 0:
        return "NO TRADE", 0

    if bullish_points >= 8 and (
        bullish_points
        >= bearish_points + 3
    ):

        score = min(
            95,
            60 + bullish_points * 4
        )

        return "LONG", score

    if bearish_points >= 8 and (
        bearish_points
        >= bullish_points + 3
    ):

        score = min(
            95,
            60 + bearish_points * 4
        )

        return "SHORT", score

    score = min(
        75,
        50 + abs(
            bullish_points
            - bearish_points
        ) * 5
    )

    return "NO TRADE", score


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(price):

    if price is None:
        return "N/A"

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    if price >= 0.01:
        return f"${price:,.5f}"

    return f"${price:.8f}"


# ============================================================
# FULL COIN SCAN
# ============================================================

def scan_coin(coin):

    if coin not in COINS:
        return (
            "❌ Unsupported cryptocurrency."
        )

    symbol = COINS[coin]

    print(
        "========================================"
    )

    print(
        "STARTING MARKET SCAN:",
        coin,
        symbol
    )

    print(
        "========================================"
    )

    data = {}

    providers = set()

    for timeframe in [
        "15m",
        "1h",
        "4h"
    ]:

        candles, provider = (
            get_market_candles(
                symbol,
                timeframe
            )
        )

        if len(candles) < 60:

            print(
                "INSUFFICIENT DATA:",
                coin,
                timeframe,
                len(candles)
            )

            return (
                f"🔎 {coin} SCAN\n\n"
                "⚠️ Market data could not be "
                "retrieved reliably right now.\n\n"
                f"Timeframe affected: {timeframe}\n\n"
                "The bot will NOT issue a trade "
                "signal without sufficient data.\n\n"
                "Please try again shortly."
            )

        data[timeframe] = candles
        providers.add(provider)

    analysis_15m = analyze_timeframe(
        data["15m"]
    )

    analysis_1h = analyze_timeframe(
        data["1h"]
    )

    analysis_4h = analyze_timeframe(
        data["4h"]
    )

    support_resistance = (
        calculate_support_resistance(
            data["1h"]
        )
    )

    signal, score = qualify_trade(
        analysis_15m,
        analysis_1h,
        analysis_4h
    )

    price = analysis_15m["price"]

    atr = analysis_15m["atr"]

    volatility = "UNKNOWN"

    if atr and price:

        atr_percent = (
            atr / price
        ) * 100

        if atr_percent < 0.50:
            volatility = "LOW"

        elif atr_percent < 1.50:
            volatility = "MODERATE"

        elif atr_percent < 3.00:
            volatility = "HIGH"

        else:
            volatility = "VERY HIGH"

    # ========================================================
    # TRADE LEVELS
    # ========================================================

    entry = price
    stop = None
    tp1 = None
    tp2 = None

    if signal == "LONG" and atr:

        stop = price - (
            atr * 1.5
        )

        tp1 = price + (
            atr * 2
        )

        tp2 = price + (
            atr * 3
        )

    elif signal == "SHORT" and atr:

        stop = price + (
            atr * 1.5
        )

        tp1 = price - (
            atr * 2
        )

        tp2 = price - (
            atr * 3
        )

    # ========================================================
    # MARKET CONDITION
    # ========================================================

    trends = [
        analysis_15m["trend"],
        analysis_1h["trend"],
        analysis_4h["trend"]
    ]

    if trends.count("BULLISH") >= 2:

        market_condition = "🟢 BULLISH"

    elif trends.count("BEARISH") >= 2:

        market_condition = "🔴 BEARISH"

    elif trends.count("CONSOLIDATION") >= 2:

        market_condition = "🟡 CONSOLIDATION"

    else:

        market_condition = "⚪ INDECISIVE"

    # ========================================================
    # RESULT
    # ========================================================

    message = (
        f"🔎 {coin} MARKET SCAN\n\n"
        f"💰 Price: {format_price(price)}\n\n"
        f"Market Condition: {market_condition}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📊 MULTI-TIMEFRAME TREND\n\n"
        f"15m: {analysis_15m['trend']}\n"
        f"1h: {analysis_1h['trend']}\n"
        f"4h: {analysis_4h['trend']}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📈 TECHNICAL ANALYSIS\n\n"
        f"RSI: "
        f"{analysis_15m['rsi']:.2f}"
        if analysis_15m["rsi"] is not None
        else
        "RSI: N/A"
    )

    message += (
        "\n"
        f"EMA20: "
        f"{format_price(analysis_15m['ema20'])}\n"
        f"EMA50: "
        f"{format_price(analysis_15m['ema50'])}\n"
        f"MACD: "
        f"{analysis_15m['macd']:.6f}"
        if analysis_15m["macd"] is not None
        else
        "\nMACD: N/A"
    )

    message += (
        "\n"
        f"Volume Ratio: "
        f"{analysis_15m['volume_ratio']:.2f}x"
        if analysis_15m["volume_ratio"] is not None
        else
        "\nVolume Ratio: N/A"
    )

    message += (
        "\n"
        f"Volatility: {volatility}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📍 SUPPORT / RESISTANCE\n\n"
        f"Support: "
        f"{format_price(support_resistance['support'])}\n"
        f"Resistance: "
        f"{format_price(support_resistance['resistance'])}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🤖 SETUP SCORE: {score}/100\n\n"
    )

    if signal == "LONG":

        message += (
            "🟢 LONG SETUP QUALIFIED\n\n"
            f"Entry: {format_price(entry)}\n"
            f"Stop: {format_price(stop)}\n"
            f"TP1: {format_price(tp1)}\n"
            f"TP2: {format_price(tp2)}\n"
        )

    elif signal == "SHORT":

        message += (
            "🔴 SHORT SETUP QUALIFIED\n\n"
            f"Entry: {format_price(entry)}\n"
            f"Stop: {format_price(stop)}\n"
            f"TP1: {format_price(tp1)}\n"
            f"TP2: {format_price(tp2)}\n"
        )

    else:

        message += (
            "⚪ NO QUALIFYING TRADE YET\n\n"
            "The market does not currently "
            "have enough confirmation for a "
            "SideShift AI trade setup.\n\n"
            "This is intentional. The bot will "
            "not force a signal simply because "
            "a user requested a scan."
        )

    message += (
        "\n\n"
        f"📡 Data source: "
        f"{', '.join(sorted(providers))}\n\n"
        "⚠️ Technical analysis is probabilistic. "
        "Always manage risk."
    )

    return message


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
        # NORMAL MESSAGE
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

                print(
                    "ERROR: No Telegram chat ID."
                )

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

                send_telegram(
                    get_crypto_news(),
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
                        "/scan SOL",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                coin = parts[1].upper()

                if coin not in COINS:

                    send_telegram(
                        "❌ That cryptocurrency "
                        "is not supported.",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                send_telegram(
                    f"🔎 Scanning {coin}/USDT...\n\n"
                    "Analyzing multiple timeframes, "
                    "trend, momentum, structure, "
                    "volume and volatility.",
                    chat_id
                )

                result = scan_coin(
                    coin
                )

                send_telegram(
                    result,
                    chat_id,
                    main_menu()
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            send_telegram(
                "Use /start to open SideShift AI.",
                chat_id,
                main_menu()
            )

            return jsonify({
                "ok": True
            })

        # ====================================================
        # CALLBACK BUTTON
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

            callback_message = (
                callback.get(
                    "message",
                    {}
                )
            )

            callback_chat = (
                callback_message.get(
                    "chat",
                    {}
                )
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

            if (
                callback_id
                and TELEGRAM_API
            ):

                try:

                    SESSION.post(
                        f"{TELEGRAM_API}/"
                        "answerCallbackQuery",
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

                    send_telegram(
                        f"🔎 Scanning "
                        f"{coin}/USDT...\n\n"
                        "Analyzing multiple "
                        "timeframes, trend, "
                        "momentum, structure, "
                        "volume and volatility.",
                        chat_id
                    )

                    result = scan_coin(
                        coin
                    )

                    send_telegram(
                        result,
                        chat_id,
                        main_menu()
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

            if (
                incoming_secret
                != WEBHOOK_SECRET
            ):

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
            f"{emoji} {signal}\n\n"
            f"{symbol}\n"
            f"⏱ Timeframe: {timeframe}\n\n"
            f"Entry: {entry}\n"
            f"Stop Loss: {stop_loss}\n\n"
            f"TP1: {tp1}\n"
            f"TP2: {tp2}\n"
            f"TP3: {tp3}\n\n"
            "⚠️ Technical analysis is "
            "probabilistic. Manage risk."
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
            "📰 CRYPTO MARKET NEWS\n\n"
            "No current headlines were "
            "available."
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
            list(COINS.keys())
    })


# ============================================================
# SET TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():

    if not TELEGRAM_BOT_TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN missing."
        )

        return False

    if not RAILWAY_PUBLIC_DOMAIN:

        print(
            "ERROR: RAILWAY_PUBLIC_DOMAIN missing."
        )

        return False

    webhook_url = (
        f"https://"
        f"{RAILWAY_PUBLIC_DOMAIN}"
        "/telegram-webhook"
    )

    print(
        "SETTING TELEGRAM WEBHOOK:",
        webhook_url
    )

    try:

        response = SESSION.post(
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

    print(
        "Telegram token:",
        "FOUND"
        if TELEGRAM_BOT_TOKEN
        else "MISSING"
    )

    print(
        "Railway domain:",
        RAILWAY_PUBLIC_DOMAIN
        if RAILWAY_PUBLIC_DOMAIN
        else "MISSING"
    )

    print(
        "Telegram chat ID:",
        "FOUND"
        if TELEGRAM_CHAT_ID
        else "MISSING"
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