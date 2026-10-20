import os
import html
import time
import math
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import ccxt
import feedparser
import psycopg
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
# POSTGRESQL - PERSISTENT SIGNAL REPORTING
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "")
VIP_OWNER_TELEGRAM_ID = os.getenv("VIP_OWNER_TELEGRAM_ID", "")

# SIMULATED FUTURES SETTINGS
SIMULATED_MARGIN_USD = float(os.getenv("SIMULATED_MARGIN_USD", "1000"))

try:
    SIMULATED_LEVERAGE = int(os.getenv("SIMULATED_LEVERAGE", "25"))
except (TypeError, ValueError):
    SIMULATED_LEVERAGE = 25

SIMULATED_LEVERAGE = max(25, min(100, SIMULATED_LEVERAGE))


def init_reporting_db():
    if not DATABASE_URL:
        print("REPORTING DB ERROR: DATABASE_URL is not configured.")
        return False

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS signal_records (
                        id BIGSERIAL PRIMARY KEY,
                        audience TEXT NOT NULL,
                        coin TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price DOUBLE PRECISION NOT NULL,
                        stop_price DOUBLE PRECISION NOT NULL,
                        tp1_price DOUBLE PRECISION NOT NULL,
                        tp2_price DOUBLE PRECISION NOT NULL,
                        tp3_price DOUBLE PRECISION NOT NULL,
                        sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        report_date DATE NOT NULL,
                        status TEXT NOT NULL DEFAULT 'OPEN',
                        exit_price DOUBLE PRECISION,
                        return_pct DOUBLE PRECISION,
                        outcome_updated_at TIMESTAMPTZ,
                        highest_target_hit INTEGER NOT NULL DEFAULT 0,
                        pnl_usd DOUBLE PRECISION,
                        position_size_usd DOUBLE PRECISION,
                        fees_usd DOUBLE PRECISION,
                        leverage INTEGER NOT NULL DEFAULT 25,
                        UNIQUE (audience, id)
                    )
                """)

                cur.execute("""
                    ALTER TABLE signal_records
                    ADD COLUMN IF NOT EXISTS highest_target_hit INTEGER
                    NOT NULL DEFAULT 0
                """)
                cur.execute("""
                    ALTER TABLE signal_records
                    ADD COLUMN IF NOT EXISTS pnl_usd DOUBLE PRECISION
                """)
                cur.execute("""
                    ALTER TABLE signal_records
                    ADD COLUMN IF NOT EXISTS position_size_usd DOUBLE PRECISION
                """)
                cur.execute("""
                    ALTER TABLE signal_records
                    ADD COLUMN IF NOT EXISTS fees_usd DOUBLE PRECISION
                """)
                cur.execute("""
                    ALTER TABLE signal_records
                    ADD COLUMN IF NOT EXISTS leverage INTEGER NOT NULL DEFAULT 25
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vip_payment_submissions (
                        id BIGSERIAL PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        username TEXT,
                        full_name TEXT,
                        payment_method TEXT,
                        status TEXT NOT NULL DEFAULT 'awaiting_receipt',
                        photo_file_id TEXT,
                        transaction_reference TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        reviewed_at TIMESTAMPTZ,
                        reviewed_by BIGINT
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vip_registration_submissions (
                        id BIGSERIAL PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        username TEXT,
                        full_name TEXT,
                        bydfi_uid TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending_review',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        reviewed_at TIMESTAMPTZ,
                        reviewed_by BIGINT
                    )
                """)
                
            conn.commit()
            
        print("REPORTING DB: signal_records table is ready.")
        return True

    except Exception as exc:
        print("REPORTING DB INIT ERROR:", repr(exc))
        return False



def save_signal_record(
    audience,
    coin,
    direction,
    entry,
    stop,
    tp1,
    tp2,
    tp3,
    position_size_usd=None,
    leverage=25,
):
    if not DATABASE_URL:
        print("REPORTING DB ERROR: cannot save signal without DATABASE_URL.")
        return False

    try:
        leverage = int(leverage)
        if leverage not in (25, 50, 75, 100):
            print("REPORTING DB ERROR: invalid leverage:", leverage)
            return False

        report_date = datetime.now(
            ZoneInfo("America/New_York")
        ).date()

        if position_size_usd is None:
            position_size_usd = SIMULATED_MARGIN_USD

        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO signal_records (
                        audience, coin, direction,
                        entry_price, stop_price,
                        tp1_price, tp2_price, tp3_price,
                        report_date, status,
                        position_size_usd, leverage
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, 'OPEN', %s, %s
                    )
                    RETURNING id
                """, (
                    audience,
                    coin,
                    direction,
                    float(entry),
                    float(stop),
                    float(tp1),
                    float(tp2),
                    float(tp3),
                    report_date,
                    float(position_size_usd),
                    leverage,
                ))
                record_id = cur.fetchone()[0]

            conn.commit()

        print(
            "REPORTING DB: saved signal",
            record_id,
            audience,
            coin,
            direction,
            "leverage:",
            leverage,
        )
        return record_id

    except Exception as exc:
        print("REPORTING DB SAVE ERROR:", repr(exc))
        return False

def update_signal_outcome(
    record_id,
    status,
    exit_price,
    highest_target_hit=0,
    pnl_usd=None,
    position_size_usd=None,
    fees_usd=None,
):
    if not DATABASE_URL:
        print("REPORTING DB ERROR: DATABASE_URL is not configured.")
        return False

    valid_statuses = {"TP1", "TP2", "TP3", "SL"}

    if status not in valid_statuses:
        print("REPORTING DB ERROR: invalid outcome status:", status)
        return False

    try:
        exit_price = float(exit_price)

        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        entry_price,
                        direction,
                        highest_target_hit,
                        leverage,
                        position_size_usd
                    FROM signal_records
                    WHERE id = %s AND status = 'OPEN'
                    FOR UPDATE
                """, (record_id,))


                record = cur.fetchone()

                if record is None:
                    print(
                        "REPORTING DB ERROR: signal not found or already closed:",
                        record_id,
                    )
                    return False

                
                (
                    entry_price,
                    direction,
                    previous_target,
                    stored_leverage,
                    stored_position_size,
                ) = record

                leverage = int(stored_leverage or SIMULATED_LEVERAGE)

                if leverage not in (25, 50, 75, 100):
                    print(
                        "REPORTING DB ERROR: invalid stored leverage:",
                        record_id,
                        leverage,
                    )
                    return False

                if position_size_usd is None:
                    position_size_usd = (
                        stored_position_size
                        if stored_position_size is not None
                        else SIMULATED_MARGIN_USD
                    )
                else:
                    position_size_usd = float(position_size_usd)

                highest_target_hit = max(
                    int(previous_target or 0),
                    int(highest_target_hit or 0),
                )

                if entry_price <= 0:
                    print("REPORTING DB ERROR: invalid entry price:", entry_price)
                    return False

                is_long = str(direction).upper() in ("LONG", "CALL / LONG")

                price_change = (
                    (exit_price - float(entry_price)) / float(entry_price)
                    if is_long
                    else (float(entry_price) - exit_price) / float(entry_price)
                )

                
                # Gross simulated return using this signal's leverage.
                return_pct = price_change * leverage * 100

                # No simulated trading fees are deducted.
                fees_usd = 0.0

                if pnl_usd is None:
                    notional_usd = position_size_usd * leverage
                    pnl_usd = notional_usd * price_change

                cur.execute("""
                    UPDATE signal_records
                    SET status = %s,
                        exit_price = %s,
                        return_pct = %s,
                        outcome_updated_at = NOW(),
                        highest_target_hit = %s,
                        pnl_usd = %s,
                        position_size_usd = %s,
                        fees_usd = 0
                    WHERE id = %s
                """, (
                    status,
                    exit_price,
                    return_pct,
                    highest_target_hit,
                    float(pnl_usd),
                    position_size_usd,
                    record_id,
                ))

            conn.commit()

        print(
            "REPORTING DB: outcome updated",
            record_id,
            status,
            "leverage:", leverage,
            "return %:", round(return_pct, 4),
            "simulated gross P/L:", round(float(pnl_usd), 2),
        )
        return True

    except Exception as exc:
        print("REPORTING DB OUTCOME ERROR:", repr(exc))
        return False


def send_daily_report(audience, report_date=None):
    if audience not in ("free", "vip"):
        return False

    chat_id = (
        FREE_SIGNAL_CHAT_ID
        if audience == "free"
        else VIP_SIGNAL_CHAT_ID
    )

    if not DATABASE_URL or not chat_id:
        print("DAILY REPORT SKIPPED: missing database or chat ID.")
        return False

    if report_date is None:
        report_date = datetime.now(
            ZoneInfo("America/New_York")
        ).date()

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1
                    FROM daily_report_log
                    WHERE report_date = %s AND audience = %s
                """, (report_date, audience))

                if cur.fetchone():
                    print(
                        "DAILY REPORT ALREADY SENT:",
                        audience, report_date,
                    )
                    return False

                cur.execute("""
                    SELECT coin, direction, status, pnl_usd,
                           highest_target_hit, leverage
                    FROM signal_records
                    WHERE report_date = %s AND audience = %s
                    ORDER BY sent_at ASC
                """, (report_date, audience))

                rows = cur.fetchall()

        if not rows:
            print(
                "DAILY REPORT SKIPPED: no signals:",
                audience, report_date,
            )
            return False

        completed = [
            row for row in rows
            if row[2] != "OPEN" and row[3] is not None
        ]

        pending = [
            row for row in rows
            if row[2] == "OPEN" or row[3] is None
        ]

        wins = sum(1 for row in completed if float(row[3]) > 0)
        losses = sum(1 for row in completed if float(row[3]) < 0)
        net_pnl = sum(float(row[3]) for row in completed)
        win_rate = (
            wins / len(completed) * 100
            if completed else 0.0
        )

        title = (
            "FREE DAILY RESULTS"
            if audience == "free"
            else "VIP DAILY RESULTS"
        )

        report_lines = [
            f"<b>📊 SIDESHIFT AI — {title}</b>",
            f"📅 {report_date.strftime('%b %d, %Y')}",
            "",
        ]

        for coin, direction, status, pnl, highest_target, leverage in rows:
            coin_text = html.escape(str(coin))
            direction_text = html.escape(str(direction))
            leverage = int(leverage or 25)
            highest_target = int(highest_target or 0)

            if status == "OPEN" or pnl is None:
                if highest_target > 0:
                    outcome = (
                        f"⏳ PENDING — TP{highest_target} reached so far"
                    )
                else:
                    outcome = "⏳ PENDING — no target confirmed yet"

                report_lines.extend([
                    f"⏳ <b>{coin_text}</b> — {direction_text}",
                    f"Status: {outcome}",
                    f"Leverage: {leverage}x",
                    "P/L: Pending",
                    "",
                ])
                continue

            pnl = float(pnl)
            result_icon = (
                "🟢" if pnl > 0
                else "🔴" if pnl < 0
                else "⚪"
            )

            status_text = {
                "TP1": "TP1 HIT",
                "TP2": "TP2 HIT",
                "TP3": "TP3 HIT",
                "SL": "STOP LOSS",
            }.get(str(status), str(status))

            report_lines.extend([
                f"{result_icon} <b>{coin_text}</b> — {direction_text}",
                f"Outcome: <b>{html.escape(status_text)}</b>",
                f"Leverage: {leverage}x",
                (
                    f"Simulated P/L: "
                    f"<b>{'+' if pnl > 0 else ''}${pnl:,.2f}</b>"
                ),
                "",
            ])

        report_lines.extend([
            "━━━━━━━━━━━━━━━━━━",
            f"Signals sent: <b>{len(rows)}</b>",
            f"Completed: <b>{len(completed)}</b>",
            f"Pending: <b>{len(pending)}</b>",
            f"Wins: <b>{wins}</b>",
            f"Losses: <b>{losses}</b>",
            f"Win rate: <b>{win_rate:.1f}%</b>",
            (
                f"Net daily simulated P/L: "
                f"<b>{'+' if net_pnl > 0 else ''}${net_pnl:,.2f}</b>"
            ),
            "",
        ])

        # Split the report before Telegram's message-length limit.
        chunks = []
        current = []

        for line in report_lines:
            candidate = "\n".join(current + [line])

            if len(candidate) > 3200 and current:
                chunks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)

        if current:
            chunks.append("\n".join(current))

        for index, message in enumerate(chunks, start=1):
            if len(chunks) > 1:
                message = (
                    f"<b>{html.escape(title)} "
                    f"({index}/{len(chunks)})</b>\n\n"
                    + message
                )

            if not send_telegram(message, chat_id):
                print(
                    "DAILY REPORT SEND FAILED:",
                    audience, report_date,
                    "part:", index,
                )
                return False

        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO daily_report_log (report_date, audience)
                    VALUES (%s, %s)
                    ON CONFLICT (report_date, audience) DO NOTHING
                """, (report_date, audience))
            conn.commit()

        print(
            "DAILY REPORT SENT:",
            audience, report_date,
            "completed:", len(completed),
            "pending:", len(pending),
            "net P/L:", round(net_pnl, 2),
        )
        return True

    except Exception as exc:
        print("DAILY REPORT ERROR:", audience, repr(exc))
        return False


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
        "5",
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

BINANCE_FUTURES_KLINES_URL = (
    "https://fapi.binance.com/fapi/v1/klines"
)

BINANCE_FUTURES_EXCHANGE_INFO_URL = (
    "https://fapi.binance.com/fapi/v1/exchangeInfo"
)

OKX_PUBLIC_INSTRUMENTS_URL = (
    "https://us.okx.com/api/v5/public/instruments"
)

OKX_MARKET_CANDLES_URL = (
    "https://us.okx.com/api/v5/market/candles"
)



# ============================================================
# OKX USDT PERPETUAL DISCOVERY
# ============================================================

# Approved assets to scan. OKX must independently verify
# that each one is a live USDT-settled perpetual swap.

HARDCODED_APPROVED_ASSETS = {
    # Core crypto contracts
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA",
    "AVAX", "LINK", "LTC", "WLD", "NEAR", "APT", "ARB",
    "OP", "INJ", "FIL", "ATOM", "DOT", "UNI", "AAVE",
    "ETC", "ALGO", "XLM", "HBAR", "SEI", "TIA", "PEPE",
    "PENGU", "WIF", "BONK", "FLOKI", "SHIB", "SUI",
    "BCH", "ICP", "RENDER", "PYTH", "JUP", "AR", "XTZ",
    "VET", "GRT", "POL", "TRX", "EGLD", "LDO", "XDC",
    "JTO", "ORCA", "JASMY", "IOST", "VIRTUAL", "GALA",
    "RUNE", "IOTA", "IMX", "CHZ", "ARKM", "USTC", "ENJ",
    "AXS", "SAGA", "CFX", "LUNA2", "SYN", "KSM", "CVX",
    "CRO", "ZRX", "MNT", "GMX", "SKL", "SPELL", "BSV",
    "AEVO", "1INCH", "PENDLE", "COMP", "SYRUP", "DYDX",
    "THETA", "FLR", "BOME", "APE", "ONE", "BLUR", "BAT",
    "HYPE", "TAO", "GRASS", "ENA", "CRV", "AERO", "ONDO",
    "STX", "SAND", "AXL", "ICNT",

    # Leveraged-denomination and meme contracts
    "1000SHIB", "1000BONK", "1000LUNC", "1000PEPE",
    "1000SATS", "1000RATS", "TOSHI", "TURBO", "MELANIA",
    "CLANKER", "JELLYJELLY", "FIGHT", "BAN", "PUMP",
    "SIREN", "SKYAI", "GIGGLE", "FARTCOIN",

    # Additional screenshot contracts
    "IBM", "ESPORTS", "PIPPIN", "BSB", "DEXE", "RAVE",
    "SLP", "ME", "TNSR", "GUN", "ACH", "DRIFT", "HIVE",
    "DYM", "RESOLV", "PRL", "TAC", "MERL", "DOOD",
    "SAHARA", "TSM", "DRAM", "ALLO", "EDGE", "PIEVERSE",
    "NAORIS", "CGPT", "HYPER", "SONIC", "MOCA", "XAI",
    "HOME", "AWE", "COPPER", "OPG", "ORDI", "B",
    "SIGN", "KAT", "OFC", "BR", "CROSS", "AIA", "MYX",
    "ERA", "OG", "BREV", "HEI", "POWR", "ALICE", "SPACE",
    "COAI", "BULLA", "PHA", "LYN", "HUMA", "ASTER",
    "AVNT", "PLTR", "GOOGL", "INTC", "MMT", "BIO", "BZ",
    "ID", "BILL", "PIXEL", "BLESS", "ANIME", "NFLX",
    "HOOD", "MSFT", "MRVL", "GENIUS", "UB", "MET",
    "DELL", "GPS", "RECALL", "CLO", "SPX", "STO",
    "EDEN", "ASR", "XAUT", "PAXG", "XAU", "XAG",
    "TSLA", "NVDA", "AMZN", "QCOM", "AVGO", "MARA",
    "XOM", "SHOP", "ON", "HYUNDAI", "UNITREE", "KR200",
    "LYTE", "SPCH", "BICO", "SKY", "WLFI", "MON",
    "KERNEL", "TAG", "AST", "TSM", "QCOM",

    # Additional symbols recorded from later screenshots
    "JUP", "XPD", "QQQ", "AMD", "ORCL", "CBRS", "APR",
    "BERA", "BEAT", "INIT", "TRUMP", "XPL", "CC",
    "VELVET", "FET", "BASE", "XPIN", "SUS", "MOVR",
    "EIGEN", "CHIP", "SOXL", "SNDK", "JCT", "ZBCN",
    "WIFU", "VYVY", "KAS", "RIVER", "RSR", "LAB",
    "ZAMA", "NMR", "SPCX", "MEGA", "ARIA", "MU",
    "USELESS", "BABY", "EDU", "CL", "META", "MSTR"
}

# Optional Railway override for the approved asset list.
# If Railway has no list configured, preserve the hardcoded list.
BYDFI_PERPETUAL_ASSETS = {
    asset.strip().upper()
    for asset in os.getenv("BYDFI_PERPETUAL_ASSETS", "").split(",")
    if asset.strip()
}

APPROVED_ASSETS = (
    BYDFI_PERPETUAL_ASSETS
    if BYDFI_PERPETUAL_ASSETS
    else HARDCODED_APPROVED_ASSETS
)

OKX_PERPETUAL_MARKETS = {}
OKX_MARKET_DISCOVERY_OK = False
GATEIO_PERPETUAL_MARKETS = {}
GATEIO_MARKET_DISCOVERY_OK = False


def inspect_okx_perpetuals():
    global OKX_PERPETUAL_MARKETS
    global OKX_MARKET_DISCOVERY_OK

    try:
        response = requests.get(
            OKX_PUBLIC_INSTRUMENTS_URL,
            params={"instType": "SWAP"},
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "SideShiftAI/4.0"},
        )

        print("OKX INSTRUMENT DISCOVERY HTTP:", response.status_code)
        response.raise_for_status()
        payload = response.json()

        if payload.get("code") != "0":
            raise RuntimeError(
                f"OKX instruments API error "
                f"{payload.get('code')}: {payload.get('msg')}"
            )

        instruments = payload.get("data", [])
        print("OKX RAW SWAP INSTRUMENT COUNT:", len(instruments))

        if instruments:
            print("OKX RAW INSTRUMENT SAMPLE:", instruments[0])

        perpetuals = {}

        for instrument in instruments:
            inst_id = str(instrument.get("instId") or "")
            if not inst_id.endswith("-USDT-SWAP"):
                continue

            # A USDT-settled swap is the required contract type.
            settle = str(instrument.get("settleCcy") or "").upper()
            if settle and settle != "USDT":
                continue

            if instrument.get("state") != "live":
                continue

            base = str(instrument.get("baseCcy") or "").upper()

            # Fallback to the exact instrument ID format.
            if not base:
                base = inst_id[:-len("-USDT-SWAP")]

            if base in APPROVED_ASSETS:
                perpetuals[base] = inst_id

        if not perpetuals:
            raise RuntimeError(
                "No approved live USDT perpetuals matched. "
                "Check OKX RAW INSTRUMENT SAMPLE above."
            )

        OKX_PERPETUAL_MARKETS = perpetuals
        OKX_MARKET_DISCOVERY_OK = True

        print("OKX APPROVED LIVE USDT PERPETUALS READY:", len(perpetuals))
        print("OKX APPROVED PERPETUAL SAMPLE:", list(perpetuals.items())[:15])
        print(
            "APPROVED ASSETS NOT AVAILABLE ON OKX:",
            sorted(APPROVED_ASSETS - set(perpetuals)),
        )
        return True

    except Exception as exc:
        OKX_PERPETUAL_MARKETS = {}
        OKX_MARKET_DISCOVERY_OK = False
        print("OKX FUTURES DISCOVERY ERROR:", repr(exc))
        return False




def inspect_gateio_perpetuals():
    """Discover approved Gate.io USDT perpetual contracts."""
    global GATEIO_PERPETUAL_MARKETS
    global GATEIO_MARKET_DISCOVERY_OK

    try:
        response = requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/contracts",
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        print("GATE.IO CONTRACT DISCOVERY HTTP:", response.status_code)
        response.raise_for_status()
        contracts = response.json()

        if not isinstance(contracts, list):
            raise RuntimeError("Unexpected Gate.io contracts response")

        markets = {}
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            if contract.get("in_delisting", False):
                continue

            name = str(contract.get("name") or "").upper()
            if name.endswith("_USDT"):
                base = name[:-5]
                if base in APPROVED_ASSETS:
                    markets[base] = name

        GATEIO_PERPETUAL_MARKETS = markets
        GATEIO_MARKET_DISCOVERY_OK = True

        missing_from_okx = set(APPROVED_ASSETS) - set(OKX_PERPETUAL_MARKETS)
        covered = sorted(missing_from_okx & set(markets))

        print("GATE.IO APPROVED USDT PERPETUALS READY:", len(markets))
        print("OKX-MISSING ASSETS FOUND ON GATE.IO:", len(covered))
        print("GATE.IO ADDITIONAL ASSET SAMPLE:", covered[:100])
        print(
            "APPROVED ASSETS NOT FOUND ON OKX OR GATE.IO:",
            sorted(missing_from_okx - set(markets)),
        )
        return True

    except Exception as exc:
        GATEIO_PERPETUAL_MARKETS = {}
        GATEIO_MARKET_DISCOVERY_OK = False
        print("GATE.IO FUTURES DISCOVERY ERROR:", repr(exc))
        return False


def get_okx_perpetual_universe():
    if not OKX_MARKET_DISCOVERY_OK:
        print("OKX FUTURES UNAVAILABLE — SCANNING PAUSED")
        return {}

    return dict(OKX_PERPETUAL_MARKETS)


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
    
    "LTC": {
        "coinbase": "LTC-USD",
        "kraken": "LTCUSD",
        "binance": "LTCUSDT",
        "cmc": "LTC",
    },
        "NEAR": {
        "coinbase": "NEAR-USD",
        "kraken": "NEARUSD",
        "binance": "NEARUSDT",
        "cmc": "NEAR",
    },
    "APT": {
        "coinbase": "APT-USD",
        "kraken": "APTUSD",
        "binance": "APTUSDT",
        "cmc": "APT",
    },
    "ARB": {
        "coinbase": "ARB-USD",
        "kraken": "ARBUSD",
        "binance": "ARBUSDT",
        "cmc": "ARB",
    },
    "OP": {
        "coinbase": "OP-USD",
        "kraken": "OPUSD",
        "binance": "OPUSDT",
        "cmc": "OP",
    },
    "INJ": {
        "coinbase": "INJ-USD",
        "kraken": "INJUSD",
        "binance": "INJUSDT",
        "cmc": "INJ",
    },
    "FIL": {
        "coinbase": "FIL-USD",
        "kraken": "FILUSD",
        "binance": "FILUSDT",
        "cmc": "FIL",
    },
    "ATOM": {
        "coinbase": "ATOM-USD",
        "kraken": "ATOMUSD",
        "binance": "ATOMUSDT",
        "cmc": "ATOM",
    },
    "DOT": {
        "coinbase": "DOT-USD",
        "kraken": "DOTUSD",
        "binance": "DOTUSDT",
        "cmc": "DOT",
    },
    "UNI": {
        "coinbase": "UNI-USD",
        "kraken": "UNIUSD",
        "binance": "UNIUSDT",
        "cmc": "UNI",
    },
    "AAVE": {
        "coinbase": "AAVE-USD",
        "kraken": "AAVEUSD",
        "binance": "AAVEUSDT",
        "cmc": "AAVE",
    },
    "ETC": {
        "coinbase": "ETC-USD",
        "kraken": "ETCUSD",
        "binance": "ETCUSDT",
        "cmc": "ETC",
    },
    "ALGO": {
        "coinbase": "ALGO-USD",
        "kraken": "ALGOUSD",
        "binance": "ALGOUSDT",
        "cmc": "ALGO",
    },
    "XLM": {
        "coinbase": "XLM-USD",
        "kraken": "XLMUSD",
        "binance": "XLMUSDT",
        "cmc": "XLM",
    },
    "HBAR": {
        "coinbase": "HBAR-USD",
        "kraken": "HBARUSD",
        "binance": "HBARUSDT",
        "cmc": "HBAR",
    },
    "SEI": {
        "coinbase": "SEI-USD",
        "kraken": "SEIUSD",
        "binance": "SEIUSDT",
        "cmc": "SEI",
    },
    "TIA": {
        "coinbase": "TIA-USD",
        "kraken": "TIAUSD",
        "binance": "TIAUSDT",
        "cmc": "TIA",
    },
    "RENDER": {
        "coinbase": "RENDER-USD",
        "kraken": "RENDERUSD",
        "binance": "RENDERUSDT",
        "cmc": "RENDER",
    },
    "WIF": {
        "coinbase": "WIF-USD",
        "kraken": "WIFUSD",
        "binance": "WIFUSDT",
        "cmc": "WIF",
    },
    "BONK": {
        "coinbase": "BONK-USD",
        "kraken": "BONKUSD",
        "binance": "BONKUSDT",
        "cmc": "BONK",
    },
    "FLOKI": {
        "coinbase": "FLOKI-USD",
        "kraken": "FLOKIUSD",
        "binance": "FLOKIUSDT",
        "cmc": "FLOKI",
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
    "30m": {
        "coinbase": 1800,
        "kraken": 30,
        "binance": "30m",
        "weight": 1.1,
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
COINGLASS_DIAGNOSTIC_LOGGED = set()

SIGNAL_STATE = {
    "date": None,

    "free_sent_today": 0,

    "vip_sent_today": 0,

    "last_free_signal": {},

    "last_vip_signal": {},
}
ACTIVE_TRADES = {}
STATE_LOCK = threading.Lock()

BACKGROUND_STARTED = False

ACTIVE_TRADES_LOCK = threading.Lock()
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


def edit_telegram_message(
    chat_id,
    message_id,
    message,
    keyboard=None,
):
    if not TELEGRAM_API or not chat_id or not message_id:
        return False

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
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
            f"{TELEGRAM_API}/editMessageText",
            json=payload,
            timeout=15,
        )
        print(
            "TELEGRAM EDIT:",
            response.status_code,
            response.text[:200],
        )
        return response.ok

    except Exception as exc:
        print("TELEGRAM EDIT ERROR:", repr(exc))
        return False

def begin_vip_receipt_submission(user_id, username, full_name, payment_method):
    if not DATABASE_URL:
        print("VIP PAYMENT ERROR: DATABASE_URL is not configured.")
        return False

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE vip_payment_submissions
                    SET status = 'cancelled'
                    WHERE telegram_user_id = %s
                      AND status = 'awaiting_receipt'
                """, (user_id,))

                cur.execute("""
                    INSERT INTO vip_payment_submissions
                        (telegram_user_id, username, full_name, payment_method, status)
                    VALUES (%s, %s, %s, %s, 'awaiting_receipt')
                """, (user_id, username, full_name, payment_method))

            conn.commit()

        return True

    except Exception as exc:
        print("VIP PAYMENT DB ERROR:", repr(exc))
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
    return [
        [
            {
                "text": "🟢 Free Channel",
                "callback_data": "free_signals",
            },
            {
                "text": "👑 VIP Channel",
                "callback_data": "vip",
            },
        ],

        [
            {
                "text": "🔎 Scan a Coin",
                "callback_data": "scan_menu",
            },
            {
                "text": "📰 Crypto News",
                "callback_data": "news_all",
            },
        ],
        [
            {
                "text": "ℹ️ How It Works",
                "callback_data": "help",
            }
        ],
    ]



def coin_selection_menu():
    coins = list(COINS.keys())
    keyboard = []

    for i in range(0, len(coins), 3):
        keyboard.append([
            {
                "text": f"🪙 {coin}",
                "callback_data": f"scan_{coin}",
            }
            for coin in coins[i:i + 3]
        ])

    keyboard.append([
        {"text": "📰 Crypto News", "callback_data": "news_all"},
        {"text": "👑 VIP", "callback_data": "vip"},
    ])
    keyboard.append([
        {"text": "⬅️ Main Menu", "callback_data": "main_menu"},
    ])

    return keyboard


def scan_menu():
    return [
        [
            {
                "text": "🔎 Scan Another Coin",
                "callback_data": "scan_menu",
            },
        ],
        [
            {
                "text": "📰 Crypto News",
                "callback_data": "news_all",
            },
            {
                "text": "⬅️ Main Menu",
                "callback_data": "main_menu",
            },
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


def validate_candles(candles, timeframe=None):
    """Validate candles and optionally require completed, fresh data."""
    valid = []
    seen_timestamps = set()
    now_ms = int(time.time() * 1000)

    timeframe_ms = {
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1D": 24 * 60 * 60 * 1000,
    }

    interval_ms = timeframe_ms.get(timeframe)

    for candle in candles:
        try:
            timestamp = int(candle["timestamp"])
            open_price = float(candle["open"])
            high = float(candle["high"])
            low = float(candle["low"])
            close = float(candle["close"])
            volume = float(candle["volume"])

            values = (open_price, high, low, close, volume)

            if not all(math.isfinite(value) for value in values):
                continue

            if timestamp <= 0 or timestamp > now_ms + 60_000:
                continue

            if timestamp in seen_timestamps:
                continue

            if min(open_price, high, low, close) <= 0:
                continue

            if volume < 0:
                continue

            if (
                high < low
                or high < open_price
                or high < close
                or low > open_price
                or low > close
            ):
                continue

            # When a timeframe is supplied, exclude unfinished candles.
            if interval_ms is not None:
                if timestamp + interval_ms > now_ms:
                    continue

            valid.append({
                "timestamp": timestamp,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            })
            seen_timestamps.add(timestamp)

        except (KeyError, TypeError, ValueError, OverflowError):
            continue

    valid.sort(key=lambda candle: candle["timestamp"])

    # Reject the entire dataset if its newest completed candle is stale.
    if interval_ms is not None and valid:
        newest_close_time = valid[-1]["timestamp"] + interval_ms

        if now_ms - newest_close_time > 2 * interval_ms:
            print(
                "STALE CANDLE DATA:",
                timeframe,
                "latest completed candle is too old",
            )
            return []

    return valid

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

    return validate_candles(candles)


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

    return validate_candles(candles)


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

    return validate_candles(candles)


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


def get_binance_futures_candles(
    symbol,
    interval,
    limit=200,
):
    try:

        response = requests.get(
            BINANCE_FUTURES_KLINES_URL,
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

            print(
                "BINANCE FUTURES HTTP:",
                response.status_code,
                symbol,
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
            "BINANCE FUTURES ERROR:",
            repr(exc),
        )

        return []



def get_market_candles(coin, timeframe):
    coin = coin.upper()

    if coin not in APPROVED_ASSETS:
        print("ASSET NOT IN MASTER LIST:", coin)
        return [], None

    configured = TIMEFRAMES.get(timeframe, {})
    interval = configured.get("binance")

    if not interval:
        print("UNSUPPORTED TIMEFRAME:", timeframe)
        return [], None

    # Source 1: OKX USDT perpetual candles.
    if OKX_MARKET_DISCOVERY_OK and coin in OKX_PERPETUAL_MARKETS:
        symbol = OKX_PERPETUAL_MARKETS[coin]

        timeframe_map = {
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1H",
            "4h": "4H",
            "1D": "1D",
        }
        bar = timeframe_map.get(timeframe)

        if bar:
            try:
                response = requests.get(
                    OKX_MARKET_CANDLES_URL,
                    params={
                        "instId": symbol,
                        "bar": bar,
                        "limit": "200",
                    },
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "SideShiftAI/4.0"},
                )
                response.raise_for_status()
                payload = response.json()

                if payload.get("code") == "0":
                    candles = []
                    for row in payload.get("data", []):
                        if len(row) >= 6:
                            candles.append({
                                "timestamp": int(row[0]),
                                "open": float(row[1]),
                                "high": float(row[2]),
                                "low": float(row[3]),
                                "close": float(row[4]),
                                "volume": float(row[5]),
                            })

                    candles.sort(key=lambda candle: candle["timestamp"])
                    candles = validate_candles(candles, timeframe)
                    if len(candles) >= 60:
                        print("CANDLE SOURCE: OKX", coin, timeframe)
                        return candles, "OKX USDT Perpetual Candles"

            except Exception as exc:
                print("OKX CANDLE FALLBACK:", coin, repr(exc))
                
    
    # Source 2: Gate.io USDT perpetual candles.
    if GATEIO_MARKET_DISCOVERY_OK and coin in GATEIO_PERPETUAL_MARKETS:
        gate_interval = {
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1D": "1d",
        }.get(timeframe)

        if gate_interval:
            try:
                gate_response = requests.get(
                    "https://api.gateio.ws/api/v4/futures/usdt/candlesticks",
                    params={
                        "contract": GATEIO_PERPETUAL_MARKETS[coin],
                        "interval": gate_interval,
                        "limit": 200,
                    },
                    timeout=REQUEST_TIMEOUT,
                    headers={"Accept": "application/json"},
                )
                gate_response.raise_for_status()
                

                rows = gate_response.json()
                candles = []

                if isinstance(rows, list):
                    for row in rows:
                        try:
                            if isinstance(row, dict):
                                timestamp = row.get("t", row.get("timestamp"))
                                open_price = row.get("o", row.get("open"))
                                high_price = row.get("h", row.get("high"))
                                low_price = row.get("l", row.get("low"))
                                close_price = row.get("c", row.get("close"))
                                volume = row.get("v", row.get("volume", 0))
                            elif isinstance(row, (list, tuple)) and len(row) >= 6:
                                timestamp, volume, close_price, high_price, low_price, open_price = row[:6]
                            else:
                                continue

                            timestamp = int(float(timestamp))
                            if timestamp < 100_000_000_000:
                                timestamp *= 1000

                            candle = {
                                "timestamp": timestamp,
                                "open": float(open_price),
                                "high": float(high_price),
                                "low": float(low_price),
                                "close": float(close_price),
                                "volume": float(volume or 0),
                            }

                            if (
                                candle["open"] > 0
                                and candle["high"] > 0
                                and candle["low"] > 0
                                and candle["close"] > 0
                                and candle["high"] >= candle["low"]
                                and candle["high"] >= candle["open"]
                                and candle["high"] >= candle["close"]
                                and candle["low"] <= candle["open"]
                                and candle["low"] <= candle["close"]
                            ):
                                candles.append(candle)

                        except (TypeError, ValueError, OverflowError):
                            continue

                candles.sort(key=lambda item: item["timestamp"])
                candles = validate_candles(candles, timeframe)
                if len(candles) >= 60:
                    print("CANDLE SOURCE: GATE.IO", coin, timeframe)
                    return candles, "Gate.io USDT Perpetual Candles"

                print(
                    "GATE.IO CANDLES INSUFFICIENT:",
                    coin,
                    timeframe,
                    len(candles),
                )
            except Exception as exc:
                print("GATE.IO CANDLE FALLBACK:", coin, timeframe, repr(exc))

    # Only allow Binance fallback for assets verified on either exchange.
    if (
        coin not in OKX_PERPETUAL_MARKETS
        and coin not in GATEIO_PERPETUAL_MARKETS
    ):
        print(
            "SKIPPING BINANCE FUTURES: NO VERIFIED USDT PERPETUAL",
            coin,
            timeframe,
        )
        print("NO USABLE PERPETUAL CANDLE SOURCE:", coin, timeframe)
        return [], None

    # Source 3: Binance USD-M perpetual candles.

        
    # Source 2: Binance USD-M perpetual candles.
    # Binance must independently have this exact futures contract.
    binance_symbol = coin + "USDT"

    try:
        candles = get_binance_futures_candles(
            binance_symbol,
            interval,
            limit=200,
        )
        candles = validate_candles(candles, timeframe)
        if len(candles) >= 60:
            print("CANDLE SOURCE: BINANCE FUTURES", coin, timeframe)
            return candles, "Binance USD-M Perpetual Candles"

    except Exception as exc:
        print("BINANCE FUTURES FALLBACK:", coin, repr(exc))

    print(
        "NO USABLE PERPETUAL CANDLE SOURCE:",
        coin,
        timeframe,
    )
    return [], None

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

    if len(candles) < (left + right + 1):
        return highs, lows

    for i in range(left, len(candles) - right):

        current = candles[i]

        high = current["high"]
        low = current["low"]

        nearby = candles[
            i - left:
            i + right + 1
        ]

        nearby_highs = [
            c["high"]
            for j, c in enumerate(nearby)
            if j != left
        ]

        nearby_lows = [
            c["low"]
            for j, c in enumerate(nearby)
            if j != left
        ]

        # Strict pivot high.
        # Prevents equal/flat highs from creating duplicate pivots.
        if nearby_highs and high > max(nearby_highs):
            highs.append((i, high))

        # Strict pivot low.
        # Prevents equal/flat lows from creating duplicate pivots.
        if nearby_lows and low < min(nearby_lows):
            lows.append((i, low))

    return highs, lows


def calculate_structure(
    candles
):
    recent = candles[-100:]

    highs, lows = pivot_points(
        recent,
        left=3,
        right=3,
    )

    if len(highs) < 2 or len(lows) < 2:
        return {
            "label": "Unknown",
            "score": 0,
            "support": None,
            "resistance": None,
        }

    recent_highs = highs[-6:]
    recent_lows = lows[-6:]

    high_values = [
        point[1]
        for point in recent_highs
    ]

    low_values = [
        point[1]
        for point in recent_lows
    ]

    higher_highs = 0
    lower_highs = 0

    higher_lows = 0
    lower_lows = 0

    # Compare consecutive swing highs.
    for i in range(1, len(high_values)):

        if high_values[i] > high_values[i - 1]:
            higher_highs += 1

        elif high_values[i] < high_values[i - 1]:
            lower_highs += 1

    # Compare consecutive swing lows.
    for i in range(1, len(low_values)):

        if low_values[i] > low_values[i - 1]:
            higher_lows += 1

        elif low_values[i] < low_values[i - 1]:
            lower_lows += 1

    latest_high = high_values[-1]
    latest_low = low_values[-1]

    score = 0

    # Basic structure scoring.
    if higher_highs >= 1:
        score += 1

    if higher_lows >= 1:
        score += 1

    if lower_highs >= 1:
        score -= 1

    if lower_lows >= 1:
        score -= 1

    # Strong bullish structure.
    if (
        higher_highs >= 1
        and higher_lows >= 1
        and lower_highs == 0
        and lower_lows == 0
    ):
        label = "Strong Bullish Structure"
        score = 3

    # Strong bearish structure.
    elif (
        lower_highs >= 1
        and lower_lows >= 1
        and higher_highs == 0
        and higher_lows == 0
    ):
        label = "Strong Bearish Structure"
        score = -3

    # Bullish lean.
    elif score >= 2:
        label = "Bullish Lean"
        score = 2

    # Bearish lean.
    elif score <= -2:
        label = "Bearish Lean"
        score = -2

    # Anything conflicting or insufficiently directional.
    else:
        label = "Mixed / Sideways"
        score = 0

    return {
        "label": label,
        "score": score,
        "support": latest_low,
        "resistance": latest_high,
    }

def detect_fibonacci_levels(candles, lookback=100):
    """
    Calculate Fibonacci retracement levels from confirmed swing points.

    Uses completed candles only. This reports potential confluence;
    it does not independently authorize a trading signal.
    """

    result = {
        "valid": False,
        "direction": None,
        "swing_low": None,
        "swing_high": None,
        "levels": {},
        "golden_pocket": None,
        "current_price": None,
        "nearest_level": None,
        "evidence": [],
    }

    if len(candles) < 20:
        return result

    # Exclude the newest candle because it may still be forming.
    completed = candles[:-1][-lookback:]

    if len(completed) < 20:
        return result

    highs, lows = pivot_points(
        completed,
        left=3,
        right=3,
    )

    if not highs or not lows:
        return result

    # Use the most recently confirmed swing high and swing low.
    latest_high_index, swing_high = highs[-1]
    latest_low_index, swing_low = lows[-1]

    if swing_high <= swing_low:
        return result

    # Determine the direction of the most recent completed swing leg.
    if latest_low_index < latest_high_index:
        direction = "Bullish"
        swing_start = swing_low
        swing_end = swing_high

    else:
        direction = "Bearish"
        swing_start = swing_high
        swing_end = swing_low

    swing_range = swing_high - swing_low

    if swing_range <= 0:
        return result

    # Retracement prices measured against the selected swing leg.
    if direction == "Bullish":
        levels = {
            "0.382": swing_high - swing_range * 0.382,
            "0.500": swing_high - swing_range * 0.500,
            "0.618": swing_high - swing_range * 0.618,
            "0.650": swing_high - swing_range * 0.650,
            "0.705": swing_high - swing_range * 0.705,
            "0.786": swing_high - swing_range * 0.786,
        }
    else:
        levels = {
            "0.382": swing_low + swing_range * 0.382,
            "0.500": swing_low + swing_range * 0.500,
            "0.618": swing_low + swing_range * 0.618,
            "0.650": swing_low + swing_range * 0.650,
            "0.705": swing_low + swing_range * 0.705,
            "0.786": swing_low + swing_range * 0.786,
        }

    # The commonly watched golden pocket is the 0.618–0.705 area.
    golden_values = [
        levels["0.618"],
        levels["0.705"],
    ]

    golden_pocket = {
        "low": min(golden_values),
        "high": max(golden_values),
    }

    current_price = float(completed[-1]["close"])

    nearest_label = min(
        levels,
        key=lambda key: abs(current_price - levels[key]),
    )

    nearest_price = levels[nearest_label]

    result.update({
        "valid": True,
        "direction": direction,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "swing_start": swing_start,
        "swing_end": swing_end,
        "swing_range": swing_range,
        "levels": levels,
        "golden_pocket": golden_pocket,
        "current_price": current_price,
        "nearest_level": {
            "label": nearest_label,
            "price": nearest_price,
            "distance_pct": (
                abs(current_price - nearest_price)
                / current_price * 100
                if current_price > 0 else None
            ),
        },
        "price_inside_golden_pocket": (
            golden_pocket["low"]
            <= current_price
            <= golden_pocket["high"]
        ),
        "evidence": [
            "confirmed_swing_points",
            "fibonacci_retracement_calculated",
        ],
    })

    return result

def detect_fair_value_gaps(candles, max_age=100):
    """
    Detect three-candle fair value gaps.

    Bullish FVG:
        Current candle's low > candle two bars earlier's high.

    Bearish FVG:
        Current candle's high < candle two bars earlier's low.

    Tracks whether price has revisited or fully mitigated each zone.
    Uses completed candles only to avoid treating a forming candle
    as confirmed evidence.
    """

    result = {
        "bullish": [],
        "bearish": [],
        "nearest_bullish": None,
        "nearest_bearish": None,
        "evidence": [],
    }

    if len(candles) < 3:
        return result

    # Exclude the newest candle because it may still be forming.
    completed = candles[:-1]
    if len(completed) < 3:
        return result

    start = max(2, len(completed) - max_age)

    for i in range(start, len(completed)):
        first = completed[i - 2]
        middle = completed[i - 1]
        third = completed[i]

        # Ignore malformed or non-positive price data.
        values = (
            first.get("high"),
            first.get("low"),
            middle.get("high"),
            middle.get("low"),
            third.get("high"),
            third.get("low"),
            third.get("close"),
        )

        if any(v is None for v in values):
            continue

        try:
            first_high = float(first["high"])
            first_low = float(first["low"])
            middle_high = float(middle["high"])
            middle_low = float(middle["low"])
            third_high = float(third["high"])
            third_low = float(third["low"])
            third_close = float(third["close"])
        except (TypeError, ValueError):
            continue

        # Bullish imbalance: the third candle's low is above
        # the first candle's high.
        if third_low > first_high:
            zone_low = first_high
            zone_high = third_low

            touched = any(
                float(c["low"]) <= zone_high
                and float(c["high"]) >= zone_low
                for c in completed[i + 1:]
            )

            fully_filled = any(
                float(c["low"]) <= zone_low
                for c in completed[i + 1:]
            )

            result["bullish"].append({
                "low": zone_low,
                "high": zone_high,
                "midpoint": (zone_low + zone_high) / 2,
                "created_index": i,
                "age": len(completed) - 1 - i,
                "touched": touched,
                "fully_filled": fully_filled,
                "impulse_range": middle_high - middle_low,
                "formation_close": third_close,
            })

        # Bearish imbalance: the third candle's high is below
        # the first candle's low.
        if third_high < first_low:
            zone_low = third_high
            zone_high = first_low

            touched = any(
                float(c["high"]) >= zone_low
                and float(c["low"]) <= zone_high
                for c in completed[i + 1:]
            )

            fully_filled = any(
                float(c["high"]) >= zone_high
                for c in completed[i + 1:]
            )

            result["bearish"].append({
                "low": zone_low,
                "high": zone_high,
                "midpoint": (zone_low + zone_high) / 2,
                "created_index": i,
                "age": len(completed) - 1 - i,
                "touched": touched,
                "fully_filled": fully_filled,
                "impulse_range": middle_high - middle_low,
                "formation_close": third_close,
            })

    return result

def detect_smc_structure(candles):
    """
    Objective Smart Money Concepts structure layer.

    Detects both bullish and bearish:
    - Liquidity sweeps
    - Break of Structure (BOS)
    - Change of Character (CHoCH)

    This is confirmation logic only.
    It does not replace the existing structure engine.
    """

    result = {
        "liquidity_sweep": None,
        "bos": None,
        "choch": None,
        "sweep_level": None,
        "break_level": None,
        "bias": "Neutral",
        "evidence": [],
    }

    if len(candles) < 30:
        return result

    recent = candles[-100:]

    highs, lows = pivot_points(
        recent,
        left=3,
        right=3,
    )

    if len(highs) < 2 or len(lows) < 2:
        return result

    previous_high = highs[-2][1]
    latest_high = highs[-1][1]

    previous_low = lows[-2][1]
    latest_low = lows[-1][1]

    last_candle = recent[-1]

    last_high = last_candle["high"]
    last_low = last_candle["low"]
    last_close = last_candle["close"]

    # ========================================================
    # LIQUIDITY SWEEP
    # ========================================================

    # Bullish liquidity sweep:
    # Price trades below a meaningful swing low,
    # then closes back above that low.
    if (
        last_low < latest_low
        and last_close > latest_low
    ):
        result["liquidity_sweep"] = "Bullish"
        result["sweep_level"] = latest_low
        result["bias"] = "Bullish"
        result["evidence"].append(
            "bullish_liquidity_sweep"
        )

    # Bearish liquidity sweep:
    # Price trades above a meaningful swing high,
    # then closes back below that high.
    elif (
        last_high > latest_high
        and last_close < latest_high
    ):
        result["liquidity_sweep"] = "Bearish"
        result["sweep_level"] = latest_high
        result["bias"] = "Bearish"
        result["evidence"].append(
            "bearish_liquidity_sweep"
        )

    # ========================================================
    # BREAK OF STRUCTURE
    # ========================================================

    # Bullish BOS:
    # Price closes above the latest confirmed swing high.
    if last_close > latest_high:
        result["bos"] = "Bullish"
        result["break_level"] = latest_high
        result["bias"] = "Bullish"
        result["evidence"].append(
            "bullish_bos"
        )

    # Bearish BOS:
    # Price closes below the latest confirmed swing low.
    elif last_close < latest_low:
        result["bos"] = "Bearish"
        result["break_level"] = latest_low
        result["bias"] = "Bearish"
        result["evidence"].append(
            "bearish_bos"
        )

    # ========================================================
    # CHANGE OF CHARACTER
    # ========================================================

    # Bullish CHoCH:
    # Existing structure has been making lower highs/lows,
    # then price breaks the latest swing high.
    if (
        latest_high < previous_high
        and latest_low < previous_low
        and last_close > latest_high
    ):
        result["choch"] = "Bullish"
        result["break_level"] = latest_high
        result["bias"] = "Bullish"
        result["evidence"].append(
            "bullish_choch"
        )

    # Bearish CHoCH:
    # Existing structure has been making higher highs/lows,
    # then price breaks the latest swing low.
    elif (
        latest_high > previous_high
        and latest_low > previous_low
        and last_close < latest_low
    ):
        result["choch"] = "Bearish"
        result["break_level"] = latest_low
        result["bias"] = "Bearish"
        result["evidence"].append(
            "bearish_choch"
        )

    return result


def evaluate_strategy_combinations(candles, technical):
    """
    Analysis-only strategy evaluator.

    Evaluates multiple price-action combinations per coin.
    Does not authorize or change live trading signals.
    """

    result = {
        "enabled": True,
        "mode": "analysis_only",
        "candidates": [],
        "best_candidate": None,
        "candidate_count": 0,
        "note": "Candidates require historical outcome validation.",
    }

    if len(candles) < 40 or not technical.get("valid"):
        return result

    try:
        completed = candles[:-1]
        current_price = float(candles[-1]["close"])
        atr = float(technical.get("atr") or 0)

        if current_price <= 0 or atr <= 0:
            return result

        smc = detect_smc_structure(candles)
        fvg = detect_fair_value_gaps(candles)
        fib = detect_fibonacci_levels(candles)

        highs, lows = pivot_points(
            completed[-100:],
            left=3,
            right=3,
        )

        recent_high = highs[-1][1] if highs else None
        recent_low = lows[-1][1] if lows else None

        # Find a recent opposing candle as a possible
        # order-block zone. This is a candidate, not proof
        # that the zone is institutionally significant.
        recent = completed[-20:]
        order_block = None

        for candle in reversed(recent[:-1]):
            candle_open = float(candle["open"])
            candle_close = float(candle["close"])
            candle_high = float(candle["high"])
            candle_low = float(candle["low"])

            if candle_close < candle_open:
                order_block = {
                    "type": "Bullish",
                    "low": candle_low,
                    "high": candle_high,
                }
                break

            if candle_close > candle_open:
                order_block = {
                    "type": "Bearish",
                    "low": candle_low,
                    "high": candle_high,
                }
                break

        candidates = []

        def add_candidate(name, direction, evidence, score):
            if direction not in ("Bullish", "Bearish"):
                return

            is_long = direction == "Bullish"

            # Use a conservative ATR-based invalidation
            # until a tested structure-based stop is available.
            if is_long:
                stop = current_price - 1.5 * atr
                if recent_low is not None and recent_low < current_price:
                    stop = min(stop, recent_low - 0.15 * atr)
                risk = current_price - stop
                targets = [
                    current_price + risk,
                    current_price + 2 * risk,
                    current_price + 3 * risk,
                ]
                liquidity_target = (
                    recent_high
                    if recent_high is not None
                    and recent_high > current_price
                    else None
                )
            else:
                stop = current_price + 1.5 * atr
                if recent_high is not None and recent_high > current_price:
                    stop = max(stop, recent_high + 0.15 * atr)
                risk = stop - current_price
                targets = [
                    current_price - risk,
                    current_price - 2 * risk,
                    current_price - 3 * risk,
                ]
                liquidity_target = (
                    recent_low
                    if recent_low is not None
                    and recent_low < current_price
                    else None
                )

            if risk <= 0:
                return

            candidates.append({
                "name": name,
                "direction": direction,
                "score": min(score, 100),
                "evidence": list(dict.fromkeys(evidence)),
                "entry_reference": current_price,
                "stop_reference": stop,
                "target_1": targets[0],
                "target_2": targets[1],
                "target_3": targets[2],
                "nearby_liquidity_target": liquidity_target,
                "risk_distance": risk,
                "reward_risk": {
                    "target_1": 1.0,
                    "target_2": 2.0,
                    "target_3": 3.0,
                },
                "status": "UNVALIDATED_CANDIDATE",
            })

        sweep = smc.get("liquidity_sweep")
        choch = smc.get("choch")
        bos = smc.get("bos")

        # Select recent, unfilled FVG zones.
        bullish_fvgs = [
            z for z in fvg["bullish"]
            if not z["fully_filled"] and z["age"] <= 30
        ]
        bearish_fvgs = [
            z for z in fvg["bearish"]
            if not z["fully_filled"] and z["age"] <= 30
        ]

        bullish_fvg_near = any(
            z["low"] <= current_price + atr
            and z["high"] >= current_price - atr
            for z in bullish_fvgs
        )
        bearish_fvg_near = any(
            z["low"] <= current_price + atr
            and z["high"] >= current_price - atr
            for z in bearish_fvgs
        )

        fib_bullish_near = (
            fib.get("valid")
            and fib.get("direction") == "Bullish"
            and fib.get("nearest_level")
            and fib["nearest_level"].get("distance_pct") is not None
            and fib["nearest_level"]["distance_pct"] <= 0.75
        )

        fib_bearish_near = (
            fib.get("valid")
            and fib.get("direction") == "Bearish"
            and fib.get("nearest_level")
            and fib["nearest_level"].get("distance_pct") is not None
            and fib["nearest_level"]["distance_pct"] <= 0.75
        )

        bullish_block_near = (
            order_block is not None
            and order_block["type"] == "Bullish"
            and order_block["low"] <= current_price + atr
            and order_block["high"] >= current_price - atr
        )

        bearish_block_near = (
            order_block is not None
            and order_block["type"] == "Bearish"
            and order_block["low"] <= current_price + atr
            and order_block["high"] >= current_price - atr
        )

        # Combination A: sweep + CHoCH + price-zone confluence.
        if sweep == "Bullish" and choch == "Bullish":
            evidence = ["bullish_sweep", "bullish_choch"]
            score = 55

            if bullish_fvg_near:
                evidence.append("near_bullish_fvg")
                score += 15
            if bullish_block_near:
                evidence.append("near_bullish_order_block")
                score += 15
            if fib_bullish_near:
                evidence.append("near_bullish_fibonacci_level")
                score += 15

            add_candidate(
                "Sweep + CHoCH reversal",
                "Bullish",
                evidence,
                score,
            )

        if sweep == "Bearish" and choch == "Bearish":
            evidence = ["bearish_sweep", "bearish_choch"]
            score = 55

            if bearish_fvg_near:
                evidence.append("near_bearish_fvg")
                score += 15
            if bearish_block_near:
                evidence.append("near_bearish_order_block")
                score += 15
            if fib_bearish_near:
                evidence.append("near_bearish_fibonacci_level")
                score += 15

            add_candidate(
                "Sweep + CHoCH reversal",
                "Bearish",
                evidence,
                score,
            )

        # Combination B: BOS continuation + nearby imbalance.
        if bos == "Bullish" and bullish_fvg_near:
            add_candidate(
                "Bullish BOS + FVG",
                "Bullish",
                ["bullish_bos", "near_bullish_fvg"],
                60 + (15 if bullish_block_near else 0)
                + (10 if fib_bullish_near else 0),
            )

        if bos == "Bearish" and bearish_fvg_near:
            add_candidate(
                "Bearish BOS + FVG",
                "Bearish",
                ["bearish_bos", "near_bearish_fvg"],
                60 + (15 if bearish_block_near else 0)
                + (10 if fib_bearish_near else 0),
            )

        # Combination C: zone confluence, even without a
        # detected sweep. This remains a lower-confidence
        # candidate and is not a live trade instruction.
        if bullish_fvg_near and bullish_block_near:
            add_candidate(
                "Bullish FVG + order-block confluence",
                "Bullish",
                ["near_bullish_fvg", "near_bullish_order_block"],
                45 + (10 if fib_bullish_near else 0),
            )

        if bearish_fvg_near and bearish_block_near:
            add_candidate(
                "Bearish FVG + order-block confluence",
                "Bearish",
                ["near_bearish_fvg", "near_bearish_order_block"],
                45 + (10 if fib_bearish_near else 0),
            )

        # A score ranks rule-based evidence only. It is not
        # a probability of winning and must not be described
        # as one until calibrated against historical results.
        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        result["candidates"] = candidates
        result["candidate_count"] = len(candidates)
        result["best_candidate"] = (
            candidates[0] if candidates else None
        )
        result["fibonacci"] = fib
        result["structure"] = smc
        result["order_block_candidate"] = order_block

        return result

    except (KeyError, TypeError, ValueError, IndexError) as exc:
        result["error"] = str(exc)
        return result

def detect_entry_setup(candles, technical):
    """
    Converts raw price action into an observable entry state.

    LONG:
        trend → pullback/dip → reclaim/sweep/BOS

    SHORT:
        trend → rally → rejection/sweep/BOS

    This does NOT claim to identify "market manipulation".
    It only records observable price/structure behavior.
    """

    result = {
        "setup": "WAIT",
        "trigger": False,
        "direction": None,
        "pullback": False,
        "liquidity_sweep": None,
        "bos": None,
        "choch": None,
        "entry_reason": None,
    }

    if (
        len(candles) < 30
        or not technical.get("valid")
    ):
        return result

    direction = technical.get(
        "direction",
        "",
    )

    if "Bullish" in direction:
        bias = "Bullish"

    elif "Bearish" in direction:
        bias = "Bearish"

    else:
        return result

    atr = technical.get("atr")
    price = technical.get("price")
    ema20 = technical.get("ema20")

    if not atr or not price:
        return result

    smc = detect_smc_structure(candles)

    fvg_data = detect_fair_value_gaps(candles)

    current_price = float(candles[-1]["close"])

    def nearest_active_fvg(zones, direction):
        active = [
            zone for zone in zones
            if not zone["fully_filled"]
            and zone["age"] <= 50
        ]

        if not active:
            return None

        # Prefer zones closest to the current market price.
        active.sort(
            key=lambda zone: abs(
                current_price - zone["midpoint"]
            )
        )

        zone = active[0]
        return {
            **zone,
            "direction": direction,
            "price_inside_zone": (
                zone["low"] <= current_price <= zone["high"]
            ),
            "distance_pct": (
                abs(current_price - zone["midpoint"])
                / current_price * 100
                if current_price > 0 else None
            ),
        }

    bullish_fvg = nearest_active_fvg(
        fvg_data["bullish"], "Bullish"
    )
    bearish_fvg = nearest_active_fvg(
        fvg_data["bearish"], "Bearish"
    )

    result["fvg"] = {
        "bullish": bullish_fvg,
        "bearish": bearish_fvg,
    }

    recent = candles[-25:-1]

    if len(recent) < 10:
        return result

    recent_high = max(
        c["high"]
        for c in recent
    )

    recent_low = min(
        c["low"]
        for c in recent
    )

    last = candles[-1]
    previous = candles[-2]

    last_close = last["close"]
    
    # Detect a confirmed reversal against the current technical bias.
    # Require a directional CHoCH and a candle closing in that direction.
    reversal_direction = None

    if (
        bias == "Bearish"
        and smc.get("choch") == "Bullish"
        and last["close"] > last["open"]
    ):
        reversal_direction = "Bullish"

    elif (
        bias == "Bullish"
        and smc.get("choch") == "Bearish"
        and last["close"] < last["open"]
    ):
        reversal_direction = "Bearish"

    if reversal_direction:
        result.update({
            "setup": f"{reversal_direction.upper()} REVERSAL TRIGGER",
            "trigger": True,
            "direction": reversal_direction,
            "pullback": False,
            "entry_reason": (
                "Confirmed opposing CHoCH with directional candle close"
            ),
            "choch": reversal_direction,
            "liquidity_sweep": smc.get("liquidity_sweep"),
            "bos": smc.get("bos"),
        })

        print(
            "REVERSAL TRIGGER:",
            reversal_direction,
            "technical_bias=", bias,
            "choch=", smc.get("choch"),
        )

        return result
        
    min_pullback = max(
        atr * 0.25,
        price * 0.002,
    )

    # ========================================================
    # BULLISH
    # ========================================================

    if bias == "Bullish":

        pullback = (
            recent_high - last_close
            >= min_pullback
            and last_close > recent_low
        )

        reclaim = (
            last_close > previous["high"]
            and (
                ema20 is None
                or last_close >= ema20
            )
        )

        sweep = (
            smc.get("liquidity_sweep")
            == "Bullish"
        )

        bos = (
            smc.get("bos")
            == "Bullish"
        )

        bullish_zone = bullish_fvg

        fvg_retest = bool(
            bullish_zone
            and not bullish_zone["fully_filled"]
            and (
                bullish_zone["price_inside_zone"]
                or (
                    last["low"] <= bullish_zone["high"]
                    and last["high"] >= bullish_zone["low"]
                )
            )
        )

        result["fvg_retest"] = fvg_retest

        bullish_choch = (
            smc.get("choch") == "Bullish"
        )

        
        # Confirm a bullish reaction inside the FVG.
        bullish_fvg_confirmation = (
            fvg_retest
            and last_close > last["open"]
            and last_close >= bullish_zone["midpoint"]
        )

        trigger = (
            reclaim
            or sweep
            or bos
            or bullish_choch
            or bullish_fvg_confirmation
        )

        result["direction"] = "Bullish"
        result["pullback"] = pullback
        result["liquidity_sweep"] = (
            smc.get("liquidity_sweep")
        )
        result["bos"] = smc.get("bos")
        result["choch"] = smc.get("choch")
        result["trigger"] = trigger
        
        print(
            "ENTRY TRIGGER CHECK:",
            "direction=Bullish",
            "pullback=", pullback,
            "reclaim=", reclaim,
            "sweep=", sweep,
            "bos=", bos,
            "choch=", bullish_choch,
            "fvg_confirmation=", bullish_fvg_confirmation,
            "trigger=", trigger,
        )
        if pullback and trigger:

            result["setup"] = (
                "BUY THE DIP"
            )

            result["entry_reason"] = (
                "Bullish trend pullback with "
                "reclaim/structure confirmation"
            )

        elif trigger:

            result["setup"] = (
                "BULLISH TRIGGER"
            )

            result["entry_reason"] = (
                "Bullish structure/momentum "
                "confirmation"
            )

    # ========================================================
    # BEARISH
    # ========================================================

    else:

        pullback = (
            last_close - recent_low
            >= min_pullback
            and last_close < recent_high
        )

        rejection = (
            last_close < previous["low"]
            and (
                ema20 is None
                or last_close <= ema20
            )
        )

        sweep = (
            smc.get("liquidity_sweep")
            == "Bearish"
        )

        bos = (
            smc.get("bos")
            == "Bearish"
        )

        bearish_zone = bearish_fvg

        fvg_retest = bool(
            bearish_zone
            and not bearish_zone["fully_filled"]
            and (
                bearish_zone["price_inside_zone"]
                or (
                    last["low"] <= bearish_zone["high"]
                    and last["high"] >= bearish_zone["low"]
                )
            )
        )

        result["fvg_retest"] = fvg_retest

        bearish_fvg_confirmation = (
                fvg_retest
                and last_close < last["open"]
                and last_close <= bearish_zone["midpoint"]
            )

        bearish_choch = (
            smc.get("choch") == "Bearish"
        )

        trigger = (
            rejection
            or sweep
            or bos
            or bearish_choch
            or bearish_fvg_confirmation
        )

        result["direction"] = "Bearish"
        result["pullback"] = pullback
        result["liquidity_sweep"] = (
            smc.get("liquidity_sweep")
        )
        result["bos"] = smc.get("bos")
        result["choch"] = smc.get("choch")
        result["trigger"] = trigger
        
        print(
            "ENTRY TRIGGER CHECK:",
            "direction=Bearish",
            "pullback=", pullback,
            "rejection=", rejection,
            "sweep=", sweep,
            "bos=", bos,
            "choch=", bearish_choch,
            "fvg_confirmation=", bearish_fvg_confirmation,
            "trigger=", trigger,
        )
        if pullback and trigger:

            result["setup"] = (
                "SELL THE RALLY"
            )

            result["entry_reason"] = (
                "Bearish trend rally with "
                "rejection/structure confirmation"
            )

        elif trigger:

            result["setup"] = (
                "BEARISH TRIGGER"
            )

            result["entry_reason"] = (
                "Bearish structure/momentum "
                "confirmation"
            )

    return result
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

    long_ema = ema200

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
    # WEIGHTED MARKET STRUCTURE
    # --------------------------------------------------------

    bullish_structure_weight = 0.0
    bearish_structure_weight = 0.0

    for timeframe, result in timeframe_results.items():
        if not result.get("valid"):
            continue

        weight = TIMEFRAMES[timeframe]["weight"]
        structure_label = str(result.get("structure", ""))

        if "Bullish" in structure_label:
            bullish_structure_weight += weight

        elif "Bearish" in structure_label:
            bearish_structure_weight += weight

    if bullish_structure_weight > bearish_structure_weight:
        structure = "Bullish"

    elif bearish_structure_weight > bullish_structure_weight:
        structure = "Bearish"

    else:
        structure = "Mixed / Sideways"


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
    ) and liquidation_data:

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

    category_status = {
        "open_interest": (
            isinstance(result["open_interest"], dict)
            and bool(result["open_interest"])
        ),
        "funding": (
            isinstance(result["funding"], dict)
            and result["funding"].get("average") is not None
        ),
        "liquidations": (
            isinstance(result["liquidations"], dict)
            and result["liquidations"].get("total") is not None
        ),
        "long_short": (
            isinstance(result["long_short"], dict)
            and any(
                result["long_short"].get(key) is not None
                for key in ("long", "short", "ratio")
            )
        ),
    }

    result["available"] = any(category_status.values())
    result["category_status"] = category_status

    if (
        coin.upper() == "BTC"
        and coin.upper() not in COINGLASS_DIAGNOSTIC_LOGGED
    ):
        print(
            "COINGLASS DIAGNOSTICS BTC:",
            "open_interest=" + (
                "OK" if category_status["open_interest"] else "MISSING"
            ),
            "funding=" + (
                "OK" if category_status["funding"] else "MISSING"
            ),
            "liquidations=" + (
                "OK" if category_status["liquidations"] else "MISSING"
            ),
            "long_short=" + (
                "OK" if category_status["long_short"] else "MISSING"
            ),
            "available=" + str(result["available"]),
        )
        COINGLASS_DIAGNOSTIC_LOGGED.add(coin.upper())

    COINGLASS_CACHE[
        coin
    ] = {
        "time": time.time(),
        "data": result,
    }

    return result


# ============================================================
# GATE.IO PUBLIC PERPETUAL DERIVATIVES FALLBACK
# ============================================================

GATEIO_DERIVATIVES_CACHE = {}
GATEIO_DERIVATIVES_CACHE_SECONDS = 60
GATEIO_TICKERS_CACHE = {"time": 0, "data": {}}


def get_gateio_derivatives(coin):
    """Fetch public Gate.io USDT perpetual derivatives data."""
    coin = str(coin).upper()
    contract = f"{coin}_USDT"
    now = time.time()

    cached = GATEIO_DERIVATIVES_CACHE.get(coin)
    if cached and now - cached["time"] < GATEIO_DERIVATIVES_CACHE_SECONDS:
        return cached["data"]

    result = {
        "available": False,
        "source": "Gate.io public USDT perpetual futures",
        "open_interest": None,
        "funding": None,
        "liquidations": None,
        "long_short": None,
        "category_status": {},
    }

    # Fetch and cache current funding rates for all contracts.
    try:
        if now - GATEIO_TICKERS_CACHE["time"] >= GATEIO_DERIVATIVES_CACHE_SECONDS:
            response = requests.get(
                "https://api.gateio.ws/api/v4/futures/usdt/tickers",
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json", "User-Agent": "SideShiftAI/4.0"},
            )
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, list):
                GATEIO_TICKERS_CACHE["data"] = {
                    str(item.get("contract", "")).upper(): item
                    for item in payload
                    if isinstance(item, dict) and item.get("contract")
                }
                GATEIO_TICKERS_CACHE["time"] = now

        ticker = GATEIO_TICKERS_CACHE["data"].get(contract)
        if ticker:
            rate = safe_float(ticker.get("funding_rate"))
            if rate is not None:
                result["funding"] = {"average": rate, "count": 1}
    except Exception as exc:
        print("GATE.IO DERIVATIVES TICKER ERROR:", coin, repr(exc))

    # Fetch recent contract statistics.
    try:
        response = requests.get(
            "https://api.gateio.ws/api/v4/futures/usdt/contract_stats",
            params={"contract": contract, "interval": "5m", "limit": 13},
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": "SideShiftAI/4.0"},
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list) and payload:
            rows = sorted(
                [
                    row for row in payload
                    if isinstance(row, dict) and row.get("time") is not None
                ],
                key=lambda row: int(row.get("time", 0)),
            )

            if rows:
                latest = rows[-1]
                latest_time = safe_float(latest.get("time"))

                # Reject stale statistics older than 20 minutes.
                if latest_time is not None and now - latest_time <= 1200:
                    oi_latest = safe_float(latest.get("open_interest_usd"))
                    oi_first = safe_float(rows[0].get("open_interest_usd"))
                    oi_change = None

                    if oi_latest is not None and oi_first is not None and oi_first > 0:
                        oi_change = ((oi_latest - oi_first) / oi_first) * 100.0

                    if oi_latest is not None:
                        result["open_interest"] = {
                            "open_interest_usd": oi_latest,
                            "open_interest_change_percent_1h": oi_change,
                            "observations": len(rows),
                            "timestamp": int(latest_time),
                        }

                    long_liq = sum(
                        max(0.0, safe_float(row.get("long_liq_usd"), 0.0) or 0.0)
                        for row in rows
                    )
                    short_liq = sum(
                        max(0.0, safe_float(row.get("short_liq_usd"), 0.0) or 0.0)
                        for row in rows
                    )

                    if any(
                        row.get("long_liq_usd") is not None
                        or row.get("short_liq_usd") is not None
                        for row in rows
                    ):
                        result["liquidations"] = {
                            "long": long_liq,
                            "short": short_liq,
                            "total": long_liq + short_liq,
                            "timestamp": int(latest_time),
                        }

                    ratio = safe_float(latest.get("lsr_account"))
                    if ratio is None:
                        ratio = safe_float(latest.get("top_lsr_account"))

                    if ratio is not None:
                        result["long_short"] = {
                            "ratio": ratio,
                            "timestamp": int(latest_time),
                        }
                else:
                    print("GATE.IO DERIVATIVES STALE STATS:", coin, latest_time)
    except Exception as exc:
        print("GATE.IO DERIVATIVES STATS ERROR:", coin, repr(exc))

    result["category_status"] = {
        "open_interest": (
            isinstance(result["open_interest"], dict)
            and result["open_interest"].get("open_interest_usd") is not None
        ),
        "funding": (
            isinstance(result["funding"], dict)
            and result["funding"].get("average") is not None
        ),
        "liquidations": (
            isinstance(result["liquidations"], dict)
            and result["liquidations"].get("total") is not None
        ),
        "long_short": (
            isinstance(result["long_short"], dict)
            and result["long_short"].get("ratio") is not None
        ),
    }

    result["available"] = any(result["category_status"].values())
    GATEIO_DERIVATIVES_CACHE[coin] = {"time": now, "data": result}

    if coin == "BTC":
        print(
            "GATE.IO DERIVATIVES BTC:",
            result["category_status"],
            "available=" + str(result["available"]),
        )

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
    # Only score liquidations when meaningful relative to open interest.
    liquidations = derivatives.get("liquidations")

    if isinstance(liquidations, dict):
        long_liq = max(
            0.0,
            safe_float(liquidations.get("long"), 0.0) or 0.0,
        )
        short_liq = max(
            0.0,
            safe_float(liquidations.get("short"), 0.0) or 0.0,
        )
        total = long_liq + short_liq

        oi = derivatives.get("open_interest")
        oi_usd = (
            safe_float(oi.get("open_interest_usd"))
            if isinstance(oi, dict)
            else None
        )

        # Require liquidations to equal at least 0.01% of open interest.
        meaningful_liquidations = (
            oi_usd is not None
            and oi_usd > 0
            and total / oi_usd >= 0.0001
        )

        if total > 0 and meaningful_liquidations:
            long_ratio = long_liq / total

            if long_ratio >= 0.70:
                result["evidence"].append("Heavy long liquidations")
                result["score"] -= 1

            elif long_ratio <= 0.30:
                result["evidence"].append("Heavy short liquidations")
                result["score"] += 1

            else:
                result["evidence"].append("Mixed liquidations")

        elif total > 0:
            result["warnings"].append(
                "Liquidations too small relative to open interest to score"
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

def get_tv_signal(symbol, timeframe):
    item = TRADINGVIEW_CACHE.get(
        tv_key(symbol, timeframe)
    )

    if not item:
        return None

    # Maximum age depends on the alert's timeframe.
    max_age_seconds = {
        "5m": 15 * 60,
        "15m": 45 * 60,
        "30m": 90 * 60,
        "1h": 3 * 60 * 60,
        "4h": 12 * 60 * 60,
        "1D": 48 * 60 * 60,
    }

    max_age = max_age_seconds.get(timeframe)

    if max_age is None:
        return None

    received_at = item.get("received_at")

    if not isinstance(received_at, (int, float)):
        return None

    age_seconds = time.time() - received_at

    # Reject future-dated or expired alerts.
    if age_seconds < 0 or age_seconds > max_age:
        return None

    return item.get("data")


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

            # ------------------------------------------------
            # NEW: PRICE-ACTION / ENTRY ANALYSIS
            # ------------------------------------------------

            result[
                "smc"
            ] = detect_smc_structure(
                candles
            )

            result[
                "entry_setup"
            ] = detect_entry_setup(
                candles,
                result,
            )
            result["strategy_analysis"] = (
                evaluate_strategy_combinations(
                    candles,
                    result,
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
    # WEIGHTED TIMEFRAME AGREEMENT
    # --------------------------------------------------------

    bullish_weight = 0.0
    bearish_weight = 0.0
    total_valid_weight = 0.0

    for timeframe, result in timeframe_results.items():
        if not result.get("valid"):
            continue

        weight = TIMEFRAMES[timeframe]["weight"]
        total_valid_weight += weight

        direction = str(result.get("direction", ""))

        if "Bullish" in direction:
            bullish_weight += weight

        elif "Bearish" in direction:
            bearish_weight += weight

    # Measure directional support against ALL valid
    # timeframes, including neutral/consolidating ones.
    bullish_ratio = (
        bullish_weight / total_valid_weight
        if total_valid_weight > 0
        else 0.0
    )

    bearish_ratio = (
        bearish_weight / total_valid_weight
        if total_valid_weight > 0
        else 0.0
    )

    agreement = max(bullish_ratio, bearish_ratio)

    print(
        "WEIGHTED TIMEFRAME AGREEMENT:",
        coin,
        "bullish=", round(bullish_ratio, 3),
        "bearish=", round(bearish_ratio, 3),
        "agreement=", round(agreement, 3),
        "valid_weight=", round(total_valid_weight, 3),
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

        derivatives = get_coinglass_derivatives(coin)

        if not derivatives.get("available"):
            derivatives = get_gateio_derivatives(coin)

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
    # WEIGHTED MARKET STRUCTURE
    # --------------------------------------------------------

    bullish_structure_weight = 0.0
    bearish_structure_weight = 0.0

    for timeframe, result in timeframe_results.items():
        if not result.get("valid"):
            continue

        weight = TIMEFRAMES[timeframe]["weight"]
        structure_label = str(result.get("structure", ""))

        if "Bullish" in structure_label:
            bullish_structure_weight += weight

        elif "Bearish" in structure_label:
            bearish_structure_weight += weight

    if bullish_structure_weight > bearish_structure_weight:
        structure = "Bullish"

    elif bearish_structure_weight > bullish_structure_weight:
        structure = "Bearish"

    else:
        structure = "Mixed / Sideways"

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
        bullish_ratio >= 0.80
        and average_score >= 5
    ):

        overall_label = (
            "Bullish"
        )

    elif (
        bearish_ratio >= 0.80
        and average_score <= -5
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

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    # --------------------------------------------------------
    # ANALYSIS STRENGTH
    # --------------------------------------------------------

    score_strength = clamp(
        (
            abs(average_score)
            / 14
        )
        * 100,
        0,
        100,
    )

    agreement_strength = (
        agreement * 100
    )

    timeframe_strength = (
        (
            len(valid_results)
            / len(TIMEFRAMES)
        )
        * 100
    )

    analysis_strength = (
        (score_strength * 0.45)
        + (agreement_strength * 0.30)
        + (timeframe_strength * 0.15)
        + 10
    )

    if structure in (
        "Bullish",
        "Bearish",
    ):
        analysis_strength += 5

    if volatility == "Very High":
        analysis_strength -= 10

    if conflicts:
        analysis_strength -= (
            len(conflicts) * 10
        )

    analysis_strength = clamp(
        analysis_strength,
        0,
        100,
    )

    # Keep the existing signal engine compatible.
    confidence = analysis_strength

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------
    entry_segments = (
        build_entry_segments(
            timeframe_results
        )
    )
    

    # The selected entry determines the proposed trade direction.
    # The overall market label remains contextual information.
    signal_label = overall_label

    if overall_label == "Bullish Lean":
        signal_label = "Bullish"
    elif overall_label == "Bearish Lean":
        signal_label = "Bearish"

    if entry_segments.get("valid") is True:
        entry_direction = entry_segments.get("direction")

        if entry_direction in ("Bullish", "Bearish"):
            signal_label = entry_direction

    print(
        "SIGNAL QUALIFICATION CHECK:",
        coin,
        "overall=", overall_label,
        "signal_label=", signal_label,
        "score=", round(average_score, 2),
        "strength=", round(confidence, 1),
        "valid_timeframes=", len(valid_results),
        "structure=", structure,
        "entry_valid=", entry_segments.get("valid"),
        "entry_direction=", entry_segments.get("direction"),
        "entry_tf=", entry_segments.get("entry_timeframe"),
    )

    signal = build_signal(
        coin=coin,
        label=signal_label,
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
                entry_segments=(
            entry_segments
        ),
    )

    return {         
        "entry_segments": entry_segments,
        "coin": coin,
        "price": price,
        "timeframes":
            timeframe_results,
                    "strategy_analysis": {
            "by_timeframe": {
                tf: item.get("strategy_analysis", {})
                for tf, item in timeframe_results.items()
            },
            "candidate_count": sum(
                item.get("strategy_analysis", {}).get(
                    "candidate_count", 0
                )
                for item in timeframe_results.values()
            ),
        },
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
    if (
        len(valid_results) == 5
        and derivatives.get("available")
    )
    else "Good"
    if (
        len(valid_results) >= 4
        and derivatives.get("available")
    )
    else "Good"
    if (
        len(valid_results) == 5
        and not derivatives.get("available")
    )
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

def build_entry_segments(timeframe_results):
    """
    1D / 4H: market context, not entry vetoes.
    1H: setup context, not an absolute requirement.
    15M / 5M: evaluate actual entry opportunities.
    """

    result = {
        "valid": False,
        "direction": None,
        "context": "WAIT",
        "setup": "WAIT",
        "entry": "WAIT",
        "entry_timeframe": None,
        "entry_price": None,
        "entry_reason": None,
        "strategy_direction": None,
        "strategy_score": 0,
        "qualified_reversal": False,
    }

    def bias(timeframe):
        item = timeframe_results.get(timeframe, {})
        direction = item.get("direction", "")

        if "Bullish" in direction:
            return "Bullish"
        if "Bearish" in direction:
            return "Bearish"
        return "Neutral"

    daily = bias("1D")
    four_hour = bias("4h")
    one_hour = bias("1h")

    context = (
        f"1D={daily}, 4H={four_hour}, 1H={one_hour}"
    )

    candidates = []

    # Evaluate BOTH entry timeframes before choosing.
    for timeframe in ("5m", "15m"):
        item = timeframe_results.get(timeframe, {})
        if not item.get("valid"):
            continue

        entry_setup = item.get("entry_setup", {})
        analysis = item.get("strategy_analysis", {})
        strategy = analysis.get("best_candidate")

        trigger = entry_setup.get("trigger") is True
        trigger_direction = entry_setup.get("direction")

        strategy_direction = None
        strategy_score = 0
        evidence = []

        if isinstance(strategy, dict):
            strategy_direction = strategy.get("direction")
            strategy_score = strategy.get("score", 0)
            evidence = strategy.get("evidence", [])

        if not isinstance(evidence, list):
            evidence = []

        if not isinstance(strategy_score, (int, float)):
            strategy_score = 0

        # A trigger must have a usable direction.
        trigger_usable = (
            trigger
            and trigger_direction in ("Bullish", "Bearish")
        )

        # A strategy candidate must have sufficient evidence.
        strategy_usable = (
            strategy_direction in ("Bullish", "Bearish")
            and strategy_score >= 60
        )

        if not trigger_usable and not strategy_usable:
            print(
                "ENTRY TIMEFRAME REJECTED:",
                timeframe,
                "reason=no_usable_trigger_or_candidate",
                "trigger=", trigger,
                "trigger_direction=", trigger_direction,
                "strategy_direction=", strategy_direction,
                "strategy_score=", strategy_score,
            )
            continue

        # If both sources qualify but disagree, do not guess.
        if (
            trigger_usable
            and strategy_usable
            and trigger_direction != strategy_direction
        ):
            print(
                "ENTRY TIMEFRAME REJECTED:",
                timeframe,
                "reason=trigger_candidate_conflict",
                "trigger_direction=", trigger_direction,
                "strategy_direction=", strategy_direction,
            )
            continue

        direction = (
            trigger_direction
            if trigger_usable
            else strategy_direction
        )

        price = item.get("price")
        atr = item.get("atr")

        if (
            not isinstance(price, (int, float))
            or price <= 0
            or not isinstance(atr, (int, float))
            or atr <= 0
        ):
            print(
                "ENTRY TIMEFRAME REJECTED:",
                timeframe,
                "reason=invalid_price_or_atr",
                "price=", price,
                "atr=", atr,
            )
            continue

        reversal_evidence = (
            (
                direction == "Bullish"
                and "bullish_sweep" in evidence
                and "bullish_choch" in evidence
            )
            or (
                direction == "Bearish"
                and "bearish_sweep" in evidence
                and "bearish_choch" in evidence
            )
        )

        qualified_reversal = (
            strategy_usable
            and strategy_direction == direction
            and strategy_score >= 70
            and reversal_evidence
            and trigger_usable
        )

        # Rank candidates by evidence strength. A confirmed trigger
        # gets a modest preference, not an automatic victory.
        rank = strategy_score if strategy_usable else 0
        if trigger_usable:
            rank += 10

        # Prefer 5M only when candidates otherwise tie.
        timeframe_tiebreak = 1 if timeframe == "5m" else 0

        candidates.append({
            "rank": rank,
            "timeframe_tiebreak": timeframe_tiebreak,
            "timeframe": timeframe,
            "item": item,
            "entry_setup": entry_setup,
            "strategy": strategy,
            "direction": direction,
            "strategy_score": (
                strategy_score if strategy_usable else 0
            ),
            "qualified_reversal": qualified_reversal,
        })

    if not candidates:
        print(
            "ENTRY SEGMENTS REJECTED:",
            "reason=no_usable_5m_or_15m_setup",
            "context=", context,
        )
        return result

    candidates.sort(
        key=lambda candidate: (
            candidate["rank"],
            candidate["timeframe_tiebreak"],
        ),
        reverse=True,
    )

    selected = candidates[0]
    item = selected["item"]
    entry_setup = selected["entry_setup"]
    strategy = selected["strategy"]

    result.update({
        "valid": True,
        "direction": selected["direction"],
        "context": context,
        "setup": (
            entry_setup.get("setup", "WAIT")
            if entry_setup.get("trigger") is True
            else (
                strategy.get("strategy", "STRATEGY CANDIDATE")
                if isinstance(strategy, dict)
                else "STRATEGY CANDIDATE"
            )
        ),
        "entry": entry_setup.get("setup", "WAIT"),
        "entry_timeframe": selected["timeframe"],
        "entry_price": item.get("price"),
        "entry_reason": (
            entry_setup.get("entry_reason")
            or "Qualified strategy candidate"
        ),
        "strategy_direction": (
            strategy.get("direction")
            if isinstance(strategy, dict)
            else None
        ),
        "strategy_score": selected["strategy_score"],
        "qualified_reversal": selected["qualified_reversal"],
    })

    print(
        "ENTRY SELECTED:",
        "timeframe=", selected["timeframe"],
        "direction=", selected["direction"],
        "rank=", selected["rank"],
        "qualified_reversal=", selected["qualified_reversal"],
        "context=", context,
    )

    return result
    
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
    entry_segments=None,
):

        
    if valid_count < 2:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=insufficient_valid_timeframes",
            "valid_count=", valid_count,
        )
        return None

    if confidence < 45:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=low_confidence",
            "confidence=", round(confidence, 1),
        )
        return None

    if abs(score) < 2:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=low_score",
            "score=", round(score, 2),
        )
        return None

    if label not in ("Bullish", "Bearish"):
        print(
            "SIGNAL REJECTED:", coin,
            "reason=non_directional_label",
            "label=", label,
        )
        return None

    qualified_reversal = (
        isinstance(entry_segments, dict)
        and entry_segments.get("valid") is True
        and entry_segments.get("qualified_reversal") is True
        and entry_segments.get("strategy_direction") == label
    )

    # Overall structure is context, not an automatic veto.
    if (
        structure in ("Bullish", "Bearish")
        and structure != label
    ):
        print(
            "ENTRY CONTEXT CONFLICT:",
            coin,
            "structure=", structure,
            "entry_direction=", label,
            "qualified_reversal=", qualified_reversal,
        )
    # ========================================================
    # NEW: SEGMENTED ENTRY VALIDATION
    # ========================================================

    
    if not entry_segments:
        print("SIGNAL REJECTED:", coin, "reason=no_entry_segments")
        return None

    if not entry_segments.get("valid"):
        print(
            "SIGNAL REJECTED:", coin,
            "reason=entry_segments_invalid",
            "details=", entry_segments,
        )
        return None

    if entry_segments.get("direction") != label:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=entry_direction_mismatch",
            "entry_direction=", entry_segments.get("direction"),
            "signal_label=", label,
        )
        return None

    direction = (
        "CALL / LONG"
        if label == "Bullish"
        else "PUT / SHORT"
    )

    entry_price = entry_segments.get("entry_price")
    entry_timeframe = entry_segments.get("entry_timeframe")

    if entry_price is None or entry_timeframe is None:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=missing_entry_price_or_timeframe",
            "entry_price=", entry_price,
            "entry_timeframe=", entry_timeframe,
        )
        return None

    anchor = timeframe_results.get(entry_timeframe)

    if not anchor:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=missing_entry_timeframe_data",
            "entry_timeframe=", entry_timeframe,
        )
        return None

    atr = anchor.get("atr")

    if atr is None or atr <= 0:
        print(
            "SIGNAL REJECTED:", coin,
            "reason=invalid_atr",
            "entry_timeframe=", entry_timeframe,
            "atr=", atr,
        )
        return None


    # ========================================================
    # RISK LEVELS
    # ========================================================

    if direction == "CALL / LONG":

        invalidation = (
            entry_price
            - (
                atr
                * 1.5
            )
        )

        target_1 = (
            entry_price
            + (
                atr
                * 1.5
            )
        )

        target_2 = (
            entry_price
            + (
                atr
                * 3
            )
        )

        target_3 = (
            entry_price
            + (
                atr
                * 4.5
            )
        )

    else:

        invalidation = (
            entry_price
            + (
                atr
                * 1.5
            )
        )

        target_1 = (
            entry_price
            - (
                atr
                * 1.5
            )
        )

        target_2 = (
            entry_price
            - (
                atr
                * 3
            )
        )

        target_3 = (
            entry_price
            - (
                atr
                * 4.5
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


        "quality": (
            "HIGH-CONFLUENCE"
            if confidence >= 75 and agreement >= 0.80
            else "CONFLUENCE"
            if confidence >= 60 and agreement >= 0.65
            else "DEVELOPING"
        ),

        "entry":
            entry_price,

        "entry_timeframe":
            entry_timeframe,

        "entry_type":
            entry_segments.get(
                "setup",
                "ENTRY",
            ),

        "entry_trigger":
            entry_segments.get(
                "entry",
                "TRIGGER",
            ),

        "entry_reason":
            entry_segments.get(
                "entry_reason"
            ),

        "context":
            entry_segments.get(
                "context"
            ),

        "setup":
            entry_segments.get(
                "setup"
            ),

        "invalidation":
            invalidation,

        "target_1":
            target_1,

        "target_2":
            target_2,

        "target_3":
            target_3,

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

    
    btc_technical = scan_technical("BTC")

    if btc_technical:
        btc_regime = determine_btc_regime(
            btc_technical[0]
        )
    else:
        btc_regime = "UNKNOWN"
        print(
            "BTC DATA UNAVAILABLE — "
            "CONTINUING ASSET SCAN WITHOUT BTC CONFIRMATION"
        )


    print(
        "BTC REGIME:",
        btc_regime,
    )

    
    results = []

    
    scan_coins = sorted(
        set(APPROVED_ASSETS)
        & (set(OKX_PERPETUAL_MARKETS) | set(GATEIO_PERPETUAL_MARKETS))
    )

    original_symbols = {}
    added_coins = []

    for base in scan_coins:
        if base in COINS:
            original_symbols[base] = COINS[base].get("binance")
            COINS[base]["binance"] = base + "USDT"
        else:
            COINS[base] = {
                "coinbase": "",
                "kraken": "",
                "binance": base + "USDT",
                "cmc": base,
            }
            added_coins.append(base)

    print("MASTER ASSET SCAN COUNT:", len(scan_coins))

    for coin in scan_coins:
        try:
            analysis = scan_coin(
                coin,
                btc_regime=btc_regime,
            )
            if analysis:
                results.append(analysis)
        except Exception as exc:
            print("MARKET SCAN ERROR:", coin, repr(exc))

    for base in added_coins:
        COINS.pop(base, None)

    for base, symbol in original_symbols.items():
        COINS[base]["binance"] = symbol

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
            ZoneInfo("America/New_York")
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



def audience_can_send(audience):
    reset_signal_day()

    limit = (
        MAX_FREE_SIGNALS_PER_DAY
        if audience == "free"
        else MAX_VIP_SIGNALS_PER_DAY
    )

    if not DATABASE_URL:
        print(
            "SIGNAL CAP ERROR: DATABASE_URL missing; "
            "using in-memory counter."
        )
        with STATE_LOCK:
            count = (
                SIGNAL_STATE["free_sent_today"]
                if audience == "free"
                else SIGNAL_STATE["vip_sent_today"]
            )
        return count < limit

    today = datetime.now(
        ZoneInfo("America/New_York")
    ).date()

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM signal_records
                    WHERE audience = %s
                      AND report_date = %s
                    """,
                    (audience, today),
                )
                row = cur.fetchone()

        sent_today = int(row[0]) if row else 0

        print(
            "PERSISTENT SIGNAL CAP:",
            audience,
            sent_today,
            "/",
            limit,
        )

        return sent_today < limit

    except Exception as exc:
        print(
            "SIGNAL CAP DATABASE ERROR — "
            "BLOCKING SIGNAL TO PREVENT OVER-SENDING:",
            repr(exc),
        )
        return None

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


def register_active_trade(analysis, record_id, audience):
    if not record_id:
        print(
            "ACTIVE TRADE ERROR: missing database record ID",
            analysis.get("coin"),
            audience,
        )
        return

    signal = analysis.get("signal")
    if not signal:
        return

    coin = analysis.get("coin")
    if not coin:
        return

    published_direction = signal.get("direction", "")

    if published_direction in ("CALL / LONG", "LONG"):
        direction = "LONG"
    elif published_direction in ("PUT / SHORT", "SHORT"):
        direction = "SHORT"
    else:
        print(
            "ACTIVE TRADE SKIPPED: unsupported direction",
            coin,
            published_direction,
        )
        return

    entry = signal.get("entry")
    stop = signal.get("invalidation")
    tp1 = signal.get("target_1")
    tp2 = signal.get("target_2")
    tp3 = signal.get("target_3")

    if any(
        value is None
        for value in (entry, stop, tp1, tp2, tp3)
    ):
        print(
            "ACTIVE TRADE SKIPPED: missing entry/risk targets",
            coin,
        )
        return

    chat_id = (
        FREE_SIGNAL_CHAT_ID
        if audience == "free"
        else VIP_SIGNAL_CHAT_ID
    )

    trade = {
        "record_id": record_id,
        "audience": audience,
        "coin": coin,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "stop_hit": False,
        "free_chat_id": chat_id if audience == "free" else None,
        "vip_chat_id": chat_id if audience == "vip" else None,
        "created_at": time.time(),
    }

    with ACTIVE_TRADES_LOCK:
        ACTIVE_TRADES[str(record_id)] = trade

    print(
        "ACTIVE TRADE REGISTERED:",
        "record_id=", record_id,
        "audience=", audience,
        "coin=", coin,
        "direction=", direction,
    )


def get_monitor_price(coin):
    try:
        candles, provider = get_market_candles(coin, "5m")

        # The validator already removes unfinished candles.
        if candles:
            return candles[-1]

    except Exception as exc:
        print("MONITOR PRICE ERROR:", coin, repr(exc))

    return None

def validate_signal_entry_price(analysis, audience):
    """
    Check the current verified USDT perpetual price before publishing.
    Fail closed if the price cannot be verified or the setup has moved.
    """
    coin = analysis.get("coin")
    signal = analysis.get("signal") or {}

    try:
        entry = float(signal["entry"])
        stop = float(signal["invalidation"])
        tp1 = float(signal["target_1"])
    except (KeyError, TypeError, ValueError):
        print("SIGNAL PRICE CHECK REJECTED:", coin, "missing or invalid levels")
        return False

    if not coin or entry <= 0 or stop <= 0 or tp1 <= 0 or stop == entry:
        print("SIGNAL PRICE CHECK REJECTED:", coin, "invalid price levels")
        return False

    direction = str(signal.get("direction", "")).upper()
    if direction in ("CALL / LONG", "LONG"):
        is_long = True
    elif direction in ("PUT / SHORT", "SHORT"):
        is_long = False
    else:
        print("SIGNAL PRICE CHECK REJECTED:", coin, "unknown direction")
        return False

    live_price = None
    price_source = None

    # Source 1: OKX live ticker for the verified perpetual contract.
    if OKX_MARKET_DISCOVERY_OK and coin in OKX_PERPETUAL_MARKETS:
        try:
            response = requests.get(
                "https://www.okx.com/api/v5/market/ticker",
                params={"instId": OKX_PERPETUAL_MARKETS[coin]},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "SideShiftAI/4.0"},
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", [])

            if payload.get("code") == "0" and rows:
                candidate = float(rows[0].get("last", 0))
                if candidate > 0:
                    live_price = candidate
                    price_source = "OKX"

        except Exception as exc:
            print("OKX LIVE PRICE FALLBACK:", coin, repr(exc))

    # Source 2: Gate.io live ticker if OKX is unavailable.
    if (
        live_price is None
        and GATEIO_MARKET_DISCOVERY_OK
        and coin in GATEIO_PERPETUAL_MARKETS
    ):
        try:
            response = requests.get(
                "https://api.gateio.ws/api/v4/futures/usdt/tickers",
                params={"contract": GATEIO_PERPETUAL_MARKETS[coin]},
                timeout=REQUEST_TIMEOUT,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            rows = response.json()

            if isinstance(rows, list) and rows:
                candidate = float(rows[0].get("last", 0))
                if candidate > 0:
                    live_price = candidate
                    price_source = "Gate.io"

        except Exception as exc:
            print("GATE.IO LIVE PRICE ERROR:", coin, repr(exc))

    if live_price is None:
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "no verified live perpetual price",
        )
        return False

    # Allow at most 20% of the entry-to-stop distance from the planned entry.
    # This scales the tolerance to the risk of each setup.
    risk_distance = abs(entry - stop)
    max_deviation = risk_distance * 0.20
    deviation = abs(live_price - entry)

    if deviation > max_deviation:
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "entry moved too far",
            "entry=", entry,
            "live=", live_price,
            "allowed_deviation=", max_deviation,
            "source=", price_source,
        )
        return False

    # Do not publish a setup if its stop or first target has already been crossed.
    if is_long and (live_price <= stop or live_price >= tp1):
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "long stop/TP1 already crossed",
            "live=", live_price,
            "source=", price_source,
        )
        return False

    if not is_long and (live_price >= stop or live_price <= tp1):
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "short stop/TP1 already crossed",
            "live=", live_price,
            "source=", price_source,
        )
        return False

    # Rebase the complete trade plan to the verified live price.
    # Preserve the original stop distance and 1R / 2R / 3R targets.
    risk_distance = abs(entry - stop)

    if risk_distance <= 0 or live_price <= 0:
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "invalid live entry or risk distance",
        )
        return False

    if is_long:
        new_entry = live_price
        new_stop = new_entry - risk_distance
        new_tp1 = new_entry + risk_distance
        new_tp2 = new_entry + (risk_distance * 2)
        new_tp3 = new_entry + (risk_distance * 3)
    else:
        new_entry = live_price
        new_stop = new_entry + risk_distance
        new_tp1 = new_entry - risk_distance
        new_tp2 = new_entry - (risk_distance * 2)
        new_tp3 = new_entry - (risk_distance * 3)

    if min(new_entry, new_stop, new_tp1, new_tp2, new_tp3) <= 0:
        print(
            "SIGNAL PRICE CHECK REJECTED:",
            coin,
            "rebased levels are invalid",
        )
        return False

    signal["entry"] = new_entry
    signal["invalidation"] = new_stop
    signal["target_1"] = new_tp1
    signal["target_2"] = new_tp2
    signal["target_3"] = new_tp3

    print(
        "SIGNAL PRICE CHECK PASSED:",
        coin,
        audience,
        "entry=", entry,
        "live=", live_price,
        "source=", price_source,
    )
    return True

def send_trade_update(trade, message):
    sent = False

    chat_ids = {
        trade.get("free_chat_id"),
        trade.get("vip_chat_id"),
    }

    for chat_id in chat_ids:
        if chat_id:
            try:
                if send_telegram(message, chat_id):
                    sent = True
            except Exception as exc:
                print("TRADE UPDATE ERROR:", repr(exc))

    return sent


def restore_active_trades_from_db():
    if not DATABASE_URL:
        print("ACTIVE TRADE RESTORE: DATABASE_URL is missing.")
        return False

    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, audience, coin, direction,
                        entry_price, stop_price,
                        tp1_price, tp2_price, tp3_price,
                        highest_target_hit, sent_at
                    FROM signal_records
                    WHERE status = 'OPEN'
                    ORDER BY sent_at ASC
                """)
                rows = cur.fetchall()

        restored = 0

        for row in rows:
            (
                record_id, audience, coin, direction,
                entry, stop, tp1, tp2, tp3,
                highest_target, sent_at
            ) = row

            if audience not in ("free", "vip"):
                continue

            direction = str(direction).upper()
            if direction in ("CALL / LONG", "LONG"):
                direction = "LONG"
            elif direction in ("PUT / SHORT", "SHORT"):
                direction = "SHORT"
            else:
                continue

            chat_id = (
                FREE_SIGNAL_CHAT_ID
                if audience == "free"
                else VIP_SIGNAL_CHAT_ID
            )

            highest_target = int(highest_target or 0)

            trade = {
                "record_id": record_id,
                "audience": audience,
                "coin": coin,
                "direction": direction,
                "entry": entry,
                "stop": stop,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "highest_target_hit": highest_target,
                "tp1_hit": highest_target >= 1,
                "tp2_hit": highest_target >= 2,
                "tp3_hit": highest_target >= 3,
                "stop_hit": False,
                "free_chat_id": (
                    chat_id if audience == "free" else None
                ),
                "vip_chat_id": (
                    chat_id if audience == "vip" else None
                ),
                "created_at": time.time(),
            }

            with ACTIVE_TRADES_LOCK:
                ACTIVE_TRADES[str(record_id)] = trade

            restored += 1

        print("ACTIVE TRADE RESTORE: restored", restored, "open trades.")
        return True

    except Exception as exc:
        print("ACTIVE TRADE RESTORE ERROR:", repr(exc))
        return False


def monitor_active_trades():
    print("SideShift trade monitor started.")

    while True:
        try:
            with ACTIVE_TRADES_LOCK:
                trades = list(ACTIVE_TRADES.items())

            for trade_id, trade in trades:
                coin = trade.get("coin")
                record_id = trade.get("record_id")

                if not coin or not record_id:
                    print("MONITOR SKIPPED: missing coin or record ID")
                    continue
                
                
                
                candle = get_monitor_price(coin)
                if candle is None:
                    continue

                candle_timestamp = candle["timestamp"]

                if trade.get("last_processed_candle") == candle_timestamp:
                    continue

                price = float(candle["close"])

                candle_high = float(candle["high"])
                candle_low = float(candle["low"])

                direction = trade.get("direction")
                if direction not in ("LONG", "SHORT"):
                    continue

                audience = trade.get("audience", "unknown")
                previous_target = int(
                    trade.get("highest_target_hit", 0)
                )

                # Stop active before this candle began.
                if previous_target == 0:
                    effective_stop = trade["stop"]
                elif previous_target == 1:
                    effective_stop = trade["entry"]
                else:
                    effective_stop = trade["tp1"]

                
                if direction == "LONG":
                    stop_hit = candle_low <= effective_stop
                    tp1_hit = candle_high >= trade["tp1"]
                    tp2_hit = candle_high >= trade["tp2"]
                    tp3_hit = candle_high >= trade["tp3"]
                else:
                    stop_hit = candle_high >= effective_stop
                    tp1_hit = candle_low <= trade["tp1"]
                    tp2_hit = candle_low <= trade["tp2"]
                    tp3_hit = candle_low <= trade["tp3"]


                highest_target = previous_target

                # If the candle touched both the active stop
                # and a target, conservatively count the stop.
                if not stop_hit:
                    if tp3_hit:
                        highest_target = max(highest_target, 3)
                    elif tp2_hit:
                        highest_target = max(highest_target, 2)
                    elif tp1_hit:
                        highest_target = max(highest_target, 1)

                # Subscriber-facing text only; IDs and audience
                # remain internal to the bot.
                prefix = (
                    f"<b>🪙 {coin}</b>\n"
                    f"📍 <b>Direction:</b> {direction}\n"
                    f"💰 <b>Current Price:</b> "
                    f"{format_price(price)}\n\n"
                )

                
                # Persist target progress before notifying subscribers.
                if highest_target > previous_target:
                    try:
                        with psycopg.connect(DATABASE_URL) as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """
                                    UPDATE signal_records
                                    SET highest_target_hit =
                                        GREATEST(highest_target_hit, %s)
                                    WHERE id = %s AND status = 'OPEN'
                                    """,
                                    (highest_target, record_id),
                                )

                                if cur.rowcount != 1:
                                    print(
                                        "TARGET PROGRESS NOT SAVED:",
                                        record_id,
                                    )
                                    continue

                    except Exception as exc:
                        print(
                            "TARGET PROGRESS DB ERROR:",
                            record_id,
                            repr(exc),
                        )
                        continue

                    trade["highest_target_hit"] = highest_target

                    target_price = trade[f"tp{highest_target}"]
                    message = (
                        f"<b>🎯 TP{highest_target} HIT</b>\n\n"
                        + prefix
                        + f"🎯 <b>TP{highest_target}:</b> "
                        + format_price(target_price)
                    )

                    if highest_target == 3:
                        message += "\n\n<i>Trade monitoring closed.</i>"

                    send_trade_update(trade, message)

                    with ACTIVE_TRADES_LOCK:
                        if trade_id in ACTIVE_TRADES:
                            ACTIVE_TRADES[trade_id]["highest_target_hit"] = (
                                highest_target
                            )
                            for level in (1, 2, 3):
                                ACTIVE_TRADES[trade_id][f"tp{level}_hit"] = (
                                    level <= highest_target
                                )

                # TP3 is the final outcome.
                if highest_target == 3:
                    saved = update_signal_outcome(
                        record_id,
                        "TP3",
                        trade["tp3"],
                        highest_target_hit=3,
                    )
                    print(
                        "TP3 OUTCOME SAVED:",
                        record_id,
                        coin,
                        saved,
                    )
                    
                    if not saved:
                        print(
                            "TP3 CLOSE DEFERRED: database save failed",
                            record_id,
                        )
                        continue
                        
                    with ACTIVE_TRADES_LOCK:
                        ACTIVE_TRADES.pop(trade_id, None)
                    continue

                
                # Close at the active stop and report the
                # highest target reached as the outcome.
                if stop_hit:
                    if highest_target > 0:
                        final_status = f"TP{highest_target}"
                        final_exit = effective_stop
                        message = (
                            "<b>📌 TRADE CLOSED</b>\n\n"
                            + prefix
                            + f"<b>Final outcome:</b> {final_status}\n"
                            + f"<b>Modeled exit:</b> {format_price(final_exit)}\n"
                            + "<i>Outcome reflects the highest target reached; P/L uses the modeled exit.</i>"
                        )
                    else:
                        final_status = "SL"
                        final_exit = effective_stop
                        message = (
                            "<b>🛑 STOP LOSS HIT</b>\n\n"
                            + prefix
                            + f"<b>Modeled exit:</b> {format_price(final_exit)}\n"
                            + "<i>Trade monitoring closed.</i>"
                        )


                    saved = update_signal_outcome(
                        record_id,
                        final_status,
                        final_exit,
                        highest_target_hit=highest_target,
                    )
                    print(
                        "FINAL OUTCOME SAVED:",
                        record_id,
                        coin,
                        final_status,
                        saved,
                    )
                    
                    if not saved:
                        print(
                            "FINAL CLOSE DEFERRED: database save failed",
                            record_id,
                        )
                        continue
                        
                    send_trade_update(trade, message)

                    with ACTIVE_TRADES_LOCK:
                        ACTIVE_TRADES.pop(trade_id, None)

                trade["last_processed_candle"] = candle_timestamp

        except Exception as exc:
            print("TRADE MONITOR ERROR:", repr(exc))

        time.sleep(60)

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

    if not analysis.get(
        "derivatives",
        {}
    ).get(
        "available",
        False
    ):
        derivatives_bias = "Unavailable"
    else:
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
            f'{analysis.get("average_rsi"):.1f}'
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


def build_signal_message(analysis, audience="free"):
    signal = analysis.get("signal")
    if not signal:
        return None

    coin = analysis.get("coin", signal.get("coin", ""))
    direction = signal.get("direction", "")
    is_long = direction in ("CALL / LONG", "LONG")
    direction_label = "LONG" if is_long else "SHORT"
    emoji = "🟢" if is_long else "🔴"
    title = "FREE SIGNAL" if audience == "free" else "VIP SIGNAL"

    entry = signal.get("entry")
    stop = signal.get("invalidation")
    tp1 = signal.get("target_1")
    tp2 = signal.get("target_2")
    tp3 = signal.get("target_3")

    if any(value is None for value in (entry, stop, tp1, tp2, tp3)):
        return None

    return (
        f"<b>🚨 SIDESHIFT AI — {title}</b>\n\n"
        f"{emoji} <b>{coin}</b>\n"
        f"📍 <b>Direction:</b> {direction_label}\n"
        f"💰 <b>Entry:</b> {format_price(entry)}\n\n"
        f"🎯 <b>TP1:</b> {format_price(tp1)}\n"
        f"🎯 <b>TP2:</b> {format_price(tp2)}\n"
        f"🎯 <b>TP3:</b> {format_price(tp3)}\n"
        f"🛑 <b>Stop-loss:</b> {format_price(stop)}"
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
                
            if not validate_signal_entry_price(analysis, "free"):
                continue
                
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
                signal = analysis["signal"]

                record_id = save_signal_record(
                    "free",
                    coin,
                    signal["direction"],
                    signal["entry"],
                    signal["invalidation"],
                    signal["target_1"],
                    signal["target_2"],
                    signal["target_3"],
                )

                free_sent += 1

                register_active_trade(
                    analysis,
                    record_id,
                    "free",
                )


                print(
                   "FREE SIGNAL SENT:",
                   coin,
                )

    if FREE_SIGNAL_CHAT_ID and audience_can_send("free") is False:
        send_daily_report("free")


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
                
            if not validate_signal_entry_price(analysis, "vip"):
                continue
                
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
                signal = analysis["signal"]

                
                record_id = save_signal_record(
                    "vip",
                    coin,
                    signal["direction"],
                    signal["entry"],
                    signal["invalidation"],
                    signal["target_1"],
                    signal["target_2"],
                    signal["target_3"],
                )

                register_active_trade(
                    analysis,
                    record_id,
                    "vip",
                )

                vip_sent += 1
                
                print(
                    "VIP SIGNAL SENT:",
                    coin,
                )

    if VIP_SIGNAL_CHAT_ID and audience_can_send("vip") is False:
        send_daily_report("vip")


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



def automatic_signal_window_open():
    """Allow automatic channel signals from 8 AM to midnight Eastern."""
    eastern = ZoneInfo("America/New_York")
    now = datetime.now(eastern)
    return now.hour >= 8


def signal_loop():
    print(
        "SideShift signal engine started. "
        "Automatic window: 8 AM to midnight Eastern."
    )

    while True:
        try:
            if not automatic_signal_window_open():
                print(
                    "AUTOMATIC SIGNAL WINDOW CLOSED. "
                    "Waiting for 8 AM Eastern."
                )
                time.sleep(60)
                continue

            if FREE_SIGNAL_CHAT_ID or VIP_SIGNAL_CHAT_ID:
                run_signal_engine()
            else:
                print("No signal channels configured.")

        except Exception as exc:
            print("SIGNAL LOOP ERROR:", repr(exc))

        time.sleep(SIGNAL_SCAN_INTERVAL)



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
                              "<b>🟢 WELCOME TO SIDESHIFT AI 4.0!</b>\n\n"
                "<b>I'm here because I want to see you win. 💚</b>\n\n"

                "My purpose isn't simply to send you trading signals. "
                "It's to help you identify opportunities, understand "
                "the market, make smarter trading decisions, and "
                "develop the discipline to become a better trader.\n\n"

                "📊 <b>AI-POWERED MARKET ANALYSIS</b>\n"
                "I'll continuously scan supported crypto perpetual "
                "futures markets for potential LONG 📈 and SHORT 📉 "
                "opportunities.\n\n"

                "🎯 <b>TRADE WITH A PLAN</b>\n"
                "Signals include structured entry levels, stop-losses, "
                "and take-profit targets to help you approach trades "
                "with a plan instead of guesswork.\n\n"

                "🧠 <b>LEARN WHILE YOU TRADE</b>\n"
                "Learn why confirmation, patience, and risk management "
                "matter. The more you understand, the better equipped "
                "you'll be to make informed decisions.\n\n"

                "🛡️ <b>YOUR GROWTH MATTERS</b>\n"
                "I'll evaluate the market, filter potential setups, "
                "and deliver signals when the required conditions "
                "are met. I won't force trades just to fill a quota.\n\n"

                "💚 <b>I WANT TO SEE YOU GROW AND WORK TOWARD "
                "YOUR PROFITABILITY.</b>\n\n"

                f"🟢 Free members can receive up to "
                f"{MAX_FREE_SIGNALS_PER_DAY} qualifying signals per day. "
                "Actual frequency depends on market conditions.\n\n"

                "Let's work toward your success together. 🚀\n\n"

                "⚠️ Crypto perpetual futures involve substantial risk, "
                "including liquidation. No signal guarantees profit. "
                "Always manage your risk responsibly."
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



def send_vip(chat_id):
    message = (
        "<b>🆓 Option 1: Free BYDFi Registration</b>\n"
        "Register using our referral link, then submit your BYDFi UID for review. "
        "Once your registration is verified and approved by our team, "
        "you'll receive free VIP access. 👑\n\n"
        "<b>👑 Option 2: VIP Access — $50 One-Time Payment</b>\n"
        "Choose a payment method, submit your receipt, "
        "and receive your VIP access link once your payment "
        "has been verified."

    )

    keyboard = [
        [
            {
                "text": "🆓 Register with BYDFi — FREE",
                "url": "https://s.bydfi.com/referral/Umn3FDfB",
            }
        ],
                [
            {
                "text": "📝 I've Registered — Submit UID",
                "callback_data": "vip_submit_uid",
            }
        ],
        [
            {
                "text": "👑 Get VIP Access — $50",
                "callback_data": "vip_payment_methods",
            }
        ],
        [
            {
                "text": "⬅️ Main Menu",
                "callback_data": "main_menu",
            }
        ],
    ]

    return send_telegram(
        message,
        chat_id,
        keyboard,
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

            if message.get("photo"):
                sender = message.get("from", {})
                user_id = sender.get("id")
                photos = message.get("photo", [])
                photo_file_id = photos[-1].get("file_id") if photos else None
                caption = (message.get("caption") or "").strip()

                if (
                    message.get("chat", {}).get("type") != "private"
                    or not user_id
                    or not photo_file_id
                ):
                    return jsonify({"ok": True})

                try:
                    with psycopg.connect(DATABASE_URL, connect_timeout=10) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE vip_payment_submissions
                                SET status = 'pending_review',
                                    photo_file_id = %s,
                                    transaction_reference = %s
                                WHERE id = (
                                    SELECT id
                                    FROM vip_payment_submissions
                                    WHERE telegram_user_id = %s
                                      AND status = 'awaiting_receipt'
                                    ORDER BY created_at DESC
                                    LIMIT 1
                                )
                                RETURNING id, payment_method
                            """, (photo_file_id, caption, user_id))
                            submission = cur.fetchone()
                        conn.commit()

                    if not submission:
                        send_telegram(
                            "I couldn't find a pending VIP payment submission. "
                            "Please select your payment method first, then tap "
                            "'Submit Payment Receipt' and send the screenshot.",
                            chat_id,
                        )
                        return jsonify({"ok": True})

                    submission_id, payment_method = submission

                    
                    send_telegram(
                        "<b>✅ Receipt Received!</b>\n\n"
                        "Thank you! Your payment receipt has been "
                        "submitted for verification.\n\n"
                        "Once your payment is confirmed, we'll send "
                        "you your SideShift AI VIP access link. 👑",
                        chat_id,
                    )

                    if VIP_OWNER_TELEGRAM_ID:
                        send_telegram(
                            f"<b>VIP PAYMENT RECEIPT — REVIEW REQUIRED</b>\n\n"
                            f"Submission: #{submission_id}\n"
                            f"User ID: <code>{user_id}</code>\n"
                            f"Username: @{sender.get('username', 'none')}\n"
                            f"Name: {sender.get('first_name', '')} "
                            f"{sender.get('last_name', '')}\n"
                            f"Method: {payment_method}\n"
                            f"Caption/reference: {caption or 'Not provided'}\n\n"
                            "Verify the payment independently before approving.",
                            VIP_OWNER_TELEGRAM_ID,
                            [[
                                {
                                    "text": "✅ Approve",
                                    "callback_data": f"vip_approve_{submission_id}",
                                },
                                {
                                    "text": "❌ Reject",
                                    "callback_data": f"vip_reject_{submission_id}",
                                },
                            ]],
                        )


                        requests.post(
                            f"{TELEGRAM_API}/sendPhoto",
                            json={
                                "chat_id": VIP_OWNER_TELEGRAM_ID,
                                "photo": photo_file_id,
                                "caption": f"Receipt for VIP submission #{submission_id}",
                            },
                            timeout=15,
                        )

                except Exception as exc:
                    print("VIP RECEIPT ERROR:", repr(exc))
                    send_telegram(
                        "Sorry, there was an error processing your receipt. "
                        "Please try again later.",
                        chat_id,
                    )

                return jsonify({"ok": True})

            if text and message.get("chat", {}).get("type") == "private":
                sender = message.get("from", {})
                user_id = sender.get("id")

                if user_id and not text.startswith("/"):
                    try:
                        if not VIP_OWNER_TELEGRAM_ID:
                            send_telegram(
                                "UID submissions are temporarily unavailable. Please try again later.",
                                chat_id,
                            )
                            return jsonify({"ok": True})

                        if len(text) > 100 or len(text) < 1:
                            send_telegram(
                                "That UID doesn't look valid. Please send your BYDFi UID as text.",
                                chat_id,
                            )
                            return jsonify({"ok": True})

                        with psycopg.connect(
                            DATABASE_URL, connect_timeout=10
                        ) as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    UPDATE vip_registration_submissions
                                    SET bydfi_uid = %s,
                                        status = 'pending_review'
                                    WHERE id = (
                                        SELECT id
                                        FROM vip_registration_submissions
                                        WHERE telegram_user_id = %s
                                          AND status = 'awaiting_uid'
                                        ORDER BY created_at DESC
                                        LIMIT 1
                                    )
                                    RETURNING id, telegram_user_id, username,
                                              full_name, bydfi_uid
                                """, (text, user_id))
                                submission = cur.fetchone()
                            conn.commit()

                        if submission:
                            submission_id, telegram_id, username, full_name, bydfi_uid = submission

                            send_telegram(
                                "✅ Your BYDFi UID has been submitted for manual review. "
                                "We'll notify you after our team reviews your registration.",
                                chat_id,
                            )

                            send_telegram(
                                "<b>🆓 FREE VIP REGISTRATION — REVIEW REQUIRED</b>\n\n"
                                f"Submission: #{submission_id}\n"
                                f"Telegram ID: <code>{telegram_id}</code>\n"
                                f"Username: @{username or 'none'}\n"
                                f"Name: {full_name or 'Not provided'}\n"
                                f"BYDFi UID: <code>{bydfi_uid}</code>\n\n"
                                "Verify the referral registration independently before approving.",
                                VIP_OWNER_TELEGRAM_ID,
                                [[
                                    {
                                        "text": "✅ Approve",
                                        "callback_data": f"vip_free_approve_{submission_id}",
                                    },
                                    {
                                        "text": "❌ Reject",
                                        "callback_data": f"vip_free_reject_{submission_id}",
                                    },
                                ]],
                            )

                            return jsonify({"ok": True})

                    except Exception as exc:
                        print("BYDFI UID SUBMISSION ERROR:", repr(exc))
                        send_telegram(
                            "Sorry, there was an error submitting your UID. Please try again later.",
                            chat_id,
                        )
                        return jsonify({"ok": True})


            if text.lower().startswith("/start"):

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

            if callback_data == "scan_menu":
                message_id = callback.get("message", {}).get("message_id")

                edited = edit_telegram_message(
                    chat_id,
                    message_id,
                    (
                        "<b>📊 SELECT A COIN</b>\n\n"
                        "Choose a cryptocurrency to analyze."
                    ),
                    coin_selection_menu(),
                )

                if not edited:
                    send_telegram(
                        (
                            "<b>📊 SELECT A COIN</b>\n\n"
                            "Choose a cryptocurrency to analyze."
                        ),
                        chat_id,
                        coin_selection_menu()
                    )

                return jsonify({"ok": True})

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

            
            if callback_data == "vip_payment_methods":
                send_telegram(
                    "<b>👑 SIDESHIFT AI VIP — $50</b>\n\n"
                    "Choose your preferred payment method.\n\n"
                    "After payment, submit your receipt. "
                    "Your VIP access link will be sent once "
                    "your payment is verified.",
                    chat_id,
                    [
                        [{
                            "text": "💵 Pay with Cash App",
                            "callback_data": "vip_pay_cashapp",
                        }],
                        [{
                            "text": "₿ Pay with Bitcoin (BTC)",
                            "callback_data": "vip_pay_btc",
                        }],
                        [{
                            "text": "◆ Pay with Ethereum",
                            "callback_data": "vip_pay_eth",
                        }],
                        [{
                            "text": "⬅️ Back to VIP Options",
                            "callback_data": "vip",
                        }],
                    ],
                )
                return jsonify({"ok": True})

            
            if callback_data == "vip":
                send_vip(chat_id)
                return jsonify({"ok": True})

            if callback_data == "vip_submit_uid":
                callback_user = callback.get("from", {})
                user_id = callback_user.get("id")
                chat = callback.get("message", {}).get("chat", {})

                if chat.get("type") != "private" or not user_id:
                    send_telegram(
                        "Please submit your BYDFi UID through a private chat with the bot.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                try:
                    with psycopg.connect(
                        DATABASE_URL, connect_timeout=10
                    ) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO vip_registration_submissions (
                                    telegram_user_id,
                                    username,
                                    full_name,
                                    bydfi_uid,
                                    status
                                )
                                VALUES (%s, %s, %s, %s, 'awaiting_uid')
                            """, (
                                user_id,
                                callback_user.get("username", ""),
                                " ".join(
                                    part for part in [
                                        callback_user.get("first_name", ""),
                                        callback_user.get("last_name", ""),
                                    ] if part
                                ),
                                "",
                            ))
                        conn.commit()

                    send_telegram(
                        "<b>📝 Submit Your BYDFi UID</b>\n\n"
                        "First, make sure you registered using our referral link. "
                        "Then send your BYDFi UID here as a text message.\n\n"
                        "Our team will review your registration manually. "
                        "Your UID alone does not guarantee approval.",
                        chat_id,
                    )

                except Exception as exc:
                    print("BYDFI UID REQUEST ERROR:", repr(exc))
                    send_telegram(
                        "Sorry, I couldn't start your UID submission. "
                        "Please try again later.",
                        chat_id,
                    )

                return jsonify({"ok": True})

            callback_user = callback.get("from", {})

            user_id = callback_user.get("id")
            username = callback_user.get("username", "")
            full_name = " ".join(
                part for part in [
                    callback_user.get("first_name", ""),
                    callback_user.get("last_name", ""),
                ] if part
            )
            
            if (
                callback_data.startswith("vip_free_approve_")
                or callback_data.startswith("vip_free_reject_")
            ):
                if (
                    not VIP_OWNER_TELEGRAM_ID
                    or str(user_id) != str(VIP_OWNER_TELEGRAM_ID)
                ):
                    send_telegram(
                        "⛔ You are not authorized to review free VIP registrations.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                try:
                    submission_id = int(callback_data.rsplit("_", 1)[1])
                except (ValueError, IndexError):
                    send_telegram("Invalid free VIP submission.", chat_id)
                    return jsonify({"ok": True})

                is_rejection = callback_data.startswith("vip_free_reject_")

                if is_rejection:
                    with psycopg.connect(
                        DATABASE_URL, connect_timeout=10
                    ) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE vip_registration_submissions
                                SET status = 'rejected',
                                    reviewed_at = NOW(),
                                    reviewed_by = %s
                                WHERE id = %s
                                  AND status = 'pending_review'
                                RETURNING telegram_user_id
                            """, (user_id, submission_id))
                            reviewed = cur.fetchone()
                        conn.commit()

                    if not reviewed:
                        send_telegram(
                            "This registration is no longer pending review.",
                            chat_id,
                        )
                        return jsonify({"ok": True})

                    send_telegram(
                        f"❌ Free VIP registration #{submission_id} rejected.",
                        chat_id,
                    )
                    send_telegram(
                        "Your free VIP registration could not be approved. "
                        "Please check your registration details and contact support if needed.",
                        reviewed[0],
                    )
                    return jsonify({"ok": True})

                if not VIP_SIGNAL_CHAT_ID:
                    send_telegram(
                        "VIP channel is not configured. No access was granted.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                with psycopg.connect(
                    DATABASE_URL, connect_timeout=10
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT telegram_user_id
                            FROM vip_registration_submissions
                            WHERE id = %s
                              AND status = 'pending_review'
                        """, (submission_id,))
                        pending = cur.fetchone()

                if not pending:
                    send_telegram(
                        "This registration is not pending review.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                invite_response = requests.post(
                    f"{TELEGRAM_API}/createChatInviteLink",
                    json={
                        "chat_id": VIP_SIGNAL_CHAT_ID,
                        "member_limit": 1,
                    },
                    timeout=15,
                )
                invite_data = invite_response.json()

                if (
                    not invite_response.ok
                    or not invite_data.get("ok")
                    or not invite_data.get("result", {}).get("invite_link")
                ):
                    print("FREE VIP INVITE ERROR:", invite_data)
                    send_telegram(
                        "Could not create the VIP invite. No access link was sent.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                invite_link = invite_data["result"]["invite_link"]

                with psycopg.connect(
                    DATABASE_URL, connect_timeout=10
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE vip_registration_submissions
                            SET status = 'approved',
                                reviewed_at = NOW(),
                                reviewed_by = %s
                            WHERE id = %s
                              AND status = 'pending_review'
                            RETURNING telegram_user_id
                        """, (user_id, submission_id))
                        approved = cur.fetchone()
                    conn.commit()

                if not approved:
                    requests.post(
                        f"{TELEGRAM_API}/revokeChatInviteLink",
                        json={
                            "chat_id": VIP_SIGNAL_CHAT_ID,
                            "invite_link": invite_link,
                        },
                        timeout=15,
                    )
                    send_telegram(
                        "This registration was already reviewed. No access was granted.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                send_telegram(
                    "<b>👑 Your free SideShift AI VIP access is ready!</b>\n\n"
                    "Your BYDFi registration has been approved. "
                    "Use your personal invite link below to join the VIP channel.",
                    approved[0],
                    [[{
                        "text": "👑 Join SideShift AI VIP",
                        "url": invite_link,
                    }]],
                )
                send_telegram(
                    f"✅ Free VIP registration #{submission_id} approved and invite sent.",
                    chat_id,
                )
                return jsonify({"ok": True})

            if (
                callback_data.startswith("vip_approve_")
                or callback_data.startswith("vip_reject_")
            ):
                if (
                    not VIP_OWNER_TELEGRAM_ID
                    or str(user_id) != str(VIP_OWNER_TELEGRAM_ID)
                ):
                    send_telegram(
                        "⛔ You are not authorized to review payments.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                try:
                    submission_id = int(callback_data.rsplit("_", 1)[1])
                except (ValueError, IndexError):
                    send_telegram("Invalid payment submission.", chat_id)
                    return jsonify({"ok": True})

                if callback_data.startswith("vip_reject_"):
                    with psycopg.connect(
                        DATABASE_URL, connect_timeout=10
                    ) as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE vip_payment_submissions
                                SET status = 'rejected',
                                    reviewed_at = NOW(),
                                    reviewed_by = %s
                                WHERE id = %s
                                  AND status = 'pending_review'
                                RETURNING telegram_user_id
                            """, (user_id, submission_id))
                            reviewed = cur.fetchone()
                        conn.commit()

                    if not reviewed:
                        send_telegram(
                            "This submission is no longer pending review.",
                            chat_id,
                        )
                        return jsonify({"ok": True})

                    send_telegram(
                        f"❌ Submission #{submission_id} was rejected.",
                        chat_id,
                    )
                    send_telegram(
                        "Your VIP payment submission could not be approved. "
                        "Please contact support if you believe this is an error.",
                        reviewed[0],
                    )
                    return jsonify({"ok": True})

                if not VIP_SIGNAL_CHAT_ID:
                    send_telegram(
                        "VIP channel is not configured. No access was granted.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                with psycopg.connect(
                    DATABASE_URL, connect_timeout=10
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT telegram_user_id
                            FROM vip_payment_submissions
                            WHERE id = %s
                              AND status = 'pending_review'
                        """, (submission_id,))
                        pending = cur.fetchone()

                if not pending:
                    send_telegram(
                        "This submission is not pending review.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                
                try:
                    invite_response = requests.post(
                        f"{TELEGRAM_API}/createChatInviteLink",
                        json={
                            "chat_id": VIP_SIGNAL_CHAT_ID,
                            "member_limit": 1,
                        },
                        timeout=15,
                    )
                    invite_data = invite_response.json()
                except Exception as exc:
                    print("VIP INVITE REQUEST EXCEPTION:", repr(exc))
                    send_telegram(
                        "Telegram invite creation failed due to a request error. "
                        "Check Railway logs for VIP INVITE REQUEST EXCEPTION.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

               
                if (
                    not invite_response.ok
                    or not invite_data.get("ok")
                    or not invite_data.get("result", {}).get("invite_link")
                ):
                    error_description = invite_data.get(
                        "description", "No error description returned"
                    )
                    error_code = invite_data.get("error_code", "unknown")
                    print(
                        "VIP INVITE ERROR:",
                        "HTTP", invite_response.status_code,
                        "Telegram code:", error_code,
                        "Description:", error_description,
                    )
                    send_telegram(
                        "Could not create the VIP invite.\n"
                        f"Telegram error {error_code}: {error_description}",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                invite_link = invite_data["result"]["invite_link"]

                with psycopg.connect(
                    DATABASE_URL, connect_timeout=10
                ) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE vip_payment_submissions
                            SET status = 'approved',
                                reviewed_at = NOW(),
                                reviewed_by = %s
                            WHERE id = %s
                              AND status = 'pending_review'
                            RETURNING telegram_user_id
                        """, (user_id, submission_id))
                        approved = cur.fetchone()
                    conn.commit()

                if not approved:
                    requests.post(
                        f"{TELEGRAM_API}/revokeChatInviteLink",
                        json={
                            "chat_id": VIP_SIGNAL_CHAT_ID,
                            "invite_link": invite_link,
                        },
                        timeout=15,
                    )
                    send_telegram(
                        "This submission was already reviewed. No access was granted.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                send_telegram(
                    "<b>👑 Your SideShift AI VIP access is ready!</b>\n\n"
                    "Your payment has been verified and approved. "
                    "Use your personal invite link below to join the VIP channel.",
                    approved[0],
                    [[{
                        "text": "👑 Join SideShift AI VIP",
                        "url": invite_link,
                    }]],
                )
                send_telegram(
                    f"✅ Submission #{submission_id} approved. "
                    "A personal VIP invite was sent to the customer.",
                    chat_id,
                )
                return jsonify({"ok": True})

            if callback_data == "vip_pay_cashapp":
                if not user_id or not begin_vip_receipt_submission(
                    user_id, username, full_name, "cashapp"
                ):
                    send_telegram(
                        "Sorry, we couldn't start your payment submission. Please try again later.",
                        chat_id,
                    )
                    return jsonify({"ok": True})

                send_telegram(
                    "<b>💵 CASH APP — $50 VIP</b>\n\n"
                    "Send the one-time $50 payment to:\n"
                    "<code>$SideShiftAI</code>\n\n"
                    "After paying, return here and send your "
                    "payment receipt screenshot privately.\n\n"
                    "Access is granted only after payment is verified.",
                    chat_id,
                    [[{
                        "text": "📸 Submit Payment Receipt",
                        "callback_data": "vip_submit_receipt",
                    }], [{
                        "text": "⬅️ Back to VIP",
                        "callback_data": "vip",
                    }]],
                )
                return jsonify({"ok": True})

            if callback_data == "vip_pay_btc":
                if not user_id or not begin_vip_receipt_submission(
                    user_id, username, full_name, "btc"
                ):
                    send_telegram(
                        "Sorry, we couldn't start your payment submission. Please try again later.",
                        chat_id,
                    )
                    return jsonify({"ok": True})


                send_telegram(
                    "<b>₿ BITCOIN — $50 VIP</b>\n\n"
                    "Send the equivalent of $50 USD in BTC to:\n"
                    "<code>3GCt2NxCpEXjriRBTvfKhLRTrN1Zt6vRgE</code>\n\n"
                    "Check the network and amount carefully. "
                    "Crypto transfers may be irreversible.\n\n"
                    "After paying, submit your transaction receipt "
                    "or screenshot for review.",
                    chat_id,
                    [[{
                        "text": "📸 Submit Payment Receipt",
                        "callback_data": "vip_submit_receipt",
                    }], [{
                        "text": "⬅️ Back to VIP",
                        "callback_data": "vip",
                    }]],
                )
                return jsonify({"ok": True})

            if callback_data == "vip_pay_eth":
                if not user_id or not begin_vip_receipt_submission(
                    user_id, username, full_name, "eth"
                ):
                    send_telegram(
                        "Sorry, we couldn't start your payment submission. Please try again later.",
                        chat_id,
                    )
                    return jsonify({"ok": True})


                send_telegram(
                    "<b>◆ ETHEREUM (ERC-20) — $50 VIP</b>\n\n"
                    "Send the equivalent of $50 USD in ETH to:\n"
                    "<code>0x0d90E36aFF0d65037e802c222258797174Cb6f16</code>\n\n"
                    "Use the Ethereum network (ERC-20) only. "
                    "Sending through the wrong network may result "
                    "in permanent loss.\n\n"
                    "After paying, submit your transaction receipt "
                    "or screenshot for review.",
                    chat_id,
                    [[{
                        "text": "📸 Submit Payment Receipt",
                        "callback_data": "vip_submit_receipt",
                    }], [{
                        "text": "⬅️ Back to VIP",
                        "callback_data": "vip",
                    }]],
                )
                return jsonify({"ok": True})

            if callback_data == "vip_submit_receipt":
                
                send_telegram(
                    "<b>📸 Submit Your Payment Receipt</b>\n\n"
                    "Please send a screenshot of your payment "
                    "directly in this private chat. Include the "
                    "transaction reference if available.\n\n"
                    "Once your payment is verified, your "
                    "<b>SideShift AI VIP access will be granted.</b>\n\n"
                    "We'll review your receipt and send your VIP "
                    "access link as soon as your payment is confirmed. 👑",
                    chat_id,
                )
                return jsonify({"ok": True})

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


        
        if symbol not in APPROVED_ASSETS:
            return jsonify({
                "error": "Symbol not on approved asset list",
                "symbol": symbol,
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


def daily_report_loop():
    print("SideShift daily report scheduler started.")
    eastern = ZoneInfo("America/New_York")

    while True:
        try:
            now = datetime.now(eastern)
            today = now.date()

            if not DATABASE_URL:
                time.sleep(60)
                continue

            with psycopg.connect(
                DATABASE_URL,
                connect_timeout=10,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT DISTINCT sr.report_date, sr.audience
                        FROM signal_records sr
                        LEFT JOIN daily_report_log dr
                          ON dr.report_date = sr.report_date
                         AND dr.audience = sr.audience
                        WHERE sr.report_date <= %s
                          AND dr.report_date IS NULL
                        ORDER BY sr.report_date, sr.audience
                    """, (today,))
                    pending_reports = cur.fetchall()

            for report_date, audience in pending_reports:
                if report_date == today:
                    continue

                send_daily_report(audience, report_date)

        except Exception as exc:
            print("DAILY REPORT SCHEDULER ERROR:", repr(exc))

        time.sleep(60)

def start_background_engines():

    global BACKGROUND_STARTED

    if BACKGROUND_STARTED:

        return

    BACKGROUND_STARTED = True

    restore_active_trades_from_db()
    
    report_thread = threading.Thread(
        target=daily_report_loop,
        daemon=True,
    )
    report_thread.start()
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


    monitor_thread = threading.Thread(
        target=monitor_active_trades,
        daemon=True,
    )
    monitor_thread.start()

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
init_reporting_db()
inspect_okx_perpetuals()
inspect_gateio_perpetuals()
start_background_engines()

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



    app.run(
        host="0.0.0.0",
        port=PORT,
    )