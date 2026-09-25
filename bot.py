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

# interval, seconds, weighting
TIMEFRAMES = {
    "5m": ("5m", 300, 0.8),
    "15m": ("15m", 900, 1.0),
    "1h": ("1h", 3600, 1.2),

    # IMPORTANT:
    # 4 hours = 14,400 seconds
    "4h": ("4h", 14400, 1.4),

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
# SMA
# ============================================================

def sma(values, period):

    if len(values) < period:

        return [None] * len(values)

    result = [None] * len(values)

    running = sum(values[:period])

    result[period - 1] = (
        running / period
    )

    for i in range(period, len(values)):

        running += (
            values[i]
            - values[i - period]
        )

        result[i] = (
            running / period
        )

    return result


# ============================================================
# VWMA
# ============================================================

def vwma(candles, period=20):

    if len(candles) < period:

        return None

    recent = candles[-period:]

    total_volume = sum(
        x["volume"]
        for x in recent
    )

    if total_volume <= 0:

        return None

    weighted_price = sum(
        (
            (
                x["high"]
                + x["low"]
                + x["close"]
            )
            / 3
        )
        * x["volume"]
        for x in recent
    )

    return (
        weighted_price
        / total_volume
    )


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    closes,
    period=14,
):

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

    for i in range(
        period,
        len(gains),
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
                + gains[i]
            )
            / period
        )

        avg_loss = (
            (
                avg_loss
                * (period - 1)
                + losses[i]
            )
            / period
        )

    if avg_loss == 0:

        return 100

    rs = (
        avg_gain
        / avg_loss
    )

    return 100 - (
        100
        / (1 + rs)
    )


# ============================================================
# ATR
# ============================================================

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
                    int(row[0])
                    * 1000,

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
                "symbol":
                    symbol,

                "interval":
                    interval,

                "limit":
                    500,
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

        candles = (
            normalize_coinbase(
                response.json()
            )
        )

        return candles[-300:]

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

    (
        binance_symbol,
        coinbase_symbol,
    ) = COINS[coin]

    (
        binance_interval,
        coinbase_seconds,
        _,
    ) = TIMEFRAMES[
        timeframe
    ]

    candles = (
        get_binance_candles(
            binance_symbol,
            binance_interval,
        )
    )

    if len(candles) >= 100:

        return (
            candles,
            "Binance",
        )

    candles = (
        get_coinbase_candles(
            coinbase_symbol,
            coinbase_seconds,
        )
    )

    if len(candles) >= 100:

        return (
            candles,
            "Coinbase",
        )

    return [], None


# ============================================================
# PIVOT / SWING DETECTION
# ============================================================

def pivot_levels(
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
        len(candles) - right,
    ):

        high = candles[i]["high"]
        low = candles[i]["low"]

        is_swing_high = (
            all(
                high
                > candles[j]["high"]
                for j in range(
                    i - left,
                    i,
                )
            )
            and
            all(
                high
                >= candles[j]["high"]
                for j in range(
                    i + 1,
                    i + right + 1,
                )
            )
        )

        is_swing_low = (
            all(
                low
                < candles[j]["low"]
                for j in range(
                    i - left,
                    i,
                )
            )
            and
            all(
                low
                <= candles[j]["low"]
                for j in range(
                    i + 1,
                    i + right + 1,
                )
            )
        )

        if is_swing_high:

            highs.append({

                "index":
                    i,

                "price":
                    high,

                "timestamp":
                    candles[i][
                        "timestamp"
                    ],
            })

        if is_swing_low:

            lows.append({

                "index":
                    i,

                "price":
                    low,

                "timestamp":
                    candles[i][
                        "timestamp"
                    ],
            })

    return highs, lows


# ============================================================
# SUPPORT / RESISTANCE CLUSTERING
# ============================================================

def cluster_levels(
    levels,
    tolerance,
):

    if not levels:

        return []

    sorted_levels = sorted(
        levels,
        key=lambda x:
        x["price"],
    )

    clusters = []

    for item in sorted_levels:

        if (
            not clusters
            or abs(
                item["price"]
                - clusters[-1]["price"]
            )
            > tolerance
        ):

            clusters.append({

                "price":
                    item["price"],

                "touches":
                    1,

                "prices":
                    [item["price"]],

                "last_index":
                    item["index"],
            })

        else:

            cluster = clusters[-1]

            cluster["prices"].append(
                item["price"]
            )

            cluster["touches"] += 1

            cluster["price"] = (
                sum(
                    cluster["prices"]
                )
                / len(
                    cluster["prices"]
                )
            )

            cluster["last_index"] = max(
                cluster["last_index"],
                item["index"],
            )

    return clusters


def support_resistance(
    candles,
    atr,
):

    if not candles or not atr:

        return {
            "supports": [],
            "resistances": [],
        }

    sample = candles[-250:]

    highs, lows = pivot_levels(
        sample,
        3,
        3,
    )

    price = candles[-1]["close"]

    tolerance = max(
        atr * 0.45,
        price * 0.0025,
    )

    resistance_clusters = (
        cluster_levels(
            highs,
            tolerance,
        )
    )

    support_clusters = (
        cluster_levels(
            lows,
            tolerance,
        )
    )

    supports = sorted(

        [
            x
            for x
            in support_clusters

            if x["price"]
            < price
        ],

        key=lambda x:
            (
                price
                - x["price"],
                -x["touches"],
            ),
    )[:3]

    resistances = sorted(

        [
            x
            for x
            in resistance_clusters

            if x["price"]
            > price
        ],

        key=lambda x:
            (
                x["price"]
                - price,
                -x["touches"],
            ),
    )[:3]

    return {

        "supports":
            supports,

        "resistances":
            resistances,
    }


# ============================================================
# REJECTION ZONES
# ============================================================

def detect_rejection_blocks(
    candles,
    atr,
):

    if len(candles) < 20 or not atr:

        return {
            "bullish": [],
            "bearish": [],
        }

    bullish = []
    bearish = []

    recent = candles[-100:]

    for i in range(
        2,
        len(recent),
    ):

        candle = recent[i]

        body = abs(
            candle["close"]
            - candle["open"]
        )

        candle_range = (
            candle["high"]
            - candle["low"]
        )

        if candle_range <= 0:

            continue

        lower_wick = (
            min(
                candle["open"],
                candle["close"],
            )
            - candle["low"]
        )

        upper_wick = (
            candle["high"]
            - max(
                candle["open"],
                candle["close"],
            )
        )

        # Bullish rejection:
        # Large lower wick + bullish close.

        if (
            lower_wick
            >= max(
                body * 1.5,
                atr * 0.20,
            )
            and
            lower_wick
            / candle_range
            >= 0.45
            and
            candle["close"]
            > candle["open"]
        ):

            bullish.append({

                "price":
                    candle["low"],

                "high":
                    candle["high"],

                "index":
                    i,
            })

        # Bearish rejection:
        # Large upper wick + bearish close.

        if (
            upper_wick
            >= max(
                body * 1.5,
                atr * 0.20,
            )
            and
            upper_wick
            / candle_range
            >= 0.45
            and
            candle["close"]
            < candle["open"]
        ):

            bearish.append({

                "price":
                    candle["high"],

                "low":
                    candle["low"],

                "index":
                    i,
            })

    return {

        "bullish":
            bullish[-3:],

        "bearish":
            bearish[-3:],
    }


# ============================================================
# FAIR VALUE GAPS
# ============================================================

def detect_fvgs(candles):

    bullish = []
    bearish = []

    for i in range(
        2,
        len(candles),
    ):

        first = candles[i - 2]
        middle = candles[i - 1]
        current = candles[i]

        # Bullish FVG

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

        # Bearish FVG

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

    return {

        "bullish":
            bullish,

        "bearish":
            bearish,
    }


# ============================================================
# LIQUIDITY SWEEPS / POTENTIAL TRAPS
# ============================================================

def liquidity_sweeps(
    candles,
    atr,
):

    if len(candles) < 20 or not atr:

        return {
            "bullish": [],
            "bearish": [],
        }

    sample = candles[-150:]

    highs, lows = pivot_levels(
        sample,
        3,
        3,
    )

    bullish = []
    bearish = []

    # Sweep below previous swing low
    # and close back above it.

    for pivot in lows[-10:]:

        index = pivot["index"]

        for j in range(
            index + 1,
            len(sample),
        ):

            candle = sample[j]

            if (
                candle["low"]
                <
                pivot["price"]
                - atr * 0.05

                and

                candle["close"]
                >
                pivot["price"]
            ):

                bullish.append({

                    "level":
                        pivot["price"],

                    "sweep":
                        candle["low"],

                    "index":
                        j,
                })

                break

    # Sweep above previous swing high
    # and close back below it.

    for pivot in highs[-10:]:

        index = pivot["index"]

        for j in range(
            index + 1,
            len(sample),
        ):

            candle = sample[j]

            if (
                candle["high"]
                >
                pivot["price"]
                + atr * 0.05

                and

                candle["close"]
                <
                pivot["price"]
            ):

                bearish.append({

                    "level":
                        pivot["price"],

                    "sweep":
                        candle["high"],

                    "index":
                        j,
                })

                break

    return {

        "bullish":
            bullish[-3:],

        "bearish":
            bearish[-3:],
    }


# ============================================================
# FIXED-RANGE VOLUME PROFILE APPROXIMATION
# ============================================================

def volume_profile_fixed_range(
    candles,
    bins=24,
    lookback=120,
):

    data = candles[-lookback:]

    if len(data) < 20:

        return None

    low = min(
        x["low"]
        for x in data
    )

    high = max(
        x["high"]
        for x in data
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

    # IMPORTANT:
    #
    # Normal OHLCV candle data does not contain
    # true volume-at-price information.
    #
    # Therefore this distributes each candle's
    # volume across the price bins touched
    # by that candle.
    #
    # This is an approximation of Fixed Range
    # Volume Profile, not TradingView's exact
    # proprietary calculation.

    for candle in data:

        candle_low = candle["low"]
        candle_high = candle["high"]

        start = max(
            0,
            min(
                bins - 1,
                int(
                    (
                        candle_low
                        - low
                    )
                    / step
                ),
            ),
        )

        end = max(
            0,
            min(
                bins - 1,
                int(
                    (
                        candle_high
                        - low
                    )
                    / step
                ),
            ),
        )

        count = max(
            1,
            end - start + 1,
        )

        share = (
            candle["volume"]
            / count
        )

        for b in range(
            start,
            end + 1,
        ):

            volumes[b] += share

    poc_index = max(
        range(bins),
        key=lambda i:
        volumes[i],
    )

    total_volume = sum(
        volumes
    )

    target = (
        total_volume
        * 0.70
    )

    included = {
        poc_index
    }

    accumulated = (
        volumes[poc_index]
    )

    left = (
        poc_index - 1
    )

    right = (
        poc_index + 1
    )

    while (
        accumulated < target
        and
        (
            left >= 0
            or
            right < bins
        )
    ):

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

        if right_volume >= left_volume:

            if right < bins:

                included.add(
                    right
                )

                accumulated += (
                    volumes[right]
                )

                right += 1

            elif left >= 0:

                included.add(
                    left
                )

                accumulated += (
                    volumes[left]
                )

                left -= 1

        else:

            if left >= 0:

                included.add(
                    left
                )

                accumulated += (
                    volumes[left]
                )

                left -= 1

            elif right < bins:

                included.add(
                    right
                )

                accumulated += (
                    volumes[right]
                )

                right += 1

    vah_index = max(
        included
    )

    val_index = min(
        included
    )

    price = data[-1]["close"]

    poc = (
        low
        + (poc_index + 0.5)
        * step
    )

    vah = (
        low
        + (vah_index + 1.0)
        * step
    )

    val = (
        low
        + val_index
        * step
    )

    if price > vah:

        position = (
            "Above Value Area"
        )

    elif price < val:

        position = (
            "Below Value Area"
        )

    else:

        position = (
            "Inside Value Area"
        )

    return {

        "poc":
            poc,

        "vah":
            vah,

        "val":
            val,

        "position":
            position,

        "low":
            low,

        "high":
            high,
    }


# ============================================================
# MARKET STRUCTURE
# ============================================================

def calculate_structure(
    candles,
):

    highs, lows = pivot_levels(
        candles[-120:],
        3,
        3,
    )

    if (
        len(highs) < 2
        or
        len(lows) < 2
    ):

        return {

            "label":
                "Insufficient pivots",

            "score":
                0,

            "swing_high":
                None,

            "swing_low":
                None,
        }

    previous_high = highs[-2]
    latest_high = highs[-1]

    previous_low = lows[-2]
    latest_low = lows[-1]

    if (
        latest_high["price"]
        > previous_high["price"]

        and

        latest_low["price"]
        > previous_low["price"]
    ):

        label = (
            "Higher Highs / "
            "Higher Lows"
        )

        score = 2

    elif (
        latest_high["price"]
        < previous_high["price"]

        and

        latest_low["price"]
        < previous_low["price"]
    ):

        label = (
            "Lower Highs / "
            "Lower Lows"
        )

        score = -2

    elif (
        latest_high["price"]
        > previous_high["price"]
    ):

        label = (
            "Higher High / "
            "Mixed Lows"
        )

        score = 1

    elif (
        latest_low["price"]
        < previous_low["price"]
    ):

        label = (
            "Lower Low / "
            "Mixed Highs"
        )

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
            latest_high["price"],

        "swing_low":
            latest_low["price"],
    }


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    candles,
):

    if len(candles) < 100:

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

    current_vwma = vwma(
        candles,
        20,
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

    score = 0.0

    evidence = []

    # --------------------------------------------------------
    # PRICE VS EMA20
    # --------------------------------------------------------

    if ema20[-1] is not None:

        if price > ema20[-1]:

            score += 1.5

            evidence.append(
                "price above EMA20"
            )

        else:

            score -= 1.5

            evidence.append(
                "price below EMA20"
            )

    # --------------------------------------------------------
    # EMA20 VS EMA50
    # --------------------------------------------------------

    if ema50[-1] is not None:

        if ema20[-1] > ema50[-1]:

            score += 1.5

            evidence.append(
                "EMA20 above EMA50"
            )

        else:

            score -= 1.5

            evidence.append(
                "EMA20 below EMA50"
            )

    # --------------------------------------------------------
    # PRICE VS EMA200
    # --------------------------------------------------------

    if ema200[-1] is not None:

        if price > ema200[-1]:

            score += 1.0

            evidence.append(
                "price above EMA200"
            )

        else:

            score -= 1.0

            evidence.append(
                "price below EMA200"
            )

    # --------------------------------------------------------
    # EMA20 SLOPE
    # --------------------------------------------------------

    if (
        len(ema20) >= 6
        and
        ema20[-6] is not None
    ):

        if (
            ema20[-1]
            > ema20[-6]
        ):

            score += 0.75

            evidence.append(
                "EMA20 rising"
            )

        else:

            score -= 0.75

            evidence.append(
                "EMA20 falling"
            )

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    previous_price = closes[-11]

    percent_change = (
        (
            price
            - previous_price
        )
        / previous_price
        * 100
    )

    if percent_change > 0.5:

        score += 1.0

        evidence.append(
            "positive momentum"
        )

    elif percent_change < -0.5:

        score -= 1.0

        evidence.append(
            "negative momentum"
        )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if rsi is not None:

        if (
            55
            <= rsi
            <= 70
        ):

            score += 0.75

            evidence.append(
                "RSI bullish zone"
            )

        elif (
            30
            <= rsi
            <= 45
        ):

            score -= 0.75

            evidence.append(
                "RSI bearish zone"
            )

        elif rsi > 75:

            evidence.append(
                "RSI overbought"
            )

        elif rsi < 25:

            evidence.append(
                "RSI oversold"
            )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if macd:

        if (
            macd["histogram"]
            > 0
        ):

            score += 0.75

            evidence.append(
                "MACD positive"
            )

        else:

            score -= 0.75

            evidence.append(
                "MACD negative"
            )

    # --------------------------------------------------------
    # MARKET STRUCTURE
    # --------------------------------------------------------

    score += (
        structure["score"]
        * 0.75
    )

    # --------------------------------------------------------
    # RELATIVE VOLUME
    # --------------------------------------------------------

    recent_volumes = [

        x["volume"]

        for x
        in candles[-21:-1]
    ]

    volume_ratio = None

    if recent_volumes:

        average_volume = (
            sum(
                recent_volumes
            )
            /
            len(
                recent_volumes
            )
        )

        if average_volume > 0:

            volume_ratio = (
                candles[-1]["volume"]
                /
                average_volume
            )

    if (
        volume_ratio is not None
        and
        volume_ratio >= 1.5
    ):

        # High volume confirms activity.
        # It is NOT automatically bullish.
        evidence.append(
            "high relative volume"
        )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr_percent = None

    if atr and price:

        atr_percent = (
            atr
            / price
        ) * 100

    # --------------------------------------------------------
    # VOLUME PROFILE
    # --------------------------------------------------------

    volume_profile = (
        volume_profile_fixed_range(
            candles
        )
    )

    # --------------------------------------------------------
    # SUPPORT / RESISTANCE
    # --------------------------------------------------------

    levels = (
        support_resistance(
            candles,
            atr,
        )
    )

    # --------------------------------------------------------
    # REJECTION ZONES
    # --------------------------------------------------------

    rejection_blocks = (
        detect_rejection_blocks(
            candles,
            atr,
        )
    )

    # --------------------------------------------------------
    # FAIR VALUE GAPS
    # --------------------------------------------------------

    fvgs = detect_fvgs(
        candles
    )

    # --------------------------------------------------------
    # LIQUIDITY SWEEPS
    # --------------------------------------------------------

    sweeps = liquidity_sweeps(
        candles,
        atr,
    )

    # --------------------------------------------------------
    # LIQUIDITY SWEEP SCORE
    # --------------------------------------------------------

    if sweeps["bullish"]:

        score += 1.0

        evidence.append(
            "bullish liquidity sweep"
        )

    if sweeps["bearish"]:

        score -= 1.0

        evidence.append(
            "bearish liquidity sweep"
        )

    # --------------------------------------------------------
    # REJECTION SCORE
    # --------------------------------------------------------

    if rejection_blocks["bullish"]:

        score += 0.5

        evidence.append(
            "bullish rejection"
        )

    if rejection_blocks["bearish"]:

        score -= 0.5

        evidence.append(
            "bearish rejection"
        )

    # --------------------------------------------------------
    # VOLUME PROFILE LOCATION
    # --------------------------------------------------------

    if volume_profile:

        if (
            price
            > volume_profile["vah"]
        ):

            score += 0.5

            evidence.append(
                "above value area"
            )

        elif (
            price
            < volume_profile["val"]
        ):

            score -= 0.5

            evidence.append(
                "below value area"
            )

    # --------------------------------------------------------
    # DIRECTION
    # --------------------------------------------------------

    if score >= 4:

        direction = "Bullish"

    elif score <= -4:

        direction = "Bearish"

    elif score >= 1.5:

        direction = "Bullish Lean"

    elif score <= -1.5:

        direction = "Bearish Lean"

    else:

        direction = "Consolidation"

    # --------------------------------------------------------
    # TIMEFRAME STRENGTH
    # --------------------------------------------------------

    max_abs_score = 10.5

    timeframe_strength = min(
        100,
        abs(score)
        / max_abs_score
        * 100,
    )

    return {

        "valid":
            True,

        "direction":
            direction,

        "score":
            score,

        "strength":
            timeframe_strength,

        "price":
            price,

        "ema20":
            ema20[-1],

        "ema50":
            ema50[-1],

        "ema200":
            ema200[-1],

        "vwma20":
            current_vwma,

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

        "structure_score":
            structure["score"],

        "swing_high":
            structure["swing_high"],

        "swing_low":
            structure["swing_low"],

        "support_resistance":
            levels,

        "rejection_blocks":
            rejection_blocks,

        "fvgs":
            fvgs,

        "liquidity_sweeps":
            sweeps,

        "volume_profile":
            volume_profile,

        "evidence":
            evidence[-12:],
    }


# ============================================================
# TRADINGVIEW SYMBOL NORMALIZATION
# ============================================================

def normalize_tv_symbol(
    raw_symbol,
):

    symbol = str(
        raw_symbol or ""
    ).upper().strip()

    # BINANCE:BTCUSDT
    if ":" in symbol:

        symbol = (
            symbol
            .split(":")[-1]
        )

    symbol = (
        symbol
        .replace(".P", "")
        .replace("PERP", "")
        .replace("/", "")
        .replace("-", "")
    )

    for quote in (
        "USDT",
        "USDC",
        "USD",
    ):

        if symbol.endswith(
            quote
        ):

            symbol = (
                symbol[
                    :-len(quote)
                ]
            )

            break

    return symbol


# ============================================================
# TRADINGVIEW TIMEFRAME NORMALIZATION
# ============================================================

def normalize_tv_timeframe(
    raw_timeframe,
):

    value = str(
        raw_timeframe or ""
    ).strip().upper()

    mapping = {

        "5":
            "5m",

        "5M":
            "5m",

        "15":
            "15m",

        "15M":
            "15m",

        "60":
            "1h",

        "60M":
            "1h",

        "1H":
            "1h",

        "240":
            "4h",

        "240M":
            "4h",

        "4H":
            "4h",

        "D":
            "1D",

        "1D":
            "1D",

        "1440":
            "1D",

        "1440M":
            "1D",
    }

    return mapping.get(
        value,
        str(
            raw_timeframe or ""
        ).strip(),
    )


# ============================================================
# TRADINGVIEW CACHE
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

    key = tradingview_key(
        coin,
        timeframe,
    )

    data = (
        TRADINGVIEW_CACHE.get(
            key
        )
    )

    if not data:

        return None

    # Two-hour freshness window.

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

        results[
            timeframe
        ] = analyze_timeframe(
            candles
        )

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
                len(
                    TIMEFRAMES
                ),
        }

    # ========================================================
    # MULTI-TIMEFRAME WEIGHTING
    # ========================================================

    weighted_score = sum(

        result["score"]
        * TIMEFRAMES[
            timeframe
        ][2]

        for timeframe, result
        in valid
    )

    total_weight = sum(

        TIMEFRAMES[
            timeframe
        ][2]

        for timeframe, _
        in valid
    )

    average_score = (
        weighted_score
        / total_weight
    )

    # ========================================================
    # TIMEFRAME DIRECTION COUNTS
    # ========================================================

    bullish = sum(

        "Bullish"
        in result["direction"]

        for _, result
        in valid
    )

    bearish = sum(

        "Bearish"
        in result["direction"]

        for _, result
        in valid
    )

    neutral = (
        len(valid)
        - bullish
        - bearish
    )

    # ========================================================
    # TRADINGVIEW CONFIRMATION
    # ========================================================

    tv_bullish = 0
    tv_bearish = 0
    tv_received = 0

    for timeframe, _ in valid:

        tv = get_tradingview_data(
            coin,
            timeframe,
        )

        if not tv:

            continue

        tv_received += 1

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

    tv_delta = (
        tv_bullish
        - tv_bearish
    )

    # TradingView only affects the score
    # when actual webhook data arrived.

    if tv_delta:

        average_score += max(
            -1.5,
            min(
                1.5,
                tv_delta * 0.5,
            ),
        )

    # ========================================================
    # CONFLUENCE / ANALYSIS STRENGTH
    # ========================================================

    agreement = (
        abs(
            bullish
            - bearish
        )
        /
        len(valid)
    )

    data_quality = (
        len(valid)
        /
        len(TIMEFRAMES)
    )

    confidence = min(

        100,

        (
            abs(
                average_score
            )
            / 8.0
        )
        * 60

        +

        agreement * 25

        +

        data_quality * 15,
    )

    # IMPORTANT:
    #
    # This is NOT a probability.
    #
    # It is a confluence/analysis-strength
    # measurement.

    # ========================================================
    # OVERALL DIRECTION
    # ========================================================

    if (
        average_score >= 3
        and
        bullish
        /
        len(valid)
        >= 0.60
    ):

        overall = "Bullish"

    elif (
        average_score <= -3
        and
        bearish
        /
        len(valid)
        >= 0.60
    ):

        overall = "Bearish"

    elif average_score >= 1:

        overall = "Bullish Lean"

    elif average_score <= -1:

        overall = "Bearish Lean"

    else:

        overall = (
            "Consolidation / "
            "Indecisive"
        )

    # ========================================================
    # AGGREGATES
    # ========================================================

    rsi_values = [

        result["rsi"]

        for _, result
        in valid

        if result.get(
            "rsi"
        ) is not None
    ]

    volume_values = [

        result["volume_ratio"]

        for _, result
        in valid

        if result.get(
            "volume_ratio"
        ) is not None
    ]

    vwma_values = [

        result["vwma20"]

        for _, result
        in valid

        if result.get(
            "vwma20"
        ) is not None
    ]

    atr_values = [

        result["atr_percent"]

        for _, result
        in valid

        if result.get(
            "atr_percent"
        ) is not None
    ]

    # ========================================================
    # STRUCTURE
    # ========================================================

    structure_score = (

        sum(

            result[
                "structure_score"
            ]

            for _, result
            in valid
        )

        /

        len(valid)
    )

    if structure_score > 0.75:

        structure = "Bullish"

    elif structure_score < -0.75:

        structure = "Bearish"

    else:

        structure = "Mixed"

    # ========================================================
    # SUPPORT / RESISTANCE
    # ========================================================

    supports = []
    resistances = []

    bullish_sweeps = 0
    bearish_sweeps = 0

    bullish_rejections = 0
    bearish_rejections = 0

    bullish_fvgs = 0
    bearish_fvgs = 0

    for _, result in valid:

        levels = (
            result[
                "support_resistance"
            ]
        )

        supports.extend(

            x["price"]

            for x
            in levels[
                "supports"
            ]
        )

        resistances.extend(

            x["price"]

            for x
            in levels[
                "resistances"
            ]
        )

        bullish_sweeps += len(
            result[
                "liquidity_sweeps"
            ][
                "bullish"
            ]
        )

        bearish_sweeps += len(
            result[
                "liquidity_sweeps"
            ][
                "bearish"
            ]
        )

        bullish_rejections += len(
            result[
                "rejection_blocks"
            ][
                "bullish"
            ]
        )

        bearish_rejections += len(
            result[
                "rejection_blocks"
            ][
                "bearish"
            ]
        )

        bullish_fvgs += len(
            result[
                "fvgs"
            ][
                "bullish"
            ]
        )

        bearish_fvgs += len(
            result[
                "fvgs"
            ][
                "bearish"
            ]
        )

    # ========================================================
    # NEAREST SUPPORT / RESISTANCE
    # ========================================================

    nearest_support = None
    nearest_resistance = None

    if price is not None:

        below = [
            x
            for x in supports
            if x < price
        ]

        above = [
            x
            for x in resistances
            if x > price
        ]

        if below:

            nearest_support = min(
                below,
                key=lambda x:
                price - x,
            )

        if above:

            nearest_resistance = min(
                above,
                key=lambda x:
                x - price,
            )

    # ========================================================
    # PRIMARY VOLUME PROFILE
    # ========================================================

    volume_profile = None

    for timeframe in (
        "1D",
        "4h",
        "1h",
        "15m",
        "5m",
    ):

        if results[
            timeframe
        ].get(
            "volume_profile"
        ):

            volume_profile = (
                results[
                    timeframe
                ][
                    "volume_profile"
                ]
            )

            break

    # ========================================================
    # RETURN
    # ========================================================

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
            len(valid),

        "total_count":
            len(TIMEFRAMES),

        "average_rsi": (

            sum(rsi_values)
            /
            len(rsi_values)

            if rsi_values

            else None
        ),

        "average_volume_ratio": (

            sum(volume_values)
            /
            len(volume_values)

            if volume_values

            else None
        ),

        "average_vwma": (

            sum(vwma_values)
            /
            len(vwma_values)

            if vwma_values

            else None
        ),

        "average_atr_percent": (

            sum(atr_values)
            /
            len(atr_values)

            if atr_values

            else None
        ),

        "structure":
            structure,

        "tradingview": {

            "bullish":
                tv_bullish,

            "bearish":
                tv_bearish,

            "received":
                tv_received,
        },

        "nearest_support":
            nearest_support,

        "nearest_resistance":
            nearest_resistance,

        "volume_profile":
            volume_profile,

        "patterns": {

            "bullish_sweeps":
                bullish_sweeps,

            "bearish_sweeps":
                bearish_sweeps,

            "bullish_rejections":
                bullish_rejections,

            "bearish_rejections":
                bearish_rejections,

            "bullish_fvgs":
                bullish_fvgs,

            "bearish_fvgs":
                bearish_fvgs,
        },

        "timeframe_counts": {

            "bullish":
                bullish,

            "bearish":
                bearish,

            "neutral":
                neutral,
        },
    }


# ============================================================
# FORMATTING
# ============================================================

def format_price(price):

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

    if "Bullish" in direction:

        return "🟢"

    if "Bearish" in direction:

        return "🔴"

    if "Consolidation" in direction:

        return "🟡"

    return "⚪"


def level_text(
    level,
    price,
):

    if (
        level is None
        or
        price is None
    ):

        return "Unavailable"

    percent = (
        (
            level
            - price
        )
        / price
    ) * 100

    return (
        f"{format_price(level)} "
        f"({percent:+.2f}%)"
    )


# ============================================================
# TELEGRAM SCAN MESSAGE
# ============================================================

def build_scan_message(
    analysis,
):

    overall = analysis[
        "overall"
    ]

    tv = analysis[
        "tradingview"
    ]

    vp = analysis.get(
        "volume_profile"
    )

    price = analysis[
        "price"
    ]

    counts = analysis[
        "timeframe_counts"
    ]

    patterns = analysis[
        "patterns"
    ]

    lines = [

        f"<b>🔎 "
        f"{analysis['coin']} "
        f"MARKET ANALYSIS</b>",

        "",

        f"💰 <b>Price:</b> "
        f"{format_price(price)}",

        f"{direction_emoji(overall['label'])} "
        f"<b>Overall:</b> "
        f"{overall['label']}",

        f"🎯 <b>Analysis Strength:</b> "
        f"{overall['confidence']:.0f}%",

        f"🧮 <b>Weighted Score:</b> "
        f"{overall['score']:+.2f} "
        f"(0 = neutral)",

        "",

        "📊 <b>MULTI-TIMEFRAME</b>",
    ]

    for timeframe in TIMEFRAMES:

        result = analysis[
            "timeframes"
        ][timeframe]

        if result.get(
            "valid"
        ):

            lines.append(

                f"{direction_emoji(result['direction'])} "
                f"<b>{timeframe}:</b> "
                f"{result['direction']} "
                f"({result['score']:+.1f})"
            )

        else:

            lines.append(

                f"⚪ <b>{timeframe}:</b> "
                f"Data Unavailable"
            )

    lines += [

        "",

        "📈 <b>MARKET CONDITIONS</b>",

        (
            f"📉 <b>Average RSI:</b> "
            f"{analysis['average_rsi']:.1f}"

            if analysis[
                "average_rsi"
            ] is not None

            else

            "📉 <b>Average RSI:</b> "
            "Unavailable"
        ),

        (
            f"📦 <b>Relative Volume:</b> "
            f"{analysis['average_volume_ratio']:.2f}x"

            if analysis[
                "average_volume_ratio"
            ] is not None

            else

            "📦 <b>Relative Volume:</b> "
            "Unavailable"
        ),

        (
            f"📐 <b>Average VWMA(20):</b> "
            f"{format_price(analysis['average_vwma'])}"

            if analysis[
                "average_vwma"
            ] is not None

            else

            "📐 <b>Average VWMA(20):</b> "
            "Unavailable"
        ),

        (
            f"🌊 <b>Average ATR:</b> "
            f"{analysis['average_atr_percent']:.2f}%"

            if analysis[
                "average_atr_percent"
            ] is not None

            else

            "🌊 <b>Average ATR:</b> "
            "Unavailable"
        ),

        f"🧱 <b>Structure:</b> "
        f"{analysis['structure']}",

        f"🛡️ <b>Nearest Support:</b> "
        f"{level_text(
            analysis['nearest_support'],
            price,
        )}",

        f"🚧 <b>Nearest Resistance:</b> "
        f"{level_text(
            analysis['nearest_resistance'],
            price,
        )}",

        "",

        "📐 <b>VOLUME PROFILE "
        "— FIXED RANGE APPROX.</b>",
    ]

    if vp:

        lines += [

            f"🎯 <b>POC:</b> "
            f"{format_price(vp['poc'])}",

            f"🔺 <b>VAH:</b> "
            f"{format_price(vp['vah'])}",

            f"🔻 <b>VAL:</b> "
            f"{format_price(vp['val'])}",

            f"📍 <b>Position:</b> "
            f"{vp['position']}",
        ]

    else:

        lines.append(
            "Unavailable"
        )

    lines += [

        "",

        "🧲 <b>LIQUIDITY / "
        "REJECTIONS</b>",

        f"🟢 Bullish sweeps: "
        f"{patterns['bullish_sweeps']}",

        f"🔴 Bearish sweeps: "
        f"{patterns['bearish_sweeps']}",

        f"🟢 Bullish rejection zones: "
        f"{patterns['bullish_rejections']}",

        f"🔴 Bearish rejection zones: "
        f"{patterns['bearish_rejections']}",

        "",

        "⚡ <b>FAIR VALUE GAPS</b>",

        f"🟢 Bullish FVGs detected: "
        f"{patterns['bullish_fvgs']}",

        f"🔴 Bearish FVGs detected: "
        f"{patterns['bearish_fvgs']}",

        "",

        "📡 <b>TRADINGVIEW "
        "WEBHOOK CONFIRMATION</b>",

        f"🟢 Bullish: "
        f"{tv['bullish']}",

        f"🔴 Bearish: "
        f"{tv['bearish']}",

        f"📥 Alerts received: "
        f"{tv['received']}",

        (
            "ℹ️ Zero means no qualifying "
            "TradingView webhook data "
            "has reached the bot. "
            "It does NOT mean TradingView "
            "itself is neutral."
        ),

        "",

        "📊 <b>DATA QUALITY</b>",

        f"{analysis['valid_count']}/"
        f"{analysis['total_count']} "
        f"timeframes available",

        f"🟢 Bullish TFs: "
        f"{counts['bullish']}",

        f"🔴 Bearish TFs: "
        f"{counts['bearish']}",

        f"🟡 Neutral TFs: "
        f"{counts['neutral']}",

        "",

        "⚠️ <b>Pattern counts are "
        "detections, not trade guarantees.</b>",
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
            f"<b>🔎 "
            f"Scanning {coin}...</b>\n\n"

            "📡 Live OHLCV\n"
            "📈 EMA 20 / 50 / 200\n"
            "📉 RSI + MACD\n"
            "📦 Relative volume + VWMA\n"
            "🌊 ATR\n"
            "🧱 Swing highs/lows + structure\n"
            "🛡️ Support / resistance\n"
            "🧲 Liquidity sweeps + rejection zones\n"
            "⚡ Fair value gaps\n"
            "📐 Fixed-range volume profile\n"
            "📡 TradingView webhook confirmation"
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
            "search?"
            "q=cryptocurrency+crypto+"
            "bitcoin+ethereum"
            "&hl=en-US"
            "&gl=US"
            "&ceid=US:en"
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

                f"<b>{number}.</b> "
                f'<a href="{link}">'
                f"{title}</a>\n\n"
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
            "market structure analysis.\n\n"

            "<b>Reads:</b>\n"

            "📈 EMA / RSI / MACD / VWMA(20)\n"

            "📦 Relative volume\n"

            "🧱 Swing highs/lows + structure\n"

            "🛡️ Support / resistance\n"

            "🧲 Liquidity sweeps + rejection zones\n"

            "⚡ Fair value gaps\n"

            "📐 Fixed-range volume profile approximation\n"

            "📡 Optional TradingView webhook confirmation\n\n"

            "This is analytical software, "
            "not a guaranteed trade signal."
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

            "It pulls OHLCV market data "
            "and evaluates multiple timeframes.\n\n"

            "The engine calculates defined "
            "technical conditions including "
            "trend, momentum, structure, "
            "support/resistance, liquidity "
            "sweeps, rejection zones, FVGs "
            "and volume profile.\n\n"

            "TradingView confirmation only "
            "appears when an actual TradingView "
            "alert posts JSON to /webhook.\n\n"

            "Volume Profile is an OHLCV "
            "approximation because standard "
            "candle data does not contain "
            "true volume-at-price."
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
            "VIP features are not enabled yet."
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

            if callback_data == "scan_menu":

                send_telegram(

                    (
                        "<b>📊 "
                        "SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency."
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

            elif callback_data == "main_menu":

                send_welcome(
                    chat_id
                )

            elif callback_data == "news_all":

                send_telegram(
                    get_crypto_news(),
                    chat_id,
                    main_menu(),
                )

            elif callback_data == "help":

                send_help(
                    chat_id
                )

            elif callback_data == "vip":

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

        # ====================================================
        # SECURITY
        # ====================================================

        if (
            WEBHOOK_SECRET
            and
            data.get(
                "secret"
            )
            != WEBHOOK_SECRET
        ):

            return jsonify({

                "error":
                    "Unauthorized"

            }), 401

        # ====================================================
        # NORMALIZE SYMBOL
        # ====================================================

        symbol = normalize_tv_symbol(
            data.get(
                "symbol",
                "",
            )
        )

        # ====================================================
        # NORMALIZE TIMEFRAME
        # ====================================================

        timeframe = (
            normalize_tv_timeframe(
                data.get(
                    "timeframe",
                    "",
                )
            )
        )

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
                "NEUTRAL",
            )

        ).upper()

        # ====================================================
        # STORE TRADINGVIEW DATA
        # ====================================================

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

        print(

            "TRADINGVIEW:",

            symbol,

            timeframe,

            signal,
        )

        # ====================================================
        # TELEGRAM UPDATE
        # ====================================================

        if TELEGRAM_CHAT_ID:

            send_telegram(

                (
                    "<b>📡 "
                    "TRADINGVIEW UPDATE</b>\n\n"

                    f"<b>"
                    f"{html.escape(symbol)}"
                    f"</b>\n"

                    f"Timeframe: "
                    f"{html.escape(timeframe)}\n"

                    f"Signal: "
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

        "tradingview_webhook":
            "/webhook",

        "market_test":
            "/test-market/BTC",

        "coins":
            list(
                COINS.keys()
            ),

        "timeframes":
            list(
                TIMEFRAMES.keys()
            ),
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
                list(
                    COINS.keys()
                ),

        }), 400

    return jsonify(
        scan_coin(
            coin
        )
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
        f"/telegram-webhook"
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