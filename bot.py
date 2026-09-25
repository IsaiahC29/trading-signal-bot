import os
import html
import time
import math
import requests
import feedparser
from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# ENVIRONMENT
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RAILWAY_PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    if TELEGRAM_BOT_TOKEN else None
)

REQUEST_TIMEOUT = 15

# ============================================================
# COINS / TIMEFRAMES
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

TIMEFRAMES = {
    "5m": {
        "binance": "5m",
        "seconds": 300,
        "weight": 0.8,
    },
    "15m": {
        "binance": "15m",
        "seconds": 900,
        "weight": 1.0,
    },
    "1h": {
        "binance": "1h",
        "seconds": 3600,
        "weight": 1.2,
    },
    "4h": {
        "binance": "4h",
        "seconds": 14400,
        "weight": 1.5,
    },
    "1D": {
        "binance": "1d",
        "seconds": 86400,
        "weight": 1.8,
    },
}

TRADINGVIEW_CACHE = {}

# ============================================================
# UTILITIES
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def mean(values):
    values = [x for x in values if x is not None]

    if not values:
        return None

    return sum(values) / len(values)


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


def format_level(price):
    if price is None:
        return "N/A"

    return format_price(price)


def direction_emoji(direction):
    if direction == "Bullish":
        return "🟢"

    if direction == "Bearish":
        return "🔴"

    if "Bullish" in direction:
        return "🟩"

    if "Bearish" in direction:
        return "🟥"

    return "🟡"


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

    if keyboard is not None:
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

    except Exception as exc:

        print(
            "TELEGRAM ERROR:",
            repr(exc),
        )

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
# TECHNICAL INDICATORS
# ============================================================

def ema(values, period):

    if len(values) < period:
        return [None] * len(values)

    result = [None] * len(values)

    multiplier = 2 / (period + 1)

    previous = (
        sum(values[:period])
        / period
    )

    result[period - 1] = previous

    for i in range(
        period,
        len(values),
    ):

        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
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
        len(closes),
    ):

        change = (
            closes[i]
            - closes[i - 1]
        )

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

    for i in range(
        period,
        len(gains),
    ):

        avg_gain = (
            (
                avg_gain * (period - 1)
                + gains[i]
            )
            / period
        )

        avg_loss = (
            (
                avg_loss * (period - 1)
                + losses[i]
            )
            / period
        )

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

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
        len(candles),
    ):

        current = candles[i]
        previous = candles[i - 1]

        tr = max(

            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
            ),
        )

        true_ranges.append(tr)

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


def calculate_macd(closes):

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
            ema12[i] is not None
            and ema26[i] is not None
        ):

            macd_values.append(
                ema12[i]
                - ema26[i]
            )

    if len(macd_values) < 9:
        return None

    signal_values = ema(
        macd_values,
        9,
    )

    if signal_values[-1] is None:
        return None

    value = macd_values[-1]

    signal = signal_values[-1]

    return {
        "value": value,
        "signal": signal,
        "histogram": value - signal,
    }


def calculate_bollinger(
    closes,
    period=20,
    deviations=2,
):

    if len(closes) < period:
        return None

    window = closes[-period:]

    middle = (
        sum(window)
        / period
    )

    variance = (
        sum(
            (x - middle) ** 2
            for x in window
        )
        / period
    )

    std = math.sqrt(
        variance
    )

    return {
        "middle":
            middle,

        "upper":
            middle
            + deviations * std,

        "lower":
            middle
            - deviations * std,
    }


def calculate_adx(
    candles,
    period=14,
):

    if len(candles) < (
        period * 2 + 1
    ):
        return None

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(
        1,
        len(candles),
    ):

        current = candles[i]
        previous = candles[i - 1]

        high_move = (
            current["high"]
            - previous["high"]
        )

        low_move = (
            previous["low"]
            - current["low"]
        )

        plus_dm.append(
            high_move
            if (
                high_move > low_move
                and high_move > 0
            )
            else 0
        )

        minus_dm.append(
            low_move
            if (
                low_move > high_move
                and low_move > 0
            )
            else 0
        )

        trs.append(
            max(

                current["high"]
                - current["low"],

                abs(
                    current["high"]
                    - previous["close"]
                ),

                abs(
                    current["low"]
                    - previous["close"]
                ),
            )
        )

    atr = (
        sum(trs[:period])
        / period
    )

    p_dm = (
        sum(plus_dm[:period])
        / period
    )

    m_dm = (
        sum(minus_dm[:period])
        / period
    )

    dx_values = []

    for i in range(
        period,
        len(trs),
    ):

        atr = (
            (
                atr * (period - 1)
                + trs[i]
            )
            / period
        )

        p_dm = (
            (
                p_dm * (period - 1)
                + plus_dm[i]
            )
            / period
        )

        m_dm = (
            (
                m_dm * (period - 1)
                + minus_dm[i]
            )
            / period
        )

        if atr == 0:
            continue

        plus_di = (
            100 * p_dm / atr
        )

        minus_di = (
            100 * m_dm / atr
        )

        denominator = (
            plus_di
            + minus_di
        )

        if denominator == 0:
            continue

        dx_values.append(
            100
            * abs(
                plus_di
                - minus_di
            )
            / denominator
        )

    if len(dx_values) < period:
        return None

    adx = (
        sum(dx_values[:period])
        / period
    )

    for value in dx_values[period:]:

        adx = (
            (
                adx * (period - 1)
                + value
            )
            / period
        )

    return adx


def calculate_vwap(
    candles,
    lookback=100,
):

    candles = candles[-lookback:]

    if not candles:
        return None

    cumulative_pv = 0
    cumulative_volume = 0

    for candle in candles:

        typical = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        volume = candle["volume"]

        cumulative_pv += (
            typical * volume
        )

        cumulative_volume += volume

    if cumulative_volume == 0:
        return None

    return (
        cumulative_pv
        / cumulative_volume
    )


def calculate_volume_profile(
    candles,
    bins=24,
    lookback=120,
):

    candles = candles[-lookback:]

    if len(candles) < 20:
        return None

    low = min(
        x["low"]
        for x in candles
    )

    high = max(
        x["high"]
        for x in candles
    )

    if high <= low:
        return None

    bucket_size = (
        high - low
    ) / bins

    profile = [
        0.0
        for _ in range(bins)
    ]

    for candle in candles:

        typical = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        index = int(
            (
                typical
                - low
            )
            / bucket_size
        )

        index = int(
            clamp(
                index,
                0,
                bins - 1,
            )
        )

        profile[index] += (
            candle["volume"]
        )

    poc_index = max(
        range(bins),
        key=lambda i:
        profile[i],
    )

    poc = (
        low
        + (poc_index + 0.5)
        * bucket_size
    )

    return {
        "poc": poc,
        "range_low": low,
        "range_high": high,
    }


# ============================================================
# PRICE ACTION / STRUCTURE
# ============================================================

def find_swings(
    candles,
    left=3,
    right=3,
):

    swing_highs = []
    swing_lows = []

    if len(candles) < (
        left
        + right
        + 1
    ):

        return (
            swing_highs,
            swing_lows,
        )

    for i in range(
        left,
        len(candles) - right,
    ):

        current = candles[i]

        is_high = all(

            current["high"]
            > candles[j]["high"]

            for j in range(
                i - left,
                i + right + 1,
            )

            if j != i
        )

        is_low = all(

            current["low"]
            < candles[j]["low"]

            for j in range(
                i - left,
                i + right + 1,
            )

            if j != i
        )

        if is_high:
            swing_highs.append(
                current["high"]
            )

        if is_low:
            swing_lows.append(
                current["low"]
            )

    return (
        swing_highs[-10:],
        swing_lows[-10:],
    )


def nearest_levels(
    price,
    swing_highs,
    swing_lows,
):

    supports = sorted(

        [
            x
            for x in swing_lows
            if x < price
        ],

        reverse=True,
    )

    resistances = sorted(

        [
            x
            for x in swing_highs
            if x > price
        ]
    )

    return {

        "support":
            supports[0]
            if supports
            else None,

        "support_2":
            supports[1]
            if len(supports) > 1
            else None,

        "resistance":
            resistances[0]
            if resistances
            else None,

        "resistance_2":
            resistances[1]
            if len(resistances) > 1
            else None,
    }


def analyze_structure(
    swing_highs,
    swing_lows,
):

    if (
        len(swing_highs) < 2
        or len(swing_lows) < 2
    ):

        return {

            "label":
                "Insufficient Swing Data",

            "score":
                0,

            "details":
                [],
        }

    last_high = swing_highs[-1]
    previous_high = swing_highs[-2]

    last_low = swing_lows[-1]
    previous_low = swing_lows[-2]

    higher_high = (
        last_high
        > previous_high
    )

    higher_low = (
        last_low
        > previous_low
    )

    lower_high = (
        last_high
        < previous_high
    )

    lower_low = (
        last_low
        < previous_low
    )

    details = []

    if higher_high:
        details.append(
            "Higher High"
        )

    elif lower_high:
        details.append(
            "Lower High"
        )

    if higher_low:
        details.append(
            "Higher Low"
        )

    elif lower_low:
        details.append(
            "Lower Low"
        )

    if (
        higher_high
        and higher_low
    ):

        label = (
            "Bullish Structure"
        )

        score = 2

    elif (
        lower_high
        and lower_low
    ):

        label = (
            "Bearish Structure"
        )

        score = -2

    elif higher_high:

        label = (
            "Higher-High Structure"
        )

        score = 1

    elif lower_low:

        label = (
            "Lower-Low Structure"
        )

        score = -1

    else:

        label = (
            "Mixed Structure"
        )

        score = 0

    return {

        "label":
            label,

        "score":
            score,

        "details":
            details,
    }


def detect_fvg(candles):

    bullish = []
    bearish = []

    if len(candles) < 3:

        return {
            "bullish": [],
            "bearish": [],
        }

    for i in range(
        2,
        len(candles),
    ):

        first = candles[i - 2]
        third = candles[i]

        if (
            third["low"]
            > first["high"]
        ):

            bullish.append({

                "low":
                    first["high"],

                "high":
                    third["low"],
            })

        if (
            third["high"]
            < first["low"]
        ):

            bearish.append({

                "low":
                    third["high"],

                "high":
                    first["low"],
            })

    return {

        "bullish":
            bullish[-5:],

        "bearish":
            bearish[-5:],
    }


def detect_rejection(candles):

    if not candles:
        return "None"

    candle = candles[-1]

    body = abs(
        candle["close"]
        - candle["open"]
    )

    upper_wick = (
        candle["high"]
        - max(
            candle["open"],
            candle["close"],
        )
    )

    lower_wick = (
        min(
            candle["open"],
            candle["close"],
        )
        - candle["low"]
    )

    if body == 0:

        body = max(
            (
                candle["high"]
                - candle["low"]
            )
            * 0.01,
            1e-12,
        )

    if (
        lower_wick > body * 2
        and lower_wick > upper_wick
    ):

        return (
            "Bullish Rejection"
        )

    if (
        upper_wick > body * 2
        and upper_wick > lower_wick
    ):

        return (
            "Bearish Rejection"
        )

    return "None"


def detect_liquidity_event(
    candles,
    swing_highs,
    swing_lows,
):

    if len(candles) < 2:
        return "None"

    current = candles[-1]

    resistance = (
        swing_highs[-1]
        if swing_highs
        else None
    )

    support = (
        swing_lows[-1]
        if swing_lows
        else None
    )

    if (
        resistance is not None
        and current["high"]
        > resistance
        and current["close"]
        < resistance
    ):

        return (
            "Bearish Liquidity Sweep"
        )

    if (
        support is not None
        and current["low"]
        < support
        and current["close"]
        > support
    ):

        return (
            "Bullish Liquidity Sweep"
        )

    return "None"


# ============================================================
# DATA SOURCES
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

            continue

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

            continue

    candles.sort(
        key=lambda x:
        x["timestamp"]
    )

    return candles


def get_binance_candles(
    symbol,
    interval,
    limit=250,
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
                    limit,
            },

            timeout=REQUEST_TIMEOUT,

            headers={
                "User-Agent":
                    "SideShiftAI/4.0"
            },
        )

        if not response.ok:

            print(
                "BINANCE ERROR:",
                symbol,
                interval,
                response.status_code,
                response.text[:300],
            )

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
            "BINANCE REQUEST ERROR:",
            repr(exc),
        )

        return []


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
                    "SideShiftAI/4.0"
            },
        )

        if not response.ok:

            print(
                "COINBASE ERROR:",
                product,
                response.status_code,
                response.text[:300],
            )

            return []

        return normalize_coinbase(
            response.json()
        )[-300:]

    except Exception as exc:

        print(
            "COINBASE REQUEST ERROR:",
            repr(exc),
        )

        return []


def aggregate_candles(
    candles,
    seconds,
):

    if not candles:
        return []

    groups = {}

    for candle in candles:

        timestamp_seconds = (
            candle["timestamp"]
            // 1000
        )

        bucket = (
            timestamp_seconds
            // seconds
        ) * seconds

        groups.setdefault(
            bucket,
            [],
        ).append(candle)

    result = []

    for bucket in sorted(
        groups,
    ):

        group = groups[bucket]

        if not group:
            continue

        result.append({

            "timestamp":
                bucket * 1000,

            "open":
                group[0]["open"],

            "high":
                max(
                    x["high"]
                    for x in group
                ),

            "low":
                min(
                    x["low"]
                    for x in group
                ),

            "close":
                group[-1]["close"],

            "volume":
                sum(
                    x["volume"]
                    for x in group
                ),
        })

    return result


def get_market_candles(
    coin,
    timeframe,
):

    (
        binance_symbol,
        coinbase_symbol,
    ) = COINS[coin]

    config = TIMEFRAMES[
        timeframe
    ]

    # --------------------------------------------------------
    # SPECIAL 4H HANDLING
    # --------------------------------------------------------

    if timeframe == "4h":

        candles = get_binance_candles(
            binance_symbol,
            "4h",
            250,
        )

        if len(candles) >= 80:

            return (
                candles,
                "Binance 4H",
            )

        one_hour = (
            get_binance_candles(
                binance_symbol,
                "1h",
                1000,
            )
        )

        four_hour = (
            aggregate_candles(
                one_hour,
                14400,
            )
        )

        if len(four_hour) >= 80:

            return (
                four_hour[-250:],
                "Binance 1H→4H",
            )

        one_hour = (
            get_coinbase_candles(
                coinbase_symbol,
                3600,
            )
        )

        four_hour = (
            aggregate_candles(
                one_hour,
                14400,
            )
        )

        if len(four_hour) >= 80:

            return (
                four_hour[-250:],
                "Coinbase 1H→4H",
            )

        return [], None

    # --------------------------------------------------------
    # NORMAL BINANCE
    # --------------------------------------------------------

    candles = get_binance_candles(

        binance_symbol,

        config["binance"],

        250,
    )

    if len(candles) >= 80:

        return (
            candles,
            f"Binance {timeframe}",
        )

    # --------------------------------------------------------
    # COINBASE FALLBACK
    # --------------------------------------------------------

    candles = get_coinbase_candles(

        coinbase_symbol,

        config["seconds"],
    )

    if len(candles) >= 80:

        return (
            candles,
            f"Coinbase {timeframe}",
        )

    return [], None


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    candles,
):

    if len(candles) < 80:

        return {

            "valid":
                False,

            "direction":
                "Data Unavailable",

            "score":
                0,
        }

    closes = [
        x["close"]
        for x in candles
    ]

    volumes = [
        x["volume"]
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

    adx = calculate_adx(
        candles
    )

    bollinger = calculate_bollinger(
        closes
    )

    vwap = calculate_vwap(
        candles
    )

    volume_average = mean(
        volumes[-21:-1]
    )

    volume_ratio = None

    if (
        volume_average
        and volume_average > 0
    ):

        volume_ratio = (
            volumes[-1]
            / volume_average
        )

    swing_highs, swing_lows = (
        find_swings(
            candles
        )
    )

    levels = nearest_levels(

        price,

        swing_highs,

        swing_lows,
    )

    structure = analyze_structure(

        swing_highs,

        swing_lows,
    )

    fvg = detect_fvg(
        candles
    )

    rejection = detect_rejection(
        candles
    )

    liquidity = detect_liquidity_event(

        candles,

        swing_highs,

        swing_lows,
    )

    volume_profile = (
        calculate_volume_profile(
            candles
        )
    )

    score = 0

    reasons = []

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if ema20[-1] is not None:

        if price > ema20[-1]:

            score += 2

            reasons.append(
                "Price above EMA20"
            )

        else:

            score -= 2

            reasons.append(
                "Price below EMA20"
            )

    if (
        ema20[-1] is not None
        and ema50[-1] is not None
    ):

        if ema20[-1] > ema50[-1]:

            score += 2

            reasons.append(
                "EMA20 above EMA50"
            )

        else:

            score -= 2

            reasons.append(
                "EMA20 below EMA50"
            )

    if ema200[-1] is not None:

        if price > ema200[-1]:

            score += 1

            reasons.append(
                "Price above EMA200"
            )

        else:

            score -= 1

            reasons.append(
                "Price below EMA200"
            )

    # --------------------------------------------------------
    # EMA SLOPE
    # --------------------------------------------------------

    if (
        ema20[-6] is not None
        and ema20[-1] is not None
    ):

        if ema20[-1] > ema20[-6]:

            score += 1

        else:

            score -= 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi is not None:

        if (
            55 <= rsi < 70
        ):

            score += 1

            reasons.append(
                "RSI bullish momentum"
            )

        elif (
            30 < rsi <= 45
        ):

            score -= 1

            reasons.append(
                "RSI bearish momentum"
            )

        elif rsi >= 70:

            reasons.append(
                "RSI overbought context"
            )

        elif rsi <= 30:

            reasons.append(
                "RSI oversold context"
            )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd:

        if macd["histogram"] > 0:

            score += 1

            reasons.append(
                "MACD positive"
            )

        elif macd["histogram"] < 0:

            score -= 1

            reasons.append(
                "MACD negative"
            )

    # --------------------------------------------------------
    # VWAP
    # --------------------------------------------------------

    if vwap is not None:

        if price > vwap:

            score += 1

            reasons.append(
                "Price above VWAP"
            )

        else:

            score -= 1

            reasons.append(
                "Price below VWAP"
            )

    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    trend_strength = "Weak"

    if adx is not None:

        if adx >= 25:

            trend_strength = "Trending"

        elif adx >= 18:

            trend_strength = "Developing"

    # --------------------------------------------------------
    # BOLLINGER
    # --------------------------------------------------------

    bollinger_state = "Normal"

    if bollinger:

        if price >= bollinger["upper"]:

            bollinger_state = (
                "Upper Band Pressure"
            )

        elif price <= bollinger["lower"]:

            bollinger_state = (
                "Lower Band Pressure"
            )

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    score += structure["score"]

    if structure["score"] > 0:

        reasons.append(
            "Structure favors buyers"
        )

    elif structure["score"] < 0:

        reasons.append(
            "Structure favors sellers"
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if volume_ratio is not None:

        if volume_ratio >= 1.5:

            reasons.append(
                "High relative volume"
            )

        elif volume_ratio <= 0.6:

            reasons.append(
                "Low relative volume"
            )

    # --------------------------------------------------------
    # REJECTION
    # --------------------------------------------------------

    if rejection == (
        "Bullish Rejection"
    ):

        score += 1

        reasons.append(
            "Bullish rejection candle"
        )

    elif rejection == (
        "Bearish Rejection"
    ):

        score -= 1

        reasons.append(
            "Bearish rejection candle"
        )

    # --------------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------------

    if liquidity == (
        "Bullish Liquidity Sweep"
    ):

        score += 2

        reasons.append(
            "Bullish liquidity sweep"
        )

    elif liquidity == (
        "Bearish Liquidity Sweep"
    ):

        score -= 2

        reasons.append(
            "Bearish liquidity sweep"
        )

    # --------------------------------------------------------
    # FAIR VALUE GAP
    # --------------------------------------------------------

    bullish_fvg_count = len(
        fvg["bullish"]
    )

    bearish_fvg_count = len(
        fvg["bearish"]
    )

    if (
        bullish_fvg_count
        > bearish_fvg_count
    ):

        score += 1

    elif (
        bearish_fvg_count
        > bullish_fvg_count
    ):

        score -= 1

    # --------------------------------------------------------
    # RECENT MOMENTUM
    # --------------------------------------------------------

    if len(closes) >= 12:

        change = (

            (
                price
                - closes[-11]
            )

            / closes[-11]

        ) * 100

        if change > 0.75:

            score += 1

        elif change < -0.75:

            score -= 1

    # --------------------------------------------------------
    # FINAL TIMEFRAME DIRECTION
    # --------------------------------------------------------

    if score >= 7:

        direction = "Bullish"

    elif score <= -7:

        direction = "Bearish"

    elif score >= 3:

        direction = "Bullish Lean"

    elif score <= -3:

        direction = "Bearish Lean"

    else:

        direction = (
            "Consolidation / Mixed"
        )

    # --------------------------------------------------------
    # ATR %
    # --------------------------------------------------------

    atr_percent = None

    if (
        atr is not None
        and price > 0
    ):

        atr_percent = (
            atr
            / price
        ) * 100

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

        "atr_percent":
            atr_percent,

        "adx":
            adx,

        "trend_strength":
            trend_strength,

        "vwap":
            vwap,

        "bollinger":
            bollinger,

        "bollinger_state":
            bollinger_state,

        "volume_ratio":
            volume_ratio,

        "structure":
            structure["label"],

        "structure_details":
            structure["details"],

        "structure_score":
            structure["score"],

        "support":
            levels["support"],

        "support_2":
            levels["support_2"],

        "resistance":
            levels["resistance"],

        "resistance_2":
            levels["resistance_2"],

        "swing_high":
            (
                swing_highs[-1]
                if swing_highs
                else None
            ),

        "swing_low":
            (
                swing_lows[-1]
                if swing_lows
                else None
            ),

        "fvg":
            fvg,

        "rejection":
            rejection,

        "liquidity":
            liquidity,

        "volume_profile":
            volume_profile,

        "reasons":
            reasons[-10:],
    }


# ============================================================
# TRADINGVIEW OPTIONAL CONTEXT
# ============================================================

def get_tradingview_confirmation(
    coin,
    timeframe,
):

    key = (
        f"{coin}:{timeframe}"
    )

    data = TRADINGVIEW_CACHE.get(
        key
    )

    if not data:
        return None

    if (
        time.time()
        - data["received"]
        > 7200
    ):

        TRADINGVIEW_CACHE.pop(
            key,
            None,
        )

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

            price = (
                candles[-1]["close"]
            )

    valid = [

        (tf, result)

        for tf, result
        in results.items()

        if result.get("valid")
    ]

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

                "strength":
                    0,

                "strength_label":
                    "No usable data",
            },

            "valid_count":
                0,

            "total_count":
                len(TIMEFRAMES),

            "bullish_count":
                0,

            "bearish_count":
                0,

            "mixed_count":
                0,

            "structure":
                "Unavailable",

            "support":
                None,

            "support_2":
                None,

            "resistance":
                None,

            "resistance_2":
                None,

            "fvg": {
                "bullish": [],
                "bearish": [],
            },

            "rejection":
                "N/A",

            "liquidity":
                "N/A",

            "volume_profile":
                None,

            "tradingview_context":
                [],
        }

    # ========================================================
    # WEIGHTED MULTI-TIMEFRAME SCORE
    # ========================================================

    weighted_score = 0

    total_weight = 0

    for timeframe, result in valid:

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
    )

    # ========================================================
    # BULL / BEAR DISTRIBUTION
    # ========================================================

    bullish = sum(

        1

        for _, result in valid

        if "Bullish"
        in result["direction"]
    )

    bearish = sum(

        1

        for _, result in valid

        if "Bearish"
        in result["direction"]
    )

    mixed = (
        len(valid)
        - bullish
        - bearish
    )

    count = len(valid)

    bullish_ratio = (
        bullish
        / count
    )

    bearish_ratio = (
        bearish
        / count
    )

    # ========================================================
    # OVERALL DIRECTION
    # ========================================================

    if (
        average_score >= 4
        and bullish_ratio >= 0.60
    ):

        overall = "Bullish"

    elif (
        average_score <= -4
        and bearish_ratio >= 0.60
    ):

        overall = "Bearish"

    elif (
        average_score >= 2
        and bullish_ratio >= 0.50
    ):

        overall = "Bullish Lean"

    elif (
        average_score <= -2
        and bearish_ratio >= 0.50
    ):

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / Mixed"
        )

    # ========================================================
    # EVIDENCE ALIGNMENT
    #
    # THIS IS NOT A PROFIT PROBABILITY.
    # ========================================================

    raw_strength = clamp(

        (
            abs(average_score)
            / 12
        ) * 100,

        0,
        100,
    )

    agreement = max(
        bullish_ratio,
        bearish_ratio,
    )

    alignment = max(

        0,

        (
            agreement
            - 0.50
        )
        / 0.50,
    )

    evidence_strength = clamp(

        raw_strength * 0.70
        + alignment * 30,

        0,
        100,
    )

    if evidence_strength >= 75:

        strength_label = (
            "High Evidence Alignment"
        )

    elif evidence_strength >= 55:

        strength_label = (
            "Moderate Evidence Alignment"
        )

    elif evidence_strength >= 35:

        strength_label = (
            "Developing"
        )

    else:

        strength_label = (
            "Weak / Conflicted"
        )

    # ========================================================
    # AGGREGATES
    # ========================================================

    rsi_values = [

        result["rsi"]

        for _, result in valid

        if result.get("rsi")
        is not None
    ]

    volume_values = [

        result["volume_ratio"]

        for _, result in valid

        if result.get(
            "volume_ratio"
        )
        is not None
    ]

    atr_values = [

        result["atr_percent"]

        for _, result in valid

        if result.get(
            "atr_percent"
        )
        is not None
    ]

    adx_values = [

        result["adx"]

        for _, result in valid

        if result.get("adx")
        is not None
    ]

    structure_score = mean([

        result[
            "structure_score"
        ]

        for _, result in valid
    ])

    if (
        structure_score is not None
        and structure_score > 0.75
    ):

        structure = "Bullish"

    elif (
        structure_score is not None
        and structure_score < -0.75
    ):

        structure = "Bearish"

    else:

        structure = "Mixed"

    # Prefer 1H for structure.
    latest = results.get(
        "1h"
    )

    if (
        not latest
        or not latest.get("valid")
    ):

        latest = valid[-1][1]

    latest_fvg = latest.get(
        "fvg",
        {},
    )

    # ========================================================
    # TRADINGVIEW CONTEXT
    # ========================================================

    tv_data = []

    for timeframe, _ in valid:

        tv = (
            get_tradingview_confirmation(
                coin,
                timeframe,
            )
        )

        if tv:

            tv_data.append({

                "timeframe":
                    timeframe,

                "signal":
                    str(
                        tv.get(
                            "signal",
                            "UNKNOWN",
                        )
                    ).upper(),
            })

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

            "strength":
                evidence_strength,

            "strength_label":
                strength_label,
        },

        "valid_count":
            count,

        "total_count":
            len(TIMEFRAMES),

        "bullish_count":
            bullish,

        "bearish_count":
            bearish,

        "mixed_count":
            mixed,

        "average_rsi":
            mean(rsi_values),

        "average_volume_ratio":
            mean(volume_values),

        "average_atr_percent":
            mean(atr_values),

        "average_adx":
            mean(adx_values),

        "structure":
            structure,

        "support":
            latest.get(
                "support"
            ),

        "support_2":
            latest.get(
                "support_2"
            ),

        "resistance":
            latest.get(
                "resistance"
            ),

        "resistance_2":
            latest.get(
                "resistance_2"
            ),

        "fvg":
            latest_fvg,

        "rejection":
            latest.get(
                "rejection"
            ),

        "liquidity":
            latest.get(
                "liquidity"
            ),

        "volume_profile":
            latest.get(
                "volume_profile"
            ),

        "tradingview_context":
            tv_data,
    }


# ============================================================
# TELEGRAM SCAN MESSAGE
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

    lines = [

        f"<b>🔎 {coin} DEEP MARKET ANALYSIS</b>",

        "",

        f"💰 <b>Price:</b> "
        f"{format_price(analysis['price'])}",

        "",

        f"{direction_emoji(overall['label'])} "
        f"<b>Overall:</b> "
        f"{overall['label']}",

        f"📊 <b>Analysis Score:</b> "
        f"{overall['score']:+.2f}",

        f"🎯 <b>Evidence Alignment:</b> "
        f"{overall['strength']:.0f}% "
        f"({overall['strength_label']})",

        "",

        "📊 <b>MULTI-TIMEFRAME READ</b>",
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

        provider = analysis[
            "providers"
        ].get(
            timeframe
        )

        if provider:

            provider_text = (
                f" • {provider}"
            )

        else:

            provider_text = (
                " • NO DATA"
            )

        lines.append(

            f"{direction_emoji(direction)} "
            f"<b>{timeframe}:</b> "
            f"{direction} "
            f"({score:+d})"
            f"{provider_text}"
        )

    # ========================================================
    # STRUCTURE
    # ========================================================

    one_hour = analysis[
        "timeframes"
    ].get(
        "1h",
        {},
    )

    if not one_hour.get(
        "valid"
    ):

        one_hour = {}

    structure_details = one_hour.get(
        "structure_details",
        [],
    )

    structure_detail_text = (

        ", ".join(
            structure_details
        )

        if structure_details

        else "N/A"
    )

    lines += [

        "",

        "🏗️ <b>MARKET STRUCTURE</b>",

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}",

        f"🔍 <b>Swing Read:</b> "
        f"{html.escape(structure_detail_text)}",

        f"📉 <b>Support:</b> "
        f"{format_level(analysis['support'])}",

        f"📉 <b>Support 2:</b> "
        f"{format_level(analysis['support_2'])}",

        f"📈 <b>Resistance:</b> "
        f"{format_level(analysis['resistance'])}",

        f"📈 <b>Resistance 2:</b> "
        f"{format_level(analysis['resistance_2'])}",

        f"🔺 <b>Latest Swing High:</b> "
        f"{format_level(one_hour.get('swing_high'))}",

        f"🔻 <b>Latest Swing Low:</b> "
        f"{format_level(one_hour.get('swing_low'))}",
    ]

    # ========================================================
    # LIQUIDITY / TRAPS
    # ========================================================

    lines += [

        "",

        "🧲 <b>LIQUIDITY / TRAP ANALYSIS</b>",

        f"🎯 <b>Liquidity Event:</b> "
        f"{analysis['liquidity']}",

        f"🕯️ <b>Rejection:</b> "
        f"{analysis['rejection']}",
    ]

    # ========================================================
    # FVG
    # ========================================================

    fvg = analysis[
        "fvg"
    ]

    lines += [

        "",

        "🟦 <b>FAIR VALUE GAP</b>",

        f"🟢 Bullish FVGs detected: "
        f"{len(fvg.get('bullish', []))}",

        f"🔴 Bearish FVGs detected: "
        f"{len(fvg.get('bearish', []))}",
    ]

    # ========================================================
    # MARKET CONDITIONS
    # ========================================================

    rsi = analysis.get(
        "average_rsi"
    )

    volume = analysis.get(
        "average_volume_ratio"
    )

    atr = analysis.get(
        "average_atr_percent"
    )

    adx = analysis.get(
        "average_adx"
    )

    lines += [

        "",

        "📈 <b>MARKET CONDITIONS</b>",

        (
            f"📉 <b>RSI:</b> "
            f"{rsi:.1f}"

            if rsi is not None

            else
            "📉 <b>RSI:</b> N/A"
        ),

        (
            f"📦 <b>Relative Volume:</b> "
            f"{volume:.2f}x"

            if volume is not None

            else
            "📦 <b>Relative Volume:</b> N/A"
        ),

        (
            f"🌊 <b>ATR:</b> "
            f"{atr:.2f}%"

            if atr is not None

            else
            "🌊 <b>ATR:</b> N/A"
        ),

        (
            f"📐 <b>ADX:</b> "
            f"{adx:.1f}"

            if adx is not None

            else
            "📐 <b>ADX:</b> N/A"
        ),
    ]

    # ========================================================
    # VOLUME PROFILE
    # ========================================================

    vp = analysis.get(
        "volume_profile"
    )

    lines += [

        "",

        "📊 <b>VOLUME PROFILE</b>",

        (
            f"🎯 <b>Approx. POC:</b> "
            f"{format_level(vp['poc'])}"

            if vp

            else
            "🎯 <b>POC:</b> N/A"
        ),
    ]

    # ========================================================
    # TRADINGVIEW
    # ========================================================

    tv_context = analysis.get(
        "tradingview_context"
    )

    if tv_context:

        lines += [

            "",

            "📡 <b>TRADINGVIEW EXTRA CONTEXT</b>",
        ]

        for item in tv_context:

            lines.append(

                f"• {item['timeframe']}: "
                f"{html.escape(item['signal'])}"
            )

    # ========================================================
    # DATA QUALITY
    # ========================================================

    lines += [

        "",

        f"📡 <b>Data Coverage:</b> "
        f"{analysis['valid_count']}/"
        f"{analysis['total_count']} "
        f"timeframes",

        "",

        "⚠️ <b>Important:</b> "
        "Evidence alignment is NOT "
        "a probability of profit. "
        "The engine compares multiple "
        "technical conditions and can "
        "return <b>Consolidation / Mixed</b> "
        "when the evidence conflicts.",
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

            "❌ Unsupported cryptocurrency.",

            chat_id,

            main_menu(),
        )

        return

    send_telegram(

        (
            f"<b>🔎 Deep-scanning "
            f"{html.escape(coin)}...</b>\n\n"

            "📡 Live market data\n"
            "📈 EMA trend\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📐 ADX\n"
            "📏 VWAP\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market structure\n"
            "🔺 Swing highs/lows\n"
            "🛡️ Support/resistance\n"
            "🟦 Fair-value gaps\n"
            "🧲 Liquidity sweeps\n"
            "🕯️ Rejection candles\n"
            "📊 Volume profile"
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

    except Exception as exc:

        print(
            "SCAN ERROR:",
            repr(exc),
        )

        send_telegram(

            (
                "<b>⚠️ SCAN ERROR</b>\n\n"

                f"<code>"
                f"{html.escape(str(exc))}"
                f"</code>"
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

    except Exception as exc:

        print(
            "NEWS ERROR:",
            repr(exc),
        )

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
            "<b>🤖 SIDESHIFT AI 4.0</b>\n\n"

            "Deep multi-timeframe cryptocurrency "
            "market analysis.\n\n"

            "<b>Core analysis:</b>\n"

            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📐 ADX\n"
            "📏 VWAP\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market Structure\n"
            "🔺 Swing Highs/Lows\n"
            "🛡️ Support/Resistance\n"
            "🟦 Fair Value Gaps\n"
            "🧲 Liquidity Sweeps\n"
            "🕯️ Rejection Candles\n"
            "📊 Volume Profile\n\n"

            "The engine evaluates both "
            "<b>bullish AND bearish</b> evidence "
            "and can remain mixed when conditions "
            "conflict.\n\n"

            "TradingView is optional extra context; "
            "it is not required for the core scan."
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
            "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"

            "The bot reads live market candles "
            "across:\n\n"

            "5m • 15m • 1h • 4h • 1D\n\n"

            "It evaluates trend, momentum, volume, "
            "volatility, market structure, swings, "
            "support/resistance, liquidity events, "
            "rejection candles, fair-value gaps "
            "and volume distribution.\n\n"

            "4H data can be built from 1H candles "
            "when direct 4H data is unavailable.\n\n"

            "TradingView alerts are optional "
            "additional context."
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
        # MESSAGE
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

                            "Examples:\n"
                            "/scan BTC\n"
                            "/scan ETH\n"
                            "/scan SOL\n"
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

            answer_callback(
                callback.get("id")
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

            if callback_data == (
                "scan_menu"
            ):

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

    except Exception as exc:

        print(
            "TELEGRAM WEBHOOK ERROR:",
            repr(exc),
        )

        return jsonify({

            "ok":
                False,

            "error":
                str(exc),

        }), 500


# ============================================================
# OPTIONAL TRADINGVIEW WEBHOOK
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

        signal = str(
            data.get(
                "signal",
                "UNKNOWN",
            )
        ).upper()

        symbol = (
            symbol
            .replace(".P", "")
            .replace("/", "")
            .replace(" ", "")
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

        print(
            "TRADINGVIEW:",
            symbol,
            timeframe,
            signal,
        )

        # TradingView is supplemental only.
        # No automatic Telegram message is sent here.

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
# HOME / HEALTH
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

        "features": [

            "EMA",

            "RSI",

            "MACD",

            "ADX",

            "VWAP",

            "ATR",

            "Volume",

            "Volume Profile",

            "Swing Highs",

            "Swing Lows",

            "Market Structure",

            "Support",

            "Resistance",

            "Fair Value Gaps",

            "Liquidity Sweeps",

            "Rejection Candles",

            "Multi-Timeframe Analysis",

            "4H 1H Aggregation Fallback",

            "Optional TradingView Context",
        ],
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
                list(COINS.keys()),

        }), 400

    try:

        return jsonify(
            scan_coin(
                coin
            )
        )

    except Exception as exc:

        print(
            "MARKET TEST ERROR:",
            repr(exc),
        )

        return jsonify({

            "error":
                str(exc),

        }), 500


# ============================================================
# TELEGRAM WEBHOOK SETUP
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

    domain = (
        RAILWAY_PUBLIC_DOMAIN
        .strip()
    )

    if domain.startswith(
        "https://"
    ):

        domain = domain[
            len("https://"):
        ]

    elif domain.startswith(
        "http://"
    ):

        domain = domain[
            len("http://"):
        ]

    domain = domain.rstrip(
        "/"
    )

    webhook_url = (
        f"https://"
        f"{domain}"
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

    except Exception as exc:

        print(
            "WEBHOOK SET ERROR:",
            repr(exc),
        )

        return False


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "======================================"
    )

    print(
        "SideShift AI 4.0 starting..."
    )

    print(
        "======================================"
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
        or "MISSING",
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