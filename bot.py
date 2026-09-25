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
CANDLE_LIMIT = 300


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
#
# IMPORTANT:
# 4h = 14,400 seconds.
# The previous code incorrectly used 21,600 seconds,
# which is 6 hours.
#
# ============================================================

TIMEFRAMES = {
    "5m": ("5m", 300, 0.8),
    "15m": ("15m", 900, 1.0),
    "1h": ("1h", 3600, 1.2),
    "4h": ("4h", 14400, 1.5),
    "1D": ("1d", 86400, 1.8),
}


# ============================================================
# OPTIONAL TRADINGVIEW CACHE
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

        print(
            "TELEGRAM ERROR:",
            e,
        )

        return False


def answer_callback(callback_id):

    if not TELEGRAM_API or not callback_id:
        return

    try:

        requests.post(
            f"{TELEGRAM_API}/answerCallbackQuery",
            json={
                "callback_query_id":
                    callback_id
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
                "callback_data":
                    f"scan_{coin}",
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
                "text":
                    "🔎 Scan Another Coin",
                "callback_data":
                    "scan_menu",
            }
        ],

        [
            {
                "text": "📰 News",
                "callback_data":
                    "news_all",
            },
            {
                "text": "👑 VIP",
                "callback_data":
                    "vip",
            },
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


# ============================================================
# BASIC INDICATORS
# ============================================================

def sma(values, period):

    if len(values) < period:
        return [None] * len(values)

    result = [None] * len(values)

    running = sum(
        values[:period]
    )

    result[period - 1] = (
        running / period
    )

    for i in range(
        period,
        len(values)
    ):

        running += (
            values[i]
            - values[i - period]
        )

        result[i] = (
            running / period
        )

    return result


def ema(values, period):

    if len(values) < period:
        return [None] * len(values)

    result = [None] * len(values)

    previous = (
        sum(values[:period])
        / period
    )

    result[period - 1] = previous

    multiplier = (
        2 / (period + 1)
    )

    for i in range(
        period,
        len(values)
    ):

        previous = (
            values[i] * multiplier
            + previous * (
                1 - multiplier
            )
        )

        result[i] = previous

    return result


def calculate_rsi(
    closes,
    period=14,
):

    if len(closes) < period + 1:
        return None

    gains = []
    losses = []

    for i in range(
        1,
        len(closes)
    ):

        change = (
            closes[i]
            - closes[i - 1]
        )

        gains.append(
            max(change, 0.0)
        )

        losses.append(
            max(-change, 0.0)
        )

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
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
        100 / (1 + rs)
    )


def calculate_atr(
    candles,
    period=14,
):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(
        1,
        len(candles)
    ):

        candle = candles[i]

        previous_close = (
            candles[i - 1]["close"]
        )

        true_range = max(

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

        true_ranges.append(
            true_range
        )

    atr = (
        sum(
            true_ranges[:period]
        )
        / period
    )

    for value in (
        true_ranges[period:]
    ):

        atr = (
            (
                atr * (period - 1)
                + value
            )
            / period
        )

    return atr


def calculate_macd(closes):

    if len(closes) < 60:
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
            ema12[i] is not None
            and ema26[i] is not None
        ):

            macd_values.append(
                ema12[i]
                - ema26[i]
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

        "value":
            value,

        "signal":
            signal[-1],

        "histogram":
            value
            - signal[-1],
    }


# ============================================================
# MARKET DATA NORMALIZATION
# ============================================================

def normalize_binance(rows):

    candles = []

    for row in rows:

        try:

            candles.append({

                "timestamp":
                    int(row[0]),

                "open":
                    float(row[1]),

                "high":
                    float(row[2]),

                "low":
                    float(row[3]),

                "close":
                    float(row[4]),

                "volume":
                    float(row[5]),
            })

        except Exception:
            pass

    candles.sort(
        key=lambda x:
            x["timestamp"]
    )

    return candles


def normalize_coinbase(rows):

    candles = []

    for row in rows:

        try:

            candles.append({

                "timestamp":
                    int(row[0]) * 1000,

                "open":
                    float(row[3]),

                "high":
                    float(row[2]),

                "low":
                    float(row[1]),

                "close":
                    float(row[4]),

                "volume":
                    float(row[5]),
            })

        except Exception:
            pass

    candles.sort(
        key=lambda x:
            x["timestamp"]
    )

    return candles


# ============================================================
# BINANCE
# ============================================================

def get_binance_candles(
    symbol,
    interval,
):

    try:

        response = requests.get(

            "https://api.binance.com/api/v3/klines",

            params={
                "symbol":
                    symbol,

                "interval":
                    interval,

                "limit":
                    CANDLE_LIMIT,
            },

            timeout=
                REQUEST_TIMEOUT,

            headers={
                "User-Agent":
                    "SideShiftAI/3.0"
            },
        )

        if not response.ok:

            print(
                "BINANCE ERROR:",
                symbol,
                interval,
                response.status_code,
                response.text[:200],
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
# COINBASE FALLBACK
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

            timeout=
                REQUEST_TIMEOUT,

            headers={
                "User-Agent":
                    "SideShiftAI/3.0"
            },
        )

        if not response.ok:

            print(
                "COINBASE ERROR:",
                product,
                response.status_code,
                response.text[:200],
            )

            return []

        return normalize_coinbase(
            response.json()
        )[-CANDLE_LIMIT:]

    except Exception as e:

        print(
            "COINBASE REQUEST ERROR:",
            e,
        )

        return []


# ============================================================
# MARKET DATA
# ============================================================

def get_market_candles(
    coin,
    timeframe,
):

    (
        binance_symbol,
        coinbase_symbol
    ) = COINS[coin]

    (
        binance_interval,
        coinbase_seconds,
        _
    ) = TIMEFRAMES[timeframe]

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
# SWING HIGH / SWING LOW DETECTION
# ============================================================

def find_swings(
    candles,
    left=3,
    right=3,
):

    highs = []
    lows = []

    if len(candles) < (
        left
        + right
        + 1
    ):

        return highs, lows

    for i in range(
        left,
        len(candles) - right
    ):

        high = candles[i]["high"]
        low = candles[i]["low"]

        left_highs = all(
            high
            > candles[j]["high"]
            for j in range(
                i - left,
                i
            )
        )

        right_highs = all(
            high
            >= candles[j]["high"]
            for j in range(
                i + 1,
                i + right + 1
            )
        )

        left_lows = all(
            low
            < candles[j]["low"]
            for j in range(
                i - left,
                i
            )
        )

        right_lows = all(
            low
            <= candles[j]["low"]
            for j in range(
                i + 1,
                i + right + 1
            )
        )

        if (
            left_highs
            and right_highs
        ):

            highs.append(
                (i, high)
            )

        if (
            left_lows
            and right_lows
        ):

            lows.append(
                (i, low)
            )

    return highs, lows


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def nearest_levels(
    candles,
    price,
):

    highs, lows = find_swings(
        candles[-180:],
        3,
        3,
    )

    swing_highs = [
        value
        for _, value
        in highs
    ]

    swing_lows = [
        value
        for _, value
        in lows
    ]

    supports = sorted(
        [
            value
            for value
            in swing_lows
            if value <= price
        ],
        reverse=True,
    )

    resistances = sorted(
        [
            value
            for value
            in swing_highs
            if value >= price
        ]
    )

    support = (
        supports[0]
        if supports
        else None
    )

    resistance = (
        resistances[0]
        if resistances
        else None
    )

    recent = candles[-120:]

    if (
        support is None
        and recent
    ):

        candidate = min(
            c["low"]
            for c in recent
        )

        if candidate < price:
            support = candidate

    if (
        resistance is None
        and recent
    ):

        candidate = max(
            c["high"]
            for c in recent
        )

        if candidate > price:
            resistance = candidate

    return (
        support,
        resistance,
        swing_highs[-5:],
        swing_lows[-5:],
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_structure(
    candles,
):

    highs, lows = find_swings(
        candles[-160:],
        3,
        3,
    )

    if (
        len(highs) < 2
        or len(lows) < 2
    ):

        return {

            "label":
                "Mixed / Developing",

            "score":
                0,

            "swing_high":
                None,

            "swing_low":
                None,
        }

    h1 = highs[-2][1]
    h2 = highs[-1][1]

    l1 = lows[-2][1]
    l2 = lows[-1][1]

    higher_high = h2 > h1
    higher_low = l2 > l1

    lower_high = h2 < h1
    lower_low = l2 < l1

    if (
        higher_high
        and higher_low
    ):

        label = (
            "Higher Highs + "
            "Higher Lows"
        )

        score = 2

    elif (
        lower_high
        and lower_low
    ):

        label = (
            "Lower Highs + "
            "Lower Lows"
        )

        score = -2

    elif (
        higher_high
        or higher_low
    ):

        label = "Bullish Lean"
        score = 1

    elif (
        lower_high
        or lower_low
    ):

        label = "Bearish Lean"
        score = -1

    else:

        label = "Mixed"
        score = 0

    return {

        "label":
            label,

        "score":
            score,

        "swing_high":
            h2,

        "swing_low":
            l2,
    }


# ============================================================
# APPROXIMATE VOLUME PROFILE
# ============================================================
#
# This is calculated from OHLCV candles.
# It is NOT TradingView's proprietary volume-profile engine.
#
# ============================================================

def volume_profile(
    candles,
    bins=36,
    lookback=150,
):

    data = candles[-lookback:]

    if len(data) < 20:
        return None

    low = min(
        c["low"]
        for c in data
    )

    high = max(
        c["high"]
        for c in data
    )

    if high <= low:
        return None

    step = (
        high - low
    ) / bins

    volumes = [
        0.0
        for _ in range(bins)
    ]

    for candle in data:

        typical = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        index = int(
            (
                typical - low
            ) / step
        )

        index = max(
            0,
            min(
                bins - 1,
                index
            )
        )

        volumes[index] += (
            candle["volume"]
        )

    poc_index = max(
        range(bins),
        key=lambda i:
            volumes[i]
    )

    total_volume = sum(
        volumes
    )

    if total_volume <= 0:
        return None

    included = {
        poc_index
    }

    accumulated = (
        volumes[poc_index]
    )

    while (
        accumulated
        / total_volume
        < 0.70
        and len(included) < bins
    ):

        candidates = []

        left = (
            min(included)
            - 1
        )

        right = (
            max(included)
            + 1
        )

        if left >= 0:
            candidates.append(left)

        if right < bins:
            candidates.append(right)

        if not candidates:
            break

        next_index = max(
            candidates,
            key=lambda i:
                volumes[i]
        )

        included.add(
            next_index
        )

        accumulated += (
            volumes[next_index]
        )

    val_index = min(
        included
    )

    vah_index = max(
        included
    )

    def center(index):

        return (
            low
            + (
                index
                + 0.5
            ) * step
        )

    return {

        "poc":
            center(poc_index),

        "val":
            low
            + val_index * step,

        "vah":
            low
            + (
                vah_index + 1
            ) * step,

        "range_low":
            low,

        "range_high":
            high,

        "coverage":
            accumulated
            / total_volume,
    }


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def find_fvgs(
    candles,
    lookback=120,
):

    data = candles[-lookback:]

    bullish = []
    bearish = []

    if len(data) < 3:
        return bullish, bearish

    for i in range(
        2,
        len(data)
    ):

        first = data[i - 2]
        current = data[i]

        # Bullish imbalance
        if (
            current["low"]
            > first["high"]
        ):

            bullish.append({

                "low":
                    first["high"],

                "high":
                    current["low"],

                "index":
                    i,
            })

        # Bearish imbalance
        if (
            current["high"]
            < first["low"]
        ):

            bearish.append({

                "low":
                    current["high"],

                "high":
                    first["low"],

                "index":
                    i,
            })

    return (
        bullish,
        bearish,
    )


def active_fvgs(
    candles,
    price,
):

    bullish, bearish = (
        find_fvgs(candles)
    )

    active_bull = [
        gap
        for gap in bullish
        if gap["high"] >= price
    ]

    active_bear = [
        gap
        for gap in bearish
        if gap["low"] <= price
    ]

    return (
        active_bull,
        active_bear,
    )


# ============================================================
# REJECTION CANDLES
# ============================================================

def candle_rejection(
    candle,
):

    body = abs(
        candle["close"]
        - candle["open"]
    )

    upper = (
        candle["high"]
        - max(
            candle["open"],
            candle["close"],
        )
    )

    lower = (
        min(
            candle["open"],
            candle["close"],
        )
        - candle["low"]
    )

    total = (
        candle["high"]
        - candle["low"]
    )

    if total <= 0:
        return "None"

    if (
        lower
        > max(
            body * 1.8,
            total * 0.45,
        )
    ):

        return "Bullish Rejection"

    if (
        upper
        > max(
            body * 1.8,
            total * 0.45,
        )
    ):

        return "Bearish Rejection"

    return "None"


def rejection_analysis(
    candles,
):

    recent = candles[-12:]

    bullish = sum(
        1
        for candle in recent
        if candle_rejection(
            candle
        )
        == "Bullish Rejection"
    )

    bearish = sum(
        1
        for candle in recent
        if candle_rejection(
            candle
        )
        == "Bearish Rejection"
    )

    if bullish > bearish:

        label = (
            "Bullish rejection "
            "pressure"
        )

    elif bearish > bullish:

        label = (
            "Bearish rejection "
            "pressure"
        )

    else:

        label = (
            "No dominant "
            "rejection"
        )

    return {

        "label":
            label,

        "bullish":
            bullish,

        "bearish":
            bearish,
    }


# ============================================================
# LIQUIDITY / TRAP HEURISTICS
# ============================================================

def liquidity_trap_analysis(
    candles,
    support,
    resistance,
):

    if len(candles) < 20:

        return {

            "label":
                "Insufficient data",

            "score":
                0,
        }

    recent = candles[-12:]

    last = recent[-1]

    avg_volume = (
        sum(
            c["volume"]
            for c
            in candles[-21:-1]
        )
        / max(
            1,
            len(
                candles[-21:-1]
            )
        )
    )

    relative_volume = (
        last["volume"]
        / avg_volume
        if avg_volume
        else 1.0
    )

    bull_trap = False
    bear_trap = False

    # Possible bull trap:
    # price sweeps resistance,
    # then closes back underneath it.
    if resistance:

        swept = any(
            candle["high"]
            > resistance
            for candle
            in recent[:-1]
        )

        failed = (
            last["close"]
            < resistance
        )

        bull_trap = (
            swept
            and failed
            and relative_volume >= 1.15
        )

    # Possible bear trap:
    # price sweeps support,
    # then reclaims it.
    if support:

        swept = any(
            candle["low"]
            < support
            for candle
            in recent[:-1]
        )

        reclaimed = (
            last["close"]
            > support
        )

        bear_trap = (
            swept
            and reclaimed
            and relative_volume >= 1.15
        )

    if (
        bull_trap
        and not bear_trap
    ):

        return {

            "label":
                "Possible bull trap / "
                "failed breakout",

            "score":
                -2,
        }

    if (
        bear_trap
        and not bull_trap
    ):

        return {

            "label":
                "Possible bear trap / "
                "failed breakdown",

            "score":
                2,
        }

    if (
        bull_trap
        and bear_trap
    ):

        return {

            "label":
                "Two-sided liquidity sweep",

            "score":
                0,
        }

    return {

        "label":
            "No clear trap detected",

        "score":
            0,
    }


# ============================================================
# INDIVIDUAL TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    candles,
):

    if len(candles) < 60:

        return {

            "valid":
                False,

            "direction":
                "Data Unavailable",

            "score":
                0,
        }

    closes = [
        candle["close"]
        for candle in candles
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

    structure = (
        calculate_structure(
            candles
        )
    )

    (
        support,
        resistance,
        swing_highs,
        swing_lows,
    ) = nearest_levels(
        candles,
        price,
    )

    profile = volume_profile(
        candles
    )

    rejection = (
        rejection_analysis(
            candles
        )
    )

    traps = (
        liquidity_trap_analysis(
            candles,
            support,
            resistance,
        )
    )

    (
        bullish_fvgs,
        bearish_fvgs,
    ) = active_fvgs(
        candles,
        price,
    )

    score = 0.0

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if ema20[-1] is not None:

        if price > ema20[-1]:
            score += 1.5
        else:
            score -= 1.5

    if (
        ema50[-1] is not None
        and ema20[-1] is not None
    ):

        if ema20[-1] > ema50[-1]:
            score += 1.5
        else:
            score -= 1.5

    if ema200[-1] is not None:

        if price > ema200[-1]:
            score += 1.0
        else:
            score -= 1.0

    # --------------------------------------------------------
    # EMA SLOPE
    # --------------------------------------------------------

    if ema20[-6] is not None:

        if ema20[-1] > ema20[-6]:
            score += 1.0
        else:
            score -= 1.0

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    previous = closes[-11]

    percent_change = (
        (
            price
            - previous
        )
        / previous
        * 100
        if previous
        else 0
    )

    if percent_change > 0.75:

        score += 1.5

    elif percent_change > 0.20:

        score += 0.75

    elif percent_change < -0.75:

        score -= 1.5

    elif percent_change < -0.20:

        score -= 0.75

    # --------------------------------------------------------
    # RSI
    #
    # We deliberately DO NOT say:
    # RSI > 70 = automatically bearish
    # RSI < 30 = automatically bullish
    #
    # Context matters.
    # --------------------------------------------------------

    if rsi is not None:

        if (
            rsi >= 52
            and rsi <= 68
        ):

            score += 0.75

        elif (
            rsi >= 32
            and rsi <= 48
        ):

            score -= 0.75

        elif rsi > 75:

            score -= 0.35

        elif rsi < 25:

            score += 0.35

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd:

        if macd["histogram"] > 0:

            score += 1.0

        elif macd["histogram"] < 0:

            score -= 1.0

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    score += (
        structure["score"]
        * 0.9
    )

    # --------------------------------------------------------
    # RELATIVE VOLUME
    # --------------------------------------------------------

    recent_volumes = [
        candle["volume"]
        for candle
        in candles[-21:-1]
    ]

    average_volume = (
        sum(recent_volumes)
        / len(recent_volumes)
        if recent_volumes
        else None
    )

    volume_ratio = (
        candles[-1]["volume"]
        / average_volume
        if average_volume
        else None
    )

    if volume_ratio is not None:

        if volume_ratio >= 1.5:

            # High volume confirms the
            # direction already supported
            # by price structure.

            if score > 0:
                score += 0.75

            elif score < 0:
                score -= 0.75

    # --------------------------------------------------------
    # VOLUME PROFILE POSITION
    # --------------------------------------------------------

    profile_position = (
        "Unavailable"
    )

    if profile:

        if price > profile["vah"]:

            profile_position = (
                "Above Value Area"
            )

            if score >= 0:
                score += 0.35
            else:
                score -= 0.35

        elif price < profile["val"]:

            profile_position = (
                "Below Value Area"
            )

            if score <= 0:
                score -= 0.35
            else:
                score += 0.35

        else:

            profile_position = (
                "Inside Value Area"
            )

    # --------------------------------------------------------
    # REJECTION
    # --------------------------------------------------------

    if (
        rejection["bullish"]
        > rejection["bearish"]
    ):

        score += 0.6

    elif (
        rejection["bearish"]
        > rejection["bullish"]
    ):

        score -= 0.6

    # --------------------------------------------------------
    # LIQUIDITY / TRAPS
    # --------------------------------------------------------

    score += traps["score"]

    # --------------------------------------------------------
    # FVG CONTEXT
    # --------------------------------------------------------

    if (
        bullish_fvgs
        and not bearish_fvgs
    ):

        score += 0.35

    elif (
        bearish_fvgs
        and not bullish_fvgs
    ):

        score -= 0.35

    # --------------------------------------------------------
    # FINAL TIMEFRAME DIRECTION
    # --------------------------------------------------------

    if score >= 5.0:

        direction = "Bullish"

    elif score <= -5.0:

        direction = "Bearish"

    elif score >= 2.0:

        direction = "Bullish Lean"

    elif score <= -2.0:

        direction = "Bearish Lean"

    else:

        direction = (
            "Consolidation / Mixed"
        )

    atr_percent = (
        atr / price * 100
        if atr and price
        else None
    )

    return {

        "valid":
            True,

        "direction":
            direction,

        "score":
            score,

        "price":
            price,

        "ema20":
            ema20[-1],

        "ema50":
            ema50[-1],

        "ema200":
            ema200[-1],

        "rsi":
            rsi,

        "macd":
            macd,

        "volume_ratio":
            volume_ratio,

        "atr_percent":
            atr_percent,

        "structure":
            structure["label"],

        "support":
            support,

        "resistance":
            resistance,

        "swing_high":
            structure.get(
                "swing_high"
            ),

        "swing_low":
            structure.get(
                "swing_low"
            ),

        "profile":
            profile,

        "profile_position":
            profile_position,

        "bullish_fvgs":
            bullish_fvgs,

        "bearish_fvgs":
            bearish_fvgs,

        "fvg_bullish_count":
            len(bullish_fvgs),

        "fvg_bearish_count":
            len(bearish_fvgs),

        "rejection":
            rejection,

        "trap":
            traps,
    }


# ============================================================
# OPTIONAL TRADINGVIEW DATA
# ============================================================

def tradingview_key(
    coin,
    timeframe,
):

    return (
        f"{coin}:{timeframe}"
    )


def get_tradingview_data(
    coin,
    timeframe,
):

    data = TRADINGVIEW_CACHE.get(
        tradingview_key(
            coin,
            timeframe,
        )
    )

    if not data:
        return None

    # Ignore stale alerts.
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

def scan_coin(
    coin,
):

    results = {}
    providers = {}

    price = None

    # --------------------------------------------------------
    # ANALYZE ALL TIMEFRAMES
    # --------------------------------------------------------

    for timeframe in TIMEFRAMES:

        (
            candles,
            provider,
        ) = get_market_candles(
            coin,
            timeframe,
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

            price = (
                candles[-1]["close"]
            )

    valid = [
        (
            timeframe,
            result
        )
        for timeframe, result
        in results.items()
        if result.get("valid")
    ]

    count = len(valid)

    # --------------------------------------------------------
    # NO DATA
    # --------------------------------------------------------

    if not valid:

        return {

            "coin":
                coin,

            "price":
                price,

            "timeframes":
                results,

            "providers":
                providers,

            "overall": {

                "label":
                    "Data Unavailable",

                "score":
                    0,

                "confidence":
                    0,
            },

            "valid_count":
                0,

            "total_count":
                len(TIMEFRAMES),

            "tradingview": {

                "bullish":
                    0,

                "bearish":
                    0,

                "available":
                    0,
            },
        }

    # --------------------------------------------------------
    # MULTI-TIMEFRAME WEIGHTING
    # --------------------------------------------------------

    total_weight = 0.0
    weighted_score = 0.0

    for (
        timeframe,
        result
    ) in valid:

        weight = (
            TIMEFRAMES[
                timeframe
            ][2]
        )

        weighted_score += (
            result["score"]
            * weight
        )

        total_weight += weight

    average_score = (
        weighted_score
        / total_weight
        if total_weight
        else 0.0
    )

    # --------------------------------------------------------
    # TIMEFRAME AGREEMENT
    # --------------------------------------------------------

    bullish = sum(

        1

        for _, result
        in valid

        if result["direction"]
        in (
            "Bullish",
            "Bullish Lean",
        )
    )

    bearish = sum(

        1

        for _, result
        in valid

        if result["direction"]
        in (
            "Bearish",
            "Bearish Lean",
        )
    )

    neutral = (
        count
        - bullish
        - bearish
    )

    # --------------------------------------------------------
    # OPTIONAL TRADINGVIEW CONFIRMATION
    #
    # IMPORTANT:
    # TradingView DOES NOT control the bot.
    #
    # If no TradingView alert has been received,
    # it contributes nothing.
    #
    # Therefore the bot does NOT automatically become
    # "bad" because TradingView = 0.
    # --------------------------------------------------------

    tv_bullish = 0
    tv_bearish = 0
    tv_available = 0

    for (
        timeframe,
        _
    ) in valid:

        tv = get_tradingview_data(
            coin,
            timeframe,
        )

        if not tv:
            continue

        tv_available += 1

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

    # Only modify the composite score
    # when actual TradingView data exists.

    if tv_available:

        tv_bias = (
            tv_bullish
            - tv_bearish
        ) / tv_available

        average_score += max(
            -1.5,
            min(
                1.5,
                tv_bias,
            )
        )

    # --------------------------------------------------------
    # OVERALL DIRECTION
    #
    # Strong labels require both:
    # 1. Score
    # 2. Multi-timeframe agreement
    #
    # This prevents "everything is bullish."
    # --------------------------------------------------------

    bull_ratio = (
        bullish / count
    )

    bear_ratio = (
        bearish / count
    )

    if (
        average_score >= 4.0
        and bull_ratio >= 0.60
    ):

        overall = "Bullish"

    elif (
        average_score <= -4.0
        and bear_ratio >= 0.60
    ):

        overall = "Bearish"

    elif (
        average_score >= 1.75
        and bull_ratio >= 0.50
    ):

        overall = "Bullish Lean"

    elif (
        average_score <= -1.75
        and bear_ratio >= 0.50
    ):

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / "
            "Indecisive"
        )

    # --------------------------------------------------------
    # CONFIDENCE / ANALYSIS STRENGTH
    #
    # This is NOT win probability.
    # It represents evidence strength + agreement + data quality.
    # --------------------------------------------------------

    agreement = (
        abs(
            bullish
            - bearish
        )
        / count
    )

    score_component = min(
        abs(
            average_score
        )
        / 8.0,
        1.0,
    )

    data_component = (
        count
        / len(TIMEFRAMES)
    )

    confidence = min(

        100.0,

        (
            score_component
            * 45
        )

        +

        (
            agreement
            * 35
        )

        +

        (
            data_component
            * 20
        ),
    )

    # --------------------------------------------------------
    # AGGREGATES
    # --------------------------------------------------------

    rsi_values = [

        result["rsi"]

        for _, result
        in valid

        if result.get("rsi")
        is not None
    ]

    volume_values = [

        result["volume_ratio"]

        for _, result
        in valid

        if result.get(
            "volume_ratio"
        )
        is not None
    ]

    atr_values = [

        result["atr_percent"]

        for _, result
        in valid

        if result.get(
            "atr_percent"
        )
        is not None
    ]

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # Prefer 4h, then 1h.
    # --------------------------------------------------------

    supports = [

        result["support"]

        for _, result
        in valid

        if result.get(
            "support"
        )
        is not None
    ]

    resistances = [

        result["resistance"]

        for _, result
        in valid

        if result.get(
            "resistance"
        )
        is not None
    ]

    support = (

        results
        .get("4h", {})
        .get("support")

        or

        results
        .get("1h", {})
        .get("support")

        or

        (
            supports[0]
            if supports
            else None
        )
    )

    resistance = (

        results
        .get("4h", {})
        .get("resistance")

        or

        results
        .get("1h", {})
        .get("resistance")

        or

        (
            resistances[0]
            if resistances
            else None
        )
    )

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

    profile = (

        results
        .get("4h", {})
        .get("profile")

        or

        results
        .get("1h", {})
        .get("profile")
    )

    # --------------------------------------------------------
    # FVG TOTALS
    # --------------------------------------------------------

    bullish_fvg_count = sum(

        result.get(
            "fvg_bullish_count",
            0,
        )

        for _, result
        in valid
    )

    bearish_fvg_count = sum(

        result.get(
            "fvg_bearish_count",
            0,
        )

        for _, result
        in valid
    )

    # --------------------------------------------------------
    # REJECTIONS
    # --------------------------------------------------------

    rejection_bullish = sum(

        result
        .get(
            "rejection",
            {}
        )
        .get(
            "bullish",
            0,
        )

        for _, result
        in valid
    )

    rejection_bearish = sum(

        result
        .get(
            "rejection",
            {}
        )
        .get(
            "bearish",
            0,
        )

        for _, result
        in valid
    )

    # --------------------------------------------------------
    # TRAP EVENTS
    # --------------------------------------------------------

    trap_labels = [

        result
        .get(
            "trap",
            {}
        )
        .get(
            "label"
        )

        for _, result
        in valid
    ]

    trap_count = sum(

        1

        for label
        in trap_labels

        if (
            label
            and
            "Possible"
            in label
        )
    )

    return {

        "coin":
            coin,

        "price":
            price,

        "timeframes":
            results,

        "providers":
            providers,

        "overall": {

            "label":
                overall,

            "score":
                average_score,

            "confidence":
                confidence,
        },

        "valid_count":
            count,

        "total_count":
            len(TIMEFRAMES),

        "bullish_count":
            bullish,

        "bearish_count":
            bearish,

        "neutral_count":
            neutral,

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

        "support":
            support,

        "resistance":
            resistance,

        "volume_profile":
            profile,

        "fvg_bullish_count":
            bullish_fvg_count,

        "fvg_bearish_count":
            bearish_fvg_count,

        "rejection_bullish":
            rejection_bullish,

        "rejection_bearish":
            rejection_bearish,

        "trap_count":
            trap_count,

        "tradingview": {

            "bullish":
                tv_bullish,

            "bearish":
                tv_bearish,

            "available":
                tv_available,
        },
    }


# ============================================================
# FORMATTING
# ============================================================

def format_price(
    price,
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
    direction,
):

    if (
        direction == "Bullish"
        or "Bullish"
        in direction
    ):

        return "🟢"

    if (
        direction == "Bearish"
        or "Bearish"
        in direction
    ):

        return "🔴"

    if (
        "Consolidation"
        in direction
        or "Indecisive"
        in direction
        or "Mixed"
        in direction
    ):

        return "🟡"

    return "⚪"


# ============================================================
# TELEGRAM ANALYSIS MESSAGE
# ============================================================

def build_scan_message(
    analysis,
):

    coin = analysis[
        "coin"
    ]

    overall = analysis[
        "overall"
    ]

    tv = analysis[
        "tradingview"
    ]

    profile = analysis.get(
        "volume_profile"
    )

    lines = [

        (
            f"<b>🔎 {coin} "
            "MARKET ANALYSIS</b>"
        ),

        "",

        (
            "💰 <b>Price:</b> "
            f"{format_price(analysis['price'])}"
        ),

        "",

        (
            f"{direction_emoji(overall['label'])} "
            "<b>Overall:</b> "
            f"{overall['label']}"
        ),

        (
            "🎯 <b>Analysis Strength:</b> "
            f"{overall['confidence']:.0f}%"
        ),

        (
            "🧮 <b>Composite Score:</b> "
            f"{overall['score']:+.2f}"
        ),

        "",

        (
            "📊 <b>MULTI-TIMEFRAME "
            "ANALYSIS</b>"
        ),
    ]

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        direction = result.get(
            "direction",
            "Data Unavailable",
        )

        score = result.get(
            "score",
            0,
        )

        lines.append(

            (
                f"{direction_emoji(direction)} "
                f"<b>{timeframe}:</b> "
                f"{direction} "
                f"({score:+.1f})"
            )
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

    lines += [

        "",

        "📈 <b>MARKET CONDITIONS</b>",

        (
            f"📉 <b>Average RSI:</b> "
            f"{average_rsi:.1f}"

            if average_rsi
            is not None

            else

            "📉 <b>Average RSI:</b> "
            "Unavailable"
        ),

        (
            f"📦 <b>Relative Volume:</b> "
            f"{volume:.2f}x"

            if volume
            is not None

            else

            "📦 <b>Relative Volume:</b> "
            "Unavailable"
        ),

        (
            f"🌊 <b>Average ATR:</b> "
            f"{atr:.2f}%"

            if atr
            is not None

            else

            "🌊 <b>Average ATR:</b> "
            "Unavailable"
        ),

        (
            "🧱 <b>Structure:</b> "
            f"{analysis['timeframes']"
            ".get('4h', {})"
            ".get('structure')"
            or
            analysis['timeframes']"
            ".get('1h', {})"
            ".get('structure')"
            or
            "Mixed"
        ),

        "",

        "📐 <b>SUPPORT / RESISTANCE</b>",

        (
            "🟢 <b>Support:</b> "
            f"{format_price(analysis['support'])}"
        ),

        (
            "🔴 <b>Resistance:</b> "
            f"{format_price(analysis['resistance'])}"
        ),

        "",

        "📊 <b>VOLUME PROFILE</b>",
    ]

    if profile:

        lines += [

            (
                "🎯 <b>POC:</b> "
                f"{format_price(profile['poc'])}"
            ),

            (
                "🔺 <b>VAH:</b> "
                f"{format_price(profile['vah'])}"
            ),

            (
                "🔻 <b>VAL:</b> "
                f"{format_price(profile['val'])}"
            ),
        ]

        position = (

            analysis[
                "timeframes"
            ]
            .get(
                "4h",
                {}
            )
            .get(
                "profile_position"
            )

            or

            analysis[
                "timeframes"
            ]
            .get(
                "1h",
                {}
            )
            .get(
                "profile_position"
            )

            or

            "Unavailable"
        )

        lines.append(

            (
                "📍 <b>Position:</b> "
                f"{position}"
            )
        )

    else:

        lines.append(
            "📍 Volume profile: "
            "Unavailable"
        )

    lines += [

        "",

        "⚡ <b>FAIR VALUE GAPS</b>",

        (
            "🟢 <b>Bullish FVGs:</b> "
            f"{analysis['fvg_bullish_count']}"
        ),

        (
            "🔴 <b>Bearish FVGs:</b> "
            f"{analysis['fvg_bearish_count']}"
        ),

        "",

        "🪝 <b>REJECTION / LIQUIDITY</b>",

        (
            "🟢 Bullish rejections: "
            f"{analysis['rejection_bullish']}"
        ),

        (
            "🔴 Bearish rejections: "
            f"{analysis['rejection_bearish']}"
        ),

        (
            "🪤 Possible liquidity-trap "
            "events: "
            f"{analysis['trap_count']}"
        ),

        "",

        "📡 <b>TRADINGVIEW</b>",
    ]

    # --------------------------------------------------------
    # IMPORTANT:
    # Do NOT make TradingView 0/0 look like an error.
    # --------------------------------------------------------

    if tv["available"]:

        lines += [

            (
                "🟢 Confirmed bullish alerts: "
                f"{tv['bullish']}"
            ),

            (
                "🔴 Confirmed bearish alerts: "
                f"{tv['bearish']}"
            ),

            (
                "ℹ️ TradingView data is "
                "supplementary."
            ),
        ]

    else:

        lines.append(

            "⚪ Optional TradingView "
            "confirmation: none received"
        )

    lines += [

        "",

        "📡 <b>DATA QUALITY</b>",

        (
            f"{analysis['valid_count']}/"
            f"{analysis['total_count']} "
            "timeframes available"
        ),

        (
            "🟢 Bullish TFs: "
            f"{analysis['bullish_count']}"
        ),

        (
            "🔴 Bearish TFs: "
            f"{analysis['bearish_count']}"
        ),

        (
            "🟡 Neutral/Mixed TFs: "
            f"{analysis['neutral_count']}"
        ),

        "",

        (
            "⚠️ <b>Analysis only — "
            "not a guaranteed trade signal.</b>"
        ),
    ]

    return "\n".join(
        lines
    )


# ============================================================
# PERFORM SCAN
# ============================================================

def perform_scan(
    coin,
    chat_id,
):

    if coin not in COINS:

        send_telegram(

            "❌ Unsupported "
            "cryptocurrency.",

            chat_id,

            main_menu(),
        )

        return

    send_telegram(

        (
            f"<b>🔎 Scanning "
            f"{coin}...</b>\n\n"

            "📡 Live market data\n"

            "📈 EMA 20 / 50 / 200\n"

            "📉 RSI + MACD\n"

            "📦 Relative volume\n"

            "🌊 ATR / volatility\n"

            "🧱 Swing structure\n"

            "📐 Support / resistance\n"

            "📊 Volume profile\n"

            "⚡ Fair value gaps\n"

            "🪝 Rejection / "
            "liquidity analysis"
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
                f"<code>"
                f"{html.escape(str(e))}"
                "</code>"
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
            "search?q=cryptocurrency+"
            "crypto+bitcoin+ethereum"
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

def send_welcome(
    chat_id,
):

    send_telegram(

        (
            "<b>🤖 SIDESHIFT AI 3.0</b>\n\n"

            "Multi-timeframe crypto "
            "market analysis.\n\n"

            "<b>Core engine:</b>\n"

            "📈 EMA 20 / 50 / 200\n"

            "📉 RSI + MACD\n"

            "📦 Relative volume\n"

            "🌊 ATR / volatility\n"

            "🧱 Swing highs/lows + "
            "structure\n"

            "📐 Support / resistance\n"

            "📊 Volume profile\n"

            "⚡ Fair value gaps\n"

            "🪝 Rejection + "
            "liquidity-trap heuristics\n\n"

            "TradingView webhook data "
            "is optional and "
            "supplementary.\n\n"

            "The engine does not treat "
            "every coin as automatically "
            "bullish."
        ),

        chat_id,

        main_menu(),
    )


# ============================================================
# HELP
# ============================================================

def send_help(
    chat_id,
):

    send_telegram(

        (
            "<b>ℹ️ HOW SIDESHIFT AI "
            "WORKS</b>\n\n"

            "SideShift analyzes live "
            "candles across:\n\n"

            "5m • 15m • 1h • 4h • 1D\n\n"

            "It combines trend, "
            "momentum, volume, "
            "volatility, swing "
            "structure, support/"
            "resistance, volume "
            "profile, FVGs and "
            "rejection/liquidity "
            "behavior.\n\n"

            "TradingView webhook alerts "
            "can be added as an "
            "optional confirmation "
            "layer.\n\n"

            "A confidence percentage "
            "describes the strength/"
            "agreement of the analysis "
            "inputs. It is NOT a "
            "probability of profit."
        ),

        chat_id,

        main_menu(),
    )


# ============================================================
# VIP
# ============================================================

def send_vip(
    chat_id,
):

    send_telegram(

        (
            "<b>👑 SIDESHIFT AI VIP</b>"
            "\n\n"
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
                .get(
                    "chat",
                    {}
                )
                .get(
                    "id"
                )
            )

            text = (
                message
                .get(
                    "text",
                    ""
                )
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
                        "Use /start to "
                        "open SideShift AI."
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

            answer_callback(
                callback.get("id")
            )

            callback_data = (
                callback.get(
                    "data",
                    ""
                )
            )

            chat_id = (
                callback
                .get(
                    "message",
                    {}
                )
                .get(
                    "chat",
                    {}
                )
                .get(
                    "id"
                )
            )

            if (
                callback_data
                == "scan_menu"
            ):

                send_telegram(

                    (
                        "<b>📊 SELECT "
                        "A COIN</b>\n\n"
                        "Choose a "
                        "cryptocurrency."
                    ),

                    chat_id,

                    main_menu(),
                )

            elif callback_data.startswith(
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

            elif (
                callback_data
                == "main_menu"
            ):

                send_welcome(
                    chat_id
                )

            elif (
                callback_data
                == "news_all"
            ):

                send_telegram(

                    get_crypto_news(),

                    chat_id,

                    main_menu(),
                )

            elif (
                callback_data
                == "help"
            ):

                send_help(
                    chat_id
                )

            elif (
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

    except Exception as e:

        print(
            "TELEGRAM WEBHOOK ERROR:",
            repr(e),
        )

        return jsonify({

            "ok":
                False,

            "error":
                str(e),

        }), 500


# ============================================================
# OPTIONAL TRADINGVIEW WEBHOOK
# ============================================================
#
# IMPORTANT:
#
# This endpoint remains available.
#
# BUT SideShift AI does NOT require TradingView alerts.
#
# If TradingView sends an alert here later,
# the bot can use it as supplementary confirmation.
#
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

        # ----------------------------------------------------
        # SECURITY
        # ----------------------------------------------------

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
                ""
            )
        ).upper()

        timeframe = str(
            data.get(
                "timeframe",
                ""
            )
        ).strip()

        # Normalize symbol.
        symbol = (
            symbol
            .replace(
                ".P",
                ""
            )
            .replace(
                "/",
                ""
            )
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
            tradingview_key(
                symbol,
                timeframe,
            )
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

        # Only notify Telegram if a real
        # TradingView alert actually arrives.

        if TELEGRAM_CHAT_ID:

            send_telegram(

                (
                    "<b>📡 TRADINGVIEW "
                    "UPDATE</b>\n\n"

                    f"<b>"
                    f"{html.escape(symbol)}"
                    f"</b>\n"

                    "Timeframe: "

                    f"{html.escape(timeframe)}"
                    "\n"

                    "Signal: "

                    f"<b>"
                    f"{html.escape(signal)}"
                    f"</b>"
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
            "3.0",

        "telegram_webhook":
            "/telegram-webhook",

        "optional_tradingview_webhook":
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
def test_market(
    coin,
):

    coin = coin.upper()

    if coin not in COINS:

        return jsonify({

            "error":
                "Unsupported coin",

            "supported":
                list(
                    COINS.keys()
                ),

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
        "SideShift AI 3.0 starting..."
    )

    print(
        "================================"
    )

    print(

        "Telegram:",

        "FOUND"

        if TELEGRAM_BOT_TOKEN

        else

        "MISSING",
    )

    print(

        "Railway domain:",

        RAILWAY_PUBLIC_DOMAIN
        or
        "MISSING",
    )

    print(

        "Telegram chat:",

        "FOUND"

        if TELEGRAM_CHAT_ID

        else

        "MISSING",
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