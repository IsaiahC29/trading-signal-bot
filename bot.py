import os
import html
import time
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

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)

REQUEST_TIMEOUT = 12


# ============================================================
# COINS
# ============================================================

COINS = {
    "BTC": ("BTCUSDT", "BTC-USD"),
    "ETH": ("ETHUSDT", "ETH-USD"),
    "SOL": ("SOLUSDT", "SOL-USD"),
    "XRP": ("XRPUSDT", "XRP-USD"),
    "PENGU": ("PENGUUSDT", "PENGU-USD"),
    "AVAX": ("AVAXUSDT", "AVAX-USD"),
    "SHIB": ("SHIBUSDT", "SHIB-USD"),
    "DOGE": ("DOGEUSDT", "DOGE-USD"),
    "LINK": ("LINKUSDT", "LINK-USD"),
    "ADA": ("ADAUSDT", "ADA-USD"),
    "SUI": ("SUIUSDT", "SUI-USD"),
    "PEPE": ("PEPEUSDT", "PEPE-USD"),
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": ("5m", 300, 1.0),
    "15m": ("15m", 900, 1.0),
    "1h": ("1h", 3600, 1.2),
    "4h": ("4h", 21600, 1.4),
    "1D": ("1d", 86400, 1.6),
}


# ============================================================
# TRADINGVIEW CACHE
# ============================================================

TRADINGVIEW_CACHE = {}


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message, chat_id, keyboard=None):

    if not TELEGRAM_API or not chat_id:
        print("Telegram configuration missing.")
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

        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json=payload,
            timeout=15,
        )

        print(
            "TELEGRAM:",
            response.status_code,
            response.text[:300],
        )

        return response.ok

    except Exception as e:

        print("TELEGRAM ERROR:", e)

        return False


def answer_callback(callback_id):

    if not TELEGRAM_API or not callback_id:
        return

    try:

        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id
            },
            timeout=10,
        )

    except Exception:
        pass


# ============================================================
# MENUS
# ============================================================

def main_menu():

    coins = list(COINS.keys())

    rows = []

    for i in range(0, len(coins), 2):

        row = []

        for coin in coins[i:i + 2]:

            row.append({
                "text": f"📊 {coin}",
                "callback_data": f"scan_{coin}",
            })

        rows.append(row)

    rows.append([
        {
            "text": "📰 Crypto News",
            "callback_data": "news_all",
        }
    ])

    rows.append([
        {
            "text": "ℹ️ How It Works",
            "callback_data": "help",
        }
    ])

    return rows


def scan_menu():

    return [
        [
            {
                "text": "🔎 Scan Another Coin",
                "callback_data": "scan_menu",
            }
        ],
        [
            {
                "text": "📰 News",
                "callback_data": "news_all",
            },
            {
                "text": "👑 VIP",
                "callback_data": "vip",
            },
        ],
        [
            {
                "text": "⬅️ Main Menu",
                "callback_data": "main_menu",
            }
        ],
    ]


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return [None] * len(values)

    multiplier = 2 / (period + 1)

    result = [None] * len(values)

    previous = (
        sum(values[:period])
        / period
    )

    result[period - 1] = previous

    for i in range(period, len(values)):

        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

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

        gains.append(
            max(change, 0)
        )

        losses.append(
            max(-change, 0)
        )

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(period, len(gains)):

        avg_gain = (
            (avg_gain * (period - 1)
             + gains[i])
            / period
        )

        avg_loss = (
            (avg_loss * (period - 1)
             + losses[i])
            / period
        )

    if avg_loss == 0:
        return 100

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

        candle = candles[i]

        previous_close = (
            candles[i - 1]["close"]
        )

        true_range = max(
            candle["high"] - candle["low"],
            abs(
                candle["high"]
                - previous_close
            ),
            abs(
                candle["low"]
                - previous_close
            ),
        )

        true_ranges.append(
            true_range
        )

    atr = (
        sum(true_ranges[:period])
        / period
    )

    for value in true_ranges[period:]:

        atr = (
            (
                atr * (period - 1)
                + value
            )
            / period
        )

    return atr


# ============================================================
# MACD
# ============================================================

def calculate_macd(closes):

    if len(closes) < 50:
        return None

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)

    macd_values = []

    for i in range(len(closes)):

        if (
            ema12[i] is not None
            and ema26[i] is not None
        ):

            macd_values.append(
                ema12[i] - ema26[i]
            )

    signal = ema(
        macd_values,
        9,
    )

    if not signal:
        return None

    if signal[-1] is None:
        return None

    value = macd_values[-1]

    return {
        "value": value,
        "signal": signal[-1],
        "histogram": (
            value - signal[-1]
        ),
    }


# ============================================================
# BINANCE NORMALIZATION
# ============================================================

def normalize_binance(rows):

    candles = []

    for row in rows:

        try:

            candles.append({
                "timestamp": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        except Exception:
            pass

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    return candles


# ============================================================
# COINBASE NORMALIZATION
# ============================================================

def normalize_coinbase(rows):

    candles = []

    for row in rows:

        try:

            candles.append({
                "timestamp": int(row[0]) * 1000,
                "open": float(row[3]),
                "high": float(row[2]),
                "low": float(row[1]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        except Exception:
            pass

    candles.sort(
        key=lambda x: x["timestamp"]
    )

    return candles


# ============================================================
# BINANCE MARKET DATA
# ============================================================

def get_binance_candles(
    symbol,
    interval,
):

    try:

        response = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": 200,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                "SideShiftAI/2.0"
            },
        )

        if not response.ok:

            print(
                "BINANCE ERROR:",
                symbol,
                interval,
                response.status_code,
            )

            return []

        return normalize_binance(
            response.json()
        )

    except Exception as e:

        print(
            "BINANCE REQUEST ERROR:",
            e,
        )

        return []


# ============================================================
# COINBASE MARKET DATA
# ============================================================

def get_coinbase_candles(
    product,
    granularity,
):

    try:

        url = (
            "https://api.exchange.coinbase.com/"
            f"products/{product}/candles"
        )

        response = requests.get(
            url,
            params={
                "granularity":
                granularity
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                "SideShiftAI/2.0"
            },
        )

        if not response.ok:

            print(
                "COINBASE ERROR:",
                product,
                response.status_code,
            )

            return []

        candles = normalize_coinbase(
            response.json()
        )

        return candles[-200:]

    except Exception as e:

        print(
            "COINBASE REQUEST ERROR:",
            e,
        )

        return []


# ============================================================
# GET MARKET DATA
# ============================================================

def get_market_candles(
    coin,
    timeframe,
):

    binance_symbol, coinbase_symbol = (
        COINS[coin]
    )

    binance_interval, coinbase_seconds, _ = (
        TIMEFRAMES[timeframe]
    )

    # PRIMARY
    candles = get_binance_candles(
        binance_symbol,
        binance_interval,
    )

    if len(candles) >= 60:

        return candles, "Binance"

    # FALLBACK
    candles = get_coinbase_candles(
        coinbase_symbol,
        coinbase_seconds,
    )

    if len(candles) >= 60:

        return candles, "Coinbase"

    return [], None


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_structure(candles):

    if len(candles) < 30:

        return {
            "label": "Unknown",
            "score": 0,
        }

    first = candles[-30:-15]
    second = candles[-15:]

    first_high = max(
        x["high"]
        for x in first
    )

    second_high = max(
        x["high"]
        for x in second
    )

    first_low = min(
        x["low"]
        for x in first
    )

    second_low = min(
        x["low"]
        for x in second
    )

    higher_high = (
        second_high > first_high
    )

    higher_low = (
        second_low > first_low
    )

    lower_high = (
        second_high < first_high
    )

    lower_low = (
        second_low < first_low
    )

    if higher_high and higher_low:

        return {
            "label":
            "Bullish Structure",
            "score": 2,
        }

    if lower_high and lower_low:

        return {
            "label":
            "Bearish Structure",
            "score": -2,
        }

    if higher_high:

        return {
            "label":
            "Bullish Lean",
            "score": 1,
        }

    if lower_low:

        return {
            "label":
            "Bearish Lean",
            "score": -1,
        }

    return {
        "label":
        "Sideways / Mixed",
        "score": 0,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(candles):

    if len(candles) < 60:

        return {
            "valid": False,
            "direction":
            "Data Unavailable",
            "score": 0,
        }

    closes = [
        x["close"]
        for x in candles
    ]

    price = closes[-1]

    ema20 = ema(
        closes,
        20,
    )

    ema50 = ema(
        closes,
        50,
    )

    ema200 = ema(
        closes,
        200,
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

    structure = calculate_structure(
        candles
    )

    score = 0

    # PRICE VS EMA20
    if price > ema20[-1]:
        score += 2
    else:
        score -= 2

    # EMA20 VS EMA50
    if ema20[-1] > ema50[-1]:
        score += 2
    else:
        score -= 2

    # EMA200
    if ema200[-1] is not None:

        if price > ema200[-1]:
            score += 1
        else:
            score -= 1

    # EMA SLOPE
    if ema20[-6] is not None:

        if ema20[-1] > ema20[-6]:
            score += 1
        else:
            score -= 1

    # PRICE MOMENTUM
    previous = closes[-11]

    percent_change = (
        (price - previous)
        / previous
        * 100
    )

    if percent_change > 0.5:
        score += 2

    elif percent_change > 0.15:
        score += 1

    elif percent_change < -0.5:
        score -= 2

    elif percent_change < -0.15:
        score -= 1

    # RSI
    if rsi is not None:

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1

    # MACD
    if macd:

        if macd["histogram"] > 0:
            score += 1

        elif macd["histogram"] < 0:
            score -= 1

    # STRUCTURE
    score += structure["score"]

    # VOLUME
    recent_volumes = [
        x["volume"]
        for x in candles[-21:-1]
    ]

    volume_ratio = None

    if recent_volumes:

        average_volume = (
            sum(recent_volumes)
            / len(recent_volumes)
        )

        if average_volume > 0:

            volume_ratio = (
                candles[-1]["volume"]
                / average_volume
            )

    # ATR
    atr_percent = None

    if atr and price:

        atr_percent = (
            atr / price
        ) * 100

    # DIRECTION
    if score >= 5:

        direction = "Bullish"

    elif score <= -5:

        direction = "Bearish"

    elif score >= 2:

        direction = "Bullish Lean"

    elif score <= -2:

        direction = "Bearish Lean"

    else:

        direction = "Consolidation"

    return {
        "valid": True,
        "direction": direction,
        "score": score,
        "price": price,
        "ema20": ema20[-1],
        "ema50": ema50[-1],
        "ema200": ema200[-1],
        "rsi": rsi,
        "macd": macd,
        "volume_ratio": volume_ratio,
        "atr_percent": atr_percent,
        "structure": structure["label"],
        "structure_score":
            structure["score"],
    }


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_key(
    coin,
    timeframe,
):

    return f"{coin}:{timeframe}"


def get_tradingview_data(
    coin,
    timeframe,
):

    key = tradingview_key(
        coin,
        timeframe,
    )

    data = TRADINGVIEW_CACHE.get(
        key
    )

    if not data:
        return None

    # Don't use stale TradingView data.
    if (
        time.time()
        - data["received"]
        > 7200
    ):

        return None

    return data["data"]


# ============================================================
# COMPLETE COIN SCAN
# ============================================================

def scan_coin(coin):

    results = {}
    providers = {}

    price = None

    for timeframe in TIMEFRAMES:

        candles, provider = (
            get_market_candles(
                coin,
                timeframe,
            )
        )

        providers[
            timeframe
        ] = provider

        result = analyze_timeframe(
            candles
        )

        results[
            timeframe
        ] = result

        if candles:

            price = candles[-1]["close"]

    valid = [
        (tf, result)
        for tf, result
        in results.items()
        if result.get("valid")
    ]

    if not valid:

        return {
            "coin": coin,
            "price": price,
            "timeframes": results,
            "providers": providers,
            "overall": {
                "label":
                "Data Unavailable",
                "score": 0,
                "confidence": 0,
            },
            "valid_count": 0,
            "total_count":
                len(TIMEFRAMES),
        }

    # ========================================================
    # MULTI-TIMEFRAME WEIGHTING
    # ========================================================

    total_weight = 0
    weighted_score = 0

    for timeframe, result in valid:

        weight = TIMEFRAMES[
            timeframe
        ][2]

        weighted_score += (
            result["score"]
            * weight
        )

        total_weight += weight

    average_score = (
        weighted_score
        / total_weight
    )

    # ========================================================
    # BULL / BEAR COUNT
    # ========================================================

    bullish = 0
    bearish = 0

    for _, result in valid:

        direction = result[
            "direction"
        ]

        if "Bullish" in direction:
            bullish += 1

        elif "Bearish" in direction:
            bearish += 1

    count = len(valid)

    # ========================================================
    # TRADINGVIEW CONFIRMATION
    # ========================================================

    tv_bullish = 0
    tv_bearish = 0

    for timeframe, _ in valid:

        tv = get_tradingview_data(
            coin,
            timeframe,
        )

        if not tv:
            continue

        signal = str(
            tv.get(
                "signal",
                "",
            )
        ).upper()

        if signal in (
            "BUY",
            "LONG",
            "BULLISH",
        ):

            tv_bullish += 1

        elif signal in (
            "SELL",
            "SHORT",
            "BEARISH",
        ):

            tv_bearish += 1

    # TradingView is confirmation,
    # not the entire decision.

    if tv_bullish > tv_bearish:

        average_score += min(
            2,
            tv_bullish * 0.5,
        )

    elif tv_bearish > tv_bullish:

        average_score -= min(
            2,
            tv_bearish * 0.5,
        )

    # ========================================================
    # OVERALL DIRECTION
    # ========================================================

    if (
        average_score >= 3
        and bullish / count >= 0.60
    ):

        overall = "Bullish"

    elif (
        average_score <= -3
        and bearish / count >= 0.60
    ):

        overall = "Bearish"

    elif average_score >= 1:

        overall = "Bullish Lean"

    elif average_score <= -1:

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / Indecisive"
        )

    confidence = min(
        100,
        abs(average_score)
        / 7
        * 100
        + min(
            20,
            abs(
                tv_bullish
                - tv_bearish
            ) * 5,
        ),
    )

    # ========================================================
    # AGGREGATES
    # ========================================================

    rsi_values = [
        result["rsi"]
        for _, result in valid
        if result.get("rsi") is not None
    ]

    volume_values = [
        result["volume_ratio"]
        for _, result in valid
        if result.get(
            "volume_ratio"
        ) is not None
    ]

    atr_values = [
        result["atr_percent"]
        for _, result in valid
        if result.get(
            "atr_percent"
        ) is not None
    ]

    structure_score = (
        sum(
            result[
                "structure_score"
            ]
            for _, result in valid
        )
        / count
    )

    if structure_score > 0.75:

        structure = "Bullish"

    elif structure_score < -0.75:

        structure = "Bearish"

    else:

        structure = "Mixed"

    return {
        "coin": coin,
        "price": price,
        "timeframes": results,
        "providers": providers,
        "overall": {
            "label": overall,
            "score": average_score,
            "confidence": confidence,
        },
        "valid_count": count,
        "total_count":
            len(TIMEFRAMES),
        "average_rsi": (
            sum(rsi_values)
            / len(rsi_values)
            if rsi_values
            else None
        ),
        "average_volume_ratio": (
            sum(volume_values)
            / len(volume_values)
            if volume_values
            else None
        ),
        "average_atr_percent": (
            sum(atr_values)
            / len(atr_values)
            if atr_values
            else None
        ),
        "structure": structure,
        "tradingview": {
            "bullish":
                tv_bullish,
            "bearish":
                tv_bearish,
        },
    }


# ============================================================
# FORMAT
# ============================================================

def format_price(price):

    if price is None:
        return "Unavailable"

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    if price >= 0.01:
        return f"${price:,.6f}"

    return f"${price:,.10f}"


def direction_emoji(direction):

    if "Bullish" in direction:
        return "🟢"

    if "Bearish" in direction:
        return "🔴"

    if "Consolidation" in direction:
        return "🟡"

    return "⚪"


# ============================================================
# TELEGRAM SCAN MESSAGE
# ============================================================

def build_scan_message(
    analysis
):

    coin = analysis["coin"]

    overall = analysis[
        "overall"
    ]

    lines = [

        f"<b>🔎 {coin} MARKET ANALYSIS</b>",

        "",

        f"💰 <b>Price:</b> "
        f"{format_price(analysis['price'])}",

        "",

        f"{direction_emoji(overall['label'])} "
        f"<b>Overall Direction:</b> "
        f"{overall['label']}",

        f"🎯 <b>Analysis Strength:</b> "
        f"{overall['confidence']:.0f}%",

        "",

        "📊 <b>MULTI-TIMEFRAME ANALYSIS</b>",
    ]

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        direction = result.get(
            "direction",
            "Data Unavailable",
        )

        lines.append(
            f"{direction_emoji(direction)} "
            f"<b>{timeframe}:</b> "
            f"{direction}"
        )

    average_rsi = analysis.get(
        "average_rsi"
    )

    volume = analysis.get(
        "average_volume_ratio"
    )

    atr = analysis.get(
        "average_atr_percent"
    )

    tv = analysis[
        "tradingview"
    ]

    lines += [

        "",

        "📈 <b>MARKET CONDITIONS</b>",

        f"⚡ <b>Direction:</b> "
        f"{overall['label']}",

        (
            f"📉 <b>Average RSI:</b> "
            f"{average_rsi:.1f}"
            if average_rsi is not None
            else
            "📉 <b>Average RSI:</b> "
            "Unavailable"
        ),

        (
            f"📦 <b>Average Volume:</b> "
            f"{volume:.2f}x"
            if volume is not None
            else
            "📦 <b>Average Volume:</b> "
            "Unavailable"
        ),

        (
            f"🌊 <b>Average ATR:</b> "
            f"{atr:.2f}%"
            if atr is not None
            else
            "🌊 <b>Average ATR:</b> "
            "Unavailable"
        ),

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}",

        "",

        "📡 <b>TRADINGVIEW CONFIRMATION</b>",

        f"🟢 Bullish: "
        f"{tv['bullish']}",

        f"🔴 Bearish: "
        f"{tv['bearish']}",

        "",

        f"📡 <b>Data Quality:</b> "
        f"{analysis['valid_count']}/"
        f"{analysis['total_count']} "
        f"timeframes",

        "",

        "⚪ <b>Analysis only — "
        "not a guaranteed trade signal.</b>",
    ]

    return "\n".join(lines)


# ============================================================
# PERFORM SCAN
# ============================================================

def perform_scan(
    coin,
    chat_id
):

    if coin not in COINS:

        send_telegram(
            "❌ Unsupported cryptocurrency.",
            chat_id,
            main_menu(),
        )

        return

    send_telegram(
        (
            f"<b>🔎 Scanning {coin}...</b>\n\n"
            "📡 Live market data\n"
            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market Structure\n"
            "📡 TradingView confirmation"
        ),
        chat_id,
    )

    try:

        analysis = scan_coin(
            coin
        )

        send_telegram(
            build_scan_message(
                analysis
            ),
            chat_id,
            scan_menu(),
        )

    except Exception as e:

        print(
            "SCAN ERROR:",
            repr(e),
        )

        send_telegram(
            (
                "<b>⚠️ SCAN ERROR</b>\n\n"
                f"<code>{html.escape(str(e))}</code>"
            ),
            chat_id,
            scan_menu(),
        )


# ============================================================
# NEWS
# ============================================================

def get_crypto_news():

    try:

        feed = feedparser.parse(
            "https://news.google.com/rss/"
            "search?q=cryptocurrency+crypto+"
            "bitcoin+ethereum"
            "&hl=en-US&gl=US&ceid=US:en"
        )

        message = (
            "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
        )

        for number, item in enumerate(
            feed.entries[:8],
            1,
        ):

            title = html.escape(
                item.get(
                    "title",
                    "",
                )
            )

            link = html.escape(
                item.get(
                    "link",
                    "",
                ),
                quote=True,
            )

            message += (
                f'<b>{number}.</b> '
                f'<a href="{link}">'
                f'{title}</a>\n\n'
            )

        return message

    except Exception:

        return (
            "<b>📰 NEWS</b>\n\n"
            "News unavailable."
        )


# ============================================================
# WELCOME
# ============================================================

def send_welcome(chat_id):

    send_telegram(
        (
            "<b>🤖 SIDESHIFT AI 2.0</b>\n\n"

            "Live multi-timeframe crypto "
            "market analysis.\n\n"

            "<b>Analyzes:</b>\n"
            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market Structure\n"
            "📡 TradingView confirmation\n\n"

            "The engine detects both "
            "<b>bullish AND bearish</b> "
            "conditions."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# HELP
# ============================================================

def send_help(chat_id):

    send_telegram(
        (
            "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"

            "SideShift pulls live market "
            "candles and analyzes:\n\n"

            "5m • 15m • 1h • 4h • 1D\n\n"

            "It evaluates EMA relationships, "
            "RSI, MACD, volume, ATR and "
            "market structure.\n\n"

            "TradingView alerts can provide "
            "an additional confirmation layer.\n\n"

            "Bullish and bearish evidence "
            "are evaluated separately."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# VIP
# ============================================================

def send_vip(chat_id):

    send_telegram(
        (
            "<b>👑 SIDESHIFT AI VIP</b>\n\n"
            "VIP signal features are "
            "not enabled yet."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.route(
    "/telegram-webhook",
    methods=["POST"],
)
def telegram_webhook():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        # ====================================================
        # NORMAL MESSAGE
        # ====================================================

        message = data.get(
            "message"
        )

        if message:

            chat_id = (
                message
                .get("chat", {})
                .get("id")
            )

            text = (
                message
                .get("text", "")
                .strip()
            )

            if text.startswith(
                "/start"
            ):

                send_welcome(
                    chat_id
                )

            elif text.startswith(
                "/help"
            ):

                send_help(
                    chat_id
                )

            elif text.startswith(
                "/news"
            ):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

            elif text.lower().startswith(
                "/scan"
            ):

                parts = text.split()

                if len(parts) < 2:

                    send_telegram(
                        (
                            "<b>📊 SCAN</b>\n\n"
                            "Example:\n"
                            "/scan BTC\n"
                            "/scan ETH\n"
                            "/scan XRP"
                        ),
                        chat_id,
                        main_menu(),
                    )

                else:

                    perform_scan(
                        parts[1].upper(),
                        chat_id,
                    )

            else:

                send_telegram(
                    (
                        "Use /start to open "
                        "SideShift AI."
                    ),
                    chat_id,
                    main_menu(),
                )

            return jsonify({
                "ok": True
            })

        # ====================================================
        # CALLBACK
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
                "",
            )

            chat_id = (
                callback
                .get("message", {})
                .get("chat", {})
                .get("id")
            )

            answer_callback(
                callback_id
            )

            # IMPORTANT:
            # scan_menu MUST come before scan_*

            if callback_data == "scan_menu":

                send_telegram(
                    (
                        "<b>📊 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency."
                    ),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            if callback_data.startswith(
                "scan_"
            ):

                coin = (
                    callback_data
                    .replace(
                        "scan_",
                        "",
                        1,
                    )
                    .upper()
                )

                perform_scan(
                    coin,
                    chat_id,
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == (
                "main_menu"
            ):

                send_welcome(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == (
                "news_all"
            ):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "help":

                send_help(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if callback_data == "vip":

                send_vip(
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
            repr(e),
        )

        return jsonify({
            "ok": False,
            "error": str(e),
        }), 500


# ============================================================
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"],
)
def tradingview_webhook():

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        # SECURITY

        if (
            WEBHOOK_SECRET
            and data.get("secret")
            != WEBHOOK_SECRET
        ):

            return jsonify({
                "error":
                "Unauthorized"
            }), 401

        symbol = str(
            data.get(
                "symbol",
                "",
            )
        ).upper()

        timeframe = str(
            data.get(
                "timeframe",
                "",
            )
        ).strip()

        # Normalize symbols

        symbol = (
            symbol
            .replace(".P", "")
            .replace("/", "")
        )

        if symbol.endswith(
            "USDT"
        ):

            symbol = symbol[:-4]

        elif symbol.endswith(
            "USD"
        ):

            symbol = symbol[:-3]

        if symbol not in COINS:

            return jsonify({
                "error":
                "Unsupported symbol",
                "symbol":
                symbol,
            }), 400

        if timeframe not in TIMEFRAMES:

            return jsonify({
                "error":
                "Unsupported timeframe",
                "timeframe":
                timeframe,
            }), 400

        TRADINGVIEW_CACHE[
            f"{symbol}:{timeframe}"
        ] = {
            "received":
                time.time(),

            "data":
                data,
        }

        signal = str(
            data.get(
                "signal",
                "NEUTRAL",
            )
        ).upper()

        print(
            "TRADINGVIEW:",
            symbol,
            timeframe,
            signal,
        )

        if TELEGRAM_CHAT_ID:

            send_telegram(
                (
                    "<b>📡 TRADINGVIEW UPDATE</b>\n\n"
                    f"<b>{html.escape(symbol)}</b>\n"
                    f"Timeframe: "
                    f"{html.escape(timeframe)}\n"
                    f"Signal: "
                    f"<b>{html.escape(signal)}</b>"
                ),
                TELEGRAM_CHAT_ID,
            )

        return jsonify({
            "status":
            "cached",

            "symbol":
            symbol,

            "timeframe":
            timeframe,

            "signal":
            signal,
        })

    except Exception as e:

        print(
            "TRADINGVIEW ERROR:",
            repr(e),
        )

        return jsonify({
            "error":
            str(e)
        }), 500


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"],
)
def home():

    return jsonify({

        "status":
        "online",

        "bot":
        "SideShift AI",

        "version":
        "2.0",

        "telegram_webhook":
        "/telegram-webhook",

        "tradingview_webhook":
        "/webhook",

        "market_test":
        "/test-market/BTC",

        "coins":
        list(COINS.keys()),

        "timeframes":
        list(TIMEFRAMES.keys()),
    })


# ============================================================
# MARKET TEST
# ============================================================

@app.route(
    "/test-market/<coin>",
    methods=["GET"],
)
def test_market(coin):

    coin = coin.upper()

    if coin not in COINS:

        return jsonify({

            "error":
            "Unsupported coin",

            "supported":
            list(COINS.keys()),

        }), 400

    return jsonify(
        scan_coin(coin)
    )


# ============================================================
# SET TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():

    if (
        not TELEGRAM_API
        or not RAILWAY_PUBLIC_DOMAIN
    ):

        print(
            "Webhook setup skipped."
        )

        return False

    webhook_url = (
        f"https://"
        f"{RAILWAY_PUBLIC_DOMAIN}"
        "/telegram-webhook"
    )

    try:

        response = requests.post(

            f"{TELEGRAM_API}"
            "/setWebhook",

            json={
                "url":
                webhook_url,

                "allowed_updates": [
                    "message",
                    "callback_query",
                ],

                "drop_pending_updates":
                True,
            },

            timeout=15,
        )

        print(
            "WEBHOOK SET:",
            response.status_code,
            response.text,
        )

        return response.ok

    except Exception as e:

        print(
            "WEBHOOK SET ERROR:",
            e,
        )

        return False


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "SideShift AI 2.0 starting..."
    )

    print(
        "================================"
    )

    print(
        "Telegram:",
        "FOUND"
        if TELEGRAM_BOT_TOKEN
        else "MISSING",
    )

    print(
        "Railway domain:",
        RAILWAY_PUBLIC_DOMAIN
        or "MISSING",
    )

    print(
        "Telegram chat:",
        "FOUND"
        if TELEGRAM_CHAT_ID
        else "MISSING",
    )

    setup_telegram_webhook()

    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )