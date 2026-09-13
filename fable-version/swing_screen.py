"""
Swing-trade screener: NYSE/NASDAQ universe -> ranked shortlist + regime snapshot.

Step 1 of PROCESS.md. Narrows ~5,000 NYSE/NASDAQ common stocks to a ranked
shortlist (shortlist.csv) and writes a market-regime summary (regime.txt).
Everything downstream (technicals.py, research_brief.py, rank_and_size.py,
backtest_screen.py) reads the price cache this script writes, so they all
see exactly the same bars.

What the score is built on, and why (see backtest_screen.py to re-test):
  Over the 40 weeks ending 2026-09-11, measured as next-week open->close
  return versus the liquid non-downtrend universe:
    Breakout flag        +1.03 pts/wk, t = +2.68, positive in both halves
    RS_20d top quintile  -0.00 pts/wk, t = -0.01  (flat across quintiles)
    Pullback flag        -0.53 pts/wk, t = -1.54, negative in both halves
    GapEvent             not separately significant
  The original score put 40% on RS_20d percentile and 20% on Pullback, and
  its top-60 beat the universe by +0.12 pts/wk (t = 0.54) -- noise. The
  weights below lean on the one signal that has shown up as real, keep RS
  as a tiebreaker, and give Pullback no score weight (the flag is still
  computed and printed, because it is a useful *label*, just not a reason
  to rank a name higher). Re-run backtest_screen.py before touching these.

Usage:
    python swing_screen.py
    python swing_screen.py --top 60 --refresh-universe
"""

import argparse
import io
import json
import pickle
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf

from market_calendar import is_trading_day, sessions_in_week

HERE = Path(__file__).resolve().parent
CACHE_DIR = HERE / ".cache"
UNIVERSE_CACHE = CACHE_DIR / "universe.csv"
UNIVERSE_PREV = CACHE_DIR / "universe_prev.csv"
ENRICH_CACHE = CACHE_DIR / "enrich.json"
PRICE_CACHE = CACHE_DIR / "prices_{date}.pkl"
SHORTLIST_OUT = HERE / "shortlist.csv"
REGIME_OUT = HERE / "regime.txt"

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
UNIVERSE_CACHE_MAX_AGE_DAYS = 7
ENRICH_MAX_AGE_DAYS = 7
ENRICH_WORKERS = 3

EXCLUDE_NAME_RE = re.compile(
    r"\b(?:warrant|warrants|right|rights|unit|units|preferred|preference|depositary|"
    r"depository|notes?|debenture|subordinated|trust pref|when issued|"
    r"exchange traded note|etn|leveraged|inverse|2x|3x|acquisition corp|"
    r"blank check)\b",
    re.IGNORECASE,
)

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = dtime(16, 0)
MARKET_OPEN = dtime(9, 30)
WEEK_SESSIONS = sessions_in_week(datetime.now(MARKET_TZ).date())

# Liquidity / history filters.
MIN_PRICE = 5.0
MIN_DOLLAR_VOL = 25_000_000
MIN_DOLLAR_VOL_DAYS = 15      # of the last 20 sessions, how many must individually clear the bar
MIN_HISTORY_DAYS = 63
HISTORY_PERIOD = "1y"
CHUNK_SIZE = 300
CHUNK_PAUSE_SEC = 1.5
TOP_N_DEFAULT = 60

# Flag definitions (shared with backtest_screen.py -- keep in sync).
BREAKOUT_HIGH_FRAC = 0.98     # close within 2% of the 20d high ...
BREAKOUT_VOL_RATIO = 1.5      # ... on >= 1.5x its 20d average volume
PULLBACK_BAND = 0.03          # within 3% of a rising 20d SMA, in an uptrend ...
PULLBACK_VOL_RATIO = 0.9      # ... on quiet volume
GAP_RET, GAP_VOL_RATIO = 0.05, 3.0

# Score weights. See the module docstring for the evidence behind them.
W_BREAKOUT = 0.60
W_RS = 0.25
W_GAP_EVENT = 0.15
W_PULLBACK = 0.00

REGIME_TICKERS = ["SPY", "QQQ", "^VIX", "^TNX"]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def session_is_incomplete():
    """True while the current US session is open. yfinance serves a partial
    bar for an open session; it poisons every volume signal and must be
    dropped. Outside 9:30-16:00 ET on a trading day nothing is partial."""
    now_et = datetime.now(MARKET_TZ)
    if not is_trading_day(now_et.date()):
        return False
    return MARKET_OPEN <= now_et.time() < MARKET_CLOSE


def drop_incomplete_bars(frames):
    if not session_is_incomplete():
        return frames, False
    today_et = datetime.now(MARKET_TZ).date()
    trimmed, dropped = {}, 0
    for ticker, df in frames.items():
        if len(df) and df.index[-1].date() == today_et:
            df = df.iloc[:-1]
            dropped += 1
        trimmed[ticker] = df
    if dropped:
        log(f"Market open -- dropped today's partial bar from {dropped} tickers.")
    return trimmed, dropped > 0


def fetch_universe(force_refresh=False):
    """Symbol directory, cached weekly. On refresh, the previous list is kept
    and the diff printed: removals are almost always completed mergers and
    delistings, which is a free corporate-actions feed for Step 3."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not force_refresh and UNIVERSE_CACHE.exists():
        age_days = (time.time() - UNIVERSE_CACHE.stat().st_mtime) / 86400
        if age_days < UNIVERSE_CACHE_MAX_AGE_DAYS:
            log(f"Using cached universe list ({age_days:.1f}d old)")
            return pd.read_csv(UNIVERSE_CACHE)["Symbol"].tolist()

    log("Downloading NASDAQ symbol directory...")
    nasdaq_df = pd.read_csv(io.StringIO(requests.get(NASDAQ_LISTED_URL, timeout=30).text), sep="|")
    nasdaq_df = nasdaq_df[(nasdaq_df["Test Issue"] == "N") & (nasdaq_df["ETF"] == "N")]
    nasdaq_df = nasdaq_df[~nasdaq_df["Security Name"].str.contains(EXCLUDE_NAME_RE, na=False)]
    nasdaq_symbols = nasdaq_df["Symbol"].dropna().tolist()

    log("Downloading NYSE/other symbol directory...")
    other_df = pd.read_csv(io.StringIO(requests.get(OTHER_LISTED_URL, timeout=30).text), sep="|")
    other_df = other_df[(other_df["Test Issue"] == "N") & (other_df["ETF"] == "N")
                        & (other_df["Exchange"] == "N")]      # NYSE proper only
    other_df = other_df[~other_df["Security Name"].str.contains(EXCLUDE_NAME_RE, na=False)]
    other_symbols = other_df["ACT Symbol"].dropna().tolist()

    symbols = sorted(set(nasdaq_symbols) | set(other_symbols))
    # 1-5 capital letters only; also drop 5-letter symbols ending in W (warrants)
    # or R (rights) that slip past the name filter.
    symbols = [s for s in symbols
               if re.fullmatch(r"[A-Z]{1,5}", s) and not re.fullmatch(r"[A-Z]{4}[WR]", s)]

    if UNIVERSE_CACHE.exists():
        prev = set(pd.read_csv(UNIVERSE_CACHE)["Symbol"])
        UNIVERSE_CACHE.replace(UNIVERSE_PREV)
        added, removed = sorted(set(symbols) - prev), sorted(prev - set(symbols))
        log(f"Universe refresh: +{len(added)} / -{len(removed)} symbols since last cache")
        if removed:
            log(f"  REMOVED (delistings / completed mergers -- check against finalists' "
                f"acquirers in Step 3): {', '.join(removed)}")
        if added:
            log(f"  added: {', '.join(added)}")
    pd.DataFrame({"Symbol": symbols}).to_csv(UNIVERSE_CACHE, index=False)
    log(f"Universe: {len(symbols)} symbols")
    return symbols


def bulk_download(tickers, use_cache=True):
    today = datetime.now(MARKET_TZ).strftime("%Y-%m-%d")
    if session_is_incomplete():
        today += "-intraday"
    cache_path = Path(str(PRICE_CACHE).format(date=today))
    if use_cache and cache_path.exists():
        log(f"Using cached price data ({cache_path.name})")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    all_tickers = tickers + REGIME_TICKERS
    frames = {}
    chunks = [all_tickers[i:i + CHUNK_SIZE] for i in range(0, len(all_tickers), CHUNK_SIZE)]
    log(f"Downloading {len(all_tickers)} tickers in {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks, 1):
        try:
            data = yf.download(chunk, period=HISTORY_PERIOD, interval="1d",
                               group_by="ticker", threads=True, auto_adjust=True,
                               progress=False)
        except Exception as e:
            log(f"  chunk {i}/{len(chunks)} FAILED: {e}")
            continue
        for t in chunk:
            try:
                df = data[t] if len(chunk) > 1 else data
                df = df.dropna(how="all")
                if not df.empty:
                    frames[t] = df
            except Exception:
                continue
        log(f"  chunk {i}/{len(chunks)} done ({len(frames)} collected)")
        time.sleep(CHUNK_PAUSE_SEC)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(frames, f)
    return frames


def compute_regime(frames, breadth_symbols):
    now_et = datetime.now(MARKET_TZ)
    lines = [f"Generated: {now_et.strftime('%Y-%m-%d %H:%M %Z')} "
             f"({'market open' if session_is_incomplete() else 'market closed'})", ""]

    def trend_desc(df, name):
        if df is None or len(df) < 60:
            return f"{name}: insufficient data"
        c = df["Close"]
        sma50 = c.rolling(50).mean().iloc[-1]
        last = c.iloc[-1]
        chg5 = (last / c.iloc[-6] - 1) * 100
        chg20 = (last / c.iloc[-21] - 1) * 100
        return (f"{name}: {last:.2f} ({'above' if last > sma50 else 'below'} 50d SMA), "
                f"5d {chg5:+.1f}%, 20d {chg20:+.1f}%")

    lines.append(trend_desc(frames.get("SPY"), "SPY"))
    lines.append(trend_desc(frames.get("QQQ"), "QQQ"))
    vix, tnx = frames.get("^VIX"), frames.get("^TNX")
    if vix is not None and not vix.empty:
        v, vp = vix["Close"].iloc[-1], vix["Close"].iloc[-6]
        lines.append(f"VIX: {v:.1f} ({'rising' if v > vp else 'falling'} vs 5d ago: {vp:.1f})")
    if tnx is not None and not tnx.empty:
        t, tp = tnx["Close"].iloc[-1], tnx["Close"].iloc[-11]
        lines.append(f"10Y yield: {t:.2f} ({'rising' if t > tp else 'falling'} vs 10d ago: {tp:.2f})")

    above = total = 0
    for t, df in frames.items():
        if t in REGIME_TICKERS or t not in breadth_symbols or len(df) < 50:
            continue
        total += 1
        above += int(df["Close"].iloc[-1] > df["Close"].rolling(50).mean().iloc[-1])
    if total:
        lines.append(f"Breadth: {above}/{total} ({100 * above / total:.0f}%) of liquid universe above its 50d SMA")
    lines += ["", "Macro calendar (FOMC / CPI / PCE / jobs) and rate direction are NOT",
              "pulled here -- confirm by web search before scoring the regime."]
    return "\n".join(lines)


def compute_metrics(symbol, df, spy_df):
    if df is None or len(df) < MIN_HISTORY_DAYS:
        return None
    close, volume, high, low = df["Close"], df["Volume"], df["High"], df["Low"]
    last = close.iloc[-1]
    if last < MIN_PRICE:
        return None
    dvol = close * volume
    dvol20 = dvol.rolling(20).mean().iloc[-1]
    if pd.isna(dvol20) or dvol20 < MIN_DOLLAR_VOL:
        return None
    if int((dvol.tail(20) >= MIN_DOLLAR_VOL).sum()) < MIN_DOLLAR_VOL_DAYS:
        return None

    sma20, sma50 = close.rolling(20).mean(), close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else None

    def ret(s, n):
        return s.iloc[-1] / s.iloc[-1 - n] - 1 if len(s) > n else np.nan
    spy_c = spy_df["Close"] if spy_df is not None else None
    rs = {n: ret(close, n) - (ret(spy_c, n) if spy_c is not None else 0) for n in (5, 10, 20)}

    s20, s50 = sma20.iloc[-1], sma50.iloc[-1]
    if sma200 is not None and not np.isnan(sma200.iloc[-1]):
        s200 = sma200.iloc[-1]
        trend = "uptrend" if last > s50 > s200 else "downtrend" if last < s50 < s200 else "chop"
    else:
        trend = "uptrend" if last > s20 > s50 else "downtrend" if last < s20 < s50 else "chop"

    vol_avg20 = volume.rolling(20).mean().iloc[-1]
    vol_ratio = volume.iloc[-1] / vol_avg20 if vol_avg20 else np.nan
    high20 = high.rolling(20).max().iloc[-1]
    breakout = bool(last >= BREAKOUT_HIGH_FRAC * high20 and vol_ratio >= BREAKOUT_VOL_RATIO)
    sma20_5ago = sma20.iloc[-6]
    pullback = bool(trend == "uptrend" and s20 > sma20_5ago
                    and (1 - PULLBACK_BAND) * s20 <= last <= (1 + PULLBACK_BAND) * s20
                    and vol_ratio <= PULLBACK_VOL_RATIO)
    recent = df.tail(10)
    gap_event = bool(((recent["Close"].pct_change().abs() >= GAP_RET)
                      & (recent["Volume"] / vol_avg20 >= GAP_VOL_RATIO)).any())

    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]
    return {
        "Symbol": symbol, "Price": round(last, 2), "DollarVol20d": round(dvol20, 0),
        "Trend": trend,
        "RS_5d": round(rs[5] * 100, 2), "RS_10d": round(rs[10] * 100, 2), "RS_20d": round(rs[20] * 100, 2),
        "VolRatio": round(vol_ratio, 2), "Breakout": breakout, "Pullback": pullback, "GapEvent": gap_event,
        "ATR14": round(atr14, 2),
        # Dispersion over the holding week (forecastable); NOT a return forecast.
        "ExpMovePct": round((atr14 / last) * np.sqrt(WEEK_SESSIONS) * 100, 1),
    }


def score_row(row, rs20_percentile):
    return (W_BREAKOUT * 100 * row["Breakout"] + W_RS * rs20_percentile
            + W_GAP_EVENT * 100 * row["GapEvent"] + W_PULLBACK * 100 * row["Pullback"])


# ---------------------------------------------------------------- enrichment
def _load_enrich_cache():
    if ENRICH_CACHE.exists():
        try:
            return json.loads(ENRICH_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _fetch_one(symbol):
    """Sector + next/last earnings date for one symbol, with rate-limit backoff.
    Returns (symbol, record_or_None)."""
    for attempt in range(5):
        try:
            t = yf.Ticker(symbol)
            info = t.info or {}
            sector = info.get("sector") or ""
            # Ex-dividend date comes free with the info call. Grading is
            # price-only, so an ex-date inside the window shows up as a
            # small loss the position never really took -- worth knowing.
            ex_div = ""
            if info.get("exDividendDate"):
                try:
                    ex_div = pd.Timestamp(info["exDividendDate"], unit="s").strftime("%Y-%m-%d")
                except Exception:
                    ex_div = ""
            nxt, last_past = "", ""
            try:
                ed = t.get_earnings_dates(limit=8)
                if ed is not None and not ed.empty:
                    now = pd.Timestamp.now(tz=ed.index.tz)
                    fut, past = ed[ed.index >= now], ed[ed.index < now]
                    if not fut.empty:
                        nxt = fut.index.min().strftime("%Y-%m-%d")
                    if not past.empty:
                        last_past = past.index.max().strftime("%Y-%m-%d")
            except Exception as inner:
                if "Rate limit" in str(inner) or "Too Many Requests" in str(inner):
                    raise
            return symbol, {"sector": sector, "next_earnings": nxt, "last_earnings": last_past,
                            "ex_div": ex_div, "fetched": datetime.now().strftime("%Y-%m-%d")}
        except Exception as e:
            if "Rate limit" in str(e) or "Too Many Requests" in str(e):
                time.sleep(2 ** attempt * 3)
                continue
            return symbol, {"sector": "", "next_earnings": "", "last_earnings": "",
                            "fetched": datetime.now().strftime("%Y-%m-%d"), "error": str(e)[:80]}
    return symbol, None


def enrich_top(df):
    """Sector and earnings dates for the shortlist. Cached per symbol for
    ENRICH_MAX_AGE_DAYS and fetched in parallel, so a re-run is instant and a
    fresh run takes minutes rather than the better part of an hour.

    A blank NextEarnings means the lookup FAILED, not that nothing is
    scheduled -- and this lookup only knows quarterly dates. Companies that
    report monthly (Progressive is one) are invisible to it; PROCESS.md Step 3
    requires a by-hand events check on every finalist for exactly that reason."""
    cache = _load_enrich_cache()
    today = pd.Timestamp.now().normalize()
    need = []
    for s in df["Symbol"]:
        rec = cache.get(s)
        if not rec or (today - pd.Timestamp(rec.get("fetched", "2000-01-01"))).days >= ENRICH_MAX_AGE_DAYS \
                or not rec.get("sector"):
            need.append(s)
    log(f"Enriching {len(df)} candidates ({len(need)} fetched, {len(df) - len(need)} from cache)...")
    if need:
        with ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as ex:
            futures = {ex.submit(_fetch_one, s): s for s in need}
            for fut in as_completed(futures):
                s, rec = fut.result()
                if rec is not None:
                    cache[s] = rec
                else:
                    log(f"  {s}: enrichment failed after retries -- VERIFY EARNINGS BY HAND")
        ENRICH_CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    def col(s, key):
        return cache.get(s, {}).get(key, "")
    df = df.copy()
    df["Sector"] = [col(s, "sector") for s in df["Symbol"]]
    df["NextEarnings"] = [col(s, "next_earnings") for s in df["Symbol"]]
    df["DaysSinceEarnings"] = [
        (today - pd.Timestamp(col(s, "last_earnings"))).days if col(s, "last_earnings") else np.nan
        for s in df["Symbol"]]
    df["ExDivDate"] = [col(s, "ex_div") for s in df["Symbol"]]

    def in_window(d):
        return bool(d) and 0 <= (pd.Timestamp(d).normalize() - today).days <= 10
    df["EarningsInWindow"] = df["NextEarnings"].apply(in_window)
    df["ExDivInWindow"] = df["ExDivDate"].apply(in_window)
    return df


def main():
    global MIN_PRICE, MIN_DOLLAR_VOL
    ap = argparse.ArgumentParser(description="NYSE/NASDAQ swing-trade screener")
    ap.add_argument("--top", type=int, default=TOP_N_DEFAULT)
    ap.add_argument("--min-price", type=float, default=MIN_PRICE)
    ap.add_argument("--min-dollar-vol", type=float, default=MIN_DOLLAR_VOL)
    ap.add_argument("--refresh-universe", action="store_true")
    ap.add_argument("--no-price-cache", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="debug: cap universe size")
    args = ap.parse_args()
    MIN_PRICE, MIN_DOLLAR_VOL = args.min_price, args.min_dollar_vol

    symbols = fetch_universe(force_refresh=args.refresh_universe)
    if args.limit:
        symbols = symbols[:args.limit]
    frames = bulk_download(symbols, use_cache=not args.no_price_cache)
    log(f"Have price data for {len(frames)}/{len(symbols)} tickers")
    frames, trimmed = drop_incomplete_bars(frames)

    spy_df = frames.get("SPY")
    liquid = [m for s in symbols if (m := compute_metrics(s, frames.get(s), spy_df)) is not None]
    log(f"{len(liquid)} tickers pass price/liquidity filters")

    regime_text = compute_regime(frames, {r["Symbol"] for r in liquid})
    if trimmed:
        regime_text += "\n\nData note: run started before the close; today's partial bar was excluded."
    REGIME_OUT.write_text(regime_text, encoding="utf-8")
    print("\n--- REGIME ---\n" + regime_text + "\n--------------\n")

    rows = [r for r in liquid if r["Trend"] != "downtrend"]
    log(f"{len(rows)} remain after dropping downtrends; "
        f"{sum(r['Breakout'] for r in rows)} carry the Breakout flag")
    if not rows:
        sys.exit("No candidates survived filtering.")

    mdf = pd.DataFrame(rows)
    mdf["RS_20d_pct"] = mdf["RS_20d"].rank(pct=True) * 100
    mdf["Score"] = mdf.apply(lambda r: score_row(r, r["RS_20d_pct"]), axis=1)
    # Tiebreak within equal scores by VolRatio -- volume confirmation is the
    # part of the breakout signal that carries it.
    mdf = mdf.sort_values(["Score", "VolRatio"], ascending=[False, False])
    shortlist = enrich_top(mdf.head(args.top).reset_index(drop=True))

    cols = ["Symbol", "Sector", "Price", "Trend", "Score", "RS_5d", "RS_10d", "RS_20d",
            "VolRatio", "Breakout", "Pullback", "GapEvent", "ATR14", "ExpMovePct",
            "DollarVol20d", "DaysSinceEarnings", "NextEarnings", "EarningsInWindow",
            "ExDivDate", "ExDivInWindow"]
    shortlist = shortlist[cols]
    shortlist.to_csv(SHORTLIST_OUT, index=False)
    log(f"Wrote {len(shortlist)} candidates to {SHORTLIST_OUT.name} "
        f"(VolRatio median {shortlist['VolRatio'].median():.2f}; healthy is ~0.8-1.0, "
        f"under ~0.5 means a broken session)")
    print(shortlist.to_string(index=False))


if __name__ == "__main__":
    main()
