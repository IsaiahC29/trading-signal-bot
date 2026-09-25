import os
import html
import time
import requests
import feedparser

from flask import Flask, request, jsonify

app = Flask(__name__)

# ============================================================
# ENVIRONMENT
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

# TradingView information is optional.
# It NEVER replaces our own market analysis.
TRADINGVIEW_CACHE = {}


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
    "4h": ("4h", 14400, 1.4),
    "1D": ("1d", 86400, 1.6),
}


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


def sma(values, period):

    if len(values) < period:
        return [None] * len(values)

    result = [None] * len(values)

    for i in range(period - 1, len(values)):

        result[i] = (
            sum(values[i - period + 1:i + 1])
            / period
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

    ema12 = ema(
        closes,
        12,
    )

    ema26 = ema(
        closes,
        26,
    )

    macd_values = []

    for i in range(len(closes)):

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

    if (
        not signal_values
        or signal_values[-1] is None
    ):
        return None

    value = macd_values[-1]

    signal = signal_values[-1]

    return {
        "value": value,
        "signal": signal,
        "histogram":
            value - signal,
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
# BINANCE DATA
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
                    500,
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
# COINBASE DATA
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
            )

            return []

        candles = normalize_coinbase(
            response.json()
        )

        return candles[-500:]

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

    binance_symbol, coinbase_symbol = (
        COINS[coin]
    )

    (
        binance_interval,
        coinbase_seconds,
        _
    ) = TIMEFRAMES[timeframe]

    candles = get_binance_candles(
        binance_symbol,
        binance_interval,
    )

    if len(candles) >= 60:

        return candles, "Binance"

    candles = get_coinbase_candles(
        coinbase_symbol,
        coinbase_seconds,
    )

    if len(candles) >= 60:

        return candles, "Coinbase"

    return [], None


# ============================================================
# SWING HIGH / LOW
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

        return (
            swing_highs,
            swing_lows
        )

    for i in range(
        left,
        len(candles) - right
    ):

        current = candles[i]

        high_is_swing = True
        low_is_swing = True

        for j in range(
            i - left,
            i + right + 1
        ):

            if j == i:
                continue

            if candles[j]["high"] >= current["high"]:
                high_is_swing = False

            if candles[j]["low"] <= current["low"]:
                low_is_swing = False

        if high_is_swing:

            swing_highs.append({
                "index": i,
                "price":
                    current["high"],
            })

        if low_is_swing:

            swing_lows.append({
                "index": i,
                "price":
                    current["low"],
            })

    return (
        swing_highs,
        swing_lows
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_structure(candles):

    swing_highs, swing_lows = (
        find_swings(candles)
    )

    if (
        len(swing_highs) < 2
        or len(swing_lows) < 2
    ):

        return {

            "label":
                "Insufficient Structure",

            "score":
                0,

            "swing_high":
                None,

            "swing_low":
                None,

            "break":
                None,
        }

    previous_high = (
        swing_highs[-2]["price"]
    )

    latest_high = (
        swing_highs[-1]["price"]
    )

    previous_low = (
        swing_lows[-2]["price"]
    )

    latest_low = (
        swing_lows[-1]["price"]
    )

    higher_high = (
        latest_high
        > previous_high
    )

    higher_low = (
        latest_low
        > previous_low
    )

    lower_high = (
        latest_high
        < previous_high
    )

    lower_low = (
        latest_low
        < previous_low
    )

    current_price = candles[-1]["close"]

    bullish_break = (
        current_price
        > latest_high
    )

    bearish_break = (
        current_price
        < latest_low
    )

    if (
        bullish_break
        and higher_low
    ):

        label = "Bullish Breakout"
        score = 3

    elif (
        bearish_break
        and lower_high
    ):

        label = "Bearish Breakdown"
        score = -3

    elif (
        higher_high
        and higher_low
    ):

        label = "Bullish Structure"
        score = 2

    elif (
        lower_high
        and lower_low
    ):

        label = "Bearish Structure"
        score = -2

    elif higher_low:

        label = "Bullish Lean"
        score = 1

    elif lower_high:

        label = "Bearish Lean"
        score = -1

    else:

        label = "Mixed Structure"
        score = 0

    return {

        "label":
            label,

        "score":
            score,

        "swing_high":
            latest_high,

        "swing_low":
            latest_low,

        "previous_swing_high":
            previous_high,

        "previous_swing_low":
            previous_low,

        "break":
            (
                "Bullish"
                if bullish_break
                else
                "Bearish"
                if bearish_break
                else
                None
            ),
    }


# ============================================================
# SUPPORT / RESISTANCE
# ============================================================

def calculate_support_resistance(
    candles
):

    if len(candles) < 30:

        return {
            "support": None,
            "resistance": None,
        }

    price = candles[-1]["close"]

    swing_highs, swing_lows = (
        find_swings(candles)
    )

    resistance_candidates = [
        x["price"]
        for x in swing_highs
        if x["price"] > price
    ]

    support_candidates = [
        x["price"]
        for x in swing_lows
        if x["price"] < price
    ]

    resistance = (
        min(resistance_candidates)
        if resistance_candidates
        else None
    )

    support = (
        max(support_candidates)
        if support_candidates
        else None
    )

    recent_high = max(
        x["high"]
        for x in candles[-50:]
    )

    recent_low = min(
        x["low"]
        for x in candles[-50:]
    )

    if resistance is None:
        resistance = recent_high

    if support is None:
        support = recent_low

    return {
        "support": support,
        "resistance": resistance,
    }


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def find_fair_value_gaps(
    candles
):

    gaps = []

    if len(candles) < 3:
        return gaps

    for i in range(
        2,
        len(candles)
    ):

        first = candles[i - 2]
        middle = candles[i - 1]
        third = candles[i]

        # Bullish FVG:
        # third candle low > first candle high

        if (
            third["low"]
            > first["high"]
        ):

            gaps.append({

                "type":
                    "Bullish",

                "low":
                    first["high"],

                "high":
                    third["low"],

                "index":
                    i,

                "active":
                    True,
            })

        # Bearish FVG:
        # third candle high < first candle low

        if (
            third["high"]
            < first["low"]
        ):

            gaps.append({

                "type":
                    "Bearish",

                "low":
                    third["high"],

                "high":
                    first["low"],

                "index":
                    i,

                "active":
                    True,
            })

    return gaps[-20:]


def evaluate_fair_value_gaps(
    candles
):

    gaps = find_fair_value_gaps(
        candles
    )

    if not gaps:
        return {
            "bullish": [],
            "bearish": [],
            "score": 0,
        }

    current_price = candles[-1]["close"]

    bullish = []
    bearish = []

    for gap in gaps:

        touched = False

        for candle in candles[
            gap["index"] + 1:
        ]:

            if (
                candle["low"]
                <= gap["high"]
                and
                candle["high"]
                >= gap["low"]
            ):

                touched = True
                break

        if touched:
            continue

        if gap["type"] == "Bullish":

            bullish.append(gap)

        else:

            bearish.append(gap)

    score = 0

    if bullish:
        score += 1

    if bearish:
        score -= 1

    return {
        "bullish": bullish[-3:],
        "bearish": bearish[-3:],
        "score": score,
    }


# ============================================================
# VOLUME PROFILE APPROXIMATION
# ============================================================

def calculate_volume_profile(
    candles,
    bins=24,
):

    if len(candles) < 30:

        return {
            "poc": None,
            "vah": None,
            "val": None,
            "hvn": [],
            "lvn": [],
        }

    window = candles[-150:]

    lowest = min(
        c["low"]
        for c in window
    )

    highest = max(
        c["high"]
        for c in window
    )

    if highest <= lowest:

        return {
            "poc": None,
            "vah": None,
            "val": None,
            "hvn": [],
            "lvn": [],
        }

    step = (
        highest - lowest
    ) / bins

    volumes = [
        0.0
        for _ in range(bins)
    ]

    for candle in window:

        typical_price = (
            candle["high"]
            + candle["low"]
            + candle["close"]
        ) / 3

        index = int(
            (
                typical_price
                - lowest
            )
            / step
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

    poc = (
        lowest
        + (
            poc_index
            + 0.5
        )
        * step
    )

    total_volume = sum(
        volumes
    )

    target_volume = (
        total_volume * 0.70
    )

    included = {
        poc_index
    }

    current_volume = (
        volumes[poc_index]
    )

    while (
        current_volume
        < target_volume
    ):

        left = (
            min(included)
            - 1
        )

        right = (
            max(included)
            + 1
        )

        left_volume = (
            volumes[left]
            if left >= 0
            else -1
        )

        right_volume = (
            volumes[right]
            if right < bins
            else -1
        )

        if (
            left_volume < 0
            and right_volume < 0
        ):
            break

        if (
            right_volume
            >= left_volume
        ):

            included.add(
                right
            )

            current_volume += (
                right_volume
            )

        else:

            included.add(
                left
            )

            current_volume += (
                left_volume
            )

    val_index = min(
        included
    )

    vah_index = max(
        included
    )

    val = (
        lowest
        + val_index
        * step
    )

    vah = (
        lowest
        + (
            vah_index + 1
        )
        * step
    )

    average_volume = (
        sum(volumes)
        / len(volumes)
    )

    hvn = []

    lvn = []

    for i, volume in enumerate(
        volumes
    ):

        level = (
            lowest
            + (
                i + 0.5
            )
            * step
        )

        if (
            volume
            >= average_volume
            * 1.5
        ):

            hvn.append(level)

        elif (
            volume
            <= average_volume
            * 0.50
        ):

            lvn.append(level)

    return {

        "poc":
            poc,

        "vah":
            vah,

        "val":
            val,

        "hvn":
            hvn[-8:],

        "lvn":
            lvn[-8:],
    }


# ============================================================
# LIQUIDITY SWEEPS / POSSIBLE TRAPS
# ============================================================

def detect_liquidity_events(
    candles
):

    if len(candles) < 30:

        return {
            "bullish_sweep": False,
            "bearish_sweep": False,
            "score": 0,
        }

    swing_highs, swing_lows = (
        find_swings(candles)
    )

    current = candles[-1]

    bullish_sweep = False
    bearish_sweep = False

    if swing_highs:

        previous_high = (
            swing_highs[-1]["price"]
        )

        if (
            current["high"]
            > previous_high
            and
            current["close"]
            < previous_high
        ):

            bearish_sweep = True

    if swing_lows:

        previous_low = (
            swing_lows[-1]["price"]
        )

        if (
            current["low"]
            < previous_low
            and
            current["close"]
            > previous_low
        ):

            bullish_sweep = True

    score = 0

    if bullish_sweep:
        score += 2

    if bearish_sweep:
        score -= 2

    return {

        "bullish_sweep":
            bullish_sweep,

        "bearish_sweep":
            bearish_sweep,

        "score":
            score,
    }


# ============================================================
# REJECTION
# ============================================================

def detect_rejection(
    candles
):

    if len(candles) < 20:

        return {
            "type": None,
            "score": 0,
        }

    candle = candles[-1]

    body = abs(
        candle["close"]
        - candle["open"]
    )

    upper_wick = (
        candle["high"]
        - max(
            candle["open"],
            candle["close"]
        )
    )

    lower_wick = (
        min(
            candle["open"],
            candle["close"]
        )
        - candle["low"]
    )

    if body == 0:

        body = (
            candle["high"]
            - candle["low"]
        ) * 0.05

    if (
        upper_wick
        > body * 2
        and
        upper_wick
        > lower_wick
    ):

        return {
            "type":
                "Bearish Rejection",

            "score":
                -1,
        }

    if (
        lower_wick
        > body * 2
        and
        lower_wick
        > upper_wick
    ):

        return {
            "type":
                "Bullish Rejection",

            "score":
                1,
        }

    return {
        "type": None,
        "score": 0,
    }


# ============================================================
# VOLUME ANALYSIS
# ============================================================

def calculate_volume_analysis(
    candles
):

    if len(candles) < 21:

        return {
            "ratio": None,
            "trend": "Unavailable",
            "score": 0,
        }

    recent = candles[-1]["volume"]

    average = (
        sum(
            c["volume"]
            for c in candles[-21:-1]
        )
        / 20
    )

    if average <= 0:

        return {
            "ratio": None,
            "trend": "Unavailable",
            "score": 0,
        }

    ratio = (
        recent / average
    )

    price_change = (
        candles[-1]["close"]
        - candles[-2]["close"]
    )

    score = 0

    if ratio >= 1.5:

        if price_change > 0:
            score = 1
            trend = "Strong buying volume"

        elif price_change < 0:
            score = -1
            trend = "Strong selling volume"

        else:
            trend = "High volume"

    elif ratio >= 1.1:

        if price_change > 0:
            score = 1
            trend = "Increasing buying volume"

        elif price_change < 0:
            score = -1
            trend = "Increasing selling volume"

        else:
            trend = "Increasing volume"

    else:

        trend = "Normal / Low volume"

    return {

        "ratio":
            ratio,

        "trend":
            trend,

        "score":
            score,
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    candles
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

    support_resistance = (
        calculate_support_resistance(
            candles
        )
    )

    fvg = (
        evaluate_fair_value_gaps(
            candles
        )
    )

    volume_profile = (
        calculate_volume_profile(
            candles
        )
    )

    liquidity = (
        detect_liquidity_events(
            candles
        )
    )

    rejection = (
        detect_rejection(
            candles
        )
    )

    volume = (
        calculate_volume_analysis(
            candles
        )
    )

    score = 0

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if (
        ema20[-1] is not None
        and price > ema20[-1]
    ):

        score += 2

    elif ema20[-1] is not None:

        score -= 2

    if (
        ema20[-1] is not None
        and ema50[-1] is not None
    ):

        if ema20[-1] > ema50[-1]:
            score += 2
        else:
            score -= 2

    if ema200[-1] is not None:

        if price > ema200[-1]:
            score += 1
        else:
            score -= 1

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
    )

    if percent_change > 0.5:
        score += 2

    elif percent_change > 0.15:
        score += 1

    elif percent_change < -0.5:
        score -= 2

    elif percent_change < -0.15:
        score -= 1

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi is not None:

        if rsi >= 55:
            score += 1

        elif rsi <= 45:
            score -= 1

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd:

        if macd["histogram"] > 0:
            score += 1

        elif macd["histogram"] < 0:
            score -= 1

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    score += (
        structure["score"]
    )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    score += (
        volume["score"]
    )

    # --------------------------------------------------------
    # FVG
    # --------------------------------------------------------

    score += (
        fvg["score"]
    )

    # --------------------------------------------------------
    # LIQUIDITY
    # --------------------------------------------------------

    score += (
        liquidity["score"]
    )

    # --------------------------------------------------------
    # REJECTION
    # --------------------------------------------------------

    score += (
        rejection["score"]
    )

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

    poc = volume_profile[
        "poc"
    ]

    if poc is not None:

        if price > poc:
            score += 1

        elif price < poc:
            score -= 1

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    if score >= 8:

        direction = "Bullish"

    elif score <= -8:

        direction = "Bearish"

    elif score >= 3:

        direction = "Bullish Lean"

    elif score <= -3:

        direction = "Bearish Lean"

    else:

        direction = "Consolidation"

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr_percent = None

    if atr and price:

        atr_percent = (
            atr / price
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

        "volume_ratio":
            volume["ratio"],

        "volume_condition":
            volume["trend"],

        "atr_percent":
            atr_percent,

        "structure":
            structure["label"],

        "structure_score":
            structure["score"],

        "swing_high":
            structure["swing_high"],

        "swing_low":
            structure["swing_low"],

        "support":
            support_resistance[
                "support"
            ],

        "resistance":
            support_resistance[
                "resistance"
            ],

        "fvg":
            fvg,

        "volume_profile":
            volume_profile,

        "liquidity":
            liquidity,

        "rejection":
            rejection,
    }


# ============================================================
# TRADINGVIEW DATA
# ============================================================

def get_tradingview_data(
    coin,
    timeframe
):

    key = (
        f"{coin}:{timeframe}"
    )

    data = (
        TRADINGVIEW_CACHE.get(
            key
        )
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


def apply_tradingview_confirmation(
    average_score,
    valid_results,
    coin
):

    tv_scores = []

    for timeframe, result in valid_results:

        tv = get_tradingview_data(
            coin,
            timeframe
        )

        if not tv:
            continue

        signal = str(
            tv.get(
                "signal",
                ""
            )
        ).upper()

        if signal in (
            "BUY",
            "LONG",
            "BULLISH"
        ):

            tv_scores.append(1)

        elif signal in (
            "SELL",
            "SHORT",
            "BEARISH"
        ):

            tv_scores.append(-1)

    if not tv_scores:

        return average_score

    tv_average = (
        sum(tv_scores)
        / len(tv_scores)
    )

    # TradingView is a small confirmation
    # layer, not the primary engine.

    average_score += (
        tv_average * 1.5
    )

    return average_score


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
        if result.get(
            "valid"
        )
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

            "overall":
                {
                    "label":
                        "Data Unavailable",

                    "internal_score":
                        0,

                },

            "valid_count":
                0,

            "total_count":
                len(TIMEFRAMES),
        }

    # --------------------------------------------------------
    # MULTI-TIMEFRAME WEIGHT
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OPTIONAL TRADINGVIEW CONFIRMATION
    # --------------------------------------------------------

    average_score = (
        apply_tradingview_confirmation(
            average_score,
            valid,
            coin
        )
    )

    # --------------------------------------------------------
    # BULL / BEAR COUNT
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OVERALL
    # --------------------------------------------------------

    if (
        average_score >= 4
        and bullish / count >= 0.60
    ):

        overall = "Bullish"

    elif (
        average_score <= -4
        and bearish / count >= 0.60
    ):

        overall = "Bearish"

    elif average_score >= 1.5:

        overall = "Bullish Lean"

    elif average_score <= -1.5:

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / Indecisive"
        )

    # --------------------------------------------------------
    # INTERNAL STRENGTH
    # --------------------------------------------------------

    # This is NOT a probability of being correct.
    # It is only the strength of the evidence.

    strength = min(
        100,
        (
            abs(average_score)
            / 12
        ) * 100
    )

    # --------------------------------------------------------
    # AGGREGATES
    # --------------------------------------------------------

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

    structure_scores = [
        result[
            "structure_score"
        ]
        for _, result in valid
    ]

    average_structure = (
        sum(structure_scores)
        / len(structure_scores)
    )

    if average_structure >= 1:

        structure = "Bullish"

    elif average_structure <= -1:

        structure = "Bearish"

    else:

        structure = "Mixed"

    # --------------------------------------------------------
    # KEY LEVELS
    # --------------------------------------------------------

    latest_result = (
        results.get("1h")
        or results.get("15m")
        or valid[0][1]
    )

    support = latest_result.get(
        "support"
    )

    resistance = latest_result.get(
        "resistance"
    )

    swing_high = latest_result.get(
        "swing_high"
    )

    swing_low = latest_result.get(
        "swing_low"
    )

    # --------------------------------------------------------
    # FVG SUMMARY
    # --------------------------------------------------------

    bullish_fvg = 0
    bearish_fvg = 0

    for _, result in valid:

        fvg = result.get(
            "fvg",
            {}
        )

        bullish_fvg += len(
            fvg.get(
                "bullish",
                []
            )
        )

        bearish_fvg += len(
            fvg.get(
                "bearish",
                []
            )
        )

    # --------------------------------------------------------
    # LIQUIDITY SUMMARY
    # --------------------------------------------------------

    bullish_sweeps = 0
    bearish_sweeps = 0

    for _, result in valid:

        liquidity = result.get(
            "liquidity",
            {}
        )

        if liquidity.get(
            "bullish_sweep"
        ):

            bullish_sweeps += 1

        if liquidity.get(
            "bearish_sweep"
        ):

            bearish_sweeps += 1

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

    vp = latest_result.get(
        "volume_profile",
        {}
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

        "overall":
            {

                "label":
                    overall,

                "strength":
                    strength,

                # Kept internally.
                "internal_score":
                    average_score,
            },

        "valid_count":
            count,

        "total_count":
            len(TIMEFRAMES),

        "average_rsi":
            (
                sum(rsi_values)
                / len(rsi_values)
                if rsi_values
                else None
            ),

        "average_volume_ratio":
            (
                sum(volume_values)
                / len(volume_values)
                if volume_values
                else None
            ),

        "average_atr_percent":
            (
                sum(atr_values)
                / len(atr_values)
                if atr_values
                else None
            ),

        "structure":
            structure,

        "support":
            support,

        "resistance":
            resistance,

        "swing_high":
            swing_high,

        "swing_low":
            swing_low,

        "volume_profile":
            vp,

        "bullish_fvg":
            bullish_fvg,

        "bearish_fvg":
            bearish_fvg,

        "bullish_sweeps":
            bullish_sweeps,

        "bearish_sweeps":
            bearish_sweeps,
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


def direction_emoji(
    direction
):

    if "Bullish" in direction:
        return "🟢"

    if "Bearish" in direction:
        return "🔴"

    if "Consolidation" in direction:
        return "🟡"

    return "⚪"


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

        f"<b>🔎 {coin} MARKET ANALYSIS</b>",

        "",

        f"💰 <b>Price:</b> "
        f"{format_price(analysis['price'])}",

        "",

        f"{direction_emoji(overall['label'])} "
        f"<b>Overall Direction:</b> "
        f"{overall['label']}",

        f"🎯 <b>Analysis Strength:</b> "
        f"{overall['strength']:.0f}%",

        "",

        "📊 <b>MULTI-TIMEFRAME ANALYSIS</b>",
    ]

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        direction = result.get(
            "direction",
            "Data Unavailable"
        )

        lines.append(

            f"{direction_emoji(direction)} "
            f"<b>{timeframe}:</b> "
            f"{direction}"

        )

    average_rsi = (
        analysis.get(
            "average_rsi"
        )
    )

    volume = (
        analysis.get(
            "average_volume_ratio"
        )
    )

    atr = (
        analysis.get(
            "average_atr_percent"
        )
    )

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
    ]

    # --------------------------------------------------------
    # KEY LEVELS
    # --------------------------------------------------------

    lines += [

        "",

        "🎯 <b>KEY LEVELS</b>",

        f"🔵 <b>Support:</b> "
        f"{format_price(analysis['support'])}",

        f"🔴 <b>Resistance:</b> "
        f"{format_price(analysis['resistance'])}",

        f"🔺 <b>Swing High:</b> "
        f"{format_price(analysis['swing_high'])}",

        f"🔻 <b>Swing Low:</b> "
        f"{format_price(analysis['swing_low'])}",
    ]

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

    vp = analysis[
        "volume_profile"
    ]

    if vp.get("poc") is not None:

        lines += [

            "",

            "📊 <b>VOLUME PROFILE</b>",

            f"POC: "
            f"{format_price(vp['poc'])}",

            f"VAH: "
            f"{format_price(vp['vah'])}",

            f"VAL: "
            f"{format_price(vp['val'])}",
        ]

    # --------------------------------------------------------
    # PRICE ACTION EVENTS
    # --------------------------------------------------------

    lines += [

        "",

        "🧠 <b>PRICE ACTION</b>",

        f"🟢 Bullish FVGs: "
        f"{analysis['bullish_fvg']}",

        f"🔴 Bearish FVGs: "
        f"{analysis['bearish_fvg']}",

        f"💧 Bullish liquidity sweeps: "
        f"{analysis['bullish_sweeps']}",

        f"💧 Bearish liquidity sweeps: "
        f"{analysis['bearish_sweeps']}",
    ]

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    lines += [

        "",

        f"📡 <b>Data Quality:</b> "
        f"{analysis['valid_count']}/"
        f"{analysis['total_count']} "
        f"timeframes",

        "",

        "⚠️ <b>Analysis only — "
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
            "📈 Trend & EMA structure\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market structure\n"
            "🔺 Swing highs/lows\n"
            "🎯 Support/resistance\n"
            "📊 Volume Profile\n"
            "🟢/🔴 Fair Value Gaps\n"
            "💧 Liquidity events\n"
            "🕯️ Rejection analysis"
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

def send_welcome(
    chat_id
):

    send_telegram(

        (
            "<b>🤖 SIDESHIFT AI 3.0</b>\n\n"

            "Live multi-timeframe "
            "crypto market analysis.\n\n"

            "<b>Analyzes:</b>\n"
            "📈 Trend & EMA structure\n"
            "📉 RSI\n"
            "📊 MACD\n"
            "📦 Volume\n"
            "🌊 ATR\n"
            "🧱 Market structure\n"
            "🔺 Swing highs/lows\n"
            "🎯 Support/resistance\n"
            "📊 Volume Profile\n"
            "🟢/🔴 Fair Value Gaps\n"
            "💧 Liquidity events\n"
            "🕯️ Rejection behavior\n\n"

            "The engine evaluates both "
            "<b>bullish AND bearish</b> "
            "conditions."
        ),

        chat_id,

        main_menu(),

    )


# ============================================================
# HELP
# ============================================================

def send_help(
    chat_id
):

    send_telegram(

        (
            "<b>ℹ️ HOW SIDESHIFT AI WORKS</b>\n\n"

            "SideShift pulls live market "
            "candles and evaluates:\n\n"

            "5m • 15m • 1h • 4h • 1D\n\n"

            "It analyzes trend, momentum, "
            "volume, market structure, "
            "swings, support/resistance, "
            "Volume Profile, FVGs and "
            "liquidity behavior.\n\n"

            "TradingView can provide "
            "additional indicator data "
            "through its webhook system "
            "when configured.\n\n"

            "Bullish and bearish evidence "
            "are evaluated separately."
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

        # ----------------------------------------------------
        # MESSAGE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CALLBACK
        # ----------------------------------------------------

        callback = data.get(
            "callback_query"
        )

        if callback:

            callback_id = (
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

            answer_callback(
                callback_id
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
# TRADINGVIEW WEBHOOK
# ============================================================

@app.route(
    "/webhook",
    methods=["POST"],
)
def tradingview_webhook():

    try:

        raw_body = (
            request.get_data(
                as_text=True
            )
            .strip()
        )

        print(
            "TRADINGVIEW WEBHOOK RECEIVED"
        )

        print(
            "CONTENT TYPE:",
            request.content_type
        )

        print(
            "RAW BODY:",
            raw_body[:1000]
        )

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        data = {}

        if raw_body:

            try:

                data = (
                    request.get_json(
                        silent=True
                    )
                    or {}
                )

            except Exception:

                data = {}

        # ----------------------------------------------------
        # SECRET
        # ----------------------------------------------------

        if WEBHOOK_SECRET:

            incoming_secret = str(
                data.get(
                    "secret",
                    ""
                )
            )

            if (
                incoming_secret
                != WEBHOOK_SECRET
            ):

                print(
                    "TRADINGVIEW INVALID SECRET"
                )

                return jsonify({
                    "status":
                        "unauthorized"
                }), 401

        # ----------------------------------------------------
        # BASIC VALUES
        # ----------------------------------------------------

        symbol = str(
            data.get(
                "symbol",
                ""
            )
        ).upper().strip()

        timeframe = str(
            data.get(
                "timeframe",
                ""
            )
        ).strip()

        signal = str(
            data.get(
                "signal",
                data.get(
                    "direction",
                    ""
                )
            )
        ).upper().strip()

        # ----------------------------------------------------
        # PLAIN TEXT SUPPORT
        # ----------------------------------------------------

        if not symbol:

            text = (
                raw_body.upper()
            )

            for coin in COINS:

                if (
                    coin in text
                    or
                    f"{coin}USDT"
                    in text
                    or
                    f"{coin}USD"
                    in text
                ):

                    symbol = coin

                    break

        # ----------------------------------------------------
        # SYMBOL NORMALIZATION
        # ----------------------------------------------------

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
            .replace(
                ":",
                ""
            )
            .replace(
                "BINANCE",
                ""
            )
            .replace(
                "BYBIT",
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

        # ----------------------------------------------------
        # TIMEFRAME NORMALIZATION
        # ----------------------------------------------------

        timeframe = (
            timeframe
            .replace(
                " ",
                ""
            )
            .lower()
        )

        timeframe_aliases = {

            "5":
                "5m",

            "5m":
                "5m",

            "15":
                "15m",

            "15m":
                "15m",

            "60":
                "1h",

            "1h":
                "1h",

            "1hr":
                "1h",

            "240":
                "4h",

            "4h":
                "4h",

            "4hr":
                "4h",

            "d":
                "1D",

            "1d":
                "1D",

            "1day":
                "1D",
        }

        timeframe = (
            timeframe_aliases.get(
                timeframe,
                timeframe
            )
        )

        # ----------------------------------------------------
        # INDICATOR VALUES
        #
        # TradingView can send values from plots.
        # These are stored but NOT blindly trusted.
        # ----------------------------------------------------

        def numeric_value(
            key
        ):

            value = data.get(
                key
            )

            try:

                if value in (
                    None,
                    "",
                    "na",
                    "NaN",
                    "nan"
                ):

                    return None

                return float(
                    value
                )

            except Exception:

                return None

        tv_data = {

            "symbol":
                symbol,

            "timeframe":
                timeframe,

            "signal":
                signal,

            "price":
                numeric_value(
                    "price"
                ),

            "rsi":
                numeric_value(
                    "rsi"
                ),

            "ema20":
                numeric_value(
                    "ema20"
                ),

            "ema50":
                numeric_value(
                    "ema50"
                ),

            "ema200":
                numeric_value(
                    "ema200"
                ),

            "macd":
                numeric_value(
                    "macd"
                ),

            "macd_signal":
                numeric_value(
                    "macd_signal"
                ),

            "macd_histogram":
                numeric_value(
                    "macd_histogram"
                ),

            "volume":
                numeric_value(
                    "volume"
                ),

            "volume_ma":
                numeric_value(
                    "volume_ma"
                ),

            "poc":
                numeric_value(
                    "poc"
                ),

            "vah":
                numeric_value(
                    "vah"
                ),

            "val":
                numeric_value(
                    "val"
                ),

            "support":
                numeric_value(
                    "support"
                ),

            "resistance":
                numeric_value(
                    "resistance"
                ),
        }

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if symbol not in COINS:

            print(
                "TRADINGVIEW UNKNOWN SYMBOL:",
                symbol
            )

            return jsonify({

                "status":
                    "received",

                "processed":
                    False,

                "reason":
                    "Unsupported symbol",

            }), 200

        if timeframe not in TIMEFRAMES:

            print(
                "TRADINGVIEW UNKNOWN TIMEFRAME:",
                timeframe
            )

            return jsonify({

                "status":
                    "received",

                "processed":
                    False,

                "reason":
                    "Unsupported timeframe",

            }), 200

        # ----------------------------------------------------
        # STORE
        # ----------------------------------------------------

        cache_key = (
            f"{symbol}:{timeframe}"
        )

        TRADINGVIEW_CACHE[
            cache_key
        ] = {

            "received":
                time.time(),

            "data":
                tv_data,
        }

        print(
            "TRADINGVIEW CACHED:",
            cache_key
        )

        return jsonify({

            "status":
                "cached",

            "processed":
                True,

            "symbol":
                symbol,

            "timeframe":
                timeframe,

        }), 200

    except Exception as e:

        print(
            "TRADINGVIEW ERROR:",
            repr(e),
        )

        return jsonify({

            "status":
                "error",

            "error":
                str(e),

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

    })


# ============================================================
# MARKET TEST
# ============================================================

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

    return jsonify(
        scan_coin(coin)
    )


# ============================================================
# SET TELEGRAM WEBHOOK
# ============================================================

def setup_telegram_webhook():

    if (
        not TELEGRAM_API
        or
        not RAILWAY_PUBLIC_DOMAIN
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