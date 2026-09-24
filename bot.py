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
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Optional: separate group chat for clean signals
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
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
# TELEGRAM SEND
# ============================================================

def send_telegram(message, chat_id=None, keyboard=None):

    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return False

    target_chat = chat_id or TELEGRAM_CHAT_ID

    if not target_chat:
        print("ERROR: Telegram chat ID is missing")
        return False

    payload = {
        "chat_id": target_chat,
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
            "Telegram:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:
        print("Telegram error:", e)
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
        "🤖 LongShortCryptoBot is ONLINE\n\n"
        "Select a market to scan."
    )

    return send_telegram(
        message,
        chat_id=chat_id,
        keyboard=main_menu()
    )


# ============================================================
# HELP
# ============================================================

def send_help(chat_id):

    message = (
        "🤖 LONGSHORTCRYPTOBOT\n\n"
        "/start — Open menu\n"
        "/scan BTC — Scan Bitcoin\n"
        "/scan ETH — Scan Ethereum\n"
        "/scan SOL — Scan Solana\n"
        "/scan XRP — Scan XRP\n"
        "/news — Crypto news\n\n"
        "TradingView supplies the technical signals."
    )

    send_telegram(
        message,
        chat_id=chat_id,
        keyboard=main_menu()
    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():

    data = request.get_json(silent=True)

    print("TELEGRAM UPDATE:", data)

    if not data:
        return jsonify({"ok": True})

    # --------------------------------------------------------
    # NORMAL MESSAGE
    # --------------------------------------------------------

    message = data.get("message")

    if message:

        chat = message.get("chat", {})
        chat_id = chat.get("id")

        text = message.get("text", "").strip()

        if not chat_id:
            return jsonify({"ok": True})

        # /start
        if text.startswith("/start"):

            send_welcome(chat_id)

            return jsonify({"ok": True})

        # /help
        if text.startswith("/help"):

            send_help(chat_id)

            return jsonify({"ok": True})

        # /news
        if text.startswith("/news"):

            news = get_crypto_news()

            send_telegram(
                news,
                chat_id=chat_id,
                keyboard=main_menu()
            )

            return jsonify({"ok": True})

        # /scan
        if text.lower().startswith("/scan"):

            parts = text.split()

            if len(parts) < 2:

                send_telegram(
                    "Example:\n\n"
                    "/scan BTC\n"
                    "/scan ETH\n"
                    "/scan XRP",
                    chat_id=chat_id
                )

                return jsonify({"ok": True})

            coin = parts[1].upper()

            if coin not in COINS:

                send_telegram(
                    "That coin isn't currently supported.",
                    chat_id=chat_id,
                    keyboard=main_menu()
                )

                return jsonify({"ok": True})

            # Important:
            # Manual scan requests are sent through TradingView
            # architecture later. For now, tell the user the
            # scanner is awaiting the TradingView signal engine.

            send_telegram(
                f"📊 {coin} scan requested.\n\n"
                "The TradingView signal engine will provide "
                "the qualified setup.",
                chat_id=chat_id
            )

            return jsonify({"ok": True})

        send_telegram(
            "Use /start to open the menu.",
            chat_id=chat_id,
            keyboard=main_menu()
        )

        return jsonify({"ok": True})

    # --------------------------------------------------------
    # BUTTON PRESS
    # --------------------------------------------------------

    callback = data.get("callback_query")

    if callback:

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

        callback_id = callback.get("id")

        # Answer Telegram's button press
        if callback_id:

            try:

                requests.post(
                    f"{TELEGRAM_API}/answerCallbackQuery",
                    json={
                        "callback_query_id": callback_id
                    },
                    timeout=10
                )

            except Exception as e:

                print("Callback error:", e)

        # Scan
        if callback_data.startswith("scan_"):

            coin = callback_data.replace(
                "scan_",
                ""
            )

            if coin in COINS:

                send_telegram(
                    f"📊 {coin} scan requested.\n\n"
                    "Waiting for the TradingView "
                    "signal engine.",
                    chat_id=chat_id
                )

            return jsonify({"ok": True})

        # News
        if callback_data == "news_all":

            news = get_crypto_news()

            send_telegram(
                news,
                chat_id=chat_id,
                keyboard=main_menu()
            )

            return jsonify({"ok": True})

        # Help
        if callback_data == "help":

            send_help(chat_id)

            return jsonify({"ok": True})

        return jsonify({"ok": True})

    return jsonify({"ok": True})


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route("/webhook", methods=["POST"])
def tradingview_webhook():

    data = request.get_json(
        silent=True
    )

    print("TRADINGVIEW:", data)

    if not data:

        return jsonify({
            "error": "No JSON received"
        }), 400

    # --------------------------------------------------------
    # SECURITY
    # --------------------------------------------------------

    if WEBHOOK_SECRET:

        incoming_secret = data.get(
            "secret"
        )

        if incoming_secret != WEBHOOK_SECRET:

            print("Unauthorized TradingView request")

            return jsonify({
                "error": "Unauthorized"
            }), 401

    # --------------------------------------------------------
    # SIGNAL DATA
    # --------------------------------------------------------

    symbol = data.get(
        "symbol",
        "UNKNOWN"
    )

    signal = data.get(
        "signal",
        "NO TRADE"
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

    # --------------------------------------------------------
    # CONFIRMATIONS
    # --------------------------------------------------------

    confirmations = data.get(
        "confirmations",
        ""
    )

    # --------------------------------------------------------
    # SIGNAL MESSAGE
    # --------------------------------------------------------

    if signal == "LONG":

        emoji = "🟢"

    elif signal == "SHORT":

        emoji = "🔴"

    else:

        emoji = "⚪"

    # --------------------------------------------------------
    # GROUP MESSAGE
    #
    # Keep group chats CLEAN:
    # signal + entry + SL + TP1/TP2/TP3
    # --------------------------------------------------------

    group_message = (
        f"{emoji} {signal}\n\n"

        f"{symbol}\n"
        f"⏱ {timeframe}\n\n"

        f"Entry: {entry}\n"
        f"Stop Loss: {stop_loss}\n\n"

        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"TP3: {tp3}"
    )

    # --------------------------------------------------------
    # SEND TO GROUP
    # --------------------------------------------------------

    if TELEGRAM_GROUP_CHAT_ID:

        send_telegram(
            group_message,
            chat_id=TELEGRAM_GROUP_CHAT_ID
        )

    # --------------------------------------------------------
    # OPTIONAL PRIVATE MESSAGE
    #
    # Private chat can include confirmations.
    # --------------------------------------------------------

    private_message = (
        f"{emoji} {signal} SIGNAL\n\n"

        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n\n"

        f"Entry: {entry}\n"
        f"Stop Loss: {stop_loss}\n\n"

        f"TP1: {tp1}\n"
        f"TP2: {tp2}\n"
        f"TP3: {tp3}\n\n"

        f"Confirmations:\n"
        f"{confirmations}"
    )

    if TELEGRAM_CHAT_ID:

        send_telegram(
            private_message
        )

    return jsonify({
        "status": "signal received",
        "signal": signal,
        "symbol": symbol
    })


# ============================================================
# CRYPTO NEWS
# ============================================================

def get_crypto_news():

    feeds = [
        "https://news.google.com/rss/search?"
        "q=cryptocurrency+crypto+bitcoin+ethereum"
        "&hl=en-US&gl=US&ceid=US:en"
    ]

    articles = []

    for feed_url in feeds:

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
                        (title, link)
                    )

        except Exception as e:

            print(
                "News error:",
                e
            )

    if not articles:

        return (
            "📰 Crypto News\n\n"
            "No current headlines were available."
        )

    message = "📰 CRYPTO MARKET NEWS\n\n"

    for i, article in enumerate(
        articles[:8],
        start=1
    ):

        title = html.unescape(
            article[0]
        )

        link = article[1]

        message += (
            f"{i}. {title}\n"
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
        "telegram": "/telegram-webhook",
        "tradingview": "/webhook",
        "coins": list(COINS.keys())
    })


# ============================================================
# SET TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():

    if not TELEGRAM_BOT_TOKEN:

        print(
            "ERROR: TELEGRAM_BOT_TOKEN missing"
        )

        return False

    if not RAILWAY_PUBLIC_DOMAIN:

        print(
            "ERROR: RAILWAY_PUBLIC_DOMAIN missing"
        )

        return False

    webhook_url = (
        f"https://{RAILWAY_PUBLIC_DOMAIN}"
        "/telegram-webhook"
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
            "Webhook setup:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:

        print(
            "Webhook setup error:",
            e
        )

        return False


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    setup_telegram_webhook()

    port = int(
        os.getenv(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
