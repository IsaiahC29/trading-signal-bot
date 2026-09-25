import os
import html
import time
import threading
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
NEWS_CHAT_ID = os.getenv("NEWS_CHAT_ID", TELEGRAM_CHAT_ID or "")
NEWS_INTERVAL_MINUTES = max(5, int(os.getenv("NEWS_INTERVAL_MINUTES", "60")))
NEWS_MONITOR_ENABLED = os.getenv("NEWS_MONITOR_ENABLED", "true").lower() in ("1", "true", "yes", "on")
FREE_CHANNEL_URL = os.getenv("FREE_CHANNEL_URL", "")
VIP_CHANNEL_URL = os.getenv("VIP_CHANNEL_URL", "")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN else None
)

BINANCE_BASE = "https://api.binance.com"

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

INTERVALS = {
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
}

# ============================================================
# TELEGRAM HELPERS
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
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}

    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=15,
        )
        print("TELEGRAM SEND:", response.status_code, response.text)
        return response.ok
    except Exception as e:
        print("TELEGRAM SEND ERROR:", e)
        return False


def answer_callback(callback_id):
    if not TELEGRAM_API or not callback_id:
        return
    try:
        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={"callback_query_id": callback_id},
            timeout=10,
        )
    except Exception as e:
        print("CALLBACK ACK ERROR:", e)


# ============================================================
# MENUS
# ============================================================

def main_menu():
    return [
        [
            {"text": "ð Join Free Signals", "callback_data": "free_join"},
            {"text": "ð Join VIP", "callback_data": "vip_join"},
        ],
        [
            {"text": "ð Scan a Coin", "callback_data": "scan_menu"},
            {"text": "ð° Crypto News", "callback_data": "news_all"},
        ],
        [
            {"text": "â¹ï¸ How It Works", "callback_data": "how_it_works"},
        ],
    ]


def coin_menu():
    rows = []
    items = list(COINS.keys())
    for i in range(0, len(items), 2):
        row = []
        for coin in items[i:i + 2]:
            row.append({"text": f"ð {coin}", "callback_data": f"scan_{coin}"})
        rows.append(row)
    rows.append([{ "text": "â¬ï¸ Main Menu", "callback_data": "main_menu" }])
    return rows


# ============================================================
# FRONT DOOR
# ============================================================

def send_welcome(chat_id):
    message = (
        "<b>ð WELCOME TO SIDESHIFT AI</b>\n\n"
        "AI-powered crypto market intelligence designed to analyze potential "
        "LONG and SHORT setups using multiple layers of market data.\n\n"
        "<b>What SideShift AI analyzes:</b>\n"
        "ð Trend & market structure\n"
        "â¡ Momentum\n"
        "ð Volume\n"
        "ð Volatility\n"
        "ð RSI / EMA relationships\n"
        "ð¯ Support & resistance\n"
        "ð° Relevant crypto news\n\n"
        "The scanner describes the current market condition. It does <b>not</b> "
        "automatically turn every bullish or bearish condition into a trade.\n\n"
        "Choose an option below."
    )
    return send_telegram(chat_id=chat_id, message=message, keyboard=main_menu())


def send_help(chat_id):
    message = (
        "<b>â¹ï¸ SIDESHIFT AI</b>\n\n"
        "Use <b>ð Scan a Coin</b> to receive a current market-condition report.\n\n"
        "The scanner can classify conditions as <b>Bullish Trend, Bearish Trend, "
        "Consolidation, Indecisive, Breakout Watch, Breakdown Watch, High Volatility, "
        "or Overextended</b>.\n\n"
        "A market condition is not automatically a trading signal. Qualifying trade "
        "alerts are handled separately through the signal channels."
    )
    return send_telegram(chat_id=chat_id, message=message, keyboard=main_menu())


def send_how_it_works(chat_id):
    message = (
        "<b>ð§  HOW SIDESHIFT AI WORKS</b>\n\n"
        "1ï¸â£ Pulls current market candles.\n"
        "2ï¸â£ Calculates trend, momentum, volume, volatility and structure metrics.\n"
        "3ï¸â£ Compares multiple timeframes.\n"
        "4ï¸â£ Checks relevant news feeds.\n"
        "5ï¸â£ Classifies the current market condition.\n"
        "6ï¸â£ Separately evaluates whether enough confirmations exist for a qualifying setup.\n\n"
        "<b>Important:</b> more indicators do not guarantee accuracy. SideShift will be "
        "tested and measured rather than promising a fixed win rate."
    )
    return send_telegram(chat_id=chat_id, message=message, keyboard=main_menu())


# ============================================================
# MARKET DATA
# ============================================================

def get_klines(symbol, interval="1h", limit=200):
    try:
        response = requests.get(
            f"{BINANCE_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=15,
        )
        response.raise_for_status()
        raw = response.json()
        return [
            {
                "open": float(x[1]),
                "high": float(x[2]),
                "low": float(x[3]),
                "close": float(x[4]),
                "volume": float(x[5]),
            }
            for x in raw
        ]
    except Exception as e:
        print(f"KLINE ERROR {symbol} {interval}:", e)
        return []


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
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(candles, period=14):
    if len(candles) <= period:
        return None
    trs = []
    for i in range(1, len(candles)):
        current = candles[i]
        previous = candles[i - 1]
        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - previous["close"]),
            abs(current["low"] - previous["close"]),
        )
        trs.append(tr)
    return sum(trs[-period:]) / period


def pct(value, base):
    return ((value - base) / base) * 100 if base else 0


# ============================================================
# MARKET CONDITION ENGINE
# ============================================================

def analyze_timeframe(candles):
    if len(candles) < 60:
        return None

    closes = [x["close"] for x in candles]
    volumes = [x["volume"] for x in candles]
    price = closes[-1]

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    rsi14 = rsi(closes, 14)
    atr14 = atr(candles, 14)

    recent_high = max(x["high"] for x in candles[-20:])
    recent_low = min(x["low"] for x in candles[-20:])
    avg_volume = sum(volumes[-20:]) / 20
    volume_ratio = volumes[-1] / avg_volume if avg_volume else 1

    # Short-term price momentum.
    momentum_pct = pct(price, closes[-10])

    bullish = price > ema20 and ema20 > ema50
    bearish = price < ema20 and ema20 < ema50

    return {
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi14,
        "atr": atr14,
        "atr_pct": (atr14 / price * 100) if atr14 and price else 0,
        "recent_high": recent_high,
        "recent_low": recent_low,
        "volume_ratio": volume_ratio,
        "momentum_pct": momentum_pct,
        "bullish": bullish,
        "bearish": bearish,
    }


def classify_market(tf15, tf1h, tf4h):
    if not tf1h or not tf4h:
        return "â« Insufficient Data"

    bullish_count = sum([tf15["bullish"] if tf15 else False, tf1h["bullish"], tf4h["bullish"]])
    bearish_count = sum([tf15["bearish"] if tf15 else False, tf1h["bearish"], tf4h["bearish"]])

    rsi1h = tf1h["rsi"] or 50
    vol = tf1h["atr_pct"]
    momentum = tf1h["momentum_pct"]

    if bullish_count >= 2 and rsi1h >= 70:
        return "â ï¸ Bullish / Overextended"
    if bearish_count >= 2 and rsi1h <= 30:
        return "â ï¸ Bearish / Overextended"
    if bullish_count >= 2 and momentum > 0:
        return "ð¢ Bullish Trend"
    if bearish_count >= 2 and momentum < 0:
        return "ð´ Bearish Trend"
    if vol >= 5:
        return "ð  High Volatility"
    if bullish_count == 1 and bearish_count == 1:
        return "âª Indecisive"
    return "ð¡ Consolidation"


def momentum_label(value):
    if value is None:
        return "Unknown"
    if value >= 2:
        return "Strong bullish"
    if value >= 0.5:
        return "Moderate bullish"
    if value <= -2:
        return "Strong bearish"
    if value <= -0.5:
        return "Moderate bearish"
    return "Weak / neutral"


def volatility_label(atr_pct):
    if atr_pct is None:
        return "Unknown"
    if atr_pct >= 5:
        return "Extreme"
    if atr_pct >= 3:
        return "High"
    if atr_pct >= 1.5:
        return "Moderate"
    return "Low"


def structure_label(candles):
    if len(candles) < 30:
        return "Insufficient data"
    recent = candles[-20:]
    first_half = recent[:10]
    second_half = recent[10:]
    h1 = max(x["high"] for x in first_half)
    h2 = max(x["high"] for x in second_half)
    l1 = min(x["low"] for x in first_half)
    l2 = min(x["low"] for x in second_half)
    if h2 > h1 and l2 > l1:
        return "Higher highs / higher lows"
    if h2 < h1 and l2 < l1:
        return "Lower highs / lower lows"
    return "Range / mixed structure"


def side_shift_scan(coin):
    symbol = COINS[coin]
    c15 = get_klines(symbol, "15m", 200)
    c1h = get_klines(symbol, "1h", 200)
    c4h = get_klines(symbol, "4h", 200)

    if len(c15) < 60 or len(c1h) < 60 or len(c4h) < 60:
        return None, "Not enough current market data was available to complete the scan."

    tf15 = analyze_timeframe(c15)
    tf1h = analyze_timeframe(c1h)
    tf4h = analyze_timeframe(c4h)
    condition = classify_market(tf15, tf1h, tf4h)

    price = tf1h["price"]
    support = tf1h["recent_low"]
    resistance = tf1h["recent_high"]
    rsi_value = tf1h["rsi"]
    volume_ratio = tf1h["volume_ratio"]

    if condition.startswith("ð¢"):
        assessment = "Bullish conditions are present, but a qualifying trade requires additional confirmation."
    elif condition.startswith("ð´"):
        assessment = "Bearish conditions are present, but a qualifying trade requires additional confirmation."
    elif condition.startswith("â ï¸"):
        assessment = "The market is showing a strong directional condition, but price may be extended."
    elif condition.startswith("ð "):
        assessment = "Volatility is elevated. Risk can increase quickly during high-volatility conditions."
    elif condition.startswith("ð¡"):
        assessment = "Price is currently behaving more like a range than a clean directional trend."
    else:
        assessment = "The timeframes are not sufficiently aligned for a clear directional classification."

    structure = structure_label(c1h)
    momentum = momentum_label(tf1h["momentum_pct"])
    volatility = volatility_label(tf1h["atr_pct"])
    volume_label = "Above average" if volume_ratio >= 1.2 else "Below average" if volume_ratio <= 0.8 else "Near average"

    report = (
        f"<b>ð SIDESHIFT AI â {coin}/USDT</b>\n\n"
        f"<b>Market Condition:</b> {condition}\n"
        f"<b>Current Price:</b> {price:,.8f}\n\n"
        f"<b>Momentum:</b> {momentum}\n"
        f"<b>1H Structure:</b> {structure}\n"
        f"<b>Volatility:</b> {volatility}\n"
        f"<b>Volume:</b> {volume_label}\n"
        f"<b>RSI (1H):</b> {rsi_value:.1f}\n"
        f"<b>Support:</b> {support:,.8f}\n"
        f"<b>Resistance:</b> {resistance:,.8f}\n\n"
        f"<b>Multi-timeframe:</b> 15m / 1H / 4H analyzed\n\n"
        f"<b>SideShift Assessment:</b>\n{assessment}\n\n"
        f"<b>Trade Status:</b> âª No qualifying trade yet.\n\n"
        f"<i>This scan describes current market conditions. It is not a guarantee of future performance.</i>"
    )
    return report, None


# ============================================================
# NEWS
# ============================================================

def get_crypto_news_articles():
    """Fetch current crypto headlines from multiple RSS sources."""
    feeds = [
        "https://news.google.com/rss/search?q=crypto+bitcoin+ethereum+solana+XRP&hl=en-US&gl=US&ceid=US:en",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
    ]

    articles = []
    seen = set()

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for item in feed.entries[:10]:
                title = html.unescape(item.get("title", "")).strip()
                link = item.get("link", "").strip()
                published = item.get("published", "") or item.get("updated", "")
                key = (link or title).lower()

                if title and key not in seen:
                    seen.add(key)
                    articles.append({
                        "title": title,
                        "link": link,
                        "published": published,
                    })
        except Exception as e:
            print("NEWS FEED ERROR:", e)

    return articles


def format_crypto_news(articles, heading="ð° <b>CRYPTO MARKET NEWS</b>"):
    if not articles:
        return "ð° <b>Crypto News</b>\n\nNo current headlines were available."

    message = heading + "\n\n"

    for number, article in enumerate(articles[:10], start=1):
        title = html.escape(article.get("title", ""))
        link = html.escape(article.get("link", ""), quote=True)
        published = html.escape(article.get("published", ""))

        if link:
            line = f'{number}. <a href="{link}">{title}</a>'
        else:
            line = f"{number}. {title}"

        if published:
            line += f"\n   <i>{published}</i>"

        message += line + "\n\n"

    return message


def get_crypto_news():
    """Manual /news response."""
    return format_crypto_news(get_crypto_news_articles())


# ------------------------------------------------------------
# RECURRING NEWS MONITOR
# ------------------------------------------------------------
# The monitor runs inside the Railway process and checks the RSS feeds
# repeatedly. It only sends headlines it has not already sent during
# the current process lifetime.

_news_seen = set()
_news_monitor_started = False


def news_monitor_loop():
    global _news_seen

    print(
        f"NEWS MONITOR: enabled={NEWS_MONITOR_ENABLED}, "
        f"interval={NEWS_INTERVAL_MINUTES} minutes, "
        f"chat={NEWS_CHAT_ID or 'MISSING'}"
    )

    # First fetch establishes the baseline so deployment does not dump
    # a large batch of old headlines into Telegram.
    initial_articles = get_crypto_news_articles()
    for article in initial_articles:
        key = (article.get("link") or article.get("title") or "").lower()
        if key:
            _news_seen.add(key)

    while True:
        try:
            time.sleep(NEWS_INTERVAL_MINUTES * 60)

            if not NEWS_MONITOR_ENABLED:
                continue

            if not NEWS_CHAT_ID:
                print("NEWS MONITOR: NEWS_CHAT_ID/TELEGRAM_CHAT_ID is missing.")
                continue

            articles = get_crypto_news_articles()
            new_articles = []

            for article in articles:
                key = (article.get("link") or article.get("title") or "").lower()
                if not key or key in _news_seen:
                    continue

                _news_seen.add(key)
                new_articles.append(article)

            # Keep memory bounded after long runtimes.
            if len(_news_seen) > 1000:
                _news_seen = set(list(_news_seen)[-500:])

            if new_articles:
                message = format_crypto_news(
                    new_articles[:5],
                    "ð° <b>NEW CRYPTO NEWS</b>",
                )
                send_telegram(message, NEWS_CHAT_ID, main_menu())
                print(f"NEWS MONITOR: sent {len(new_articles[:5])} new headline(s).")
            else:
                print("NEWS MONITOR: no new headlines.")

        except Exception as e:
            print("NEWS MONITOR ERROR:", e)
            time.sleep(60)


def start_news_monitor():
    global _news_monitor_started

    if _news_monitor_started:
        return

    if not NEWS_MONITOR_ENABLED:
        print("NEWS MONITOR: disabled by NEWS_MONITOR_ENABLED.")
        return

    if not NEWS_CHAT_ID:
        print("NEWS MONITOR: no Telegram chat configured; monitor not started.")
        return

    _news_monitor_started = True
    thread = threading.Thread(target=news_monitor_loop, name="crypto-news-monitor", daemon=True)
    thread.start()


# Start the recurring news monitor when Railway/Gunicorn imports this module.
start_news_monitor()


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(silent=True)
        print("TELEGRAM UPDATE RECEIVED:", data)
        if not data:
            return jsonify({"ok": True})

        message = data.get("message")
        if message:
            chat_id = message.get("chat", {}).get("id")
            text = (message.get("text") or "").strip()
            if not chat_id:
                return jsonify({"ok": True})

            if text.startswith("/start"):
                send_welcome(chat_id)
                return jsonify({"ok": True})

            if text.startswith("/help"):
                send_help(chat_id)
                return jsonify({"ok": True})

            if text.startswith("/news"):
                send_telegram(get_crypto_news(), chat_id, main_menu())
                return jsonify({"ok": True})

            if text.lower().startswith("/scan"):
                parts = text.split()
                if len(parts) < 2:
                    send_telegram("ð Choose a coin to scan.", chat_id, coin_menu())
                    return jsonify({"ok": True})
                coin = parts[1].upper()
                if coin not in COINS:
                    send_telegram("â That coin is not currently supported.", chat_id, coin_menu())
                    return jsonify({"ok": True})
                send_telegram(f"ð Scanning <b>{coin}</b> across 15m, 1H and 4H...", chat_id)
                report, error = side_shift_scan(coin)
                send_telegram(report if not error else f"â ï¸ {error}", chat_id, main_menu())
                return jsonify({"ok": True})

            send_telegram("Use /start to open SideShift AI.", chat_id, main_menu())
            return jsonify({"ok": True})

        callback = data.get("callback_query")
        if callback:
            callback_id = callback.get("id")
            callback_data = callback.get("data", "")
            chat_id = callback.get("message", {}).get("chat", {}).get("id")
            answer_callback(callback_id)

            if callback_data == "main_menu":
                send_welcome(chat_id)
                return jsonify({"ok": True})

            if callback_data == "scan_menu":
                send_telegram("<b>ð Choose a coin to scan:</b>", chat_id, coin_menu())
                return jsonify({"ok": True})

            if callback_data.startswith("scan_"):
                coin = callback_data.replace("scan_", "", 1)
                if coin in COINS:
                    send_telegram(f"ð Scanning <b>{coin}</b> across 15m, 1H and 4H...", chat_id)
                    report, error = side_shift_scan(coin)
                    send_telegram(report if not error else f"â ï¸ {error}", chat_id, main_menu())
                return jsonify({"ok": True})

            if callback_data == "news_all":
                send_telegram(get_crypto_news(), chat_id, main_menu())
                return jsonify({"ok": True})

            if callback_data == "how_it_works":
                send_how_it_works(chat_id)
                return jsonify({"ok": True})

            if callback_data == "help":
                send_help(chat_id)
                return jsonify({"ok": True})

            if callback_data == "free_join":
                if FREE_CHANNEL_URL:
                    keyboard = [[{"text": "ð Open Free Signals", "url": FREE_CHANNEL_URL}],
                                [{"text": "â¬ï¸ Main Menu", "callback_data": "main_menu"}]]
                    send_telegram(
                        "<b>ð FREE SIGNALS</b>\n\nJoin the free SideShift signal channel for qualifying market alerts.",
                        chat_id,
                        keyboard,
                    )
                else:
                    send_telegram(
                        "<b>ð FREE SIGNALS</b>\n\nThe free channel link has not been configured yet.",
                        chat_id,
                        main_menu(),
                    )
                return jsonify({"ok": True})

            if callback_data == "vip_join":
                if VIP_CHANNEL_URL:
                    keyboard = [[{"text": "ð Open VIP", "url": VIP_CHANNEL_URL}],
                                [{"text": "â¬ï¸ Main Menu", "callback_data": "main_menu"}]]
                    send_telegram(
                        "<b>ð VIP ACCESS</b>\n\nVIP access is reserved for verified members. Payment verification will be connected before this link is used in production.",
                        chat_id,
                        keyboard,
                    )
                else:
                    send_telegram(
                        "<b>ð VIP ACCESS</b>\n\nVIP payment and automatic membership verification are not connected yet.",
                        chat_id,
                        main_menu(),
                    )
                return jsonify({"ok": True})

            return jsonify({"ok": True})

        return jsonify({"ok": True})

    except Exception as e:
        print("TELEGRAM WEBHOOK ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route("/webhook", methods=["POST"])
def tradingview_webhook():
    try:
        data = request.get_json(silent=True)
        print("TRADINGVIEW SIGNAL:", data)
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        if WEBHOOK_SECRET and data.get("secret") != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 401

        symbol = data.get("symbol", "UNKNOWN")
        signal = str(data.get("signal", "NO TRADE")).upper()
        timeframe = data.get("timeframe", "N/A")
        entry = data.get("entry", "N/A")
        stop_loss = data.get("stop_loss", "N/A")
        tp1 = data.get("tp1", "N/A")
        tp2 = data.get("tp2", "N/A")
        tp3 = data.get("tp3", "N/A")

        emoji = "ð¢" if signal == "LONG" else "ð´" if signal == "SHORT" else "âª"
        signal_message = (
            f"{emoji} <b>{signal}</b>\n\n"
            f"<b>{html.escape(str(symbol))}</b>\n"
            f"â± Timeframe: {html.escape(str(timeframe))}\n\n"
            f"Entry: {html.escape(str(entry))}\n"
            f"Stop Loss: {html.escape(str(stop_loss))}\n\n"
            f"TP1: {html.escape(str(tp1))}\n"
            f"TP2: {html.escape(str(tp2))}\n"
            f"TP3: {html.escape(str(tp3))}"
        )

        if TELEGRAM_CHAT_ID:
            send_telegram(signal_message, TELEGRAM_CHAT_ID)
        else:
            print("WARNING: TELEGRAM_CHAT_ID is not configured.")

        return jsonify({"status": "signal received", "symbol": symbol, "signal": signal})
    except Exception as e:
        print("TRADINGVIEW WEBHOOK ERROR:", e)
        return jsonify({"error": str(e)}), 500


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
        "coins": list(COINS.keys()),
    })


# ============================================================
# SET TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():
    if not TELEGRAM_BOT_TOKEN or not RAILWAY_PUBLIC_DOMAIN:
        print("Webhook setup skipped: missing token or Railway domain.")
        return False

    webhook_url = f"https://{RAILWAY_PUBLIC_DOMAIN}/telegram-webhook"
    try:
        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
            json={
                "url": webhook_url,
                "allowed_updates": ["message", "callback_query"],
                "drop_pending_updates": True,
            },
            timeout=15,
        )
        print("WEBHOOK SETUP:", response.status_code, response.text)
        return response.ok
    except Exception as e:
        print("WEBHOOK SETUP ERROR:", e)
        return False


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    print("========================================")
    print("SideShift AI starting...")
    print("========================================")
    print("Telegram token:", "FOUND" if TELEGRAM_BOT_TOKEN else "MISSING")
    print("Railway domain:", RAILWAY_PUBLIC_DOMAIN or "MISSING")
    print("Telegram chat ID:", "FOUND" if TELEGRAM_CHAT_ID else "MISSING")
    print("Free channel URL:", "CONFIGURED" if FREE_CHANNEL_URL else "NOT CONFIGURED")
    print("VIP channel URL:", "CONFIGURED" if VIP_CHANNEL_URL else "NOT CONFIGURED")

    setup_telegram_webhook()

    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)