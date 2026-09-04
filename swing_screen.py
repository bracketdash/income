"""
Swing-trade screener: NYSE/NASDAQ universe -> technical/momentum shortlist.

Two-stage pipeline for the swing-trade workflow (see SWING_TRADE_PROCESS.md
for the full process this script is step 1 of):
  1. This script narrows ~5,500 NYSE/NASDAQ common stocks down to a ranked
     shortlist (shortlist.csv) using price/liquidity filters and momentum/
     structure metrics, plus a market-regime summary (regime.txt).
  2. Claude reads both files, verifies the finalists against live data and
     news, checks the macro calendar, and produces the final ranked list.

Usage:
    python swing_screen.py
    python swing_screen.py --top 60 --min-dollar-vol 25000000

Notes on scope (see SWING_TRADE_PROCESS.md for the rules this enforces):
  - "No OTC" is satisfied by construction: the universe comes only from the
    NASDAQ Trader symbol directories (NASDAQ + NYSE), which never include
    OTC/pink-sheet names.
  - "Nothing pinned by pending merger arbitrage" is NOT detected here -- it
    requires reading news, which happens in Claude's research pass.
  - Sector and next-earnings-date require a per-ticker info/calendar call,
    which is slow at full-universe scale. Those are fetched only for the
    top N candidates after ranking (enrichment step), not the whole universe.
  - Valuation froth is deliberately NOT used to disqualify here -- your
    rule is "use valuation only as a disqualifier for extreme froth, never
    a reason to include," which is a judgment call better made by Claude
    during research than hard-coded into the score.
"""

import argparse
import io
import pickle
import re
import sys
import time
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from market_calendar import is_trading_day, sessions_in_week

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

CACHE_DIR = Path(r"M:\Code\income\.cache")
UNIVERSE_CACHE = CACHE_DIR / "universe.csv"
UNIVERSE_CACHE_MAX_AGE_DAYS = 7
PRICE_CACHE = CACHE_DIR / "prices_{date}.pkl"

# Exclude obvious non-common-stock instruments by name.
EXCLUDE_NAME_RE = re.compile(
    r"\b(?:warrant|right|rights|unit|units|preferred|preference|depositary|"
    r"depository|notes?|debenture|subordinated|trust pref|when issued|"
    r"exchange traded note|etn|leveraged|inverse|2x|3x|acquisition corp|"
    r"blank check)\b",
    re.IGNORECASE,
)

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = dtime(16, 0)
MARKET_OPEN = dtime(9, 30)

# Sessions in the week being screened for, so the expected-move column is on
# the same scale as the holding window and as rank_and_size.py. Four in a
# holiday week, five otherwise.
WEEK_SESSIONS = sessions_in_week(datetime.now(MARKET_TZ).date())

MIN_PRICE = 5.0
MIN_DOLLAR_VOL = 25_000_000
MIN_DOLLAR_VOL_DAYS = 15  # of the last 20 sessions, how many must individually clear MIN_DOLLAR_VOL
# (a 20-day average can be gamed by one or two spike days on an otherwise
# illiquid name; requiring most individual days to clear the bar closes that)
MIN_HISTORY_DAYS = 63  # ~3 trading months
HISTORY_PERIOD = "1y"
CHUNK_SIZE = 300
CHUNK_PAUSE_SEC = 1.5
TOP_N_DEFAULT = 60

# Score weights (defaults -- tune here).
W_RS = 0.40
W_BREAKOUT = 0.25
W_PULLBACK = 0.20
W_GAP_EVENT = 0.15

REGIME_TICKERS = ["SPY", "QQQ", "^VIX", "^TNX"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def session_is_incomplete():
    """True when the current US session is open or hasn't closed yet.

    yfinance's daily bars include a partial, still-forming bar for the
    current session while the market is open. That bar poisons every
    volume-based signal: the day's volume is only fractionally
    accumulated, so VolRatio collapses toward zero, `breakout`
    (needs >= 1.5) can never fire, and `pullback` (needs <= 0.9) fires on
    essentially everything, so a run between the opening and closing bell
    must drop that bar. See drop_incomplete_bars().

    Outside those hours there is nothing partial to drop: before the open
    the session has not started, and after the close it is final. That
    distinction matters because the normal run window for this process is
    exactly the non-trading hours -- treating a 5am run as mid-session
    would key its price cache as intraday and stop a later run reusing it.
    """
    now_et = datetime.now(MARKET_TZ)
    if not is_trading_day(now_et.date()):
        return False
    return MARKET_OPEN <= now_et.time() < MARKET_CLOSE


def drop_incomplete_bars(frames):
    """Remove today's still-forming bar from every frame, if present.

    Keyed off each frame's own last index date rather than a global
    assumption, so holidays and halted names are handled correctly: if a
    ticker's last bar isn't today, nothing is dropped for it.
    """
    if not session_is_incomplete():
        return frames, False
    today_et = datetime.now(MARKET_TZ).date()
    trimmed = {}
    dropped = 0
    for ticker, df in frames.items():
        if len(df) and df.index[-1].date() == today_et:
            df = df.iloc[:-1]
            dropped += 1
        trimmed[ticker] = df
    if dropped:
        now_et = datetime.now(MARKET_TZ).strftime("%H:%M %Z")
        log(f"Market open ({now_et}) -- dropped today's partial bar from "
            f"{dropped} tickers; all signals use completed sessions only.")
    return trimmed, dropped > 0


def fetch_universe(force_refresh=False):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not force_refresh and UNIVERSE_CACHE.exists():
        age_days = (time.time() - UNIVERSE_CACHE.stat().st_mtime) / 86400
        if age_days < UNIVERSE_CACHE_MAX_AGE_DAYS:
            log(f"Using cached universe list ({UNIVERSE_CACHE}, {age_days:.1f}d old)")
            return pd.read_csv(UNIVERSE_CACHE)["Symbol"].tolist()

    log("Downloading NASDAQ symbol directory...")
    nasdaq_txt = requests.get(NASDAQ_LISTED_URL, timeout=30).text
    nasdaq_df = pd.read_csv(io.StringIO(nasdaq_txt), sep="|")
    nasdaq_df = nasdaq_df[nasdaq_df["Test Issue"] == "N"]
    nasdaq_df = nasdaq_df[nasdaq_df["ETF"] == "N"]
    nasdaq_df = nasdaq_df[~nasdaq_df["Security Name"].str.contains(EXCLUDE_NAME_RE, na=False)]
    nasdaq_symbols = nasdaq_df["Symbol"].dropna().tolist()

    log("Downloading NYSE/other symbol directory...")
    other_txt = requests.get(OTHER_LISTED_URL, timeout=30).text
    other_df = pd.read_csv(io.StringIO(other_txt), sep="|")
    other_df = other_df[other_df["Test Issue"] == "N"]
    other_df = other_df[other_df["ETF"] == "N"]
    other_df = other_df[other_df["Exchange"] == "N"]  # NYSE only (not Arca/American)
    other_df = other_df[~other_df["Security Name"].str.contains(EXCLUDE_NAME_RE, na=False)]
    other_symbols = other_df["ACT Symbol"].dropna().tolist()

    symbols = sorted(set(nasdaq_symbols) | set(other_symbols))
    # Drop symbols with special characters (share classes, warrants, units)
    # that don't map cleanly to yfinance tickers.
    symbols = [s for s in symbols if re.fullmatch(r"[A-Z]{1,5}", s)]

    pd.DataFrame({"Symbol": symbols}).to_csv(UNIVERSE_CACHE, index=False)
    log(f"Universe: {len(symbols)} symbols (cached to {UNIVERSE_CACHE})")
    return symbols


def bulk_download(tickers, use_cache=True):
    # Tag intraday caches separately: a snapshot taken while the market was
    # open holds a partial final bar, so it must never be reused by a later
    # post-close run (or vice versa).
    today = datetime.now(MARKET_TZ).strftime("%Y-%m-%d")
    if session_is_incomplete():
        today += "-intraday"
    cache_path = Path(str(PRICE_CACHE).format(date=today))
    if use_cache and cache_path.exists():
        log(f"Using cached price data ({cache_path})")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    all_tickers = tickers + REGIME_TICKERS
    frames = {}
    chunks = [all_tickers[i:i + CHUNK_SIZE] for i in range(0, len(all_tickers), CHUNK_SIZE)]
    log(f"Downloading {len(all_tickers)} tickers in {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks, 1):
        try:
            data = yf.download(
                chunk, period=HISTORY_PERIOD, interval="1d",
                group_by="ticker", threads=True, auto_adjust=True,
                progress=False,
            )
        except Exception as e:
            log(f"  chunk {i}/{len(chunks)} FAILED: {e}")
            continue
        for t in chunk:
            try:
                df = data[t] if len(chunk) > 1 else data
                df = df.dropna(how="all")
                if not df.empty:
                    frames[t] = df
            except (KeyError, Exception):
                continue
        log(f"  chunk {i}/{len(chunks)} done ({len(frames)} tickers collected so far)")
        time.sleep(CHUNK_PAUSE_SEC)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(frames, f)
    return frames


def compute_regime(frames, breadth_symbols=None):
    """Regime snapshot. `breadth_symbols` restricts the breadth proxy to the
    liquid, tradeable universe -- measuring breadth across all ~5,000
    downloaded names lets illiquid microcaps dominate a number that is
    supposed to describe the tape you can actually trade."""
    now_et = datetime.now(MARKET_TZ)
    lines = [f"Generated: {now_et.strftime('%Y-%m-%d %H:%M %Z')} "
             f"({'market open' if session_is_incomplete() else 'market closed'})",
             ""]
    spy = frames.get("SPY")
    qqq = frames.get("QQQ")
    vix = frames.get("^VIX")
    tnx = frames.get("^TNX")

    def trend_desc(df, name):
        if df is None or len(df) < 60:
            return f"{name}: insufficient data"
        close = df["Close"]
        sma20, sma50 = close.rolling(20).mean().iloc[-1], close.rolling(50).mean().iloc[-1]
        last = close.iloc[-1]
        chg5 = (last / close.iloc[-6] - 1) * 100 if len(close) > 6 else float("nan")
        chg20 = (last / close.iloc[-21] - 1) * 100 if len(close) > 21 else float("nan")
        posture = "above" if last > sma50 else "below"
        return f"{name}: {last:.2f} ({posture} 50d SMA), 5d {chg5:+.1f}%, 20d {chg20:+.1f}%"

    lines.append(trend_desc(spy, "SPY"))
    lines.append(trend_desc(qqq, "QQQ"))

    if vix is not None and not vix.empty:
        vlast = vix["Close"].iloc[-1]
        vprev = vix["Close"].iloc[-6] if len(vix) > 6 else vlast
        lines.append(f"VIX: {vlast:.1f} ({'rising' if vlast > vprev else 'falling'} vs 5d ago: {vprev:.1f})")
    if tnx is not None and not tnx.empty:
        tlast = tnx["Close"].iloc[-1]
        tprev = tnx["Close"].iloc[-11] if len(tnx) > 11 else tlast
        lines.append(f"10Y yield (^TNX): {tlast:.2f} ({'rising' if tlast > tprev else 'falling'} vs 10d ago: {tprev:.2f})")

    # Breadth proxy: % of the liquid universe above its own 50-day SMA.
    above_50 = 0
    total = 0
    for t, df in frames.items():
        if t in REGIME_TICKERS or len(df) < 50:
            continue
        if breadth_symbols is not None and t not in breadth_symbols:
            continue
        total += 1
        sma50 = df["Close"].rolling(50).mean().iloc[-1]
        if df["Close"].iloc[-1] > sma50:
            above_50 += 1
    if total:
        scope = "liquid universe" if breadth_symbols is not None else "all downloaded names"
        lines.append(f"Breadth: {above_50}/{total} ({100*above_50/total:.0f}%) of {scope} above its 50d SMA")

    lines.append("")
    lines.append("NOTE: Fed/CPI/PCE/jobs calendar and rate-CUT-vs-HIKE direction are")
    lines.append("not pulled here -- confirm those live (web search) before writing the regime call.")
    return "\n".join(lines)


def compute_metrics(symbol, df, spy_df):
    if df is None or len(df) < MIN_HISTORY_DAYS:
        return None
    close, volume = df["Close"], df["Volume"]
    high, low = df["High"], df["Low"]
    last_price = close.iloc[-1]
    if last_price < MIN_PRICE:
        return None

    daily_dollar_vol = close * volume
    dollar_vol_20d = daily_dollar_vol.rolling(20).mean().iloc[-1]
    if pd.isna(dollar_vol_20d) or dollar_vol_20d < MIN_DOLLAR_VOL:
        return None
    consistent_days = int((daily_dollar_vol.tail(20) >= MIN_DOLLAR_VOL).sum())
    if consistent_days < MIN_DOLLAR_VOL_DAYS:
        return None

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else pd.Series(dtype=float)

    def ret(n):
        if len(close) <= n:
            return np.nan
        return close.iloc[-1] / close.iloc[-1 - n] - 1

    def spy_ret(n):
        if spy_df is None or len(spy_df["Close"]) <= n:
            return np.nan
        c = spy_df["Close"]
        return c.iloc[-1] / c.iloc[-1 - n] - 1

    rs_5 = ret(5) - spy_ret(5)
    rs_10 = ret(10) - spy_ret(10)
    rs_20 = ret(20) - spy_ret(20)

    s20, s50 = sma20.iloc[-1], sma50.iloc[-1]
    s200 = sma200.iloc[-1] if not sma200.empty else np.nan
    if not np.isnan(s200):
        if last_price > s50 > s200:
            trend = "uptrend"
        elif last_price < s50 < s200:
            trend = "downtrend"
        else:
            trend = "chop"
    else:
        if last_price > s20 > s50:
            trend = "uptrend"
        elif last_price < s20 < s50:
            trend = "downtrend"
        else:
            trend = "chop"

    vol_avg20 = volume.rolling(20).mean().iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_avg20 if vol_avg20 else np.nan

    high20 = high.rolling(20).max().iloc[-1]
    breakout = bool(last_price >= 0.98 * high20 and vol_ratio >= 1.5)

    sma20_5ago = sma20.iloc[-6] if len(sma20) > 6 else np.nan
    pullback = bool(
        trend == "uptrend"
        and not np.isnan(sma20_5ago) and s20 > sma20_5ago
        and 0.97 * s20 <= last_price <= 1.03 * s20
        and (not np.isnan(vol_ratio) and vol_ratio <= 0.9)
    )

    # Gap-event proxy: a big volume + price spike in the last 10 sessions,
    # confirmed as earnings-related later during enrichment.
    recent = df.tail(10)
    daily_ret = recent["Close"].pct_change()
    daily_vol_ratio = recent["Volume"] / vol_avg20 if vol_avg20 else pd.Series(dtype=float)
    gap_event = bool(((daily_ret.abs() >= 0.05) & (daily_vol_ratio >= 3)).any())

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]

    return {
        "Symbol": symbol,
        "Price": round(last_price, 2),
        "DollarVol20d": round(dollar_vol_20d, 0),
        "Trend": trend,
        "RS_5d": round(rs_5 * 100, 2) if not np.isnan(rs_5) else np.nan,
        "RS_10d": round(rs_10 * 100, 2) if not np.isnan(rs_10) else np.nan,
        "RS_20d": round(rs_20 * 100, 2) if not np.isnan(rs_20) else np.nan,
        "VolRatio": round(vol_ratio, 2) if not np.isnan(vol_ratio) else np.nan,
        "Breakout": breakout,
        "Pullback": pullback,
        "GapEvent": gap_event,
        "ATR14": round(atr14, 2) if not np.isnan(atr14) else np.nan,
        # Typical travel over the holding week, in percent -- scaled to the
        # week's actual session count so a holiday week reads 4 sessions,
        # matching what rank_and_size.py computes. A dispersion estimate
        # (which IS forecastable -- volatility clusters), not a forecast of
        # return.
        "ExpMovePct": round((atr14 / last_price) * np.sqrt(WEEK_SESSIONS) * 100, 1) if not np.isnan(atr14) else np.nan,
    }


def score_row(row, rs20_percentile):
    return (
        W_RS * rs20_percentile
        + W_BREAKOUT * 100 * row["Breakout"]
        + W_PULLBACK * 100 * row["Pullback"]
        + W_GAP_EVENT * 100 * row["GapEvent"]
    )


def enrich_top(df):
    log(f"Enriching top {len(df)} candidates with sector + earnings date...")
    sectors, next_earn, days_since_earn = [], [], []
    for symbol in df["Symbol"]:
        sector, nxt, since = "", "", np.nan
        for attempt in range(4):
            try:
                t = yf.Ticker(symbol)
                info = t.info
                sector = info.get("sector") or ""
                # Earnings dates are fetched in their own try so a malformed
                # calendar frame (some tickers return an unexpected shape)
                # costs us only the date, not the sector we already have.
                try:
                    edates = t.get_earnings_dates(limit=8)
                    if edates is not None and not edates.empty:
                        now = pd.Timestamp.now(tz=edates.index.tz)
                        future = edates[edates.index >= now]
                        past = edates[edates.index < now]
                        if not future.empty:
                            nxt = future.index.min().strftime("%Y-%m-%d")
                        if not past.empty:
                            since = (now - past.index.max()).days
                except Exception as inner:
                    if "Rate limit" in str(inner) or "Too Many Requests" in str(inner):
                        raise
                    log(f"  {symbol}: earnings-date lookup failed ({inner}); "
                        f"VERIFY THIS NAME'S EARNINGS DATE MANUALLY")
                break
            except Exception as e:
                if "Rate limit" in str(e) or "Too Many Requests" in str(e):
                    wait = 2 ** attempt * 3
                    log(f"  {symbol}: rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                log(f"  {symbol}: enrichment error ({e})")
                break
        sectors.append(sector)
        next_earn.append(nxt)
        days_since_earn.append(since)
        time.sleep(0.6)
    df = df.copy()
    df["Sector"] = sectors
    df["NextEarnings"] = next_earn
    df["DaysSinceEarnings"] = days_since_earn
    # Normalize both sides to dates: comparing a midnight timestamp against
    # an intraday `now` made same-day earnings compute to -1 days and slip
    # through the flag entirely.
    today = pd.Timestamp.now().normalize()
    df["EarningsInWindow"] = df["NextEarnings"].apply(
        lambda d: bool(d) and 0 <= (pd.Timestamp(d).normalize() - today).days <= 10
    )
    return df


def main():
    global MIN_PRICE, MIN_DOLLAR_VOL
    parser = argparse.ArgumentParser(description="NYSE/NASDAQ swing-trade screener")
    parser.add_argument("--top", type=int, default=TOP_N_DEFAULT, help="shortlist size")
    parser.add_argument("--min-price", type=float, default=MIN_PRICE)
    parser.add_argument("--min-dollar-vol", type=float, default=MIN_DOLLAR_VOL)
    parser.add_argument("--refresh-universe", action="store_true", help="force re-download of symbol directory")
    parser.add_argument("--no-price-cache", action="store_true", help="force re-download of price history")
    parser.add_argument("--limit", type=int, default=None, help="debug: cap universe size")
    parser.add_argument("--output", default=r"M:\Code\income\shortlist.csv")
    parser.add_argument("--regime-output", default=r"M:\Code\income\regime.txt")
    args = parser.parse_args()

    MIN_PRICE = args.min_price
    MIN_DOLLAR_VOL = args.min_dollar_vol

    symbols = fetch_universe(force_refresh=args.refresh_universe)
    if args.limit:
        symbols = symbols[:args.limit]

    frames = bulk_download(symbols, use_cache=not args.no_price_cache)
    log(f"Have price data for {len(frames)}/{len(symbols)} tickers")

    frames, trimmed = drop_incomplete_bars(frames)

    spy_df = frames.get("SPY")
    liquid_rows = []
    for symbol in symbols:
        m = compute_metrics(symbol, frames.get(symbol), spy_df)
        if m is not None:
            liquid_rows.append(m)
    log(f"{len(liquid_rows)} tickers pass price/liquidity filters")

    # Breadth is measured across the liquid universe (including downtrends);
    # candidate scoring then drops downtrends.
    liquid_symbols = {r["Symbol"] for r in liquid_rows}
    regime_text = compute_regime(frames, breadth_symbols=liquid_symbols)
    if trimmed:
        regime_text += ("\n\nData note: run started before the close; today's "
                        "partial bar was excluded, so all figures reflect the "
                        "last completed session.")
    Path(args.regime_output).write_text(regime_text, encoding="utf-8")
    log(f"Regime summary written to {args.regime_output}")
    print("\n--- REGIME ---")
    print(regime_text)
    print("--------------\n")

    rows = [r for r in liquid_rows if r["Trend"] != "downtrend"]
    log(f"{len(rows)} tickers remain after dropping downtrends")

    if not rows:
        log("No candidates survived filtering. Exiting.")
        sys.exit(1)

    metrics_df = pd.DataFrame(rows)
    metrics_df["RS_20d_pct"] = metrics_df["RS_20d"].rank(pct=True) * 100
    metrics_df["Score"] = metrics_df.apply(
        lambda r: score_row(r, r["RS_20d_pct"] if not np.isnan(r["RS_20d_pct"]) else 50), axis=1
    )
    metrics_df = metrics_df.sort_values("Score", ascending=False)

    shortlist = metrics_df.head(args.top).reset_index(drop=True)
    shortlist = enrich_top(shortlist)

    cols = ["Symbol", "Sector", "Price", "Trend", "Score", "RS_5d", "RS_10d", "RS_20d",
            "VolRatio", "Breakout", "Pullback", "GapEvent", "ATR14", "ExpMovePct",
            "DollarVol20d", "DaysSinceEarnings", "NextEarnings",
            "EarningsInWindow"]
    shortlist = shortlist[cols]
    shortlist.to_csv(args.output, index=False)
    log(f"Wrote {len(shortlist)} candidates to {args.output}")
    print(shortlist.to_string(index=False))


if __name__ == "__main__":
    main()
