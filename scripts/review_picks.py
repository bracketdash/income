"""
Step 0 -- grade closed-out batches and report what the whole record says.

Every pick is graded one way: bought at the OPEN of the week's first
session, sold at the CLOSE of its last. That is the user's routine exactly,
so the log and the account describe the same thing. Holidays are part of
the window definition (stamped by log_picks.py), not exceptions.

After grading, two layers are printed:
  1. The batch: per-name results, portfolio vs equal-weight, the batch
     against SPY over the same window, and the research funnel -- did the
     picks beat the names on the shortlist that were never researched?
  2. The POOLED record across every graded batch: conviction calibration,
     setup type, sector, flagged-vs-clean, sizing's cumulative edge, and
     whether realised moves have matched the ATR estimates. Single batches
     are ~12 names; the pooled view is where a pattern becomes visible.

Usage:
    python scripts/review_picks.py            # grade what is due, then pooled summary
    python scripts/review_picks.py --pooled   # pooled summary only, no fetching
"""
import argparse
import time
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from market_calendar import is_trading_day
from paths import PICK_LOG, RESEARCHED, RUNS_DIR, SHORTLIST

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = dtime(16, 0)
COLUMNS = [
    "BatchDate", "Ticker", "Sector", "SetupType", "Rank", "Thesis",
    "Conviction", "Weight", "CashPct", "RegimeScore",
    "ReferenceClose", "ATR14", "ExpMovePct", "Flags",
    "WindowEndDate", "GeneratedAt",
    "Reviewed", "EntryOpen", "ReturnPct", "OutcomeClass", "ReviewDate",
]


def session_is_incomplete():
    now = datetime.now(MARKET_TZ)
    return is_trading_day(now.date()) and now.time() < MARKET_CLOSE


def load_log():
    if not PICK_LOG.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(PICK_LOG)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    df = df[COLUMNS]
    for c in ["OutcomeClass", "ReviewDate", "Flags", "Reviewed"]:
        df[c] = df[c].astype(object)
    for c in ["EntryOpen", "ReturnPct", "Weight", "CashPct", "Conviction", "ExpMovePct"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def fetch(ticker, start, end):
    for attempt in range(4):
        try:
            return yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        except Exception as e:
            if "Rate limit" in str(e) or "Too Many Requests" in str(e):
                time.sleep(2 ** attempt * 3)
                continue
            print(f"  {ticker}: fetch error ({e})")
            return None
    return None


def open_to_close(hist, window_end):
    hist.index = hist.index.tz_localize(None)
    h = hist[hist.index <= window_end]
    if h.empty:
        h = hist
    return float(h["Open"].iloc[0]), float(h["Close"].iloc[-1])


def review():
    df = load_log()
    if df.empty:
        print("No pick log yet -- nothing to review.")
        return df
    df["WindowEndDate"] = pd.to_datetime(df["WindowEndDate"])
    today = pd.Timestamp.now().normalize()
    reviewed = df["Reviewed"].isin([True, "True", "TRUE"])
    due = df[(df["WindowEndDate"] <= today) & ~reviewed]
    if session_is_incomplete():
        ends_today = due["WindowEndDate"] == today
        if ends_today.any():
            print("Holding batch(es) whose window ends today: market still open. Re-run after 4:00 PM ET.")
            due = due[~ends_today]
    if due.empty:
        print("No closed-out batches awaiting review.")
        df["WindowEndDate"] = df["WindowEndDate"].dt.strftime("%Y-%m-%d")
        return df

    print(f"Reviewing {len(due)} picks across {due['BatchDate'].nunique()} batch(es)...")
    today_str = today.strftime("%Y-%m-%d")
    for idx, row in due.iterrows():
        bd, we = pd.to_datetime(row["BatchDate"]), row["WindowEndDate"]
        hist = fetch(row["Ticker"], bd.strftime("%Y-%m-%d"), (we + pd.Timedelta(days=2)).strftime("%Y-%m-%d"))
        if hist is None or hist.empty:
            print(f"  {row['Ticker']}: no price data, leaving unreviewed")
            continue
        time.sleep(0.4)
        entry, exit_px = open_to_close(hist, we)
        if entry <= 0:
            continue
        ret = (exit_px / entry - 1) * 100
        df.loc[idx, ["EntryOpen", "ReturnPct", "OutcomeClass", "Reviewed", "ReviewDate"]] = \
            [round(entry, 2), round(ret, 2), "win" if ret > 0 else "loss", True, today_str]
        print(f"  {row['Ticker']}: {'win' if ret > 0 else 'loss'} ({ret:+.1f}%)  {entry:.2f} -> {exit_px:.2f}")
    df["WindowEndDate"] = df["WindowEndDate"].dt.strftime("%Y-%m-%d")
    df.to_csv(PICK_LOG, index=False)
    summarize_batches(df[df["ReviewDate"] == today_str])
    return df


def summarize_batches(rows):
    if rows.empty:
        return
    for batch, g in rows.groupby("BatchDate"):
        print(f"\n--- BATCH {batch} ---")
        print(f"{int((g['ReturnPct'] > 0).sum())} wins / {int((g['ReturnPct'] <= 0).sum())} losses, "
              f"avg {g['ReturnPct'].mean():+.2f}% per name")
        w, r = g["Weight"], g["ReturnPct"]
        we = pd.to_datetime(g["WindowEndDate"].iloc[0])
        if w.notna().all() and w.sum() > 0:
            cash = g["CashPct"].iloc[0] if pd.notna(g["CashPct"].iloc[0]) else 0.0
            port, equal = float((w * r).sum()), float(r.mean() * w.sum())
            print(f"Portfolio on capital: {port:+.2f}%  ({cash:.0%} cash)   equal-weight: {equal:+.2f}%   "
                  f"sizing {'added' if port > equal else 'cost'} {abs(port - equal):.2f} pts")
            spy = fetch("SPY", batch, (we + pd.Timedelta(days=2)).strftime("%Y-%m-%d"))
            if spy is not None and not spy.empty:
                so, sc = open_to_close(spy, we)
                spy_ret = (sc / so - 1) * 100
                print(f"SPY same window: {spy_ret:+.2f}%   book minus SPY: {port - spy_ret:+.2f} pts")
        by = g.groupby("SetupType")["ReturnPct"].agg(["mean", "count"]).sort_values("mean", ascending=False)
        print("By setup:", "; ".join(f"{k} {v['mean']:+.1f}% (n={int(v['count'])})" for k, v in by.iterrows()))
        research_funnel(batch, g["Ticker"].tolist(), we)


def research_funnel(batch, picks, window_end):
    """Did research selection beat the raw screen? Equal-weight open->close
    for: the whole shortlist, its top 30 by score, the names researched and
    rejected, the names never researched, and the picks. If the picks trail
    the never-researched remainder, the funnel started in the wrong place;
    if they trail the rejected set, selection itself hurt."""
    rd = RUNS_DIR / batch
    sl_path, rs_path = rd / SHORTLIST, rd / RESEARCHED
    if not sl_path.exists():
        print(f"(funnel diagnostic skipped: {sl_path} not found)")
        return
    syms = pd.read_csv(sl_path)["Symbol"].tolist()
    try:
        data = yf.download(syms, start=batch, end=(window_end + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
                           progress=False, auto_adjust=True, threads=True)
        o, c = data["Open"], data["Close"]
        o.index, c.index = o.index.tz_localize(None), c.index.tz_localize(None)
        o, c = o[o.index <= window_end], c[c.index <= window_end]
        fwd = ((c.iloc[-1] / o.iloc[0]) - 1) * 100
    except Exception as e:
        print(f"(funnel diagnostic skipped: {e})")
        return
    researched = set()
    if rs_path.exists():
        txt = rs_path.read_text(encoding="utf-8")
        researched = {t.strip().upper() for t in txt.replace("\n", ",").split(",") if t.strip()}
    picks = set(picks)
    rejected = researched - picks
    never = set(syms) - researched - picks

    def ew(s):
        v = fwd.reindex([t for t in s if t in fwd.index]).dropna()
        return f"{v.mean():+.2f}% (n={len(v)})" if len(v) else "n/a"
    print("Research funnel, equal-weight open->close:")
    print(f"  whole shortlist {ew(syms)}   top-30 by score {ew(syms[:30])}")
    print(f"  picked {ew(picks)}   researched & rejected {ew(rejected)}   never researched {ew(never)}")


def pooled(df):
    g = df[df["Reviewed"].isin([True, "True", "TRUE"]) & df["ReturnPct"].notna()].copy()
    if g.empty:
        print("\nNo graded picks yet -- the pooled view starts after the first review.")
        return
    nb = g["BatchDate"].nunique()
    print(f"\n=== POOLED: {len(g)} graded picks across {nb} batches ===")
    if len(g) < 40 or nb < 5:
        print("(Below the 5-batch / 40-pick bar for changing any constant. Read for direction only.)")

    def bucket(key, label, min_n=1):
        b = g.groupby(key)["ReturnPct"].agg(["mean", "median", "count"])
        b = b[b["count"] >= min_n].sort_values("mean", ascending=False)
        print(f"\n{label}:")
        for k, v in b.iterrows():
            print(f"  {str(k):28s} n={int(v['count']):3d}  mean {v['mean']:+6.2f}%  median {v['median']:+6.2f}%")
    bucket("Conviction", "Conviction (should be monotonic if the rubric means anything)")
    bucket("SetupType", "Setup type")
    bucket("Sector", "Sector", min_n=3)

    fl = g["Flags"].fillna("").astype(str).str.strip() != ""
    if fl.any() and (~fl).any():
        print(f"\nTechnicals-flagged vs clean: flagged n={int(fl.sum())} {g[fl]['ReturnPct'].mean():+.2f}%   "
              f"clean n={int((~fl).sum())} {g[~fl]['ReturnPct'].mean():+.2f}%")

    print("\nPer batch (sizing vs equal-weight, and cash):")
    tot_edge = 0.0
    for b, gb in g.groupby("BatchDate"):
        w, r = gb["Weight"], gb["ReturnPct"]
        if w.notna().all() and w.sum() > 0:
            port, eq = float((w * r).sum()), float(r.mean() * w.sum())
            cash = gb["CashPct"].iloc[0] if pd.notna(gb["CashPct"].iloc[0]) else 0.0
            tot_edge += port - eq
            print(f"  {b}  n={len(gb):2d}  regime {gb['RegimeScore'].iloc[0]}  cash {cash:4.0%}  "
                  f"book {port:+.2f}%  equal {eq:+.2f}%  sizing {port - eq:+.2f}")
    print(f"  sizing edge, summed: {tot_edge:+.2f} pts over {nb} batches")

    if g["ExpMovePct"].notna().any():
        m = g[g["ExpMovePct"].notna()]
        ratio = (m["ReturnPct"].abs() / m["ExpMovePct"])
        print(f"\nDispersion calibration: |realised| / ATR-expected move, median {ratio.median():.2f}, "
              f"mean {ratio.mean():.2f}, share over 1.0: {100 * (ratio > 1).mean():.0f}%  "
              f"(a well-calibrated estimate lands median ~0.7-0.8; >1 means ATR understated the week)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Step 0: grade closed-out batches; pooled summary")
    ap.add_argument("--pooled", action="store_true", help="pooled summary only")
    a = ap.parse_args()
    if a.pooled:
        pooled(load_log())
    else:
        pooled(review())
