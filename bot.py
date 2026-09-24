import os
import html
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
# TELEGRAM MAIN MENU
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
        "🤖 LongShortCryptoBot\n\n"
        "Welcome!\n\n"
        "Select a cryptocurrency below to request a scan.\n\n"
        "📰 Crypto News is also available."
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
        "🤖 LONGSHORTCRYPTOBOT\n\n"
        "/start — Open the menu\n"
        "/scan BTC — Request a Bitcoin scan\n"
        "/scan ETH — Request an Ethereum scan\n"
        "/scan XRP — Request an XRP scan\n"
        "/news — View crypto news\n\n"
        "Use the menu buttons to request a market scan."
    )

    return send_telegram(
        message,
        chat_id,
        main_menu()
    )


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
        # NORMAL TELEGRAM MESSAGE
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
                print("ERROR: No chat ID in Telegram message.")
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

                send_help(chat_id)

                return jsonify({"ok": True})

            # ------------------------------------------------
            # NEWS
            # ------------------------------------------------

            if text.startswith("/news"):

                news = get_crypto_news()

                send_telegram(
                    news,
                    chat_id,
                    main_menu()
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # SCAN
            # ------------------------------------------------

            if text.lower().startswith("/scan"):

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

                    return jsonify({"ok": True})

                coin = parts[1].upper()

                if coin not in COINS:

                    send_telegram(
                        "❌ That coin is not currently supported.",
                        chat_id,
                        main_menu()
                    )

                    return jsonify({"ok": True})

                send_telegram(
                    f"📊 {coin} scan requested.\n\n"
                    "⏳ Please hold while the market "
                    "scan is processed.",
                    chat_id
                )

                return jsonify({"ok": True})

            # ------------------------------------------------
            # UNKNOWN MESSAGE
            # ------------------------------------------------

            send_telegram(
                "Use /start to open the menu.",
                chat_id,
                main_menu()
            )

            return jsonify({"ok": True})

        # ====================================================
        # TELEGRAM BUTTON PRESS
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

            print(
                f"Telegram button pressed: "
                f"{callback_data}"
            )

            # ------------------------------------------------
            # ACKNOWLEDGE BUTTON PRESS
            # ------------------------------------------------

            if callback_id and TELEGRAM_API:

                try:

                    response = requests.post(
                        f"{TELEGRAM_API}/answerCallbackQuery",
                        json={
                            "callback_query_id": callback_id
                        },
                        timeout=10
                    )

                    print(
                        "CALLBACK ACK:",
                        response.status_code,
                        response.text
                    )

                except Exception as e:

                    print(
                        "CALLBACK ACK ERROR:",
                        e
                    )

            # ------------------------------------------------
            # COIN SCAN
            # ------------------------------------------------

            if callback_data.startswith("scan_"):

                coin = callback_data.replace(
                    "scan_",
                    ""
                )

                if coin in COINS:

                    send_telegram(
                        f"📊 {coin} scan requested.\n\n"
                        "⏳ Please hold while the market "
                        "scan is processed.",
                        chat_id
                    )

                return jsonify({"ok": True})

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

                return jsonify({"ok": True})

            # ------------------------------------------------
            # HELP
            # ------------------------------------------------

            if callback_data == "help":

                send_help(chat_id)

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
            f"{emoji} {signal}\n\n"
            f"{symbol}\n"
            f"⏱ Timeframe: {timeframe}\n\n"
            f"Entry: {entry}\n"
            f"Stop Loss: {stop_loss}\n\n"
            f"TP1: {tp1}\n"
            f"TP2: {tp2}\n"
            f"TP3: {tp3}"
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

        feed = feedparser.parse(feed_url)

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

    message = "📰 CRYPTO MARKET NEWS\n\n"

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

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "bot": "LongShortCryptoBot",
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
    print("LongShortCryptoBot starting...")
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
