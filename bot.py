import os
import html
import time
import requests
import feedparser
from statistics import mean, pstdev

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

FREE_CHANNEL_URL = os.getenv("FREE_CHANNEL_URL", "")
VIP_CHANNEL_URL = os.getenv("VIP_CHANNEL_URL", "")

TELEGRAM_API = None

if TELEGRAM_BOT_TOKEN:
    TELEGRAM_API = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    )


# ============================================================
# COINS
# Coinbase USD market pairs
# ============================================================

COINS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "XRP": "XRP-USD",
    "PENGU": "PENGU-USD",
    "AVAX": "AVAX-USD",
    "SHIB": "SHIB-USD",
    "DOGE": "DOGE-USD",
    "LINK": "LINK-USD",
    "ADA": "ADA-USD",
    "SUI": "SUI-USD",
    "PEPE": "PEPE-USD",
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 21600,
    "1D": 86400,
}


# ============================================================
# HTTP SESSION
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "SideshiftAI/1.0"
})


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
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if keyboard:
        payload["reply_markup"] = {
            "inline_keyboard": keyboard
        }

    try:

        response = SESSION.post(
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

    # Optional channel buttons.
    # These only appear if the Railway variables are configured.

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
        "An automated market-analysis bot designed to "
        "identify potential bullish, bearish and neutral "
        "market conditions.\n\n"

        "📊 <b>Market Analysis</b>\n"
        "Scan supported cryptocurrencies using multiple "
        "timeframes and technical measurements.\n\n"

        "The scanner analyzes:\n"
        "📊 Trend\n"
        "⚡ Momentum\n"
        "📈 RSI\n"
        "📦 Volume\n"
        "🌊 Volatility\n"
        "🧱 Market Structure\n"
        "⏱️ 5m • 15m • 1h • 4h • 1D\n\n"

        "A market scan describes current conditions. "
        "It does not automatically mean a trade should be taken.\n\n"

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
        "/news — View crypto news\n\n"

        "<b>Market Scan</b>\n"
        "The scanner analyzes multiple timeframes and "
        "reports the current market condition.\n\n"

        "<b>Important:</b>\n"
        "A market condition is not automatically a trade signal. "
        "Trade signals can be handled separately by the signal engine."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# COINBASE MARKET DATA
# ============================================================

def fetch_candles(product_id, granularity, limit=200):

    """
    Coinbase public candle data.

    Candle format:
    [time, low, high, open, close, volume]
    """

    url = (
        "https://api.coinbase.com"
        f"/api/v3/brokerage/market/products/"
        f"{product_id}/candles"
    )

    # Request enough historical time to calculate indicators.
    seconds_needed = granularity * (limit + 20)

    end_time = int(time.time())
    start_time = end_time - seconds_needed

    params = {
        "start": str(start_time),
        "end": str(end_time),
        "granularity": granularity,
        "limit": limit,
    }

    last_error = None

    for attempt in range(3):

        try:

            response = SESSION.get(
                url,
                params=params,
                timeout=15
            )

            print(
                "COINBASE:",
                product_id,
                granularity,
                response.status_code
            )

            if response.status_code == 200:

                data = response.json()

                candles = data.get(
                    "candles",
                    []
                )

                if candles:

                    parsed = []

                    for candle in candles:

                        try:

                            parsed.append({
                                "time": int(candle["start"]),
                                "low": float(candle["low"]),
                                "high": float(candle["high"]),
                                "open": float(candle["open"]),
                                "close": float(candle["close"]),
                                "volume": float(candle["volume"]),
                            })

                        except Exception:
                            continue

                    parsed.sort(
                        key=lambda x: x["time"]
                    )

                    if len(parsed) >= 20:
                        return parsed

            last_error = (
                f"HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        except Exception as e:

            last_error = str(e)

        time.sleep(1)

    print(
        "COINBASE DATA ERROR:",
        product_id,
        last_error
    )

    return None


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        result = (
            (price - result) * multiplier
        ) + result

    return result


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

    for i in range(
        period,
        len(gains)
    ):

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
# ATR / VOLATILITY
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        current = candles[i]
        previous = candles[i - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    return mean(
        true_ranges[-period:]
    )


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(closes, lookback=10):

    if len(closes) <= lookback:
        return None

    previous = closes[-lookback - 1]
    current = closes[-1]

    if previous == 0:
        return None

    return (
        (current - previous)
        / previous
    ) * 100


# ============================================================
# TREND
# ============================================================

def determine_trend(candles):

    closes = [
        candle["close"]
        for candle in candles
    ]

    if len(closes) < 50:
        return "Insufficient Data"

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    price = closes[-1]

    if price > ema20 and ema20 > ema50:
        return "Bullish"

    if price < ema20 and ema20 < ema50:
        return "Bearish"

    return "Neutral"


# ============================================================
# MARKET STRUCTURE
# ============================================================

def determine_structure(candles):

    if len(candles) < 20:
        return "Insufficient Data"

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

    if (
        recent_high > previous_high
        and recent_low > previous_low
    ):
        return "Higher Highs / Higher Lows"

    if (
        recent_high < previous_high
        and recent_low < previous_low
    ):
        return "Lower Highs / Lower Lows"

    recent_range = (
        recent_high - recent_low
    )

    previous_range = (
        previous_high - previous_low
    )

    if previous_range == 0:
        return "Sideways"

    if (
        recent_range
        < previous_range * 0.75
    ):
        return "Consolidating"

    return "Mixed / Sideways"


# ============================================================
# VOLUME
# ============================================================

def determine_volume(candles):

    if len(candles) < 30:
        return "Insufficient Data", None

    volumes = [
        candle["volume"]
        for candle in candles
    ]

    recent_volume = mean(
        volumes[-5:]
    )

    average_volume = mean(
        volumes[-30:]
    )

    if average_volume == 0:
        return "Unknown", None

    ratio = (
        recent_volume
        / average_volume
    )

    if ratio >= 1.5:
        label = "High"

    elif ratio >= 0.8:
        label = "Normal"

    else:
        label = "Low"

    return label, ratio


# ============================================================
# VOLATILITY
# ============================================================

def determine_volatility(candles):

    atr = calculate_atr(candles)

    if atr is None:
        return "Unknown", None

    price = candles[-1]["close"]

    if price == 0:
        return "Unknown", None

    atr_percent = (
        atr / price
    ) * 100

    if atr_percent >= 3:
        label = "Very High"

    elif atr_percent >= 1.5:
        label = "High"

    elif atr_percent >= 0.75:
        label = "Moderate"

    else:
        label = "Low"

    return label, atr_percent


# ============================================================
# OVERALL CONDITION
# ============================================================

def determine_overall(
    timeframe_results,
    momentum,
    rsi,
    structure
):

    bullish = 0
    bearish = 0

    for result in timeframe_results.values():

        trend = result["trend"]

        if trend == "Bullish":
            bullish += 1

        elif trend == "Bearish":
            bearish += 1

    # Momentum

    if momentum is not None:

        if momentum > 1:
            bullish += 1

        elif momentum < -1:
            bearish += 1

    # RSI

    if rsi is not None:

        if 55 <= rsi <= 70:
            bullish += 1

        elif 30 <= rsi < 45:
            bearish += 1

    # Structure

    if "Higher" in structure:
        bullish += 1

    elif "Lower" in structure:
        bearish += 1

    difference = bullish - bearish

    if difference >= 3:
        return "Bullish"

    if difference <= -3:
        return "Bearish"

    if abs(difference) <= 1:

        if structure == "Consolidating":
            return "Consolidation"

        return "Indecisive"

    return "Mixed"


# ============================================================
# FORMAT PRICE
# ============================================================

def format_price(price):

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    return f"${price:,.8f}"


# ============================================================
# MARKET INTERPRETATION
# ============================================================

def market_interpretation(
    overall,
    momentum,
    rsi,
    volatility,
    structure
):

    parts = []

    if overall == "Bullish":

        parts.append(
            "The market is showing a bullish bias "
            "across the analyzed conditions."
        )

    elif overall == "Bearish":

        parts.append(
            "The market is showing a bearish bias "
            "across the analyzed conditions."
        )

    elif overall == "Consolidation":

        parts.append(
            "Price action is currently consolidating "
            "rather than showing a clear directional move."
        )

    elif overall == "Indecisive":

        parts.append(
            "The market is currently indecisive, "
            "with conflicting conditions across timeframes."
        )

    else:

        parts.append(
            "Market conditions are mixed."
        )

    if momentum is not None:

        if momentum > 2:

            parts.append(
                "Momentum is positive."
            )

        elif momentum < -2:

            parts.append(
                "Momentum is negative."
            )

        else:

            parts.append(
                "Momentum is relatively weak."
            )

    if rsi is not None:

        if rsi >= 70:

            parts.append(
                "RSI is in an overbought area."
            )

        elif rsi <= 30:

            parts.append(
                "RSI is in an oversold area."
            )

        else:

            parts.append(
                "RSI is not currently in an extreme zone."
            )

    if volatility in [
        "High",
        "Very High"
    ]:

        parts.append(
            "Volatility is elevated, so price swings "
            "may be larger than normal."
        )

    if structure == "Consolidating":

        parts.append(
            "Market structure suggests consolidation."
        )

    return " ".join(parts)


# ============================================================
# FULL MARKET SCAN
# ============================================================

def analyze_coin(symbol):

    product_id = COINS[symbol]

    print(
        f"Starting market analysis for {symbol}"
    )

    timeframe_results = {}

    # --------------------------------------------------------
    # Fetch every timeframe separately.
    # One failed timeframe should NOT destroy the entire scan.
    # --------------------------------------------------------

    for label, granularity in TIMEFRAMES.items():

        candles = fetch_candles(
            product_id,
            granularity,
            limit=200
        )

        if candles:

            timeframe_results[label] = {
                "candles": candles,
                "trend": determine_trend(candles)
            }

    # --------------------------------------------------------
    # Need at least one valid timeframe
    # --------------------------------------------------------

    if not timeframe_results:

        return None

    # --------------------------------------------------------
    # Pick the best available candles for indicators.
    # Prefer 1D, then 4h, 1h, 15m, 5m.
    # --------------------------------------------------------

    preferred = [
        "1D",
        "4h",
        "1h",
        "15m",
        "5m"
    ]

    selected_candles = None

    for timeframe in preferred:

        if timeframe in timeframe_results:

            selected_candles = (
                timeframe_results[timeframe]["candles"]
            )

            break

    if not selected_candles:

        return None

    closes = [
        candle["close"]
        for candle in selected_candles
    ]

    current_price = closes[-1]

    rsi = calculate_rsi(
        closes
    )

    momentum = calculate_momentum(
        closes
    )

    volume_label, volume_ratio = (
        determine_volume(
            selected_candles
        )
    )

    volatility_label, volatility_percent = (
        determine_volatility(
            selected_candles
        )
    )

    structure = determine_structure(
        selected_candles
    )

    overall = determine_overall(
        timeframe_results,
        momentum,
        rsi,
        structure
    )

    interpretation = market_interpretation(
        overall,
        momentum,
        rsi,
        volatility_label,
        structure
    )

    return {
        "symbol": symbol,
        "product_id": product_id,
        "price": current_price,
        "overall": overall,
        "timeframes": timeframe_results,
        "rsi": rsi,
        "momentum": momentum,
        "volume": volume_label,
        "volume_ratio": volume_ratio,
        "volatility": volatility_label,
        "volatility_percent": volatility_percent,
        "structure": structure,
        "interpretation": interpretation,
    }


# ============================================================
# MARKET SCAN MESSAGE
# ============================================================

def build_scan_message(result):

    symbol = result["symbol"]

    price = result["price"]

    overall = result["overall"]

    # --------------------------------------------------------
    # Overall emoji
    # --------------------------------------------------------

    if overall == "Bullish":
        condition_emoji = "🟢"

    elif overall == "Bearish":
        condition_emoji = "🔴"

    elif overall == "Consolidation":
        condition_emoji = "🟡"

    elif overall == "Indecisive":
        condition_emoji = "⚪"

    else:
        condition_emoji = "🟠"

    # --------------------------------------------------------
    # Timeframes
    # --------------------------------------------------------

    timeframe_lines = []

    for timeframe in [
        "5m",
        "15m",
        "1h",
        "4h",
        "1D"
    ]:

        if timeframe in result["timeframes"]:

            trend = result[
                "timeframes"
            ][timeframe]["trend"]

            if trend == "Bullish":
                emoji = "🟢"

            elif trend == "Bearish":
                emoji = "🔴"

            elif trend == "Neutral":
                emoji = "🟡"

            else:
                emoji = "⚪"

            timeframe_lines.append(
                f"• {timeframe}: "
                f"{emoji} {trend}"
            )

        else:

            timeframe_lines.append(
                f"• {timeframe}: ⚪ Data unavailable"
            )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if result["rsi"] is not None:
        rsi_text = f"{result['rsi']:.1f}"
    else:
        rsi_text = "N/A"

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    if result["momentum"] is not None:

        momentum_text = (
            f"{result['momentum']:+.2f}%"
        )

    else:

        momentum_text = "N/A"

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    volume_text = result["volume"]

    if result["volume_ratio"] is not None:

        volume_text += (
            f" ({result['volume_ratio']:.2f}x avg)"
        )

    # --------------------------------------------------------
    # Volatility
    # --------------------------------------------------------

    volatility_text = result[
        "volatility"
    ]

    if result["volatility_percent"] is not None:

        volatility_text += (
            f" ({result['volatility_percent']:.2f}% ATR)"
        )

    # --------------------------------------------------------
    # Build message
    # --------------------------------------------------------

    message = (
        f"🔎 <b>{symbol} MARKET ANALYSIS</b>\n\n"

        f"💰 <b>Price:</b> "
        f"{format_price(price)}\n\n"

        f"<b>Overall Condition:</b>\n"
        f"{condition_emoji} <b>{overall}</b>\n\n"

        f"📊 <b>Multi-Timeframe Trend</b>\n"
        + "\n".join(timeframe_lines)
        + "\n\n"

        f"⚡ <b>Momentum:</b> "
        f"{momentum_text}\n"

        f"📈 <b>RSI:</b> "
        f"{rsi_text}\n"

        f"📦 <b>Volume:</b> "
        f"{volume_text}\n"

        f"🌊 <b>Volatility:</b> "
        f"{volatility_text}\n"

        f"🧱 <b>Market Structure:</b> "
        f"{result['structure']}\n\n"

        f"📡 <b>Data Source:</b> "
        f"Coinbase public market data\n\n"

        f"🧠 <b>Market Interpretation</b>\n"
        f"{result['interpretation']}\n\n"

        f"ℹ️ <b>Important:</b>\n"
        f"This is a market-condition analysis, "
        f"not a guaranteed trade outcome."
    )

    return message


# ============================================================
# SCAN COIN
# ============================================================

def scan_coin(chat_id, symbol):

    product_id = COINS.get(symbol)

    if not product_id:

        send_telegram(
            "❌ That cryptocurrency is not currently supported.",
            chat_id,
            main_menu()
        )

        return

    # --------------------------------------------------------
    # Scanning message
    # --------------------------------------------------------

    scanning_message = (
        f"🔎 <b>Scanning {symbol}...</b>\n\n"

        f"Analyzing:\n"
        f"📊 Trend\n"
        f"⚡ Momentum\n"
        f"📈 RSI\n"
        f"📦 Volume\n"
        f"🌊 Volatility\n"
        f"🧱 Market Structure\n"
        f"⏱️ 5m • 15m • 1h • 4h • 1D"
    )

    send_telegram(
        scanning_message,
        chat_id
    )

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    result = analyze_coin(symbol)

    if not result:

        error_message = (
            f"⚠️ <b>{symbol} SCAN ERROR</b>\n\n"

            "The market-data provider did not return "
            "enough reliable candle data to complete "
            "the analysis.\n\n"

            "This does <b>not</b> mean the market is bullish "
            "or bearish. The scanner simply needs valid data "
            "before describing the market.\n\n"

            "Please try again shortly."
        )

        send_telegram(
            error_message,
            chat_id,
            main_menu()
        )

        return

    # --------------------------------------------------------
    # Send result
    # --------------------------------------------------------

    message = build_scan_message(
        result
    )

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
            "📰 <b>Crypto News</b>\n\n"
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

        safe_title = html.escape(
            title
        )

        safe_link = html.escape(
            link
        )

        message += (
            f"<b>{number}.</b> "
            f"{safe_title}\n"
            f"🔗 {safe_link}\n\n"
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
                        "📊 <b>Select a cryptocurrency.</b>\n\n"
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
                        "❌ That cryptocurrency "
                        "is not currently supported.",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({
                        "ok": True
                    })

                scan_coin(
                    chat_id,
                    coin
                )

                return jsonify({
                    "ok": True
                })

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            send_telegram(
                "Use /start to open the SideShift AI menu.",
                chat_id,
                main_menu()
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

            print(
                "BUTTON:",
                callback_data
            )

            # ------------------------------------------------
            # ACKNOWLEDGE BUTTON
            # ------------------------------------------------

            if callback_id and TELEGRAM_API:

                try:

                    SESSION.post(
                        f"{TELEGRAM_API}/answerCallbackQuery",
                        json={
                            "callback_query_id":
                            callback_id
                        },
                        timeout=10
                    )

                except Exception as e:

                    print(
                        "CALLBACK ERROR:",
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

                    scan_coin(
                        chat_id,
                        coin
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
            f"{emoji} <b>{signal}</b>\n\n"
            f"<b>{html.escape(str(symbol))}</b>\n"
            f"⏱️ Timeframe: "
            f"{html.escape(str(timeframe))}\n\n"
            f"Entry: {html.escape(str(entry))}\n"
            f"Stop Loss: "
            f"{html.escape(str(stop_loss))}\n\n"
            f"TP1: {html.escape(str(tp1))}\n"
            f"TP2: {html.escape(str(tp2))}\n"
            f"TP3: {html.escape(str(tp3))}"
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
                "WARNING: TELEGRAM_CHAT_ID "
                "is not configured."
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
        "market_data": "Coinbase public market data",
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

    webhook_url = (
        f"https://{RAILWAY_PUBLIC_DOMAIN}"
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