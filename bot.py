import os
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-this-secret")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials are not configured.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }

    response = requests.post(url, json=payload, timeout=15)

    if response.ok:
        return True

    print("Telegram error:", response.text)
    return False


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "online",
        "bot": "LongShortCryptoBot"
    })


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    secret = data.get("secret")

    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "Unauthorized"}), 401

    symbol = data.get("symbol", "UNKNOWN")
    signal = data.get("signal", "UNKNOWN").upper()
    price = data.get("price", "N/A")
    timeframe = data.get("timeframe", "N/A")

    ema9 = data.get("ema9", "N/A")
    ema21 = data.get("ema21", "N/A")
    ema50 = data.get("ema50", "N/A")
    ema200 = data.get("ema200", "N/A")
    rsi = data.get("rsi", "N/A")
    macd = data.get("macd", "N/A")
    volume = data.get("volume", "N/A")

    if signal == "LONG":
        emoji = "🟢"
    elif signal == "SHORT":
        emoji = "🔴"
    else:
        emoji = "⚪"

    message = f"""
{emoji} {signal} SIGNAL

Symbol: {symbol}
Timeframe: {timeframe}
Price: {price}

EMA 9: {ema9}
EMA 21: {ema21}
EMA 50: {ema50}
EMA 200: {ema200}

RSI: {rsi}
MACD: {macd}
Volume: {volume}

⚠️ Signal only — no automatic trade executed.
"""

    send_telegram(message)

    return jsonify({
        "status": "signal received",
        "signal": signal
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
