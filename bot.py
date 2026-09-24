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

# Optional future channels
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID", "")
VIP_CHANNEL_ID = os.getenv("VIP_CHANNEL_ID", "")

TELEGRAM_API = None

if TELEGRAM_BOT_TOKEN:
    TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

BINANCE_API = "https://api.binance.com"


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
        "text": message,
        "parse_mode": "HTML"
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

        print("TELEGRAM SEND:", response.status_code)

        if not response.ok:
            print(response.text)

        return response.ok

    except Exception as e:
        print("TELEGRAM SEND ERROR:", e)
        return False


def answer_callback(callback_id):

    if not callback_id or not TELEGRAM_API:
        return

    try:
        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=10
        )
    except Exception as e:
        print("CALLBACK ACK ERROR:", e)


# ============================================================
# MAIN MENU
# ============================================================

def main_menu():

    return [
        [
            {"text": "🆓 JOIN FREE SIGNALS", "callback_data": "free_join"},
            {"text": "👑 JOIN VIP", "callback_data": "vip_join"}
        ],
        [
            {"text": "🔎 SCAN A COIN", "callback_data": "scan_menu"},
            {"text": "📰 CRYPTO NEWS", "callback_data": "news_all"}
        ],
        [
            {"text": "ℹ️ HOW SIDESHIFT WORKS", "callback_data": "how_it_works"}
        ]
    ]


def coin_menu():

    rows = []

    coin_list = list(COINS.keys())

    for i in range(0, len(coin_list), 2):
        row = []

        for coin in coin_list[i:i + 2]:
            row.append({
                "text": f"📊 {coin}",
                "callback_data": f"scan_{coin}"
            })

        rows.append(row)

    rows.append([
        {"text": "📰 News", "callback_data": "news_all"},
        {"text": "⬅️ Main Menu", "callback_data": "main_menu"}
    ])

    return rows


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    message = (
        "<b>🚀 WELCOME TO SIDESHIFT AI</b>\n\n"
        "Your AI-powered crypto market intelligence assistant "
        "designed to analyze potential LONG and SHORT setups.\n\n"

        "<b>What SideShift AI analyzes:</b>\n"
        "📈 Trend & market structure\n"
        "⚡ Momentum\n"
        "📊 Volume\n"
        "🌊 Volatility\n"
        "📉 RSI & moving averages\n"
        "🎯 Support & resistance\n"
        "📰 Crypto market news\n"
        "⏱ Multiple timeframes\n"
        "⚠️ Risk conditions\n\n"

        "<b>Important:</b>\n"
        "A bullish market does not automatically mean LONG, "
        "and a bearish market does not automatically mean SHORT.\n\n"

        "SideShift only identifies a potential trade when "
        "the required conditions align.\n\n"

        "Choose an option below:"
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


# ============================================================
# HOW IT WORKS
# ============================================================

def send_how_it_works(chat_id):

    message = (
        "<b>🧠 HOW SIDESHIFT AI WORKS</b>\n\n"

        "SideShift analyzes multiple pieces of market information "
        "before determining the current market condition.\n\n"

        "<b>1️⃣ Trend</b>\n"
        "Determines whether price is trending bullish, bearish, "
        "or moving sideways.\n\n"

        "<b>2️⃣ Momentum</b>\n"
        "Measures the strength and direction of the current move.\n\n"

        "<b>3️⃣ Market Structure</b>\n"
        "Looks for higher highs/lows, lower highs/lows, or range-bound price action.\n\n"

        "<b>4️⃣ Volume</b>\n"
        "Checks whether trading activity supports the current move.\n\n"

        "<b>5️⃣ Volatility</b>\n"
        "Determines whether the market is calm, active, or extremely volatile.\n\n"

        "<b>6️⃣ Multiple Timeframes</b>\n"
        "Compares short-term and higher-timeframe conditions.\n\n"

        "<b>7️⃣ News</b>\n"
        "Relevant crypto news can provide additional market context.\n\n"

        "<b>8️⃣ Final Decision</b>\n"
        "The system can classify the market as bullish, bearish, "
        "consolidating, indecisive, highly volatile, or overextended.\n\n"

        "If the conditions do not meet the signal requirements, "
        "SideShift can simply report:\n\n"
        "⚪ <b>NO QUALIFYING TRADE YET</b>"
    )

    return send_telegram(
        message,
        chat_id,
        [
            [{"text": "🔎 Scan a Coin", "callback_data": "scan_menu"}],
            [{"text": "⬅️ Main Menu", "callback_data": "main_menu"}]
        ]
    )


# ============================================================
# FREE / VIP
# ============================================================

def send_free_info(chat_id):

    message = (
        "<b>🆓 FREE SIGNALS</b>\n\n"
        "Join the SideShift AI free signal channel for "
        "qualifying market alerts.\n\n"
        "The scanner itself can be used to understand current "
        "market conditions.\n\n"
        "The system does not manufacture trades simply to produce "
        "a certain number of signals.\n\n"
        "When no setup qualifies, the system can say:\n"
        "⚪ No qualifying trade yet.\n\n"
        "👇 Join the free channel:"
    )

    keyboard = []

    if FREE_CHANNEL_ID:
        keyboard.append([
            {
                "text": "🆓 JOIN FREE SIGNALS",
                "url": FREE_CHANNEL_ID
            }
        ])

    keyboard.append([
        {"text": "👑 VIP", "callback_data": "vip_join"},
        {"text": "⬅️ Main Menu", "callback_data": "main_menu"}
    ])

    return send_telegram(
        message,
        chat_id,
        keyboard
    )


def send_vip_info(chat_id):

    message = (
        "<b>👑 SIDESHIFT AI VIP</b>\n\n"
        "VIP is designed to provide expanded access to "
        "SideShift AI market alerts and analysis.\n\n"

        "Potential VIP features include:\n"
        "📡 Expanded signal coverage\n"
        "📊 Additional market analysis\n"
        "🔎 More qualifying setups when conditions exist\n"
        "📰 Additional market context\n\n"

        "<b>VIP access: $20</b>\n\n"

        "Payment verification will be connected before "
        "VIP access is activated.\n\n"

        "⚠️ SideShift AI does not guarantee profits or a specific "
        "win rate. Trading involves risk."
    )

    return send_telegram(
        message,
        chat_id,
        [
            [
                {
                    "text": "💳 VIP PAYMENT — COMING NEXT",
                    "callback_data": "vip_payment"
                }
            ],
            [
                {"text": "🆓 Free Signals", "callback_data": "free_join"},
                {"text": "⬅️ Main Menu", "callback_data": "main_menu"}
            ]
        ]
    )


# ============================================================
# BINANCE MARKET DATA
# ============================================================

def get_klines(symbol, interval="1h", limit=100):

    try:

        response = requests.get(
            f"{BINANCE_API}/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            },
            timeout=15
        )

        if not response.ok:
            print("BINANCE ERROR:", response.text)
            return None

        raw = response.json()

        candles = []

        for item in raw:
            candles.append({
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5])
            })

        return candles

    except Exception as e:

        print("MARKET DATA ERROR:", e)
        return None


# ============================================================
# INDICATORS
# ============================================================

def sma(values, period):

    if len(values) < period:
        return None

    return sum(values[-period:]) / period


def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for value in values[period:]:
        result = (value - result) * multiplier + result

    return result


def rsi(values, period=14):

    if len(values) <= period:
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

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def atr(candles, period=14):

    if len(candles) <= period:
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

    return sum(true_ranges[-period:]) / period


# ============================================================
# MARKET CONDITION ENGINE
# ============================================================

def classify_market(symbol):

    candles_15m = get_klines(symbol, "15m", 100)
    candles_1h = get_klines(symbol, "1h", 100)
    candles_4h = get_klines(symbol, "4h", 100)

    if not candles_15m or not candles_1h or not candles_4h:
        return None

    closes_15m = [x["close"] for x in candles_15m]
    closes_1h = [x["close"] for x in candles_1h]
    closes_4h = [x["close"] for x in candles_4h]

    volumes = [x["volume"] for x in candles_1h]

    current_price = closes_1h[-1]

    ema20_1h = ema(closes_1h, 20)
    ema50_1h = ema(closes_1h, 50)

    ema20_4h = ema(closes_4h, 20)
    ema50_4h = ema(closes_4h, 50)

    rsi_value = rsi(closes_1h)

    atr_value = atr(candles_1h)

    volume_average = sma(volumes, 20)

    current_volume = volumes[-1]

    # --------------------------------------------------------
    # TREND SCORE
    # --------------------------------------------------------

    bullish_points = 0
    bearish_points = 0

    if ema20_1h and ema50_1h:

        if current_price > ema20_1h:
            bullish_points += 1
        else:
            bearish_points += 1

        if ema20_1h > ema50_1h:
            bullish_points += 1
        else:
            bearish_points += 1

    if ema20_4h and ema50_4h:

        if ema20_4h > ema50_4h:
            bullish_points += 2
        else:
            bearish_points += 2

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    momentum = "Neutral"

    if rsi_value is not None:

        if rsi_value >= 60:
            momentum = "Strong bullish"

        elif rsi_value >= 52:
            momentum = "Moderate bullish"

        elif rsi_value <= 40:
            momentum = "Strong bearish"

        elif rsi_value <= 48:
            momentum = "Moderate bearish"

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    recent = candles_1h[-12:]

    highs = [x["high"] for x in recent]
    lows = [x["low"] for x in recent]

    midpoint = len(recent) // 2

    first_half_high = max(highs[:midpoint])
    second_half_high = max(highs[midpoint:])

    first_half_low = min(lows[:midpoint])
    second_half_low = min(lows[midpoint:])

    if (
        second_half_high > first_half_high
        and second_half_low > first_half_low
    ):
        structure = "Higher highs / higher lows"

    elif (
        second_half_high < first_half_high
        and second_half_low < first_half_low
    ):
        structure = "Lower highs / lower lows"

    else:
        structure = "Range / mixed structure"

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if volume_average:

        volume_ratio = current_volume / volume_average

        if volume_ratio >= 1.5:
            volume_condition = "Well above average"

        elif volume_ratio >= 1.1:
            volume_condition = "Above average"

        elif volume_ratio <= 0.75:
            volume_condition = "Below average"

        else:
            volume_condition = "Near average"

    else:

        volume_condition = "Unavailable"
        volume_ratio = None

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    volatility_percent = None

    if atr_value and current_price:

        volatility_percent = (atr_value / current_price) * 100

    if volatility_percent is None:

        volatility = "Unknown"

    elif volatility_percent >= 4:

        volatility = "Extreme"

    elif volatility_percent >= 2:

        volatility = "High"

    elif volatility_percent >= 0.8:

        volatility = "Moderate"

    else:

        volatility = "Low"

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # --------------------------------------------------------

    support = min(
        x["low"] for x in candles_1h[-30:]
    )

    resistance = max(
        x["high"] for x in candles_1h[-30:]
    )

    # --------------------------------------------------------
    # OVEREXTENDED
    # --------------------------------------------------------

    overextended = False

    if rsi_value:

        if rsi_value >= 75 or rsi_value <= 25:
            overextended = True

    # --------------------------------------------------------
    # MARKET STATE
    # --------------------------------------------------------

    if overextended:

        market_state = "⚠️ OVEREXTENDED"

    elif volatility == "Extreme":

        market_state = "🟠 HIGH VOLATILITY"

    elif bullish_points >= 4 and structure == "Higher highs / higher lows":

        market_state = "🟢 BULLISH TREND"

    elif bearish_points >= 4 and structure == "Lower highs / lower lows":

        market_state = "🔴 BEARISH TREND"

    elif (
        abs(bullish_points - bearish_points) <= 1
        and structure == "Range / mixed structure"
    ):

        market_state = "🟡 CONSOLIDATION"

    else:

        market_state = "⚪ INDECISIVE"

    # --------------------------------------------------------
    # SIGNAL QUALIFICATION
    # --------------------------------------------------------

    signal = "NO TRADE"

    long_score = 0
    short_score = 0

    if bullish_points >= 4:
        long_score += 2

    if bearish_points >= 4:
        short_score += 2

    if rsi_value:

        if 52 <= rsi_value <= 70:
            long_score += 1

        if 30 <= rsi_value <= 48:
            short_score += 1

    if structure == "Higher highs / higher lows":
        long_score += 1

    if structure == "Lower highs / lower lows":
        short_score += 1

    if volume_ratio and volume_ratio >= 1.1:

        if long_score > short_score:
            long_score += 1

        elif short_score > long_score:
            short_score += 1

    # Require multiple confirmations.
    if long_score >= 4 and long_score > short_score and not overextended:
        signal = "POTENTIAL LONG"

    elif short_score >= 4 and short_score > long_score and not overextended:
        signal = "POTENTIAL SHORT"

    return {
        "price": current_price,
        "market_state": market_state,
        "momentum": momentum,
        "structure": structure,
        "volume": volume_condition,
        "volatility": volatility,
        "rsi": rsi_value,
        "support": support,
        "resistance": resistance,
        "signal": signal,
        "long_score": long_score,
        "short_score": short_score
    }


# ============================================================
# FORMAT MARKET SCAN
# ============================================================

def format_scan(coin, result):

    if not result:

        return (
            f"<b>🔎 {coin} SCAN</b>\n\n"
            "⚠️ Market data could not be retrieved right now.\n\n"
            "Please try again."
        )

    price = result["price"]

    rsi_value = result["rsi"]

    if rsi_value is not None:
        rsi_text = f"{rsi_value:.1f}"
    else:
        rsi_text = "N/A"

    signal = result["signal"]

    if signal == "POTENTIAL LONG":

        signal_text = (
            "🟢 Potential LONG conditions detected.\n"
            "The setup still requires confirmation before "
            "being treated as a trade alert."
        )

    elif signal == "POTENTIAL SHORT":

        signal_text = (
            "🔴 Potential SHORT conditions detected.\n"
            "The setup still requires confirmation before "
            "being treated as a trade alert."
        )

    else:

        signal_text = (
            "⚪ <b>NO QUALIFYING TRADE YET</b>\n"
            "Current conditions do not meet the required "
            "signal threshold."
        )

    message = (
        f"<b>🔎 SIDESHIFT AI — {coin}/USDT</b>\n\n"

        f"<b>Market Condition:</b> {result['market_state']}\n"
        f"<b>Price:</b> {price:,.8f}\n\n"

        f"<b>Momentum:</b> {result['momentum']}\n"
        f"<b>Structure:</b> {result['structure']}\n"
        f"<b>Volume:</b> {result['volume']}\n"
        f"<b>Volatility:</b> {result['volatility']}\n"
        f"<b>RSI:</b> {rsi_text}\n\n"

        f"<b>Support:</b> {result['support']:,.8f}\n"
        f"<b>Resistance:</b> {result['resistance']:,.8f}\n\n"

        f"<b>Assessment:</b>\n"
        f"{signal_text}\n\n"

        "This scan describes current market conditions. "
        "It is not a guarantee of future price movement."
    )

    return message


# ============================================================
# SCAN COIN
# ============================================================

def send_scan(chat_id, coin):

    if coin not in COINS:

        send_telegram(
            "❌ That coin is not currently supported.",
            chat_id,
            coin_menu()
        )

        return

    send_telegram(
        f"🔎 <b>Scanning {coin}/USDT...</b>\n\n"
        "Analyzing trend, momentum, structure, volume, "
        "volatility and multiple timeframes.",
        chat_id
    )

    result = classify_market(COINS[coin])

    message = format_scan(coin, result)

    send_telegram(
        message,
        chat_id,
        [
            [
                {
                    "text": "🔎 Scan Another Coin",
                    "callback_data": "scan_menu"
                }
            ],
            [
                {
                    "text": "📰 News",
                    "callback_data": "news_all"
                },
                {
                    "text": "👑 VIP",
                    "callback_data": "vip_join"
                }
            ],
            [
                {
                    "text": "⬅️ Main Menu",
                    "callback_data": "main_menu"
                }
            ]
        ]
    )


# ============================================================
# CRYPTO NEWS
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
        "Google Crypto News",
        "https://news.google.com/rss/search?"
        "q=cryptocurrency+crypto+bitcoin+ethereum+solana"
        "&hl=en-US&gl=US&ceid=US:en"
    )
]


def get_crypto_news():

    articles = []
    seen_titles = set()

    for source, feed_url in NEWS_FEEDS:

        try:

            feed = feedparser.parse(feed_url)

            for item in feed.entries[:6]:

                title = html.unescape(
                    item.get("title", "")
                ).strip()

                link = item.get("link", "").strip()

                if not title:
                    continue

                title_key = title.lower()

                if title_key in seen_titles:
                    continue

                seen_titles.add(title_key)

                articles.append({
                    "source": source,
                    "title": title,
                    "link": link
                })

        except Exception as e:

            print(
                f"NEWS ERROR ({source}):",
                e
            )

    if not articles:

        return (
            "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
            "No current headlines were available."
        )

    message = "<b>📰 CRYPTO MARKET NEWS</b>\n\n"

    for number, article in enumerate(
        articles[:10],
        start=1
    ):

        message += (
            f"<b>{number}. {article['title']}</b>\n"
            f"Source: {article['source']}\n"
        )

        if article["link"]:
            message += f"{article['link']}\n"

        message += "\n"

    return message


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():

    try:

        data = request.get_json(silent=True)

        print("========================================")
        print("TELEGRAM UPDATE RECEIVED")
        print(data)
        print("========================================")

        if not data:
            return jsonify({"ok": True})

        # ====================================================
        # NORMAL MESSAGE
        # ====================================================

        message = data.get("message")

        if message:

            chat = message.get("chat", {})
            chat_id = chat.get("id")

            text = message.get("text", "")

            if not text:
                return jsonify({"ok": True})

            text = text.strip()

            if not chat_id:
                return jsonify({"ok": True})

            print(
                f"Telegram message from {chat_id}: {text}"
            )

            # ------------------------------------------------
            # START
            # ------------------------------------------------

            if text.startswith("/start"):

                send_welcome(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # HELP
            # ------------------------------------------------

            if text.startswith("/help"):

                send_how_it_works(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if text.startswith("/news"):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    [
                        [
                            {
                                "text": "⬅️ Main Menu",
                                "callback_data": "main_menu"
                            }
                        ]
                    ]
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            if text.lower().startswith("/scan"):

                parts = text.split()

                if len(parts) < 2:

                    send_telegram(
                        "<b>🔎 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency to analyze.",
                        chat_id,
                        coin_menu()
                    )

                    return jsonify({"ok": True})

                coin = parts[1].upper()

                send_scan(chat_id, coin)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # UNKNOWN
            # ------------------------------------------------

            send_welcome(chat_id)

            return jsonify({"ok": True})

        # ====================================================
        # BUTTON PRESS
        # ====================================================

        callback = data.get("callback_query")

        if callback:

            callback_id = callback.get("id")
            callback_data = callback.get("data", "")

            callback_message = callback.get(
                "message",
                {}
            )

            callback_chat = callback_message.get(
                "chat",
                {}
            )

            chat_id = callback_chat.get("id")

            answer_callback(callback_id)

            print(
                f"Telegram button pressed: {callback_data}"
            )

            # ------------------------------------------------
            # MAIN MENU
            # ------------------------------------------------

            if callback_data == "main_menu":

                send_welcome(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # SCAN MENU
            # ------------------------------------------------

            if callback_data == "scan_menu":

                send_telegram(
                    "<b>🔎 SCAN A COIN</b>\n\n"
                    "Select a supported cryptocurrency.\n\n"
                    "The scanner will analyze current market "
                    "conditions including trend, momentum, "
                    "structure, volume and volatility.",
                    chat_id,
                    coin_menu()
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # COIN SCAN
            # ------------------------------------------------

            if callback_data.startswith("scan_"):

                coin = callback_data.replace(
                    "scan_",
                    ""
                )

                send_scan(chat_id, coin)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # FREE
            # ------------------------------------------------

            if callback_data == "free_join":

                send_free_info(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # VIP
            # ------------------------------------------------

            if callback_data == "vip_join":

                send_vip_info(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # VIP PAYMENT PLACEHOLDER
            # ------------------------------------------------

            if callback_data == "vip_payment":

                send_telegram(
                    "<b>👑 VIP PAYMENT</b>\n\n"
                    "Payment verification is not connected yet.\n\n"
                    "We will connect the payment system after "
                    "the market scanner and signal engine are tested.",
                    chat_id,
                    [
                        [
                            {
                                "text": "⬅️ VIP",
                                "callback_data": "vip_join"
                            }
                        ],
                        [
                            {
                                "text": "⬅️ Main Menu",
                                "callback_data": "main_menu"
                            }
                        ]
                    ]
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if callback_data == "news_all":

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    [
                        [
                            {
                                "text": "🔎 Scan",
                                "callback_data": "scan_menu"
                            },
                            {
                                "text": "👑 VIP",
                                "callback_data": "vip_join"
                            }
                        ],
                        [
                            {
                                "text": "⬅️ Main Menu",
                                "callback_data": "main_menu"
                            }
                        ]
                    ]
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # HOW IT WORKS
            # ------------------------------------------------

            if callback_data == "how_it_works":

                send_how_it_works(chat_id)

                return jsonify({"ok": True})

            return jsonify({"ok": True})

        return jsonify({"ok": True})

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

@app.route("/webhook", methods=["POST"])
def tradingview_webhook():

    try:

        data = request.get_json(silent=True)

        print("TRADINGVIEW SIGNAL:", data)

        if not data:

            return jsonify({
                "error": "No JSON received"
            }), 400

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

        if WEBHOOK_SECRET:

            incoming_secret = data.get("secret")

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
            f"<b>{emoji} {signal}</b>\n\n"
            f"<b>{symbol}</b>\n"
            f"⏱ Timeframe: {timeframe}\n\n"
            f"Entry: {entry}\n"
            f"Stop Loss: {stop_loss}\n\n"
            f"TP1: {tp1}\n"
            f"TP2: {tp2}\n"
            f"TP3: {tp3}\n\n"
            "⚠️ Trading involves risk."
        )

        if TELEGRAM_CHAT_ID:

            send_telegram(
                signal_message,
                TELEGRAM_CHAT_ID
            )

        else:

            print(
                "WARNING: TELEGRAM_CHAT_ID is not configured."
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

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "bot": "SideShift AI",
        "telegram_webhook": "/telegram-webhook",
        "tradingview_webhook": "/webhook",
        "coins": list(COINS.keys())
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

    print("========================================")
    print("SideShift AI starting...")
    print("========================================")

    if TELEGRAM_BOT_TOKEN:
        print("Telegram token: FOUND")
    else:
        print("Telegram token: MISSING")

    if RAILWAY_PUBLIC_DOMAIN:
        print(
            "Railway domain:",
            RAILWAY_PUBLIC_DOMAIN
        )
    else:
        print("Railway domain: MISSING")

    if TELEGRAM_CHAT_ID:
        print("Telegram chat ID: FOUND")
    else:
        print("Telegram chat ID: MISSING")

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
