import os
import html
import requests
import feedparser
import pandas as pd

from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

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
# MARKET DATA PROVIDERS
# ============================================================

BINANCE_URL = "https://api.binance.com/api/v3/klines"

COINBASE_PRODUCTS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "AVAX": "AVAX-USD",
    "DOGE": "DOGE-USD",
    "LINK": "LINK-USD",
    "ADA": "ADA-USD",
    "SUI": "SUI-USD",
}


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message, chat_id, keyboard=None):

    if not TELEGRAM_API:
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
# FRONT DOOR MENU
# ============================================================

def main_menu():

    return [
        [
            {
                "text": "🔎 Scan Market",
                "callback_data": "scan_menu"
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
                "text": "🆓 Free Signals",
                "callback_data": "free_info"
            },
            {
                "text": "👑 VIP",
                "callback_data": "vip_info"
            }
        ],
        [
            {
                "text": "ℹ️ How It Works",
                "callback_data": "help"
            }
        ]
    ]


# ============================================================
# COIN MENU
# ============================================================

def coin_menu():

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
            {
                "text": "⬅️ Back",
                "callback_data": "back_main"
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
        "Your AI-powered crypto market analysis assistant.\n\n"
        "SideShift analyzes market conditions across "
        "multiple timeframes to help identify whether "
        "the market is currently:\n\n"
        "🟢 Bullish\n"
        "🔴 Bearish\n"
        "🟡 Consolidating\n"
        "⚪ Indecisive\n\n"
        "You can scan individual cryptocurrencies, "
        "review current crypto news, and learn more "
        "about the signal channels.\n\n"
        "Choose an option below."
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
        "ℹ️ HOW SIDESHIFT AI WORKS\n\n"
        "🔎 MARKET SCANNER\n"
        "Select a cryptocurrency and SideShift analyzes "
        "multiple market timeframes.\n\n"
        "The scanner evaluates trend, momentum, RSI, "
        "EMA alignment, volume, volatility and market "
        "structure.\n\n"
        "The scanner describes the current market condition. "
        "It does NOT automatically mean a trade signal.\n\n"
        "🟢 Bullish\n"
        "🔴 Bearish\n"
        "🟡 Consolidation\n"
        "⚪ Indecisive\n\n"
        "Trade entries and setups are handled separately."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# FREE INFO
# ============================================================

def free_info(chat_id):

    message = (
        "🆓 FREE SIGNALS\n\n"
        "Receive a limited number of qualifying trade "
        "setups when market conditions meet the required "
        "criteria.\n\n"
        "The free channel is intended to provide selected "
        "market opportunities rather than every market "
        "movement.\n\n"
        "No signal is guaranteed."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# VIP INFO
# ============================================================

def vip_info(chat_id):

    message = (
        "👑 SIDESHIFT VIP\n\n"
        "VIP is designed for expanded signal coverage "
        "and more detailed trade analysis.\n\n"
        "VIP may provide more qualifying setups, additional "
        "market coverage and more detailed information "
        "when conditions allow.\n\n"
        "No signal is guaranteed and trading involves risk."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# BINANCE DATA
# ============================================================

def get_binance_candles(symbol, interval, limit=200):

    try:

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        response = requests.get(
            BINANCE_URL,
            params=params,
            timeout=15
        )

        if not response.ok:

            print(
                "BINANCE ERROR:",
                response.status_code,
                response.text
            )

            return None

        data = response.json()

        if not isinstance(data, list) or len(data) < 50:

            return None

        rows = []

        for candle in data:

            rows.append({
                "time": candle[0],
                "open": float(candle[1]),
                "high": float(candle[2]),
                "low": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5])
            })

        df = pd.DataFrame(rows)

        return df

    except Exception as e:

        print(
            "BINANCE DATA ERROR:",
            e
        )

        return None


# ============================================================
# COINBASE FALLBACK
# ============================================================

def get_coinbase_candles(coin, granularity):

    product = COINBASE_PRODUCTS.get(coin)

    if not product:
        return None

    url = (
        f"https://api.exchange.coinbase.com/"
        f"products/{product}/candles"
    )

    try:

        response = requests.get(
            url,
            params={
                "granularity": granularity
            },
            timeout=15
        )

        if not response.ok:

            print(
                "COINBASE ERROR:",
                response.status_code,
                response.text
            )

            return None

        data = response.json()

        if not isinstance(data, list) or len(data) < 50:
            return None

        rows = []

        for candle in data:

            rows.append({
                "time": candle[0] * 1000,
                "low": float(candle[1]),
                "high": float(candle[2]),
                "open": float(candle[3]),
                "close": float(candle[4]),
                "volume": float(candle[5])
            })

        df = pd.DataFrame(rows)

        df = df.sort_values(
            "time"
        ).reset_index(drop=True)

        return df

    except Exception as e:

        print(
            "COINBASE DATA ERROR:",
            e
        )

        return None


# ============================================================
# GET MARKET DATA
# ============================================================

def get_market_data(coin, interval):

    symbol = COINS.get(coin)

    if not symbol:
        return None

    # --------------------------------------------------------
    # PRIMARY PROVIDER
    # --------------------------------------------------------

    df = get_binance_candles(
        symbol,
        interval
    )

    if df is not None:
        return df

    # --------------------------------------------------------
    # COINBASE FALLBACK
    # --------------------------------------------------------

    coinbase_granularity = {
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400
    }

    granularity = coinbase_granularity.get(
        interval
    )

    if granularity:

        df = get_coinbase_candles(
            coin,
            granularity
        )

        if df is not None:
            return df

    return None


# ============================================================
# TECHNICAL INDICATORS
# ============================================================

def calculate_indicators(df):

    df = df.copy()

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    df["ema20"] = (
        df["close"]
        .ewm(span=20, adjust=False)
        .mean()
    )

    df["ema50"] = (
        df["close"]
        .ewm(span=50, adjust=False)
        .mean()
    )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    delta = df["close"].diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.rolling(
        14
    ).mean()

    avg_loss = loss.rolling(
        14
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        pd.NA
    )

    df["rsi"] = (
        100 -
        (
            100 /
            (1 + rs)
        )
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    df["volume_avg"] = (
        df["volume"]
        .rolling(20)
        .mean()
    )

    # --------------------------------------------------------
    # ATR / VOLATILITY
    # --------------------------------------------------------

    previous_close = df["close"].shift(1)

    tr1 = (
        df["high"] -
        df["low"]
    )

    tr2 = (
        df["high"] -
        previous_close
    ).abs()

    tr3 = (
        df["low"] -
        previous_close
    ).abs()

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    df["atr"] = (
        true_range
        .rolling(14)
        .mean()
    )

    # --------------------------------------------------------
    # PRICE STRUCTURE
    # --------------------------------------------------------

    df["recent_high"] = (
        df["high"]
        .rolling(20)
        .max()
    )

    df["recent_low"] = (
        df["low"]
        .rolling(20)
        .min()
    )

    return df


# ============================================================
# ANALYZE TIMEFRAME
# ============================================================

def analyze_timeframe(df):

    if df is None or len(df) < 60:

        return {
            "direction": "DATA UNAVAILABLE",
            "score": 0,
            "rsi": None,
            "volume": "Unknown",
            "volatility": "Unknown",
            "structure": "Unknown"
        }

    df = calculate_indicators(df)

    latest = df.iloc[-1]
    previous = df.iloc[-2]

    score = 0

    # --------------------------------------------------------
    # EMA TREND
    # --------------------------------------------------------

    if latest["ema20"] > latest["ema50"]:
        score += 2

    elif latest["ema20"] < latest["ema50"]:
        score -= 2

    # --------------------------------------------------------
    # PRICE VS EMA
    # --------------------------------------------------------

    if latest["close"] > latest["ema20"]:
        score += 1

    elif latest["close"] < latest["ema20"]:
        score -= 1

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if latest["close"] > previous["close"]:
        score += 1

    elif latest["close"] < previous["close"]:
        score -= 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = latest["rsi"]

    if pd.notna(rsi):

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    if score >= 3:

        direction = "BULLISH"

    elif score <= -3:

        direction = "BEARISH"

    elif -1 <= score <= 1:

        direction = "CONSOLIDATION"

    else:

        direction = "INDECISIVE"

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if latest["volume_avg"] > 0:

        volume_ratio = (
            latest["volume"] /
            latest["volume_avg"]
        )

        if volume_ratio >= 1.20:
            volume_status = "Above Average"

        elif volume_ratio <= 0.80:
            volume_status = "Below Average"

        else:
            volume_status = "Average"

    else:

        volume_status = "Unknown"

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    if latest["atr"] and latest["close"]:

        atr_percent = (
            latest["atr"] /
            latest["close"]
        ) * 100

        if atr_percent >= 3:
            volatility = "High"

        elif atr_percent >= 1:
            volatility = "Moderate"

        else:
            volatility = "Low"

    else:

        volatility = "Unknown"

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    recent = df.tail(20)

    midpoint = (
        recent["high"].mean() +
        recent["low"].mean()
    ) / 2

    if latest["close"] > midpoint:

        structure = "Bullish Lean"

    elif latest["close"] < midpoint:

        structure = "Bearish Lean"

    else:

        structure = "Mixed"

    return {
        "direction": direction,
        "score": score,
        "rsi": rsi,
        "volume": volume_status,
        "volatility": volatility,
        "structure": structure
    }


# ============================================================
# OVERALL MARKET ANALYSIS
# ============================================================

def determine_overall_direction(results):

    valid = [
        r for r in results.values()
        if r["direction"] != "DATA UNAVAILABLE"
    ]

    if not valid:

        return "DATA UNAVAILABLE"

    scores = [
        r["score"]
        for r in valid
    ]

    average = sum(scores) / len(scores)

    bullish = sum(
        1 for r in valid
        if r["direction"] == "BULLISH"
    )

    bearish = sum(
        1 for r in valid
        if r["direction"] == "BEARISH"
    )

    consolidation = sum(
        1 for r in valid
        if r["direction"] == "CONSOLIDATION"
    )

    if bullish >= 4 and average >= 2:

        return "BULLISH"

    if bearish >= 4 and average <= -2:

        return "BEARISH"

    if consolidation >= 3:

        return "CONSOLIDATION"

    return "INDECISIVE"


# ============================================================
# MARKET SCAN
# ============================================================

def scan_market(coin):

    timeframes = {
        "5m": "5m",
        "15m": "15m",
        "1h": "1h",
        "4h": "4h",
        "1D": "1d"
    }

    results = {}

    latest_price = None

    for label, interval in timeframes.items():

        df = get_market_data(
            coin,
            interval
        )

        if df is not None and len(df) > 0:

            latest_price = float(
                df.iloc[-1]["close"]
            )

        results[label] = analyze_timeframe(
            df
        )

    overall = determine_overall_direction(
        results
    )

    return {
        "coin": coin,
        "price": latest_price,
        "overall": overall,
        "timeframes": results
    }


# ============================================================
# FORMAT MARKET SCAN
# ============================================================

def format_scan(scan):

    coin = scan["coin"]
    price = scan["price"]
    overall = scan["overall"]
    results = scan["timeframes"]

    direction_emoji = {
        "BULLISH": "🟢",
        "BEARISH": "🔴",
        "CONSOLIDATION": "🟡",
        "INDECISIVE": "⚪",
        "DATA UNAVAILABLE": "⚠️"
    }

    emoji = direction_emoji.get(
        overall,
        "⚪"
    )

    if price is not None:

        price_text = (
            f"${price:,.6f}"
            if price < 1
            else f"${price:,.2f}"
        )

    else:

        price_text = "Unavailable"

    message = (
        f"🔎 {coin} MARKET ANALYSIS\n\n"
        f"💰 Price: {price_text}\n\n"
        f"{emoji} Overall Direction: "
        f"{overall.title()}\n\n"
        "📊 MULTI-TIMEFRAME ANALYSIS\n"
    )

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h",
        "1D"
    ]:

        result = results[timeframe]

        d = result["direction"]

        d_emoji = direction_emoji.get(
            d,
            "⚪"
        )

        message += (
            f"{timeframe}: "
            f"{d_emoji} {d.title()}\n"
        )

    # --------------------------------------------------------
    # USE 1H FOR GENERAL INDICATOR SUMMARY
    # --------------------------------------------------------

    reference = results["1h"]

    rsi = reference["rsi"]

    if rsi is not None and pd.notna(rsi):

        rsi_text = f"{float(rsi):.1f}"

    else:

        rsi_text = "Unavailable"

    message += (
        "\n📈 MARKET CONDITIONS\n"
        f"⚡ Momentum Score: "
        f"{reference['score']}\n"
        f"📊 RSI: {rsi_text}\n"
        f"📦 Volume: {reference['volume']}\n"
        f"🌊 Volatility: "
        f"{reference['volatility']}\n"
        f"🧱 Structure: "
        f"{reference['structure']}\n"
    )

    # --------------------------------------------------------
    # INTERPRETATION
    # --------------------------------------------------------

    if overall == "BULLISH":

        interpretation = (
            "Buying pressure is currently stronger "
            "across the analyzed timeframes. "
            "Several timeframes are showing bullish "
            "conditions."
        )

    elif overall == "BEARISH":

        interpretation = (
            "Selling pressure is currently stronger "
            "across the analyzed timeframes. "
            "Several timeframes are showing bearish "
            "conditions."
        )

    elif overall == "CONSOLIDATION":

        interpretation = (
            "Price action is relatively balanced. "
            "The market is showing consolidation "
            "rather than a strong directional move."
        )

    elif overall == "INDECISIVE":

        interpretation = (
            "The analyzed timeframes are conflicting. "
            "There is not enough agreement to describe "
            "the market as strongly bullish or bearish."
        )

    else:

        interpretation = (
            "Reliable market data could not be obtained "
            "for enough timeframes."
        )

    message += (
        "\n🧠 MARKET INTERPRETATION\n"
        f"{interpretation}\n\n"
        "⚪ This is a market analysis, "
        "not a trade entry signal.\n\n"
        "🎯 Want actual trade setups with "
        "entry, stop loss and targets?\n\n"
        "🆓 Join Free Signals\n"
        "👑 Join VIP\n\n"
        "⚠️ Market conditions change quickly. "
        "Trading involves risk."
    )

    return message


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
            "📰 CRYPTO NEWS\n\n"
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
            "TELEGRAM UPDATE:",
            data
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

            if not chat_id:

                return jsonify({
                    "ok": True
                })

            text = text.strip()

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
            # SCAN COMMAND
            # ------------------------------------------------

            if text.lower().startswith(
                "/scan"
            ):

                parts = text.split()

                if len(parts) < 2:

                    send_telegram(
                        "🔎 Choose a coin to scan.",
                        chat_id,
                        coin_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                coin = parts[1].upper()

                if coin not in COINS:

                    send_telegram(
                        "❌ That coin is not supported.",
                        chat_id,
                        coin_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                send_telegram(
                    f"🔎 Scanning {coin}...\n\n"
                    "Analyzing multiple timeframes "
                    "and market conditions.",
                    chat_id
                )

                scan = scan_market(
                    coin
                )

                result = format_scan(
                    scan
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

            send_welcome(
                chat_id
            )

            return jsonify({
                "ok": True
            })

        # ====================================================
        # BUTTON PRESS
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
            # SCAN MENU
            # ------------------------------------------------

            if callback_data == "scan_menu":

                send_telegram(
                    "🔎 SELECT A COIN TO SCAN\n\n"
                    "SideShift will analyze multiple "
                    "timeframes and describe the current "
                    "market condition.",
                    chat_id,
                    coin_menu()
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # COIN SCAN
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
                        f"🔎 Scanning {coin}...\n\n"
                        "Analyzing 5m, 15m, 1h, "
                        "4h and 1D market conditions.",
                        chat_id
                    )

                    scan = scan_market(
                        coin
                    )

                    result = format_scan(
                        scan
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

            # ------------------------------------------------
            # FREE
            # ------------------------------------------------

            if callback_data == "free_info":

                free_info(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # VIP
            # ------------------------------------------------

            if callback_data == "vip_info":

                vip_info(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # BACK
            # ------------------------------------------------

            if callback_data == "back_main":

                send_welcome(
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
            "WEBHOOK ERROR:",
            e
        )

        return jsonify({
            "ok": False,
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
        "telegram_webhook":
            "/telegram-webhook",
        "coins":
            list(COINS.keys()),
        "scanner":
            "multi-timeframe"
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
# START
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