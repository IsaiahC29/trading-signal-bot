import os
import html
import time
import threading
from datetime import datetime, timezone

import requests
import feedparser
from flask import Flask, request, jsonify


# ============================================================
# SIDESHIFT AI 4.0
# Complete single-file Telegram crypto analysis bot
#
# MARKET ENGINE
#   Coinbase
#   Kraken
#   Binance
#
# TECHNICAL ENGINE
#   EMA 20 / 50 / 200
#   RSI
#   MACD
#   Momentum
#   Volume
#   ATR
#   Market Structure
#
# DERIVATIVES ENGINE
#   CoinGlass Open Interest
#   CoinGlass Funding
#   CoinGlass Liquidations
#   CoinGlass Long/Short
#
# MARKET REGIME
#   BTC confirmation
#   Multi-timeframe alignment
#
# SIGNAL LIMITS
#   FREE = maximum 4/day
#   VIP  = maximum 10/day
#
# IMPORTANT
#   Daily limits are ceilings, NOT quotas.
#   The bot will not manufacture signals.
# ============================================================

app = Flask(__name__)


# ============================================================
# ENVIRONMENT
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN",
    "",
)

RAILWAY_PUBLIC_DOMAIN = os.getenv(
    "RAILWAY_PUBLIC_DOMAIN",
    "",
)

WEBHOOK_SECRET = os.getenv(
    "WEBHOOK_SECRET",
    "",
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID",
    "",
)

FREE_CHANNEL = os.getenv(
    "FREE_CHANNEL",
    "",
)

FREE_SIGNAL_CHAT_ID = os.getenv(
    "FREE_SIGNAL_CHAT_ID",
    "",
)

VIP_SIGNAL_CHAT_ID = os.getenv(
    "VIP_SIGNAL_CHAT_ID",
    "",
)

NEWS_CHAT_ID = os.getenv(
    "NEWS_CHAT_ID",
    "",
)

CMC_API_KEY = os.getenv(
    "CMC_API_KEY",
    "",
)

# NEW
COINGLASS_API_KEY = os.getenv(
    "COINGLASS_API_KEY",
    "",
)

PORT = int(
    os.getenv(
        "PORT",
        "8080",
    )
)

REQUEST_TIMEOUT = 15


# ============================================================
# SIGNAL SETTINGS
# ============================================================

SIGNAL_SCAN_INTERVAL = int(
    os.getenv(
        "SIGNAL_SCAN_INTERVAL",
        "30",
    )
) * 60

# FREE = MAXIMUM 4
MAX_FREE_SIGNALS_PER_DAY = int(
    os.getenv(
        "MAX_FREE_SIGNALS_PER_DAY",
        "4",
    )
)

# VIP = MAXIMUM 10
MAX_VIP_SIGNALS_PER_DAY = int(
    os.getenv(
        "MAX_VIP_SIGNALS_PER_DAY",
        "10",
    )
)

MIN_SIGNAL_SCORE = float(
    os.getenv(
        "MIN_SIGNAL_SCORE",
        "7.0",
    )
)

SIGNAL_COOLDOWN_MINUTES = int(
    os.getenv(
        "SIGNAL_COOLDOWN_MINUTES",
        "180",
    )
)

# CoinGlass cache prevents unnecessary API requests.
COINGLASS_CACHE_SECONDS = int(
    os.getenv(
        "COINGLASS_CACHE_SECONDS",
        "30",
    )
)


# ============================================================
# NEWS
# ============================================================

NEWS_INTERVAL = int(
    os.getenv(
        "NEWS_INTERVAL",
        "360",
    )
) * 60


# ============================================================
# TELEGRAM API
# ============================================================

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN
    else None
)


# ============================================================
# MARKET PROVIDERS
# ============================================================

COINBASE_CANDLES_URL = (
    "https://api.exchange.coinbase.com/products/{product}/candles"
)

KRAKEN_OHLC_URL = (
    "https://api.kraken.com/0/public/OHLC"
)

BINANCE_KLINES_URL = (
    "https://api.binance.com/api/v3/klines"
)

CMC_PRICE_URL = (
    "https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest"
)


# ============================================================
# COINGLASS V4
# ============================================================

COINGLASS_BASE_URL = (
    "https://open-api-v4.coinglass.com"
)

COINGLASS_OI_URL = (
    COINGLASS_BASE_URL
    + "/api/futures/open-interest/exchange-list"
)

COINGLASS_FUNDING_URL = (
    COINGLASS_BASE_URL
    + "/api/futures/funding-rate/exchange-list"
)

COINGLASS_LIQUIDATION_URL = (
    COINGLASS_BASE_URL
    + "/api/futures/liquidation/aggregated-history"
)

COINGLASS_LONG_SHORT_URL = (
    COINGLASS_BASE_URL
    + "/api/futures/global-long-short-account-ratio/history"
)


# ============================================================
# COINS
# ============================================================

COINS = {
    "BTC": {
        "coinbase": "BTC-USD",
        "kraken": "XBTUSD",
        "binance": "BTCUSDT",
        "cmc": "BTC",
    },
    "ETH": {
        "coinbase": "ETH-USD",
        "kraken": "ETHUSD",
        "binance": "ETHUSDT",
        "cmc": "ETH",
    },
    "SOL": {
        "coinbase": "SOL-USD",
        "kraken": "SOLUSD",
        "binance": "SOLUSDT",
        "cmc": "SOL",
    },
    "XRP": {
        "coinbase": "XRP-USD",
        "kraken": "XRPUSD",
        "binance": "XRPUSDT",
        "cmc": "XRP",
    },
    "AVAX": {
        "coinbase": "AVAX-USD",
        "kraken": "AVAXUSD",
        "binance": "AVAXUSDT",
        "cmc": "AVAX",
    },
    "DOGE": {
        "coinbase": "DOGE-USD",
        "kraken": "DOGEUSD",
        "binance": "DOGEUSDT",
        "cmc": "DOGE",
    },
    "LINK": {
        "coinbase": "LINK-USD",
        "kraken": "LINKUSD",
        "binance": "LINKUSDT",
        "cmc": "LINK",
    },
    "ADA": {
        "coinbase": "ADA-USD",
        "kraken": "ADAUSD",
        "binance": "ADAUSDT",
        "cmc": "ADA",
    },
    "SHIB": {
        "coinbase": "SHIB-USD",
        "kraken": "SHIBUSD",
        "binance": "SHIBUSDT",
        "cmc": "SHIB",
    },
    "SUI": {
        "coinbase": "SUI-USD",
        "kraken": "SUIUSD",
        "binance": "SUIUSDT",
        "cmc": "SUI",
    },
    "PEPE": {
        "coinbase": "PEPE-USD",
        "kraken": "PEPEUSD",
        "binance": "PEPEUSDT",
        "cmc": "PEPE",
    },
    "PENGU": {
        "coinbase": "PENGU-USD",
        "kraken": "PENGUUSD",
        "binance": "PENGUUSDT",
        "cmc": "PENGU",
    },
}


# ============================================================
# TIMEFRAMES
# ============================================================

TIMEFRAMES = {
    "5m": {
        "coinbase": 300,
        "kraken": 5,
        "binance": "5m",
        "weight": 0.8,
    },
    "15m": {
        "coinbase": 900,
        "kraken": 15,
        "binance": "15m",
        "weight": 1.0,
    },
    "1h": {
        "coinbase": 3600,
        "kraken": 60,
        "binance": "1h",
        "weight": 1.2,
    },
    "4h": {
        "coinbase": 21600,
        "kraken": 240,
        "binance": "4h",
        "weight": 1.5,
    },
    "1D": {
        "coinbase": 86400,
        "kraken": 1440,
        "binance": "1d",
        "weight": 1.7,
    },
}


# ============================================================
# STATE
# ============================================================

TRADINGVIEW_CACHE = {}

COINGLASS_CACHE = {}

SIGNAL_STATE = {
    "date": None,

    "free_sent_today": 0,

    "vip_sent_today": 0,

    "last_free_signal": {},

    "last_vip_signal": {},
}

STATE_LOCK = threading.Lock()

BACKGROUND_STARTED = False


# ============================================================
# GENERAL HELPERS
# ============================================================

def clamp(
    value,
    minimum,
    maximum,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def safe_float(
    value,
    default=None,
):

    try:

        return float(value)

    except Exception:

        return default


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(
    message,
    chat_id,
    keyboard=None,
):

    if not TELEGRAM_API or not chat_id:

        print(
            "Telegram unavailable: "
            "token/chat_id missing"
        )

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
            response.text[:200],
        )

        return response.ok

    except Exception as exc:

        print(
            "TELEGRAM ERROR:",
            repr(exc),
        )

        return False


def answer_callback(
    callback_id
):

    if (
        not callback_id
        or not TELEGRAM_API
    ):

        return

    try:

        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id": callback_id
            },
            timeout=10,
        )

    except Exception as exc:

        print(
            "CALLBACK ERROR:",
            repr(exc),
        )


# ============================================================
# TELEGRAM MENUS
# ============================================================

def main_menu():

    rows = []

    coins = list(
        COINS.keys()
    )

    for i in range(
        0,
        len(coins),
        2,
    ):

        row = []

        for coin in coins[
            i:i + 2
        ]:

            row.append({
                "text": f"📊 {coin}",
                "callback_data": (
                    f"scan_{coin}"
                ),
            })

        rows.append(row)

    rows.extend([
        [
            {
                "text": "🟢 Free Signals",
                "callback_data": (
                    "free_signals"
                ),
            },
            {
                "text": "👑 VIP",
                "callback_data": "vip",
            },
        ],
        [
            {
                "text": "🔎 Scan a Coin",
                "callback_data": (
                    "scan_menu"
                ),
            },
            {
                "text": "📰 Crypto News",
                "callback_data": (
                    "news_all"
                ),
            },
        ],
        [
            {
                "text": "ℹ️ How It Works",
                "callback_data": "help",
            }
        ],
    ])

    return rows


def scan_menu():

    return [
        [
            {
                "text": "🔎 Scan Another Coin",
                "callback_data": (
                    "scan_menu"
                ),
            }
        ],
        [
            {
                "text": "📰 News",
                "callback_data": (
                    "news_all"
                ),
            },
            {
                "text": "👑 VIP",
                "callback_data": "vip",
            },
        ],
        [
            {
                "text": "⬅️ Main Menu",
                "callback_data": (
                    "main_menu"
                ),
            }
        ],
    ]


# ============================================================
# TECHNICAL MATH
# ============================================================

def ema(
    values,
    period,
):

    if len(values) < period:

        return [
            None
            for _ in values
        ]

    multiplier = (
        2
        / (period + 1)
    )

    result = [
        None
        for _ in values
    ]

    previous = (
        sum(
            values[:period]
        )
        / period
    )

    result[
        period - 1
    ] = previous

    for i in range(
        period,
        len(values),
    ):

        previous = (
            values[i]
            * multiplier
            + previous
            * (
                1
                - multiplier
            )
        )

        result[i] = previous

    return result


def calculate_rsi(
    closes,
    period=14,
):

    if len(closes) < (
        period + 1
    ):

        return None

    gains = []
    losses = []

    for i in range(
        1,
        len(closes),
    ):

        change = (
            closes[i]
            - closes[i - 1]
        )

        gains.append(
            max(
                change,
                0,
            )
        )

        losses.append(
            max(
                -change,
                0,
            )
        )

    avg_gain = (
        sum(
            gains[:period]
        )
        / period
    )

    avg_loss = (
        sum(
            losses[:period]
        )
        / period
    )

    for i in range(
        period,
        len(gains),
    ):

        avg_gain = (
            avg_gain
            * (
                period - 1
            )
            + gains[i]
        ) / period

        avg_loss = (
            avg_loss
            * (
                period - 1
            )
            + losses[i]
        ) / period

    if avg_loss == 0:

        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return 100 - (
        100
        / (
            1 + rs
        )
    )


def calculate_atr(
    candles,
    period=14,
):

    if len(candles) < (
        period + 1
    ):

        return None

    ranges = []

    for i in range(
        1,
        len(candles),
    ):

        candle = candles[i]

        previous_close = (
            candles[
                i - 1
            ]["close"]
        )

        tr = max(
            candle["high"]
            - candle["low"],

            abs(
                candle["high"]
                - previous_close
            ),

            abs(
                candle["low"]
                - previous_close
            ),
        )

        ranges.append(tr)

    atr = (
        sum(
            ranges[:period]
        )
        / period
    )

    for i in range(
        period,
        len(ranges),
    ):

        atr = (
            atr
            * (
                period - 1
            )
            + ranges[i]
        ) / period

    return atr


def calculate_macd(
    closes,
):

    if len(closes) < 50:

        return None

    ema12 = ema(
        closes,
        12,
    )

    ema26 = ema(
        closes,
        26,
    )

    macd_values = []

    for i in range(
        len(closes)
    ):

        if (
            ema12[i]
            is not None
            and ema26[i]
            is not None
        ):

            macd_values.append(
                ema12[i]
                - ema26[i]
            )

    if len(
        macd_values
    ) < 9:

        return None

    signal_values = ema(
        macd_values,
        9,
    )

    signal = (
        signal_values[-1]
    )

    if signal is None:

        return None

    value = (
        macd_values[-1]
    )

    return {
        "value": value,
        "signal": signal,
        "histogram": (
            value - signal
        ),
    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_coinbase(
    rows
):

    candles = []

    for row in rows:

        try:

            candles.append({
                "timestamp": (
                    int(row[0])
                    * 1000
                ),
                "low": float(
                    row[1]
                ),
                "high": float(
                    row[2]
                ),
                "open": float(
                    row[3]
                ),
                "close": float(
                    row[4]
                ),
                "volume": float(
                    row[5]
                ),
            })

        except Exception:

            continue

    candles.sort(
        key=lambda x:
        x["timestamp"]
    )

    return candles


def normalize_kraken(
    rows
):

    candles = []

    for row in rows:

        try:

            candles.append({
                "timestamp": (
                    int(
                        float(
                            row[0]
                        )
                    )
                    * 1000
                ),
                "open": float(
                    row[1]
                ),
                "high": float(
                    row[2]
                ),
                "low": float(
                    row[3]
                ),
                "close": float(
                    row[4]
                ),
                "volume": float(
                    row[6]
                ),
            })

        except Exception:

            continue

    candles.sort(
        key=lambda x:
        x["timestamp"]
    )

    return candles


def normalize_binance(
    rows
):

    candles = []

    for row in rows:

        try:

            candles.append({
                "timestamp": int(
                    row[0]
                ),
                "open": float(
                    row[1]
                ),
                "high": float(
                    row[2]
                ),
                "low": float(
                    row[3]
                ),
                "close": float(
                    row[4]
                ),
                "volume": float(
                    row[5]
                ),
            })

        except Exception:

            continue

    candles.sort(
        key=lambda x:
        x["timestamp"]
    )

    return candles


# ============================================================
# MARKET DATA
# ============================================================

def get_coinbase_candles(
    product,
    granularity,
    limit=200,
):

    try:

        response = requests.get(
            COINBASE_CANDLES_URL.format(
                product=product
            ),
            params={
                "granularity":
                    granularity,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                    "SideShiftAI/4.0"
            },
        )

        if response.status_code != 200:

            return []

        data = response.json()

        if not isinstance(
            data,
            list,
        ):

            return []

        return normalize_coinbase(
            data
        )[-limit:]

    except Exception as exc:

        print(
            "COINBASE ERROR:",
            repr(exc),
        )

        return []


def get_kraken_candles(
    pair,
    interval,
):

    try:

        response = requests.get(
            KRAKEN_OHLC_URL,
            params={
                "pair": pair,
                "interval": interval,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                    "SideShiftAI/4.0"
            },
        )

        if response.status_code != 200:

            return []

        payload = response.json()

        if payload.get(
            "error"
        ):

            return []

        result = payload.get(
            "result",
            {},
        )

        rows = None

        for key, value in (
            result.items()
        ):

            if key != "last":

                rows = value
                break

        if not rows:

            return []

        return normalize_kraken(
            rows
        )

    except Exception as exc:

        print(
            "KRAKEN ERROR:",
            repr(exc),
        )

        return []


def get_binance_candles(
    symbol,
    interval,
    limit=200,
):

    try:

        response = requests.get(
            BINANCE_KLINES_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent":
                    "SideShiftAI/4.0"
            },
        )

        if response.status_code != 200:

            return []

        data = response.json()

        if not isinstance(
            data,
            list,
        ):

            return []

        return normalize_binance(
            data
        )

    except Exception as exc:

        print(
            "BINANCE ERROR:",
            repr(exc),
        )

        return []


def get_market_candles(
    coin,
    timeframe,
):

    config = COINS[coin]

    tf = TIMEFRAMES[
        timeframe
    ]

    providers = []

    candles = (
        get_coinbase_candles(
            config["coinbase"],
            tf["coinbase"],
        )
    )

    if len(candles) >= 60:

        providers.append(
            (
                "Coinbase",
                candles,
            )
        )

    candles = (
        get_kraken_candles(
            config["kraken"],
            tf["kraken"],
        )
    )

    if len(candles) >= 60:

        providers.append(
            (
                "Kraken",
                candles,
            )
        )

    candles = (
        get_binance_candles(
            config["binance"],
            tf["binance"],
        )
    )

    if len(candles) >= 60:

        providers.append(
            (
                "Binance",
                candles,
            )
        )

    if not providers:

        return [], None

    # Select longest clean dataset.
    providers.sort(
        key=lambda x:
        len(x[1]),
        reverse=True,
    )

    selected = providers[0]

    return (
        selected[1],
        ", ".join(
            p[0]
            for p in providers
        ),
    )


# ============================================================
# COINMARKETCAP FALLBACK
# ============================================================

def get_cmc_price(
    symbol
):

    if not CMC_API_KEY:

        return None

    try:

        response = requests.get(
            CMC_PRICE_URL,
            params={
                "symbol": symbol,
                "convert": "USD",
            },
            headers={
                "X-CMC_PRO_API_KEY":
                    CMC_API_KEY,
                "User-Agent":
                    "SideShiftAI/4.0",
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            return None

        payload = response.json()

        coin = (
            payload
            .get("data", {})
            .get(symbol)
        )

        if not coin:

            return None

        return (
            coin[0]
            .get("quote", {})
            .get("USD", {})
            .get("price")
        )

    except Exception:

        return None


# ============================================================
# MARKET STRUCTURE
# ============================================================

def pivot_points(
    candles,
    left=3,
    right=3,
):

    highs = []
    lows = []

    if len(candles) < 20:

        return highs, lows

    for i in range(
        left,
        len(candles)
        - right,
    ):

        nearby = candles[
            i - left:
            i + right + 1
        ]

        high = candles[
            i
        ]["high"]

        low = candles[
            i
        ]["low"]

        if high == max(
            c["high"]
            for c in nearby
        ):

            highs.append(
                (i, high)
            )

        if low == min(
            c["low"]
            for c in nearby
        ):

            lows.append(
                (i, low)
            )

    return highs, lows


def calculate_structure(
    candles
):

    recent = candles[-100:]

    highs, lows = pivot_points(
        recent
    )

    if (
        len(highs) < 2
        or len(lows) < 2
    ):

        return {
            "label": "Unknown",
            "score": 0,
            "support": None,
            "resistance": None,
        }

    previous_high = highs[-2][1]
    latest_high = highs[-1][1]

    previous_low = lows[-2][1]
    latest_low = lows[-1][1]

    hh = (
        latest_high
        > previous_high
    )

    hl = (
        latest_low
        > previous_low
    )

    lh = (
        latest_high
        < previous_high
    )

    ll = (
        latest_low
        < previous_low
    )

    if hh and hl:

        label = "Bullish Structure"
        score = 3

    elif lh and ll:

        label = "Bearish Structure"
        score = -3

    elif hh or hl:

        label = "Bullish Lean"
        score = 1

    elif lh or ll:

        label = "Bearish Lean"
        score = -1

    else:

        label = "Mixed / Sideways"
        score = 0

    return {
        "label": label,
        "score": score,
        "support": latest_low,
        "resistance": latest_high,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    candles
):

    if len(candles) < 60:

        return {
            "valid": False,
            "direction":
                "Data Unavailable",
            "score": 0,
        }

    closes = [
        c["close"]
        for c in candles
    ]

    price = closes[-1]

    ema20_series = ema(
        closes,
        20,
    )

    ema50_series = ema(
        closes,
        50,
    )

    ema200_series = ema(
        closes,
        200,
    )

    ema20 = (
        ema20_series[-1]
    )

    ema50 = (
        ema50_series[-1]
    )

    ema200 = (
        ema200_series[-1]
        if ema200_series[-1]
        is not None
        else None
    )

    score = 0

    evidence = []

    # --------------------------------------------------------
    # EMA
    # --------------------------------------------------------

    if ema20 is not None:

        if price > ema20:

            score += 1
            evidence.append(
                "price_above_ema20"
            )

        else:

            score -= 1
            evidence.append(
                "price_below_ema20"
            )

    if (
        ema20 is not None
        and ema50 is not None
    ):

        if ema20 > ema50:

            score += 2
            evidence.append(
                "ema20_above_ema50"
            )

        else:

            score -= 2
            evidence.append(
                "ema20_below_ema50"
            )

    long_ema = (
        ema200
        if ema200 is not None
        else ema50
    )

    if long_ema is not None:

        if price > long_ema:

            score += 2
            evidence.append(
                "price_above_long_ema"
            )

        else:

            score -= 2
            evidence.append(
                "price_below_long_ema"
            )

    # --------------------------------------------------------
    # EMA SLOPE
    # --------------------------------------------------------

    if (
        len(ema20_series) >= 8
        and ema20_series[-8]
        is not None
    ):

        if (
            ema20_series[-1]
            > ema20_series[-8]
        ):

            score += 1
            evidence.append(
                "ema20_rising"
            )

        elif (
            ema20_series[-1]
            < ema20_series[-8]
        ):

            score -= 1
            evidence.append(
                "ema20_falling"
            )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi = calculate_rsi(
        closes
    )

    if rsi is not None:

        if 55 <= rsi <= 70:

            score += 2
            evidence.append(
                "rsi_bullish"
            )

        elif 30 <= rsi <= 45:

            score -= 2
            evidence.append(
                "rsi_bearish"
            )

        elif rsi > 75:

            score -= 1
            evidence.append(
                "rsi_extreme_high"
            )

        elif rsi < 25:

            score += 1
            evidence.append(
                "rsi_extreme_low"
            )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    macd = calculate_macd(
        closes
    )

    if macd:

        if macd[
            "histogram"
        ] > 0:

            score += 2
            evidence.append(
                "macd_positive"
            )

        elif macd[
            "histogram"
        ] < 0:

            score -= 2
            evidence.append(
                "macd_negative"
            )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if len(closes) >= 11:

        previous = closes[-11]

        if previous:

            momentum = (
                (
                    price
                    - previous
                )
                / previous
            ) * 100

        else:

            momentum = 0

    else:

        momentum = 0

    if momentum >= 0.5:

        score += 2
        evidence.append(
            "momentum_up"
        )

    elif momentum >= 0.15:

        score += 1
        evidence.append(
            "momentum_up_weak"
        )

    elif momentum <= -0.5:

        score -= 2
        evidence.append(
            "momentum_down"
        )

    elif momentum <= -0.15:

        score -= 1
        evidence.append(
            "momentum_down_weak"
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    volumes = [
        c["volume"]
        for c in candles[-21:-1]
    ]

    average_volume = (
        sum(volumes)
        / len(volumes)
        if volumes
        else 0
    )

    volume_ratio = (
        candles[-1]["volume"]
        / average_volume
        if average_volume
        else None
    )

    if volume_ratio is not None:

        if volume_ratio >= 1.25:

            move = (
                candles[-1]["close"]
                - candles[-1]["open"]
            )

            if move > 0:

                score += 1
                evidence.append(
                    "volume_confirms_up"
                )

            elif move < 0:

                score -= 1
                evidence.append(
                    "volume_confirms_down"
                )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr = calculate_atr(
        candles
    )

    atr_percent = (
        (
            atr
            / price
        ) * 100
        if atr and price
        else None
    )

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    structure = calculate_structure(
        candles
    )

    score += structure[
        "score"
    ]

    evidence.append(
        structure["label"]
    )

    # --------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------

    if score >= 8:

        direction = "Strong Bullish"

    elif score >= 4:

        direction = "Bullish"

    elif score >= 2:

        direction = "Bullish Lean"

    elif score <= -8:

        direction = "Strong Bearish"

    elif score <= -4:

        direction = "Bearish"

    elif score <= -2:

        direction = "Bearish Lean"

    else:

        direction = "Consolidation"

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if volume_ratio is None:

        volume_label = "Unknown"

    elif volume_ratio >= 1.75:

        volume_label = "Very High"

    elif volume_ratio >= 1.25:

        volume_label = "Above Average"

    elif volume_ratio >= 0.80:

        volume_label = "Normal"

    else:

        volume_label = "Below Average"

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    if atr_percent is None:

        volatility = "Unknown"

    elif atr_percent >= 4:

        volatility = "Very High"

    elif atr_percent >= 2:

        volatility = "High"

    elif atr_percent >= 0.75:

        volatility = "Moderate"

    else:

        volatility = "Low"

    return {
        "valid": True,
        "direction": direction,
        "score": score,
        "price": price,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi,
        "macd": macd,
        "momentum_pct": momentum,
        "volume_ratio": volume_ratio,
        "volume": volume_label,
        "atr": atr,
        "atr_percent": atr_percent,
        "volatility": volatility,
        "structure": structure[
            "label"
        ],
        "support": structure[
            "support"
        ],
        "resistance": structure[
            "resistance"
        ],
        "evidence": evidence,
    }


# ============================================================
# COINGLASS
# ============================================================

def coinglass_request(
    url,
    params=None,
):

    if not COINGLASS_API_KEY:

        return None

    try:

        response = requests.get(
            url,
            params=params or {},
            headers={
                "CG-API-KEY":
                    COINGLASS_API_KEY,
                "Accept":
                    "application/json",
                "User-Agent":
                    "SideShiftAI/4.0",
            },
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:

            print(
                "COINGLASS HTTP:",
                response.status_code,
                response.text[:300],
            )

            return None

        payload = response.json()

        if str(
            payload.get("code")
        ) not in (
            "0",
            "None",
        ):

            print(
                "COINGLASS API:",
                payload,
            )

            return None

        return payload.get(
            "data"
        )

    except Exception as exc:

        print(
            "COINGLASS ERROR:",
            repr(exc),
        )

        return None


def get_coinglass_derivatives(
    coin
):

    if not COINGLASS_API_KEY:

        return {
            "available": False,
            "reason":
                "COINGLASS_API_KEY not configured",
        }

    cached = COINGLASS_CACHE.get(
        coin
    )

    if cached:

        if (
            time.time()
            - cached["time"]
            < COINGLASS_CACHE_SECONDS
        ):

            return cached["data"]

    result = {
        "available": False,
        "open_interest": None,
        "funding": None,
        "liquidations": None,
        "long_short": None,
    }

    # --------------------------------------------------------
    # OPEN INTEREST
    # --------------------------------------------------------

    oi_data = coinglass_request(
        COINGLASS_OI_URL,
        {
            "symbol": coin,
        },
    )

    if isinstance(
        oi_data,
        list,
    ):

        for item in oi_data:

            if str(
                item.get(
                    "exchange",
                    "",
                )
            ).lower() == "all":

                result[
                    "open_interest"
                ] = item

                break

    # --------------------------------------------------------
    # FUNDING
    # --------------------------------------------------------

    funding_data = (
        coinglass_request(
            COINGLASS_FUNDING_URL
        )
    )

    if isinstance(
        funding_data,
        list,
    ):

        for item in funding_data:

            if (
                str(
                    item.get(
                        "symbol",
                        "",
                    )
                ).upper()
                != coin.upper()
            ):

                continue

            rates = []

            for key in (
                "stablecoin_margin_list",
                "token_margin_list",
            ):

                for exchange in (
                    item.get(key)
                    or []
                ):

                    rate = safe_float(
                        exchange.get(
                            "funding_rate"
                        )
                    )

                    if rate is not None:

                        rates.append(
                            rate
                        )

            if rates:

                result[
                    "funding"
                ] = {
                    "average":
                        sum(rates)
                        / len(rates),
                    "count":
                        len(rates),
                }

            break

    # --------------------------------------------------------
    # LIQUIDATIONS
    # --------------------------------------------------------

    liquidation_data = (
        coinglass_request(
            COINGLASS_LIQUIDATION_URL,
            {
                "exchange_list":
                    "Binance,OKX,Bybit",
                "symbol":
                    coin,
                "interval":
                    "4h",
                "limit":
                    6,
            },
        )
    )

    if isinstance(
        liquidation_data,
        list,
    ):

        long_total = 0.0
        short_total = 0.0

        for item in (
            liquidation_data
        ):

            long_total += (
                safe_float(
                    item.get(
                        "aggregated_long_liquidation_usd",
                        0,
                    ),
                    0,
                )
                or 0
            )

            short_total += (
                safe_float(
                    item.get(
                        "aggregated_short_liquidation_usd",
                        0,
                    ),
                    0,
                )
                or 0
            )

        result[
            "liquidations"
        ] = {
            "long":
                long_total,
            "short":
                short_total,
            "total":
                long_total
                + short_total,
        }

    # --------------------------------------------------------
    # LONG / SHORT
    # --------------------------------------------------------

    long_short_data = (
        coinglass_request(
            COINGLASS_LONG_SHORT_URL,
            {
                "exchange":
                    "Binance",
                "symbol":
                    f"{coin}USDT",
                "interval":
                    "4h",
                "limit":
                    3,
            },
        )
    )

    if isinstance(
        long_short_data,
        list,
    ) and long_short_data:

        latest = (
            long_short_data[-1]
        )

        result[
            "long_short"
        ] = {
            "long":
                safe_float(
                    latest.get(
                        "global_account_long_percent"
                    )
                ),
            "short":
                safe_float(
                    latest.get(
                        "global_account_short_percent"
                    )
                ),
            "ratio":
                safe_float(
                    latest.get(
                        "global_account_long_short_ratio"
                    )
                ),
        }

    result["available"] = any(
        value is not None
        for value in (
            result[
                "open_interest"
            ],
            result[
                "funding"
            ],
            result[
                "liquidations"
            ],
            result[
                "long_short"
            ],
        )
    )

    COINGLASS_CACHE[
        coin
    ] = {
        "time": time.time(),
        "data": result,
    }

    return result


def analyze_derivatives(
    derivatives,
    price_momentum,
):

    result = {
        "score": 0,
        "bias": "Neutral",
        "warnings": [],
        "evidence": [],
    }

    if not derivatives.get(
        "available"
    ):

        result[
            "warnings"
        ].append(
            "Derivatives data unavailable"
        )

        return result

    # --------------------------------------------------------
    # OPEN INTEREST
    # --------------------------------------------------------

    oi = derivatives.get(
        "open_interest"
    )

    if oi:

        oi_change = safe_float(
            oi.get(
                "open_interest_change_percent_1h"
            )
        )

        if oi_change is not None:

            if (
                oi_change > 1
                and price_momentum > 0
            ):

                result["score"] += 2

                result[
                    "evidence"
                ].append(
                    "price_up_oi_up"
                )

            elif (
                oi_change > 1
                and price_momentum < 0
            ):

                result["score"] -= 2

                result[
                    "evidence"
                ].append(
                    "price_down_oi_up"
                )

            elif (
                oi_change < -1
                and price_momentum > 0
            ):

                result["score"] += 1

                result[
                    "warnings"
                ].append(
                    "price_up_oi_falling"
                )

            elif (
                oi_change < -1
                and price_momentum < 0
            ):

                result["score"] -= 1

                result[
                    "warnings"
                ].append(
                    "price_down_oi_falling"
                )

    # --------------------------------------------------------
    # FUNDING
    # --------------------------------------------------------

    funding = derivatives.get(
        "funding"
    )

    if funding:

        rate = funding.get(
            "average"
        )

        if rate is not None:

            funding_pct = (
                rate * 100
            )

            if funding_pct >= 0.05:

                result[
                    "warnings"
                ].append(
                    "Elevated positive funding"
                )

                result[
                    "score"
                ] -= 1

            elif funding_pct <= -0.05:

                result[
                    "warnings"
                ].append(
                    "Elevated negative funding"
                )

                result[
                    "score"
                ] += 1

    # --------------------------------------------------------
    # LONG / SHORT
    # --------------------------------------------------------

    long_short = derivatives.get(
        "long_short"
    )

    if long_short:

        ratio = long_short.get(
            "ratio"
        )

        if ratio is not None:

            if ratio >= 1.75:

                result[
                    "warnings"
                ].append(
                    "Crowded long positioning"
                )

                result[
                    "score"
                ] -= 1

            elif ratio <= 0.57:

                result[
                    "warnings"
                ].append(
                    "Crowded short positioning"
                )

                result[
                    "score"
                ] += 1

    # --------------------------------------------------------
    # LIQUIDATIONS
    # --------------------------------------------------------

    liquidations = (
        derivatives.get(
            "liquidations"
        )
    )

    if liquidations:

        long_liq = liquidations.get(
            "long",
            0,
        )

        short_liq = liquidations.get(
            "short",
            0,
        )

        total = (
            long_liq
            + short_liq
        )

        if total > 0:

            long_ratio = (
                long_liq
                / total
            )

            if long_ratio >= 0.70:

                result[
                    "evidence"
                ].append(
                    "Heavy long liquidations"
                )

            elif long_ratio <= 0.30:

                result[
                    "evidence"
                ].append(
                    "Heavy short liquidations"
                )

    if result["score"] >= 2:

        result[
            "bias"
        ] = "Bullish"

    elif result["score"] <= -2:

        result[
            "bias"
        ] = "Bearish"

    return result


# ============================================================
# TRADINGVIEW
# ============================================================

def tv_key(
    symbol,
    timeframe,
):

    return (
        f"{symbol.upper()}:"
        f"{timeframe}"
    )


def get_tv_signal(
    symbol,
    timeframe,
):

    item = (
        TRADINGVIEW_CACHE.get(
            tv_key(
                symbol,
                timeframe,
            )
        )
    )

    if not item:

        return None

    if (
        time.time()
        - item["received_at"]
        > 7200
    ):

        return None

    return item["data"]


def apply_tradingview(
    result,
    tv,
):

    if not tv:

        return result

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

        result["score"] += 2

    elif signal in (
        "SELL",
        "SHORT",
        "BEARISH",
    ):

        result["score"] -= 2

    result[
        "tradingview"
    ] = {
        "signal":
            signal or "N/A",
        "received":
            True,
    }

    return result


# ============================================================
# BTC REGIME
# ============================================================

def determine_btc_regime(
    btc_timeframes
):

    valid = [
        x
        for x in btc_timeframes.values()
        if x.get("valid")
    ]

    if not valid:

        return "Unknown"

    bullish = sum(
        1
        for x in valid
        if "Bullish"
        in x["direction"]
    )

    bearish = sum(
        1
        for x in valid
        if "Bearish"
        in x["direction"]
    )

    if (
        bullish >= 4
        and bullish > bearish
    ):

        return "Bullish"

    if (
        bearish >= 4
        and bearish > bullish
    ):

        return "Bearish"

    return "Neutral"


# ============================================================
# TECHNICAL SCAN
# ============================================================

def scan_technical(
    coin
):

    timeframe_results = {}

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
        ] = (
            provider
            or "Unavailable"
        )

        result = analyze_timeframe(
            candles
        )

        if result.get(
            "valid"
        ):

            price = result[
                "price"
            ]

            result = (
                apply_tradingview(
                    result,
                    get_tv_signal(
                        coin,
                        timeframe,
                    ),
                )
            )

        timeframe_results[
            timeframe
        ] = result

    return (
        timeframe_results,
        providers,
        price,
    )


# ============================================================
# COMPLETE COIN SCAN
# ============================================================

def scan_coin(
    coin,
    btc_regime=None,
    include_derivatives=True,
):

    if coin not in COINS:

        return None

    (
        timeframe_results,
        providers,
        price,
    ) = scan_technical(
        coin
    )

    valid_results = [
        x
        for x in
        timeframe_results.values()
        if x.get("valid")
    ]

    if price is None:

        price = get_cmc_price(
            COINS[
                coin
            ]["cmc"]
        )

    if not valid_results:

        return {
            "coin": coin,
            "price": price,
            "timeframes":
                timeframe_results,
            "providers":
                providers,
            "valid_count": 0,
            "total_count":
                len(TIMEFRAMES),
            "overall": {
                "label":
                    "Data Unavailable",
                "score": 0,
                "confidence": 0,
            },
            "data_quality":
                "Insufficient",
            "signal": None,
        }

    # --------------------------------------------------------
    # WEIGHTED TECHNICAL SCORE
    # --------------------------------------------------------

    weighted_score = 0
    total_weight = 0

    for timeframe, result in (
        timeframe_results.items()
    ):

        if not result.get(
            "valid"
        ):

            continue

        weight = TIMEFRAMES[
            timeframe
        ]["weight"]

        weighted_score += (
            result["score"]
            * weight
        )

        total_weight += weight

    average_score = (
        weighted_score
        / total_weight
        if total_weight
        else 0
    )

    # --------------------------------------------------------
    # AGREEMENT
    # --------------------------------------------------------

    bullish = sum(
        1
        for x in valid_results
        if "Bullish"
        in x["direction"]
    )

    bearish = sum(
        1
        for x in valid_results
        if "Bearish"
        in x["direction"]
    )

    total = len(
        valid_results
    )

    bullish_ratio = (
        bullish / total
        if total
        else 0
    )

    bearish_ratio = (
        bearish / total
        if total
        else 0
    )

    agreement = max(
        bullish_ratio,
        bearish_ratio,
    )

    # --------------------------------------------------------
    # DERIVATIVES
    # --------------------------------------------------------

    derivatives = {
        "available": False
    }

    derivatives_analysis = {
        "score": 0,
        "bias": "Neutral",
        "warnings": [],
        "evidence": [],
    }

    if include_derivatives:

        derivatives = (
            get_coinglass_derivatives(
                coin
            )
        )

        one_hour = (
            timeframe_results.get(
                "1h",
                {},
            )
        )

        momentum = (
            one_hour.get(
                "momentum_pct",
                0,
            )
            if one_hour.get(
                "valid"
            )
            else 0
        )

        derivatives_analysis = (
            analyze_derivatives(
                derivatives,
                momentum,
            )
        )

        average_score += (
            derivatives_analysis[
                "score"
            ] * 1.25
        )

    # --------------------------------------------------------
    # BTC FILTER
    # --------------------------------------------------------

    btc_warning = None

    if coin != "BTC":

        if (
            btc_regime == "Bearish"
            and bullish_ratio >= 0.60
        ):

            btc_warning = (
                "Altcoin bullish setup "
                "against bearish BTC regime"
            )

            average_score -= 2

        elif (
            btc_regime == "Bullish"
            and bearish_ratio >= 0.60
        ):

            btc_warning = (
                "Altcoin bearish setup "
                "against bullish BTC regime"
            )

            average_score += 2

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    structures = [
        x["structure"]
        for x in valid_results
    ]

    bullish_structure = sum(
        1
        for x in structures
        if "Bullish" in x
    )

    bearish_structure = sum(
        1
        for x in structures
        if "Bearish" in x
    )

    if (
        bullish_structure
        > bearish_structure
    ):

        structure = "Bullish"

    elif (
        bearish_structure
        > bullish_structure
    ):

        structure = "Bearish"

    else:

        structure = (
            "Mixed / Sideways"
        )

    # --------------------------------------------------------
    # VOLATILITY
    # --------------------------------------------------------

    volatility_values = [
        x["volatility"]
        for x in valid_results
    ]

    if "Very High" in (
        volatility_values
    ):

        volatility = "Very High"

    elif "High" in (
        volatility_values
    ):

        volatility = "High"

    elif "Moderate" in (
        volatility_values
    ):

        volatility = "Moderate"

    elif "Low" in (
        volatility_values
    ):

        volatility = "Low"

    else:

        volatility = "Unknown"

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    rsi_values = [
        x["rsi"]
        for x in valid_results
        if x.get("rsi")
        is not None
    ]

    average_rsi = (
        sum(rsi_values)
        / len(rsi_values)
        if rsi_values
        else None
    )

    # --------------------------------------------------------
    # OVERALL LABEL
    # --------------------------------------------------------

    if (
        bullish_ratio >= 0.75
        and average_score >= 4
    ):

        overall_label = (
            "Bullish"
        )

    elif (
        bearish_ratio >= 0.75
        and average_score <= -4
    ):

        overall_label = (
            "Bearish"
        )

    elif (
        bullish_ratio >= 0.60
        and average_score >= 2.5
    ):

        overall_label = (
            "Bullish Lean"
        )

    elif (
        bearish_ratio >= 0.60
        and average_score <= -2.5
    ):

        overall_label = (
            "Bearish Lean"
        )

    elif max(
        bullish_ratio,
        bearish_ratio,
    ) < 0.50:

        overall_label = (
            "Indecisive"
        )

    else:

        overall_label = (
            "Consolidation"
        )

    # --------------------------------------------------------
    # CONFLICT DETECTION
    # --------------------------------------------------------

    conflicts = []

    derivatives_bias = (
        derivatives_analysis[
            "bias"
        ]
    )

    if (
        overall_label == "Bullish"
        and derivatives_bias
        == "Bearish"
    ):

        conflicts.append(
            "Technical trend conflicts "
            "with derivatives"
        )

    if (
        overall_label == "Bearish"
        and derivatives_bias
        == "Bullish"
    ):

        conflicts.append(
            "Technical trend conflicts "
            "with derivatives"
        )

    if btc_warning:

        conflicts.append(
            btc_warning
        )

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    confidence = clamp(
        (
            abs(
                average_score
            )
            / 14
        )
        * 100,
        0,
        100,
    )

    confidence *= (
        0.65
        + (
            0.35
            * agreement
        )
    )

    if conflicts:

        confidence -= (
            len(conflicts)
            * 10
        )

    confidence = clamp(
        confidence,
        0,
        100,
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signal = build_signal(
        coin=coin,
        label=overall_label,
        score=average_score,
        confidence=confidence,
        agreement=agreement,
        valid_count=len(
            valid_results
        ),
        total_count=len(
            TIMEFRAMES
        ),
        structure=structure,
        volatility=volatility,
        conflicts=conflicts,
        derivatives_bias=(
            derivatives_bias
        ),
        btc_regime=btc_regime,
        timeframe_results=(
            timeframe_results
        ),
    )

    return {
        "coin": coin,
        "price": price,
        "timeframes":
            timeframe_results,
        "providers":
            providers,
        "valid_count":
            len(valid_results),
        "total_count":
            len(TIMEFRAMES),
        "overall": {
            "label":
                overall_label,
            "score":
                average_score,
            "confidence":
                confidence,
        },
        "data_quality": (
            "Excellent"
            if len(valid_results) == 5
            else "Good"
            if len(valid_results) >= 4
            else "Partial"
            if len(valid_results) >= 3
            else "Insufficient"
        ),
        "average_rsi":
            average_rsi,
        "volatility":
            volatility,
        "structure":
            structure,
        "derivatives":
            derivatives,
        "derivatives_analysis":
            derivatives_analysis,
        "btc_regime":
            btc_regime,
        "conflicts":
            conflicts,
        "signal":
            signal,
    }


# ============================================================
# SIGNAL BUILDER
# ============================================================

def build_signal(
    coin,
    label,
    score,
    confidence,
    agreement,
    valid_count,
    total_count,
    structure,
    volatility,
    conflicts,
    derivatives_bias,
    btc_regime,
    timeframe_results,
):

    # Need at least 4/5 valid timeframes.
    if valid_count < 4:

        return None

    # Need strong timeframe agreement.
    if agreement < 0.75:

        return None

    # Need strong analysis.
    if confidence < 65:

        return None

    # Need meaningful score.
    if abs(score) < MIN_SIGNAL_SCORE:

        return None

    # Never issue a signal with unresolved
    # major directional conflict.
    if conflicts:

        return None

    if volatility == "Very High":

        return None

    if label not in (
        "Bullish",
        "Bearish",
    ):

        return None

    if structure not in (
        "Bullish",
        "Bearish",
    ):

        return None

    if label == "Bullish":

        direction = (
            "CALL / LONG"
        )

    else:

        direction = (
            "PUT / SHORT"
        )

    # --------------------------------------------------------
    # ATR-BASED RISK LEVELS
    #
    # These are analytical reference levels,
    # not guarantees.
    # --------------------------------------------------------

    anchor = (
        timeframe_results.get(
            "1h"
        )
        or timeframe_results.get(
            "15m"
        )
    )

    if not anchor:

        return None

    price = anchor.get(
        "price"
    )

    atr = anchor.get(
        "atr"
    )

    if (
        price is None
        or atr is None
        or atr <= 0
    ):

        return None

    if direction == "CALL / LONG":

        invalidation = (
            price
            - (
                atr
                * 1.5
            )
        )

        target_1 = (
            price
            + (
                atr
                * 1.5
            )
        )

        target_2 = (
            price
            + (
                atr
                * 3
            )
        )

    else:

        invalidation = (
            price
            + (
                atr
                * 1.5
            )
        )

        target_1 = (
            price
            - (
                atr
                * 1.5
            )
        )

        target_2 = (
            price
            - (
                atr
                * 3
            )
        )

    return {
        "coin":
            coin,

        "direction":
            direction,

        "score":
            round(
                score,
                2,
            ),

        "analysis_strength":
            round(
                confidence,
                1,
            ),

        "agreement":
            round(
                agreement * 100,
                1,
            ),

        "quality":
            "HIGH-CONFLUENCE",

        "entry":
            price,

        "invalidation":
            invalidation,

        "target_1":
            target_1,

        "target_2":
            target_2,

        "derivatives_bias":
            derivatives_bias,

        "btc_regime":
            btc_regime,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }


# ============================================================
# MARKET SCAN
# ============================================================

def scan_market():

    print(
        "===================================="
    )

    print(
        "SIDESHIFT: FULL MARKET SCAN"
    )

    print(
        "===================================="
    )

    # --------------------------------------------------------
    # BTC FIRST
    # --------------------------------------------------------

    btc_technical = scan_technical(
        "BTC"
    )

    btc_regime = (
        determine_btc_regime(
            btc_technical[0]
        )
    )

    print(
        "BTC REGIME:",
        btc_regime,
    )

    results = []

    for coin in COINS:

        try:

            analysis = scan_coin(
                coin,
                btc_regime=btc_regime,
            )

            if analysis:

                results.append(
                    analysis
                )

        except Exception as exc:

            print(
                "MARKET SCAN ERROR:",
                coin,
                repr(exc),
            )

    qualified = [
        x
        for x in results
        if x.get("signal")
    ]

    qualified.sort(
        key=lambda x:
        x["signal"][
            "analysis_strength"
        ],
        reverse=True,
    )

    print(
        "QUALIFIED SIGNALS:",
        len(qualified),
    )

    return {
        "btc_regime":
            btc_regime,
        "analyses":
            results,
        "signals":
            qualified,
    }


# ============================================================
# SIGNAL STATE
# ============================================================

def reset_signal_day():

    today = (
        datetime.now(
            timezone.utc
        )
        .date()
        .isoformat()
    )

    with STATE_LOCK:

        if (
            SIGNAL_STATE[
                "date"
            ]
            != today
        ):

            SIGNAL_STATE[
                "date"
            ] = today

            SIGNAL_STATE[
                "free_sent_today"
            ] = 0

            SIGNAL_STATE[
                "vip_sent_today"
            ] = 0

            SIGNAL_STATE[
                "last_free_signal"
            ] = {}

            SIGNAL_STATE[
                "last_vip_signal"
            ] = {}


def audience_can_send(
    audience
):

    reset_signal_day()

    with STATE_LOCK:

        if audience == "free":

            return (
                SIGNAL_STATE[
                    "free_sent_today"
                ]
                < MAX_FREE_SIGNALS_PER_DAY
            )

        return (
            SIGNAL_STATE[
                "vip_sent_today"
            ]
            < MAX_VIP_SIGNALS_PER_DAY
        )


def audience_cooldown(
    coin,
    audience
):

    reset_signal_day()

    with STATE_LOCK:

        store = (
            SIGNAL_STATE[
                "last_free_signal"
            ]
            if audience == "free"
            else
            SIGNAL_STATE[
                "last_vip_signal"
            ]
        )

        last = store.get(
            coin
        )

        if not last:

            return False

        return (
            time.time()
            - last
            <
            SIGNAL_COOLDOWN_MINUTES
            * 60
        )


def mark_signal_sent(
    coin,
    audience
):

    reset_signal_day()

    with STATE_LOCK:

        if audience == "free":

            SIGNAL_STATE[
                "free_sent_today"
            ] += 1

            SIGNAL_STATE[
                "last_free_signal"
            ][coin] = time.time()

        else:

            SIGNAL_STATE[
                "vip_sent_today"
            ] += 1

            SIGNAL_STATE[
                "last_vip_signal"
            ][coin] = time.time()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def format_price(
    price
):

    if price is None:

        return "Unavailable"

    if price >= 1000:

        return (
            f"${price:,.2f}"
        )

    if price >= 1:

        return (
            f"${price:,.4f}"
        )

    if price >= 0.01:

        return (
            f"${price:,.6f}"
        )

    return (
        f"${price:,.10f}"
    )


def direction_emoji(
    direction
):

    if "Bullish" in direction:

        return "🟢"

    if "Bearish" in direction:

        return "🔴"

    if direction in (
        "Consolidation",
        "Indecisive",
    ):

        return "🟡"

    return "⚪"


def build_interpretation(
    analysis
):

    label = analysis[
        "overall"
    ]["label"]

    if label == "Bullish":

        return (
            "Multiple timeframes are aligned "
            "to the bullish side."
        )

    if label == "Bearish":

        return (
            "Multiple timeframes are aligned "
            "to the bearish side."
        )

    if label == "Bullish Lean":

        return (
            "Bullish evidence exists, but "
            "alignment is not strong enough "
            "for a high-confluence setup."
        )

    if label == "Bearish Lean":

        return (
            "Bearish evidence exists, but "
            "alignment is not strong enough "
            "for a high-confluence setup."
        )

    if label == "Consolidation":

        return (
            "The market lacks strong directional "
            "alignment."
        )

    if label == "Indecisive":

        return (
            "The timeframes are conflicting."
        )

    return (
        "There is not enough reliable data."
    )


# ============================================================
# MANUAL SCAN MESSAGE
# ============================================================

def build_scan_message(
    analysis
):

    coin = analysis[
        "coin"
    ]

    overall = analysis[
        "overall"
    ]

    label = overall[
        "label"
    ]

    message = (
        f"<b>🔎 {coin} MARKET ANALYSIS</b>\n\n"

        f"💰 <b>Price:</b> "
        f"{format_price(analysis['price'])}\n\n"

        f"{direction_emoji(label)} "
        f"<b>Overall:</b> "
        f"{label}\n"

        f"🎯 <b>Analysis Strength:</b> "
        f"{overall['confidence']:.0f}%\n"

        f"📡 <b>Data Quality:</b> "
        f"{analysis['data_quality']} "
        f"({analysis['valid_count']}/"
        f"{analysis['total_count']})\n\n"

        "<b>📊 TIMEFRAMES</b>\n"
    )

    for timeframe in TIMEFRAMES:

        result = (
            analysis[
                "timeframes"
            ][timeframe]
        )

        direction = result.get(
            "direction",
            "Unavailable",
        )

        provider = (
            analysis[
                "providers"
            ].get(
                timeframe,
                "Unavailable",
            )
        )

        message += (
            f"{direction_emoji(direction)} "
            f"<b>{timeframe}</b>: "
            f"{html.escape(direction)} "
            f"— {html.escape(provider)}\n"
        )

    derivatives = (
        analysis.get(
            "derivatives_analysis",
            {},
        )
    )

    derivatives_bias = (
        derivatives.get(
            "bias",
            "Unavailable",
        )
    )

    warnings = derivatives.get(
        "warnings",
        [],
    )

    message += (
        "\n<b>📈 CONDITIONS</b>\n"

        f"📉 <b>RSI:</b> "
        f"{(
            f'{analysis.get(\"average_rsi\"):.1f}'
            if analysis.get(
                'average_rsi'
            ) is not None
            else 'Unavailable'
        )}\n"

        f"🌊 <b>Volatility:</b> "
        f"{analysis['volatility']}\n"

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}\n"

        f"₿ <b>BTC Regime:</b> "
        f"{analysis.get('btc_regime', 'Unknown')}\n"

        f"📊 <b>Derivatives:</b> "
        f"{derivatives_bias}\n"
    )

    if warnings:

        message += (
            "\n<b>⚠️ DERIVATIVES WARNINGS</b>\n"
        )

        for warning in warnings[
            :5
        ]:

            message += (
                f"• "
                f"{html.escape(warning)}\n"
            )

    message += (
        "\n<b>🧠 INTERPRETATION</b>\n"

        f"{build_interpretation(analysis)}\n\n"

        "<i>Analysis strength is not a "
        "probability of profit. "
        "No market outcome is guaranteed.</i>"
    )

    return message


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def build_signal_message(
    analysis,
    audience="free",
):

    signal = analysis.get(
        "signal"
    )

    if not signal:

        return None

    coin = analysis[
        "coin"
    ]

    direction = signal[
        "direction"
    ]

    emoji = (
        "🟢"
        if direction
        == "CALL / LONG"
        else "🔴"
    )

    title = (
        "FREE SIGNAL"
        if audience == "free"
        else "VIP SIGNAL"
    )

    return (
        f"<b>🚨 SIDESHIFT AI — "
        f"{title}</b>\n\n"

        f"{emoji} <b>{coin}</b>\n"

        f"📍 <b>Direction:</b> "
        f"{direction}\n"

        f"💰 <b>Reference Price:</b> "
        f"{format_price(signal['entry'])}\n\n"

        f"🎯 <b>Analysis Strength:</b> "
        f"{signal['analysis_strength']:.0f}%\n"

        f"📊 <b>Timeframe Agreement:</b> "
        f"{signal['agreement']:.0f}%\n"

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}\n"

        f"₿ <b>BTC Regime:</b> "
        f"{signal['btc_regime']}\n"

        f"📡 <b>Derivatives:</b> "
        f"{signal['derivatives_bias']}\n\n"

        "<b>📍 REFERENCE LEVELS</b>\n"

        f"Entry: "
        f"{format_price(signal['entry'])}\n"

        f"Invalidation: "
        f"{format_price(signal['invalidation'])}\n"

        f"Target 1: "
        f"{format_price(signal['target_1'])}\n"

        f"Target 2: "
        f"{format_price(signal['target_2'])}\n\n"

        "<b>⚠️ IMPORTANT</b>\n"

        "These are analytical reference levels, "
        "not guaranteed outcomes. "
        "Use your own risk management.\n\n"

        "<i>SideShift AI — "
        "high-confluence market analysis.</i>"
    )


# ============================================================
# SIGNAL ENGINE
# ============================================================

def run_signal_engine():

    market = scan_market()

    signals = market[
        "signals"
    ]

    if not signals:

        print(
            "NO HIGH-CONFLUENCE SIGNALS."
        )

        return

    # --------------------------------------------------------
    # FREE
    # --------------------------------------------------------

    free_sent = 0

    if FREE_SIGNAL_CHAT_ID:

        for analysis in signals:

            if free_sent >= (
                MAX_FREE_SIGNALS_PER_DAY
            ):

                break

            coin = analysis[
                "coin"
            ]

            if audience_cooldown(
                coin,
                "free",
            ):

                continue

            if not audience_can_send(
                "free"
            ):

                break

            message = (
                build_signal_message(
                    analysis,
                    "free",
                )
            )

            if not message:

                continue

            if send_telegram(
                message,
                FREE_SIGNAL_CHAT_ID,
            ):

                mark_signal_sent(
                    coin,
                    "free",
                )

                free_sent += 1

                print(
                    "FREE SIGNAL SENT:",
                    coin,
                )

    # --------------------------------------------------------
    # VIP
    # --------------------------------------------------------

    vip_sent = 0

    if VIP_SIGNAL_CHAT_ID:

        for analysis in signals:

            if vip_sent >= (
                MAX_VIP_SIGNALS_PER_DAY
            ):

                break

            coin = analysis[
                "coin"
            ]

            if audience_cooldown(
                coin,
                "vip",
            ):

                continue

            if not audience_can_send(
                "vip"
            ):

                break

            message = (
                build_signal_message(
                    analysis,
                    "vip",
                )
            )

            if not message:

                continue

            if send_telegram(
                message,
                VIP_SIGNAL_CHAT_ID,
            ):

                mark_signal_sent(
                    coin,
                    "vip",
                )

                vip_sent += 1

                print(
                    "VIP SIGNAL SENT:",
                    coin,
                )

    print(
        "FREE TODAY:",
        SIGNAL_STATE[
            "free_sent_today"
        ],
        "/",
        MAX_FREE_SIGNALS_PER_DAY,
    )

    print(
        "VIP TODAY:",
        SIGNAL_STATE[
            "vip_sent_today"
        ],
        "/",
        MAX_VIP_SIGNALS_PER_DAY,
    )


def signal_loop():

    print(
        "SideShift signal engine started."
    )

    while True:

        try:

            if (
                FREE_SIGNAL_CHAT_ID
                or VIP_SIGNAL_CHAT_ID
            ):

                run_signal_engine()

            else:

                print(
                    "No signal channels configured."
                )

        except Exception as exc:

            print(
                "SIGNAL LOOP ERROR:",
                repr(exc),
            )

        time.sleep(
            SIGNAL_SCAN_INTERVAL
        )


# ============================================================
# NEWS
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

        for item in (
            feed.entries[:10]
        ):

            title = item.get(
                "title",
                "",
            )

            link = item.get(
                "link",
                "",
            )

            published = item.get(
                "published",
                "",
            )

            if title and link:

                articles.append(
                    (
                        html.unescape(
                            title
                        ),
                        link,
                        published,
                    )
                )

    except Exception as exc:

        print(
            "NEWS ERROR:",
            repr(exc),
        )

    if not articles:

        return (
            "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
            "No current headlines available."
        )

    message = (
        "<b>📰 CRYPTO MARKET NEWS</b>\n\n"
    )

    for number, (
        title,
        link,
        published,
    ) in enumerate(
        articles,
        1,
    ):

        message += (
            f"<b>{number}.</b> "
            f'<a href="{html.escape(link, quote=True)}">'
            f"{html.escape(title)}</a>\n"
        )

        if published:

            message += (
                f"<i>{html.escape(published)}</i>\n"
            )

        message += "\n"

    return message


def news_loop():

    print(
        "SideShift news engine started."
    )

    while True:

        try:

            if NEWS_CHAT_ID:

                send_telegram(
                    get_crypto_news(),
                    NEWS_CHAT_ID,
                )

        except Exception as exc:

            print(
                "NEWS LOOP ERROR:",
                repr(exc),
            )

        time.sleep(
            NEWS_INTERVAL
        )


# ============================================================
# WELCOME / HELP
# ============================================================

def send_welcome(
    chat_id
):

    return send_telegram(
        (
            "<b>🤖 SIDESHIFT AI 4.0</b>\n\n"

            "Multi-factor crypto market "
            "analysis engine.\n\n"

            "<b>Technical Engine</b>\n"
            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market Structure\n\n"

            "<b>Derivatives Engine</b>\n"
            "💠 Open Interest\n"
            "💰 Funding\n"
            "🔥 Liquidations\n"
            "⚖️ Long / Short positioning\n\n"

            "<b>Market Context</b>\n"
            "₿ BTC regime\n"
            "⏱ Multi-timeframe alignment\n"
            "⚠️ Conflict detection\n\n"

            "<b>Signal Limits</b>\n"
            f"🟢 Free: max "
            f"{MAX_FREE_SIGNALS_PER_DAY}/day\n"
            f"👑 VIP: max "
            f"{MAX_VIP_SIGNALS_PER_DAY}/day\n\n"

            "Daily limits are maximums. "
            "SideShift does not manufacture "
            "signals to reach a quota."
        ),
        chat_id,
        main_menu(),
    )


def send_help(
    chat_id
):

    return send_telegram(
        (
            "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"

            "SideShift combines technical "
            "market structure with "
            "multi-timeframe confirmation "
            "and derivatives information.\n\n"

            "The system can examine:\n"
            "• Trend\n"
            "• Momentum\n"
            "• RSI\n"
            "• MACD\n"
            "• Volume\n"
            "• ATR volatility\n"
            "• Market structure\n"
            "• Open interest\n"
            "• Funding\n"
            "• Liquidations\n"
            "• Long/short positioning\n"
            "• BTC market regime\n\n"

            "Conflicting evidence can cause "
            "the engine to reject a setup.\n\n"

            "No signal is guaranteed."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# FREE CHANNEL
# ============================================================

def get_free_channel_url():

    if not FREE_CHANNEL:

        return None

    channel = (
        FREE_CHANNEL.strip()
    )

    if channel.startswith(
        "https://t.me/"
    ):

        return channel

    if channel.startswith(
        "http://t.me/"
    ):

        return (
            "https://"
            + channel[7:]
        )

    if channel.startswith(
        "@"
    ):

        return (
            "https://t.me/"
            + channel[1:]
        )

    return (
        "https://t.me/"
        + channel
    )


def send_free_info(
    chat_id
):

    url = (
        get_free_channel_url()
    )

    if url:

        keyboard = [
            [
                {
                    "text":
                        "🚀 JOIN FREE CHANNEL",
                    "url":
                        url,
                }
            ],
            [
                {
                    "text":
                        "⬅️ Main Menu",
                    "callback_data":
                        "main_menu",
                }
            ],
        ]

        return send_telegram(
            (
                "<b>🟢 SIDESHIFT AI "
                "FREE SIGNALS</b>\n\n"

                f"Maximum "
                f"{MAX_FREE_SIGNALS_PER_DAY} "
                "signals per day.\n\n"

                "The daily number is a ceiling, "
                "not a promise that all signals "
                "will be used.\n\n"

                "Only setups that pass the "
                "SideShift filters are sent."
            ),
            chat_id,
            keyboard,
        )

    return send_telegram(
        (
            "<b>🟢 FREE SIGNALS</b>\n\n"
            "Free channel is currently "
            "being configured."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# VIP
# ============================================================

def send_vip(
    chat_id
):

    return send_telegram(
        (
            "<b>👑 SIDESHIFT AI VIP</b>\n\n"

            f"Maximum "
            f"{MAX_VIP_SIGNALS_PER_DAY} "
            "signals per day.\n\n"

            "VIP receives the broader "
            "high-confluence signal pool.\n\n"

            "The number is a maximum, "
            "not a forced daily quota.\n\n"

            "The engine can send fewer "
            "signals when market conditions "
            "do not meet the required filters."
        ),
        chat_id,
        main_menu(),
    )


# ============================================================
# MANUAL SCAN
# ============================================================

def perform_scan(
    coin,
    chat_id,
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
            f"<b>🔎 SCANNING {coin}</b>\n\n"

            "Collecting market data...\n"
            "Checking exchanges...\n"
            "Analyzing 5m / 15m / 1h / 4h / 1D...\n"
            "Checking technical indicators...\n"
            "Checking market structure...\n"
            "Checking derivatives...\n"
            "Checking BTC regime..."
        ),
        chat_id,
    )

    try:

        # Determine BTC regime first.
        btc_technical = (
            scan_technical(
                "BTC"
            )
        )

        btc_regime = (
            determine_btc_regime(
                btc_technical[0]
            )
        )

        analysis = scan_coin(
            coin,
            btc_regime=btc_regime,
        )

        if not analysis:

            send_telegram(
                "⚠️ Scan failed.",
                chat_id,
                scan_menu(),
            )

            return

        send_telegram(
            build_scan_message(
                analysis
            ),
            chat_id,
            scan_menu(),
        )

    except Exception as exc:

        print(
            "MANUAL SCAN ERROR:",
            repr(exc),
        )

        send_telegram(
            (
                "<b>⚠️ SCAN ERROR</b>\n\n"
                "The scanner encountered "
                "an internal error.\n\n"
                "No signal was assumed."
            ),
            chat_id,
            scan_menu(),
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
                message.get(
                    "text"
                )
                or ""
            ).strip()

            if not chat_id:

                return jsonify({
                    "ok": True
                })

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
                            "/scan BTC"
                        ),
                        chat_id,
                        main_menu(),
                    )

                else:

                    coin = (
                        parts[1]
                        .upper()
                    )

                    perform_scan(
                        coin,
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

        callback = data.get(
            "callback_query"
        )

        if callback:

            answer_callback(
                callback.get("id")
            )

            callback_data = (
                callback.get(
                    "data",
                    "",
                )
            )

            chat_id = (
                callback
                .get("message", {})
                .get("chat", {})
                .get("id")
            )

            if (
                callback_data
                == "scan_menu"
            ):

                send_telegram(
                    (
                        "<b>📊 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency "
                        "to analyze."
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

            if (
                callback_data
                == "main_menu"
            ):

                send_welcome(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if (
                callback_data
                == "news_all"
            ):

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

                return jsonify({
                    "ok": True
                })

            if (
                callback_data
                == "help"
            ):

                send_help(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if (
                callback_data
                == "free_signals"
            ):

                send_free_info(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

            if (
                callback_data
                == "vip"
            ):

                send_vip(
                    chat_id
                )

                return jsonify({
                    "ok": True
                })

        return jsonify({
            "ok": True
        })

    except Exception as exc:

        print(
            "WEBHOOK ERROR:",
            repr(exc),
        )

        return jsonify({
            "ok": False,
            "error": str(exc),
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

        if (
            WEBHOOK_SECRET
            and data.get(
                "secret"
            )
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

        symbol = (
            symbol
            .replace(
                ".P",
                "",
            )
            .replace(
                "/",
                "",
            )
        )

        if symbol.endswith(
            "USDT"
        ):

            symbol = symbol[
                :-4
            ]

        elif symbol.endswith(
            "USD"
        ):

            symbol = symbol[
                :-3
            ]

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
            tv_key(
                symbol,
                timeframe,
            )
        ] = {
            "received_at":
                time.time(),
            "data":
                data,
        }

        return jsonify({
            "status":
                "cached",
            "symbol":
                symbol,
            "timeframe":
                timeframe,
        })

    except Exception as exc:

        print(
            "TRADINGVIEW ERROR:",
            repr(exc),
        )

        return jsonify({
            "error":
                str(exc)
        }), 500


# ============================================================
# HEALTH
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
            "4.0",

        "market_engine":
            "online",

        "signal_engine":
            (
                "enabled"
                if (
                    FREE_SIGNAL_CHAT_ID
                    or VIP_SIGNAL_CHAT_ID
                )
                else
                "not configured"
            ),

        "free_signals_per_day":
            MAX_FREE_SIGNALS_PER_DAY,

        "vip_signals_per_day":
            MAX_VIP_SIGNALS_PER_DAY,

        "coinglass":
            (
                "enabled"
                if COINGLASS_API_KEY
                else
                "not configured"
            ),

        "news_engine":
            (
                "enabled"
                if NEWS_CHAT_ID
                else
                "manual only"
            ),

        "providers": [
            "Coinbase",
            "Kraken",
            "Binance",
        ],

        "coins":
            list(COINS.keys()),

        "timeframes":
            list(TIMEFRAMES.keys()),
    })


@app.route(
    "/health",
    methods=["GET"],
)
def health():

    return jsonify({
        "status":
            "healthy",
        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),
    })


@app.route(
    "/test-market/<coin>",
    methods=["GET"],
)
def test_market(
    coin
):

    coin = coin.upper()

    if coin not in COINS:

        return jsonify({
            "error":
                "Unsupported coin",
            "supported":
                list(COINS.keys()),
        }), 400

    try:

        btc_technical = (
            scan_technical(
                "BTC"
            )
        )

        btc_regime = (
            determine_btc_regime(
                btc_technical[0]
            )
        )

        analysis = scan_coin(
            coin,
            btc_regime=btc_regime,
        )

        return jsonify(
            analysis
        )

    except Exception as exc:

        return jsonify({
            "error":
                str(exc)
        }), 500


# ============================================================
# TELEGRAM WEBHOOK SETUP
# ============================================================

def setup_telegram_webhook():

    if (
        not TELEGRAM_BOT_TOKEN
        or not RAILWAY_PUBLIC_DOMAIN
    ):

        print(
            "Webhook setup skipped: "
            "missing token or domain."
        )

        return False

    webhook_url = (
        f"https://"
        f"{RAILWAY_PUBLIC_DOMAIN}"
        f"/telegram-webhook"
    )

    try:

        response = requests.post(
            f"{TELEGRAM_API}/setWebhook",
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
            "WEBHOOK SETUP:",
            response.status_code,
            response.text,
        )

        return response.ok

    except Exception as exc:

        print(
            "WEBHOOK SETUP ERROR:",
            repr(exc),
        )

        return False


# ============================================================
# BACKGROUND ENGINES
# ============================================================

def start_background_engines():

    global BACKGROUND_STARTED

    if BACKGROUND_STARTED:

        return

    BACKGROUND_STARTED = True

    if (
        FREE_SIGNAL_CHAT_ID
        or VIP_SIGNAL_CHAT_ID
    ):

        signal_thread = (
            threading.Thread(
                target=signal_loop,
                daemon=True,
            )
        )

        signal_thread.start()

    if NEWS_CHAT_ID:

        news_thread = (
            threading.Thread(
                target=news_loop,
                daemon=True,
            )
        )

        news_thread.start()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "SideShift AI 4.0 starting..."
    )

    print(
        "========================================"
    )

    print(
        "Telegram:",
        (
            "FOUND"
            if TELEGRAM_BOT_TOKEN
            else "MISSING"
        ),
    )

    print(
        "Railway domain:",
        (
            RAILWAY_PUBLIC_DOMAIN
            or "MISSING"
        ),
    )

    print(
        "Free channel:",
        (
            FREE_CHANNEL
            or "NOT CONFIGURED"
        ),
    )

    print(
        "Free signal channel:",
        (
            "FOUND"
            if FREE_SIGNAL_CHAT_ID
            else "NOT CONFIGURED"
        ),
    )

    print(
        "VIP signal channel:",
        (
            "FOUND"
            if VIP_SIGNAL_CHAT_ID
            else "NOT CONFIGURED"
        ),
    )

    print(
        "Free daily maximum:",
        MAX_FREE_SIGNALS_PER_DAY,
    )

    print(
        "VIP daily maximum:",
        MAX_VIP_SIGNALS_PER_DAY,
    )

    print(
        "CoinGlass:",
        (
            "FOUND"
            if COINGLASS_API_KEY
            else "NOT CONFIGURED"
        ),
    )

    print(
        "Market providers:",
        "Coinbase -> Kraken -> Binance",
    )

    setup_telegram_webhook()

    start_background_engines()

    app.run(
        host="0.0.0.0",
        port=PORT,
    )