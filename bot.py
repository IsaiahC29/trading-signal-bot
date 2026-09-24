import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)


# ============================================================
# TELEGRAM: SEND MESSAGE
# ============================================================

def send_telegram(message, chat_id=None, keyboard=None):
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is missing")
        return False

    target_chat = chat_id or TELEGRAM_CHAT_ID

    if not target_chat:
        print("ERROR: TELEGRAM_CHAT_ID is missing")
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

        print("Telegram send:", response.status_code, response.text)

        return response.ok

    except Exception as e:
        print("Telegram send error:", str(e))
        return False


# ============================================================
# TELEGRAM: ANSWER BUTTON PRESS
# ============================================================

def answer_callback(callback_id, text="Done"):
    if not TELEGRAM_BOT_TOKEN:
        return False

    try:
        response = requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id,
                "text": text
            },
            timeout=10
        )

        print("Callback answer:", response.status_code, response.text)

        return response.ok

    except Exception as e:
        print("Callback error:", str(e))
        return False


# ============================================================
# TELEGRAM MAIN MENU
# ============================================================

def main_menu():
    return [
        [
            {
                "text": "📊 Scan BTC",
                "callback_data": "scan_BTCUSDT"
            },
            {
                "text": "📊 Scan ETH",
                "callback_data": "scan_ETHUSDT"
            }
        ],
        [
            {
                "text": "📊 Scan SOL",
                "callback_data": "scan_SOLUSDT"
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
# TELEGRAM /start
# ============================================================

def send_welcome(chat_id):
    message = (
        "🤖 LongShortCryptoBot is ONLINE\n\n"
        "Choose an option below:\n\n"
        "📊 Scan BTC\n"
        "📊 Scan ETH\n"
        "📊 Scan SOL\n\n"
        "You can also type:\n"
        "/scan BTC\n"
        "/scan ETH\n"
        "/scan SOL\n"
        "/help"
    )

    return send_telegram(
        message,
        chat_id=chat_id,
        keyboard=main_menu()
    )


# ============================================================
# TELEGRAM /help
# ============================================================

def send_help(chat_id):
    message = (
        "ℹ️ BOT COMMANDS\n\n"
        "/start — Open the main menu\n"
        "/scan BTC — Scan Bitcoin\n"
        "/scan ETH — Scan Ethereum\n"
        "/scan SOL — Scan Solana\n"
        "/help — Show this help\n\n"
        "TradingView signals can also be sent to this bot "
        "through the Railway webhook."
    )

    return send_telegram(
        message,
        chat_id=chat_id,
        keyboard=main_menu()
    )


# ============================================================
# TELEGRAM WEBHOOK
# THIS RECEIVES /start AND BUTTON PRESSES
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

        print("Telegram message:", text)

        # /start
        if text.startswith("/start"):
            send_welcome(chat_id)
            return jsonify({"ok": True})

        # /help
        if text.startswith("/help"):
            send_help(chat_id)
            return jsonify({"ok": True})

        # /scan BTC
        if text.lower().startswith("/scan"):

            parts = text.split()

            if len(parts) < 2:
                send_telegram(
                    "Please choose a coin:\n\n"
                    "/scan BTC\n"
                    "/scan ETH\n"
                    "/scan SOL",
                    chat_id=chat_id
                )

                return jsonify({"ok": True})

            coin = parts[1].upper()

            symbol_map = {
                "BTC": "BTCUSDT",
                "ETH": "ETHUSDT",
                "SOL": "SOLUSDT"
            }

            symbol = symbol_map.get(coin)

            if not symbol:
                send_telegram(
                    "I currently support:\n"
                    "BTC\n"
                    "ETH\n"
                    "SOL",
                    chat_id=chat_id
                )

                return jsonify({"ok": True})

            result = scan_market(symbol)

            send_telegram(
                result,
                chat_id=chat_id,
                keyboard=main_menu()
            )

            return jsonify({"ok": True})

        # Any other message
        send_telegram(
            "I received your message.\n\n"
            "Use /start to open the menu.",
            chat_id=chat_id,
            keyboard=main_menu()
        )

        return jsonify({"ok": True})

    # --------------------------------------------------------
    # INLINE BUTTON PRESS
    # --------------------------------------------------------

    callback = data.get("callback_query")

    if callback:

        callback_id = callback.get("id")
        callback_data = callback.get("data", "")

        callback_message = callback.get("message", {})
        callback_chat = callback_message.get("chat", {})
        chat_id = callback_chat.get("id")

        print("BUTTON PRESSED:", callback_data)

        answer_callback(callback_id)

        # Scan button
        if callback_data.startswith("scan_"):

            symbol = callback_data.replace("scan_", "")

            result = scan_market(symbol)

            send_telegram(
                result,
                chat_id=chat_id,
                keyboard=main_menu()
            )

            return jsonify({"ok": True})

        # Help button
        if callback_data == "help":

            send_help(chat_id)

            return jsonify({"ok": True})

        return jsonify({"ok": True})

    return jsonify({"ok": True})


# ============================================================
# MARKET SCANNER
# ============================================================

def scan_market(symbol, interval="15m"):

    try:

        url = "https://api.binance.com/api/v3/klines"

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 250
        }

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        candles = response.json()

        if len(candles) < 50:
            return f"⚠️ Not enough market data for {symbol}."

        closes = [
            float(candle[4])
            for candle in candles
        ]

        volumes = [
            float(candle[5])
            for candle in candles
        ]

        price = closes[-1]

        ema9 = ema(closes, 9)
        ema21 = ema(closes, 21)
        ema50 = ema(closes, 50)
        ema200 = ema(closes, 200)

        rsi_value = rsi(closes, 14)

        macd_value, signal_value = macd(closes)

        volume = volumes[-1]
        average_volume = sum(volumes[-20:]) / 20

        # ----------------------------------------------------
        # SIMPLE SIGNAL LOGIC
        # ----------------------------------------------------

        long_score = 0
        short_score = 0

        if price > ema9:
            long_score += 1
        else:
            short_score += 1

        if ema9 > ema21:
            long_score += 1
        else:
            short_score += 1

        if ema21 > ema50:
            long_score += 1
        else:
            short_score += 1

        if price > ema200:
            long_score += 1
        else:
            short_score += 1

        if rsi_value > 50:
            long_score += 1
        else:
            short_score += 1

        if macd_value > signal_value:
            long_score += 1
        else:
            short_score += 1

        if volume > average_volume:
            volume_status = "HIGH"
        else:
            volume_status = "NORMAL"

        if long_score >= 4:
            signal = "LONG"
            emoji = "🟢"

        elif short_score >= 4:
            signal = "SHORT"
            emoji = "🔴"

        else:
            signal = "NEUTRAL"
            emoji = "⚪"

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        entry = price

        message = (
            f"{emoji} {signal} SIGNAL\n\n"

            f"Symbol: {symbol}\n"
            f"Timeframe: {interval}\n\n"

            f"💰 Entry Price: {entry:.6f}\n\n"

            f"EMA 9: {ema9:.6f}\n"
            f"EMA 21: {ema21:.6f}\n"
            f"EMA 50: {ema50:.6f}\n"
            f"EMA 200: {ema200:.6f}\n\n"

            f"RSI: {rsi_value:.2f}\n"
            f"MACD: {macd_value:.6f}\n"
            f"MACD Signal: {signal_value:.6f}\n\n"

            f"Volume: {volume_status}\n\n"

            f"Long Score: {long_score}/6\n"
            f"Short Score: {short_score}/6\n\n"

            "⚠️ Technical signal only — "
            "not an automatic trade."
        )

        return message

    except Exception as e:

        print("Scanner error:", str(e))

        return (
            f"❌ Could not scan {symbol}.\n\n"
            f"Error: {str(e)}"
        )


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    multiplier = 2 / (period + 1)

    ema_value = values[0]

    for price in values[1:]:

        ema_value = (
            (price - ema_value) * multiplier
            + ema_value
        )

    return ema_value


# ============================================================
# RSI
# ============================================================

def rsi(values, period=14):

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

    if len(gains) < period:
        return 50

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


# ============================================================
# MACD
# ============================================================

def macd(values):

    ema12 = ema(values, 12)
    ema26 = ema(values, 26)

    macd_value = ema12 - ema26

    # Simplified signal estimate
    signal_value = macd_value

    if len(values) >= 35:

        recent_macd = []

        for i in range(26, len(values)):

            fast = ema(values[:i + 1], 12)
            slow = ema(values[:i + 1], 26)

            recent_macd.append(fast - slow)

        if len(recent_macd) >= 9:
            signal_value = ema(recent_macd, 9)

    return macd_value, signal_value


# ============================================================
# TRADINGVIEW WEBHOOK
# THIS IS SEPARATE FROM TELEGRAM
# ============================================================

@app.route("/webhook", methods=["POST"])
def tradingview_webhook():

    data = request.get_json(silent=True)

    print("TRADINGVIEW WEBHOOK:", data)

    if not data:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    # Optional security check
    if WEBHOOK_SECRET:

        received_secret = data.get("secret")

        if received_secret != WEBHOOK_SECRET:

            print("Unauthorized TradingView webhook")

            return jsonify({
                "error": "Unauthorized"
            }), 401

    symbol = data.get("symbol", "UNKNOWN")
    signal = data.get("signal", "UNKNOWN").upper()

    price = data.get("price", "N/A")
    timeframe = data.get("timeframe", "N/A")

    entry = data.get(
        "entry",
        price
    )

    ema9 = data.get("ema9", "N/A")
    ema21 = data.get("ema21", "N/A")
    ema50 = data.get("ema50", "N/A")
    ema200 = data.get("ema200", "N/A")

    rsi_value = data.get("rsi", "N/A")
    macd_value = data.get("macd", "N/A")
    volume = data.get("volume", "N/A")

    if signal == "LONG":

        emoji = "🟢"

    elif signal == "SHORT":

        emoji = "🔴"

    else:

        emoji = "⚪"

    message = (
        f"{emoji} {signal} SIGNAL\n\n"

        f"Symbol: {symbol}\n"
        f"Timeframe: {timeframe}\n\n"

        f"💰 Entry Price: {entry}\n\n"

        f"EMA 9: {ema9}\n"
        f"EMA 21: {ema21}\n"
        f"EMA 50: {ema50}\n"
        f"EMA 200: {ema200}\n\n"

        f"RSI: {rsi_value}\n"
        f"MACD: {macd_value}\n"
        f"Volume: {volume}\n\n"

        "⚠️ Signal only — "
        "no automatic trade executed."
    )

    telegram_sent = send_telegram(message)

    return jsonify({
        "status": "signal received",
        "telegram_sent": telegram_sent,
        "signal": signal,
        "symbol": symbol,
        "entry": entry
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "bot": "LongShortCryptoBot",
        "telegram_webhook": "/telegram-webhook",
        "tradingview_webhook": "/webhook"
    })


# ============================================================
# REGISTER TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():

    if not TELEGRAM_BOT_TOKEN:

        print("ERROR: TELEGRAM_BOT_TOKEN is missing")

        return False

    if not RAILWAY_PUBLIC_DOMAIN:

        print("ERROR: RAILWAY_PUBLIC_DOMAIN is missing")

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
            "Telegram webhook setup:",
            response.status_code,
            response.text
        )

        return response.ok

    except Exception as e:

        print(
            "Telegram webhook setup error:",
            str(e)
        )

        return False


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    setup_telegram_webhook()

    port = int(
        os.getenv("PORT", 8080)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
