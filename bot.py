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
    if TELEGRAM_BOT_TOKEN
    else None
)

REQUEST_TIMEOUT = 15


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


# ============================================================
# OPTIONAL TRADINGVIEW ALERT CACHE
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

        print("TELEGRAM ERROR:", repr(e))
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
# BASIC MATH
# ============================================================

def safe_float(value):

    try:
        return float(value)
    except Exception:
        return None


def mean(values):

    values = [
        x for x in values
        if x is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def clamp(value, minimum, maximum):

    return max(
        minimum,
        min(maximum, value)
    )


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return [None] * len(values)

    result = [None] * len(values)

    multiplier = 2 / (period + 1)

    previous = sum(
        values[:period]
    ) / period

    result[period - 1] = previous

    for i in range(period, len(values)):

        previous = (
            values[i] * multiplier
            + previous * (1 - multiplier)
        )

        result[i] = previous

    return result


# ============================================================
# SMA
# ============================================================

def sma(values, period):

    result = [None] * len(values)

    if len(values) < period:
        return result

    running = sum(values[:period])

    result[period - 1] = (
        running / period
    )

    for i in range(period, len(values)):

        running += values[i]
        running -= values[i - period]

        result[i] = (
            running / period
        )

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

    for i in range(period, len(gains)):

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


# ============================================================
# ATR
# ============================================================

def calculate_atr(candles, period=14):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

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


# ============================================================
# BOLLINGER BANDS
# ============================================================

def calculate_bollinger(
    closes,
    period=20,
    deviations=2,
):

    if len(closes) < period:
        return None

    window = closes[-period:]

    middle = sum(window) / period

    variance = (
        sum(
            (x - middle) ** 2
            for x in window
        )
        / period
    )

    std = math.sqrt(variance)

    upper = (
        middle
        + deviations * std
    )

    lower = (
        middle
        - deviations * std
    )

    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
    }


# ============================================================
# ADX
# ============================================================

def calculate_adx(candles, period=14):

    if len(candles) < period * 2 + 1:
        return None

    trs = []
    plus_dm = []
    minus_dm = []

    for i in range(1, len(candles)):

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

        up = (
            high_move
            if high_move > low_move
            and high_move > 0
            else 0
        )

        down = (
            low_move
            if low_move > high_move
            and low_move > 0
            else 0
        )

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

        trs.append(tr)
        plus_dm.append(up)
        minus_dm.append(down)

    if len(trs) < period:
        return None

    atr = sum(
        trs[:period]
    ) / period

    p_dm = sum(
        plus_dm[:period]
    ) / period

    m_dm = sum(
        minus_dm[:period]
    ) / period

    dx_values = []

    for i in range(
        period,
        len(trs)
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

        dx = (
            100
            * abs(
                plus_di
                - minus_di
            )
            / denominator
        )

        dx_values.append(
            dx
        )

    if len(dx_values) < period:
        return None

    adx = sum(
        dx_values[:period]
    ) / period

    for value in dx_values[period:]:

        adx = (
            (
                adx * (period - 1)
                + value
            )
            / period
        )

    return adx


# ============================================================
# VWAP
# ============================================================

def calculate_vwap(candles, lookback=100):

    candles = candles[-lookback:]

    if not candles:
        return None

    cumulative_pv = 0
    cumulative_volume = 0

    for candle in candles:

        typical_price = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        volume = candle["volume"]

        cumulative_pv += (
            typical_price * volume
        )

        cumulative_volume += volume

    if cumulative_volume == 0:
        return None

    return (
        cumulative_pv
        / cumulative_volume
    )


# ============================================================
# VOLUME PROFILE APPROXIMATION
# ============================================================

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
            (typical - low)
            / bucket_size
        )

        index = clamp(
            index,
            0,
            bins - 1,
        )

        profile[index] += (
            candle["volume"]
        )

    poc_index = max(
        range(bins),
        key=lambda i: profile[i]
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
# SWING HIGHS / LOWS
# ============================================================

def find_swings(
    candles,
    left=3,
    right=3,
):

    swing_highs = []
    swing_lows = []

    if len(candles) < (
        left + right + 1
    ):
        return swing_highs, swing_lows

    for i in range(
        left,
        len(candles) - right
    ):

        current = candles[i]

        is_high = all(
            current["high"]
            > candles[j]["high"]
            for j in range(
                i - left,
                i + right + 1
            )
            if j != i
        )

        is_low = all(
            current["low"]
            < candles[j]["low"]
            for j in range(
                i - left,
                i + right + 1
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
        swing_highs[-8:],
        swing_lows[-8:],
    )


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

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
        "support": (
            supports[0]
            if supports
            else None
        ),
        "support_2": (
            supports[1]
            if len(supports) > 1
            else None
        ),
        "resistance": (
            resistances[0]
            if resistances
            else None
        ),
        "resistance_2": (
            resistances[1]
            if len(resistances) > 1
            else None
        ),
    }


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def detect_fvg(candles):

    bullish = []
    bearish = []

    if len(candles) < 3:
        return {
            "bullish": bullish,
            "bearish": bearish,
        }

    for i in range(
        2,
        len(candles)
    ):

        first = candles[i - 2]
        third = candles[i]

        # Bullish FVG:
        # current low > candle two bars earlier high

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

        # Bearish FVG:
        # current high < candle two bars earlier low

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


# ============================================================
# REJECTION CANDLES
# ============================================================

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
        body = (
            candle["high"]
            - candle["low"]
        ) * 0.01

    if (
        lower_wick > body * 2
        and lower_wick > upper_wick
    ):

        return "Bullish Rejection"

    if (
        upper_wick > body * 2
        and upper_wick > lower_wick
    ):

        return "Bearish Rejection"

    return "None"


# ============================================================
# LIQUIDITY SWEEP / TRAP
# ============================================================

def detect_liquidity_event(
    candles,
    swing_highs,
    swing_lows,
):

    if len(candles) < 2:
        return "None"

    current = candles[-1]

    previous_high = (
        max(swing_highs)
        if swing_highs
        else None
    )

    previous_low = (
        min(swing_lows)
        if swing_lows
        else None
    )

    # Sweep above resistance and close back below
    if (
        previous_high is not None
        and current["high"]
        > previous_high
        and current["close"]
        < previous_high
    ):

        return "Bearish Liquidity Sweep"

    # Sweep below support and close back above
    if (
        previous_low is not None
        and current["low"]
        < previous_low
        and current["close"]
        > previous_low
    ):

        return "Bullish Liquidity Sweep"

    return "None"


# ============================================================
# MARKET STRUCTURE
# ============================================================

def analyze_structure(
    swing_highs,
    swing_lows,
):

    if (
        len(swing_highs) < 2
        or len(swing_lows) < 2
    ):

        return {
            "label": "Insufficient Swing Data",
            "score": 0,
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

    if higher_high and higher_low:

        return {
            "label": "Bullish Structure",
            "score": 2,
        }

    if lower_high and lower_low:

        return {
            "label": "Bearish Structure",
            "score": -2,
        }

    if higher_high:

        return {
            "label": "Higher-High Structure",
            "score": 1,
        }

    if lower_low:

        return {
            "label": "Lower-Low Structure",
            "score": -1,
        }

    return {
        "label": "Mixed Structure",
        "score": 0,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(candles):

    if len(candles) < 80:

        return {
            "valid": False,
            "direction": "Data Unavailable",
            "score": 0,
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
        find_swings(candles)
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

    fvg = detect_fvg(candles)

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
    # EMA TREND
    # --------------------------------------------------------

    if (
        ema20[-1] is not None
        and price > ema20[-1]
    ):

        score += 2
        reasons.append(
            "Price above EMA20"
        )

    elif ema20[-1] is not None:

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

    # --------------------------------------------------------
    # LONGER TREND
    # --------------------------------------------------------

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

        if 55 <= rsi < 70:

            score += 1
            reasons.append(
                "RSI bullish momentum"
            )

        elif 30 < rsi <= 45:

            score -= 1
            reasons.append(
                "RSI bearish momentum"
            )

        elif rsi >= 70:

            # Do not automatically call overbought bearish.
            reasons.append(
                "RSI overbought"
            )

        elif rsi <= 30:

            reasons.append(
                "RSI oversold"
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

        else:

            trend_strength = "Weak"

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

    if rejection == "Bullish Rejection":

        score += 1
        reasons.append(
            "Bullish rejection candle"
        )

    elif rejection == "Bearish Rejection":

        score -= 1
        reasons.append(
            "Bearish rejection candle"
        )

    # --------------------------------------------------------
    # LIQUIDITY SWEEP
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
    # FVG CONTEXT
    # --------------------------------------------------------

    bullish_fvg_count = len(
        fvg["bullish"]
    )

    bearish_fvg_count = len(
        fvg["bearish"]
    )

    # Only use FVG as a contextual factor,
    # not as an automatic buy/sell trigger.

    if bullish_fvg_count > bearish_fvg_count:

        score += 1

    elif bearish_fvg_count > bullish_fvg_count:

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
    # FINAL DIRECTION
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

        direction = "Consolidation / Mixed"

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr_percent = None

    if (
        atr is not None
        and price > 0
    ):

        atr_percent = (
            atr / price
        ) * 100

    return {
        "valid": True,

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
            reasons[-8:],
    }


# ============================================================
# BINANCE NORMALIZATION
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


# ============================================================
# COINBASE NORMALIZATION
# ============================================================

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
# BINANCE CANDLES
# ============================================================

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
                    "SideShiftAI/3.0"
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

        if not isinstance(data, list):

            return []

        return normalize_binance(
            data
        )

    except Exception as e:

        print(
            "BINANCE REQUEST ERROR:",
            repr(e),
        )

        return []


# ============================================================
# COINBASE CANDLES
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
                    "SideShiftAI/3.0"
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

    except Exception as e:

        print(
            "COINBASE REQUEST ERROR:",
            repr(e),
        )

        return []


# ============================================================
# RESAMPLE 1H -> 4H
# ============================================================

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
            []
        ).append(candle)

    result = []

    for bucket in sorted(
        groups.keys()
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


# ============================================================
# MARKET DATA
# ============================================================

def get_market_candles(
    coin,
    timeframe,
):

    binance_symbol, coinbase_symbol = (
        COINS[coin]
    )

    config = TIMEFRAMES[
        timeframe
    ]

    interval = config[
        "binance"
    ]

    # --------------------------------------------------------
    # PRIMARY BINANCE
    # --------------------------------------------------------

    candles = get_binance_candles(
        binance_symbol,
        interval,
        250,
    )

    if len(candles) >= 80:

        return candles, "Binance"

    # --------------------------------------------------------
    # 4H SPECIAL FALLBACK
    # --------------------------------------------------------

    if timeframe == "4h":

        one_hour = get_binance_candles(
            binance_symbol,
            "1h",
            1000,
        )

        four_hour = aggregate_candles(
            one_hour,
            14400,
        )

        if len(four_hour) >= 80:

            return (
                four_hour[-250:],
                "Binance 1H→4H",
            )

    # --------------------------------------------------------
    # COINBASE FALLBACK
    # --------------------------------------------------------

    candles = get_coinbase_candles(
        coinbase_symbol,
        config["seconds"],
    )

    if len(candles) >= 80:

        return candles, "Coinbase"

    # --------------------------------------------------------
    # COINBASE 1H → 4H FALLBACK
    # --------------------------------------------------------

    if timeframe == "4h":

        one_hour = get_coinbase_candles(
            coinbase_symbol,
            3600,
        )

        four_hour = aggregate_candles(
            one_hour,
            14400,
        )

        if len(four_hour) >= 80:

            return (
                four_hour[-250:],
                "Coinbase 1H→4H",
            )

    return [], None


# ============================================================
# OPTIONAL TRADINGVIEW DATA
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
                    "Insufficient data",
            },

            "valid_count":
                0,

            "total_count":
                len(TIMEFRAMES),
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

    bullish = 0
    bearish = 0
    mixed = 0

    for _, result in valid:

        direction = result[
            "direction"
        ]

        if "Bullish" in direction:

            bullish += 1

        elif "Bearish" in direction:

            bearish += 1

        else:

            mixed += 1

    count = len(valid)

    # ========================================================
    # MULTI-TIMEFRAME AGREEMENT
    # ========================================================

    bullish_ratio = (
        bullish / count
    )

    bearish_ratio = (
        bearish / count
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

    elif average_score >= 2:

        overall = "Bullish Lean"

    elif average_score <= -2:

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / Mixed"
        )

    # ========================================================
    # STRENGTH — NOT A PROBABILITY
    # ========================================================

    raw_strength = (
        abs(average_score)
        / 12
    ) * 100

    agreement_bonus = (
        max(
            bullish_ratio,
            bearish_ratio,
        )
        * 20
    )

    strength = clamp(
        raw_strength
        + agreement_bonus,
        0,
        100,
    )

    if strength >= 75:

        strength_label = "Strong"

    elif strength >= 55:

        strength_label = "Moderate"

    elif strength >= 35:

        strength_label = "Developing"

    else:

        strength_label = "Weak / Mixed"

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

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    latest = valid[-1][1]

    support = latest.get(
        "support"
    )

    resistance = latest.get(
        "resistance"
    )

    # ========================================================
    # FVG SUMMARY
    # ========================================================

    latest_fvg = latest.get(
        "fvg",
        {}
    )

    # ========================================================
    # TRADINGVIEW OPTIONAL CONTEXT
    # ========================================================

    tv_data = []

    for timeframe, _ in valid:

        tv = get_tradingview_confirmation(
            coin,
            timeframe,
        )

        if tv:

            tv_data.append({
                "timeframe":
                    timeframe,

                "signal":
                    str(
                        tv.get(
                            "signal",
                            "UNKNOWN"
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
                strength,

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
            support,

        "resistance":
            resistance,

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
# PRICE FORMAT
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
# SCAN MESSAGE
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
        f"{overall['score']:.2f}",

        f"🎯 <b>Evidence Strength:</b> "
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
        ].get(timeframe)

        if provider:

            provider_text = (
                f" • {provider}"
            )

        else:

            provider_text = ""

        lines.append(
            f"{direction_emoji(direction)} "
            f"<b>{timeframe}:</b> "
            f"{direction} "
            f"({score:+d})"
            f"{provider_text}"
        )

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    lines += [

        "",

        "🏗️ <b>MARKET STRUCTURE</b>",

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}",

        f"📉 <b>Support:</b> "
        f"{format_level(analysis['support'])}",

        f"📈 <b>Resistance:</b> "
        f"{format_level(analysis['resistance'])}",

        f"🔺 <b>Latest Swing High:</b> "
        f"{format_level("
        f"analysis['timeframes']["
        f"'1h'"
        f"].get('swing_high')"
        f")}",

        f"🔻 <b>Latest Swing Low:</b> "
        f"{format_level("
        f"analysis['timeframes']["
        f"'1h'"
        f"].get('swing_low')"
        f")}",
    ]

    # --------------------------------------------------------
    # LIQUIDITY / TRAPS
    # --------------------------------------------------------

    lines += [

        "",

        "🧲 <b>LIQUIDITY / TRAP ANALYSIS</b>",

        f"🎯 <b>Liquidity Event:</b> "
        f"{analysis['liquidity']}",

        f"🕯️ <b>Rejection:</b> "
        f"{analysis['rejection']}",
    ]

    # --------------------------------------------------------
    # FVG
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MARKET CONDITIONS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # TRADINGVIEW
    # --------------------------------------------------------

    tv_context = analysis.get(
        "tradingview_context"
    )

    # We ONLY display this section when actual
    # TradingView webhook data exists.

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

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    lines += [

        "",

        f"📡 <b>Data Coverage:</b> "
        f"{analysis['valid_count']}/"
        f"{analysis['total_count']} "
        f"timeframes",

        "",

        "⚠️ <b>Important:</b> "
        "Analysis strength is not a probability "
        "of profit. The engine weighs multiple "
        "technical conditions and can remain "
        "mixed when the evidence conflicts.",
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
            f"<b>🔎 Deep-scanning {coin}...</b>\n\n"

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
            "<b>🤖 SIDESHIFT AI 3.0</b>\n\n"

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
            "do not agree."
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

            "The bot reads live market candles "
            "across:\n\n"

            "5m • 15m • 1h • 4h • 1D\n\n"

            "It evaluates trend, momentum, "
            "volume, volatility, market structure, "
            "swings, support/resistance, liquidity "
            "events, rejection candles, fair-value "
            "gaps and volume distribution.\n\n"

            "TradingView alerts can also be accepted "
            "as an optional additional context source."
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

            # MUST COME BEFORE scan_*

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

        signal = str(
            data.get(
                "signal",
                "UNKNOWN",
            )
        ).upper()

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

        # Optional notification.
        # This does NOT affect the core analysis.

        if TELEGRAM_CHAT_ID:

            send_telegram(

                (
                    "<b>📡 TRADINGVIEW DATA RECEIVED</b>\n\n"
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
            "3.0",

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
            "Support",
            "Resistance",
            "Fair Value Gaps",
            "Liquidity Sweeps",
            "Rejection Candles",
            "Multi-Timeframe Analysis",
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
def test_market(coin):

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
            scan_coin(coin)
        )

    except Exception as e:

        return jsonify({

            "error":
                str(e),

        }), 500


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
            repr(e),
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
        "SideShift AI 3.0 starting..."
    )

    print(
        "======================================"
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