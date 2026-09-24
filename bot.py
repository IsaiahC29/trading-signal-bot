import os
import html
import time
import math
import requests
import feedparser

from flask import Flask, request, jsonify


# ============================================================
# APP
# ============================================================

app = Flask(__name__)


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Optional channel links
FREE_CHANNEL_URL = os.getenv("FREE_CHANNEL_URL", "")
VIP_CHANNEL_URL = os.getenv("VIP_CHANNEL_URL", "")

# Binance public market-data endpoint
MARKET_DATA_URL = "https://api.binance.com"

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
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
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
        "disable_web_page_preview": True
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
            timeout=10
        )

    except Exception as e:

        print("CALLBACK ACK ERROR:", e)


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    keyboard = [
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
            },
            {
                "text": "ℹ️ Help",
                "callback_data": "help"
            }
        ]
    ]

    if FREE_CHANNEL_URL:

        keyboard.append([
            {
                "text": "🆓 Join Free Signals",
                "url": FREE_CHANNEL_URL
            }
        ])

    if VIP_CHANNEL_URL:

        keyboard.append([
            {
                "text": "👑 Join VIP",
                "url": VIP_CHANNEL_URL
            }
        ])

    return keyboard


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    message = (
        "🤖 <b>SIDESHIFT AI</b>\n\n"

        "Welcome to SideShift AI.\n\n"

        "This bot analyzes cryptocurrency markets "
        "across multiple timeframes and identifies "
        "current market conditions.\n\n"

        "📊 <b>Market Analysis</b>\n"
        "Check trend, momentum, RSI, volume, "
        "volatility and market structure.\n\n"

        "⏱️ <b>Multiple Timeframes</b>\n"
        "5m • 15m • 1h • 4h • 1D\n\n"

        "🧠 The analysis is designed to help you "
        "understand what the market is doing before "
        "considering a trade.\n\n"

        "⚠️ Market analysis is not a guarantee "
        "of future results.\n\n"

        "👇 <b>Select a coin to scan:</b>"
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
        "ℹ️ <b>SIDESHIFT AI HELP</b>\n\n"

        "/start — Open the main menu\n"
        "/scan BTC — Scan Bitcoin\n"
        "/scan ETH — Scan Ethereum\n"
        "/scan XRP — Scan XRP\n"
        "/news — View crypto news\n\n"

        "📊 A market scan evaluates:\n"
        "• Multi-timeframe trend\n"
        "• Momentum\n"
        "• RSI\n"
        "• Volume\n"
        "• Volatility\n"
        "• Market structure\n\n"

        "🎯 A market scan does NOT automatically "
        "mean there is a qualifying trade setup."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# MARKET DATA
# ============================================================

def get_klines(symbol, interval, limit=200):

    url = f"{MARKET_DATA_URL}/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if not data or len(data) < 60:
        raise ValueError(
            f"Insufficient candle data for {interval}"
        )

    candles = []

    for row in data:

        candles.append({
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5])
        })

    return candles


# ============================================================
# PRICE
# ============================================================

def get_current_price(symbol):

    url = f"{MARKET_DATA_URL}/api/v3/ticker/price"

    response = requests.get(
        url,
        params={"symbol": symbol},
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    return float(data["price"])


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    ema_value = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        ema_value = (
            (price - ema_value) * multiplier
            + ema_value
        )

    return ema_value


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = values[i] - values[i - 1]

        if change > 0:

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
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

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
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    return (
        sum(true_ranges[-period:])
        / period
    )


# ============================================================
# TREND ANALYSIS
# ============================================================

def analyze_timeframe(candles):

    closes = [
        candle["close"]
        for candle in candles
    ]

    current_price = closes[-1]

    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
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
    # Short-term return
    # --------------------------------------------------------

    lookback = 5

    if len(closes) > lookback:

        return_pct = (
            (
                current_price
                - closes[-lookback - 1]
            )
            / closes[-lookback - 1]
        ) * 100

    else:

        return_pct = 0

    # --------------------------------------------------------
    # EMA direction
    # --------------------------------------------------------

    score = 0

    if ema20 and ema50:

        if ema20 > ema50:
            score += 2

        elif ema20 < ema50:
            score -= 2

        if current_price > ema20:
            score += 1

        elif current_price < ema20:
            score -= 1

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    if return_pct > 0.35:
        score += 2

    elif return_pct > 0.10:
        score += 1

    elif return_pct < -0.35:
        score -= 2

    elif return_pct < -0.10:
        score -= 1

    # --------------------------------------------------------
    # RSI influence
    # --------------------------------------------------------

    if rsi is not None:

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1

    # --------------------------------------------------------
    # Trend label
    # --------------------------------------------------------

    if score >= 3:

        trend = "🟢 Bullish"

    elif score <= -3:

        trend = "🔴 Bearish"

    else:

        trend = "⚪ Neutral"

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    volumes = [
        candle["volume"]
        for candle in candles
    ]

    average_volume = (
        sum(volumes[-21:-1])
        / 20
    )

    current_volume = volumes[-1]

    if average_volume > 0:

        volume_ratio = (
            current_volume
            / average_volume
        )

    else:

        volume_ratio = 1

    if volume_ratio >= 1.5:

        volume_state = "🟢 High"

    elif volume_ratio <= 0.70:

        volume_state = "🔵 Low"

    else:

        volume_state = "🟡 Normal"

    # --------------------------------------------------------
    # Volatility
    # --------------------------------------------------------

    if atr and current_price > 0:

        atr_percent = (
            atr / current_price
        ) * 100

    else:

        atr_percent = 0

    if atr_percent >= 3:

        volatility = "🔴 Very High"

    elif atr_percent >= 1.5:

        volatility = "🟠 High"

    elif atr_percent >= 0.7:

        volatility = "🟡 Moderate"

    else:

        volatility = "🟢 Low"

    # --------------------------------------------------------
    # Market structure
    # --------------------------------------------------------

    structure = analyze_structure(
        candles
    )

    # --------------------------------------------------------
    # Momentum description
    # --------------------------------------------------------

    if return_pct >= 1.0:

        momentum = "🟢 Strong Positive"

    elif return_pct >= 0.25:

        momentum = "🟢 Positive"

    elif return_pct <= -1.0:

        momentum = "🔴 Strong Negative"

    elif return_pct <= -0.25:

        momentum = "🔴 Negative"

    else:

        momentum = "⚪ Weak / Mixed"

    return {
        "trend": trend,
        "rsi": rsi,
        "momentum": momentum,
        "volume": volume_state,
        "volatility": volatility,
        "structure": structure,
        "return_pct": return_pct,
        "atr_percent": atr_percent,
        "volume_ratio": volume_ratio,
        "score": score
    }


# ============================================================
# MARKET STRUCTURE
# ============================================================

def analyze_structure(candles):

    if len(candles) < 20:
        return "⚪ Insufficient Data"

    recent = candles[-10:]
    previous = candles[-20:-10]

    recent_high = max(
        c["high"]
        for c in recent
    )

    previous_high = max(
        c["high"]
        for c in previous
    )

    recent_low = min(
        c["low"]
        for c in recent
    )

    previous_low = min(
        c["low"]
        for c in previous
    )

    higher_high = recent_high > previous_high
    higher_low = recent_low > previous_low

    lower_high = recent_high < previous_high
    lower_low = recent_low < previous_low

    if higher_high and higher_low:

        return "🟢 Higher Highs / Higher Lows"

    if lower_high and lower_low:

        return "🔴 Lower Highs / Lower Lows"

    return "⚪ Mixed / Sideways"


# ============================================================
# OVERALL CONDITION
# ============================================================

def calculate_overall_condition(results):

    weights = {
        "5m": 1,
        "15m": 1,
        "1h": 2,
        "4h": 3,
        "1d": 4
    }

    total = 0
    weight_total = 0

    for timeframe, result in results.items():

        weight = weights.get(
            timeframe,
            1
        )

        total += (
            result["score"]
            * weight
        )

        weight_total += weight

    if weight_total == 0:

        return "⚪ Neutral"

    average = (
        total
        / weight_total
    )

    if average >= 1.0:

        return "🟢 Bullish"

    if average <= -1.0:

        return "🔴 Bearish"

    return "⚪ Neutral"


# ============================================================
# MARKET INTERPRETATION
# ============================================================

def generate_interpretation(
    results,
    overall
):

    if not results:

        return (
            "Insufficient market data was available "
            "to produce an interpretation."
        )

    bullish = 0
    bearish = 0
    neutral = 0

    for result in results.values():

        if "Bullish" in result["trend"]:
            bullish += 1

        elif "Bearish" in result["trend"]:
            bearish += 1

        else:
            neutral += 1

    short_term = []

    for timeframe in ["5m", "15m"]:

        if timeframe in results:

            short_term.append(
                results[timeframe]["trend"]
            )

    higher_term = []

    for timeframe in ["4h", "1d"]:

        if timeframe in results:

            higher_term.append(
                results[timeframe]["trend"]
            )

    # --------------------------------------------------------
    # Conflict between higher and short timeframes
    # --------------------------------------------------------

    higher_bullish = any(
        "Bullish" in x
        for x in higher_term
    )

    higher_bearish = any(
        "Bearish" in x
        for x in higher_term
    )

    short_bearish = any(
        "Bearish" in x
        for x in short_term
    )

    short_bullish = any(
        "Bullish" in x
        for x in short_term
    )

    if higher_bullish and short_bearish:

        return (
            "Higher-timeframe structure is leaning bullish, "
            "while short-term momentum is showing weakness. "
            "This can indicate a pullback or consolidation "
            "inside a broader bullish structure."
        )

    if higher_bearish and short_bullish:

        return (
            "Higher-timeframe structure is leaning bearish, "
            "while short-term momentum is attempting to move "
            "higher. This can indicate a short-term recovery "
            "inside a broader bearish structure."
        )

    if bullish >= 4:

        return (
            "Bullish conditions are appearing across most "
            "available timeframes. Momentum and structure "
            "should still be monitored for confirmation."
        )

    if bearish >= 4:

        return (
            "Bearish conditions are appearing across most "
            "available timeframes. Short-term rallies may "
            "still occur, so confirmation remains important."
        )

    if neutral >= 3:

        return (
            "Several timeframes are neutral or mixed. "
            "The market appears to be consolidating or "
            "lacking clear directional agreement."
        )

    return (
        "The market is showing mixed conditions across "
        "different timeframes. The broader trend and "
        "short-term momentum should be considered separately."
    )


# ============================================================
# FORMAT MARKET ANALYSIS
# ============================================================

def format_market_analysis(
    coin,
    price,
    results,
    overall,
    data_quality,
    failed_timeframes
):

    # --------------------------------------------------------
    # Individual timeframes
    # --------------------------------------------------------

    timeframe_lines = []

    labels = {
        "5m": "5 Minute",
        "15m": "15 Minute",
        "1h": "1 Hour",
        "4h": "4 Hour",
        "1d": "1 Day"
    }

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h",
        "1d"
    ]:

        if timeframe in results:

            timeframe_lines.append(
                f"• ⏱️ {labels[timeframe]}: "
                f"{results[timeframe]['trend']}"
            )

        else:

            timeframe_lines.append(
                f"• ⏱️ {labels[timeframe]}: "
                f"⚠️ Unavailable"
            )

    timeframe_text = "\n".join(
        timeframe_lines
    )

    # --------------------------------------------------------
    # Use the 1h timeframe as primary indicator display
    # --------------------------------------------------------

    if "1h" in results:

        primary = results["1h"]

    elif results:

        primary = list(
            results.values()
        )[0]

    else:

        primary = {
            "momentum": "⚪ Unknown",
            "rsi": None,
            "volume": "⚪ Unknown",
            "volatility": "⚪ Unknown",
            "structure": "⚪ Unknown"
        }

    rsi = primary.get("rsi")

    if rsi is None:

        rsi_text = "Unavailable"

    else:

        rsi_text = f"{rsi:.1f}"

    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    interpretation = generate_interpretation(
        results,
        overall
    )

    # --------------------------------------------------------
    # Trade status
    # --------------------------------------------------------

    trade_status = (
        "⚪ <b>No qualifying trade setup yet.</b>\n\n"
        "This market scan describes current conditions. "
        "It does not automatically create a LONG or SHORT "
        "signal."
    )

    # --------------------------------------------------------
    # Data warning
    # --------------------------------------------------------

    warning = ""

    if failed_timeframes:

        warning = (
            "\n\n⚠️ <b>Data Warning</b>\n"
            "Unavailable timeframe(s): "
            + ", ".join(failed_timeframes)
            + "\n\n"
            "The available timeframes were still analyzed."
        )

    message = (
        f"🔎 <b>{coin} MARKET ANALYSIS</b>\n\n"

        f"💰 <b>Price:</b> ${price:,.2f}\n\n"

        f"📌 <b>Overall Condition:</b> "
        f"{overall}\n\n"

        f"📊 <b>Multi-Timeframe Trend</b>\n"
        f"{timeframe_text}\n\n"

        f"⚡ <b>Momentum:</b> "
        f"{primary.get('momentum', '⚪ Unknown')}\n"

        f"📈 <b>RSI:</b> "
        f"{rsi_text}\n"

        f"📊 <b>Volume:</b> "
        f"{primary.get('volume', '⚪ Unknown')}\n"

        f"🌊 <b>Volatility:</b> "
        f"{primary.get('volatility', '⚪ Unknown')}\n"

        f"🏗️ <b>Structure:</b> "
        f"{primary.get('structure', '⚪ Unknown')}\n\n"

        f"🛰️ <b>Data Quality:</b> "
        f"{data_quality}\n\n"

        f"🧠 <b>Market Interpretation</b>\n"
        f"{html.escape(interpretation)}\n\n"

        f"🎯 <b>Trade Status</b>\n"
        f"{trade_status}"

        f"{warning}"
    )

    return message


# ============================================================
# FULL MARKET SCAN
# ============================================================

def scan_coin(coin):

    if coin not in COINS:

        raise ValueError(
            "Unsupported coin."
        )

    symbol = COINS[coin]

    results = {}

    failed_timeframes = []

    # --------------------------------------------------------
    # Current price
    # --------------------------------------------------------

    price = get_current_price(
        symbol
    )

    # --------------------------------------------------------
    # Scan every timeframe
    # --------------------------------------------------------

    for timeframe, interval in TIMEFRAMES.items():

        try:

            candles = get_klines(
                symbol,
                interval,
                200
            )

            results[timeframe] = (
                analyze_timeframe(
                    candles
                )
            )

        except Exception as e:

            print(
                f"{coin} {timeframe} ERROR:",
                e
            )

            failed_timeframes.append(
                timeframe
            )

    if not results:

        raise RuntimeError(
            "No timeframe data could be retrieved."
        )

    # --------------------------------------------------------
    # Overall condition
    # --------------------------------------------------------

    overall = calculate_overall_condition(
        results
    )

    # --------------------------------------------------------
    # Data quality
    # --------------------------------------------------------

    if len(results) == 5:

        data_quality = "🟢 Excellent"

    elif len(results) >= 4:

        data_quality = "🟡 Good"

    elif len(results) >= 3:

        data_quality = "🟠 Partial"

    else:

        data_quality = "🔴 Limited"

    return format_market_analysis(
        coin=coin,
        price=price,
        results=results,
        overall=overall,
        data_quality=data_quality,
        failed_timeframes=failed_timeframes
    )


# ============================================================
# NEWS
# ============================================================

NEWS_FEEDS = [
    (
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/"
    ),
    (
        "Cointelegraph",
        "https://cointelegraph.com/rss"
    ),
    (
        "Decrypt",
        "https://decrypt.co/feed"
    ),
    (
        "CryptoSlate",
        "https://cryptoslate.com/feed/"
    ),
    (
        "CryptoNews",
        "https://cryptonews.com/news/feed/"
    )
]


def get_crypto_news():

    articles = []

    for source, feed_url in NEWS_FEEDS:

        try:

            feed = feedparser.parse(
                feed_url
            )

            for item in feed.entries[:5]:

                title = item.get(
                    "title",
                    ""
                )

                link = item.get(
                    "link",
                    ""
                )

                published = item.get(
                    "published",
                    ""
                )

                if not title:
                    continue

                articles.append({
                    "source": source,
                    "title": html.escape(
                        title
                    ),
                    "link": html.escape(
                        link,
                        quote=True
                    ),
                    "published": html.escape(
                        published
                    )
                })

        except Exception as e:

            print(
                f"NEWS ERROR {source}:",
                e
            )

    if not articles:

        return (
            "📰 <b>CRYPTO MARKET NEWS</b>\n\n"
            "No current headlines were available."
        )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    seen = set()
    unique_articles = []

    for article in articles:

        key = article["title"].lower()

        if key in seen:
            continue

        seen.add(key)

        unique_articles.append(
            article
        )

    # --------------------------------------------------------
    # Limit news
    # --------------------------------------------------------

    unique_articles = unique_articles[:10]

    message = (
        "📰 <b>CRYPTO MARKET NEWS</b>\n\n"
    )

    for number, article in enumerate(
        unique_articles,
        start=1
    ):

        message += (
            f"<b>{number}. "
            f"{article['source']}</b>\n"
            f"{article['title']}\n"
            f"🔗 {article['link']}\n\n"
        )

    return message


# ============================================================
# ACCESS MENU
# ============================================================

def access_menu_message(chat_id):

    message = (
        "🔐 <b>SIDESHIFT AI ACCESS</b>\n\n"

        "Choose how you want to use SideShift AI.\n\n"

        "🆓 <b>Free Signals</b>\n"
        "Access the free signal community.\n\n"

        "👑 <b>VIP</b>\n"
        "Access the VIP community when your "
        "VIP access system is configured.\n\n"

        "Select an option below."
    )

    keyboard = []

    if FREE_CHANNEL_URL:

        keyboard.append([
            {
                "text": "🆓 Join Free Signals",
                "url": FREE_CHANNEL_URL
            }
        ])

    if VIP_CHANNEL_URL:

        keyboard.append([
            {
                "text": "👑 Join VIP",
                "url": VIP_CHANNEL_URL
            }
        ])

    keyboard.append([
        {
            "text": "↩️ Main Menu",
            "callback_data": "main_menu"
        }
    ])

    return send_telegram(
        message,
        chat_id,
        keyboard
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

                return jsonify({
                    "ok": True
                })

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
                        "📊 <b>Please choose a coin.</b>\n\n"
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

                perform_scan(
                    coin,
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # UNKNOWN MESSAGE
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
                    ""
                )

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

            # ------------------------------------------------
            # ACCESS
            # ------------------------------------------------

            if callback_data == "access":

                access_menu_message(
                    chat_id
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
# PERFORM SCAN
# ============================================================

def perform_scan(
    coin,
    chat_id
):

    symbol = COINS[coin]

    # --------------------------------------------------------
    # Scanning message
    # --------------------------------------------------------

    send_telegram(
        (
            f"🔎 <b>Scanning "
            f"{symbol}...</b>\n\n"
            "Analyzing:\n"
            "📊 Trend\n"
            "⚡ Momentum\n"
            "📈 RSI\n"
            "📊 Volume\n"
            "🌊 Volatility\n"
            "🏗️ Market Structure\n"
            "⏱️ 5m • 15m • 1h • 4h • 1D"
        ),
        chat_id
    )

    try:

        result = scan_coin(
            coin
        )

        send_telegram(
            result,
            chat_id,
            main_menu()
        )

    except Exception as e:

        print(
            f"SCAN ERROR {coin}:",
            e
        )

        send_telegram(
            (
                f"⚠️ <b>{coin} SCAN ERROR</b>\n\n"
                "The market data could not be retrieved "
                "reliably enough to complete the scan.\n\n"
                "Please try again shortly."
            ),
            chat_id,
            main_menu()
        )


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
            f"{emoji} <b>{html.escape(signal)}</b>\n\n"

            f"<b>{html.escape(str(symbol))}</b>\n"

            f"⏱️ <b>Timeframe:</b> "
            f"{html.escape(str(timeframe))}\n\n"

            f"🎯 <b>Entry:</b> "
            f"{html.escape(str(entry))}\n"

            f"🛑 <b>Stop Loss:</b> "
            f"{html.escape(str(stop_loss))}\n\n"

            f"TP1: {html.escape(str(tp1))}\n"
            f"TP2: {html.escape(str(tp2))}\n"
            f"TP3: {html.escape(str(tp3))}\n\n"

            "⚠️ <i>Trading involves risk. "
            "This is not a guarantee of results.</i>"
        )

        # ----------------------------------------------------
        # SEND SIGNAL
        # ----------------------------------------------------

        if TELEGRAM_CHAT_ID:

            send_telegram(
                signal_message,
                TELEGRAM_CHAT_ID
            )

        else:

            print(
                "WARNING: "
                "TELEGRAM_CHAT_ID is not configured."
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
        "telegram_webhook": "/telegram-webhook",
        "tradingview_webhook": "/webhook",
        "coins": list(COINS.keys()),
        "timeframes": list(TIMEFRAMES.keys())
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

    domain = RAILWAY_PUBLIC_DOMAIN.strip()

    if domain.startswith(
        "https://"
    ):

        domain = domain.replace(
            "https://",
            "",
            1
        )

    if domain.startswith(
        "http://"
    ):

        domain = domain.replace(
            "http://",
            "",
            1
        )

    webhook_url = (
        f"https://{domain}"
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