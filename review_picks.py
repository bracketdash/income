"""
Grade logged swing-trade batches whose window has closed.

Run this at the start of every screening cycle, before the screener
(see SWING_TRADE_PROCESS.md Step 0).

Every pick is graded exactly one way, with no execution modelling at all:

    bought at the OPEN of the week's first trading day,
    sold at the CLOSE of the week's last trading day.

Holidays are part of that definition, not an exception to it: a Labor Day
week runs Tuesday to Friday and a Good Friday week runs Monday to Thursday.
The window end is fixed by log_picks.py when the batch is written.

No fills, no exit rules, no record of which positions were taken, and
nothing the user has to report. That is deliberate. This log exists to
improve the *selection* -- whether the screen picks names that rise across
the week. Folding the trading account into the same number answers a
different question, and mixing the two degrades both: a good week of
trading can hide a bad week of picking, and the reverse. So the log answers
only: were these the right names, and did the weighting help?

Two consequences worth keeping straight:
  - Every name in the table is bought at that open and sold at that close,
    which is exactly the routine the user follows -- so unlike earlier
    versions of this system, the graded record and the account should now
    agree. A divergence means something went wrong, not that the log is
    measuring something else.

Usage:
    python review_picks.py
    python review_picks.py --summary [BATCH]
"""
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from market_calendar import is_trading_day

LOG_PATH = Path(r"M:\Code\income\pick_log.csv")
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_CLOSE = dtime(16, 0)


def session_is_incomplete():
    """True when today's US session is open or hasn't closed yet.

    Mirrors swing_screen.py. Grading reads the window end's CLOSE, and
    yfinance serves a partial, still-forming bar for the current session
    while the market is open -- so a batch whose window ends today would be
    graded against an hour of trading dressed up as a closing price. Worse,
    the row is then marked Reviewed and never revisited.

    A weekend or holiday is never incomplete: the last bar on record is
    already a finished session.
    """
    now_et = datetime.now(MARKET_TZ)
    if not is_trading_day(now_et.date()):
        return False
    return now_et.time() < MARKET_CLOSE
COLUMNS = [
    "BatchDate", "Ticker", "Sector", "SetupType", "Rank", "Thesis",
    "Conviction", "Weight", "CashPct", "RegimeScore",
    "ReferenceClose", "WindowEndDate", "GeneratedAt",
    "Reviewed", "EntryOpen", "ReturnPct", "OutcomeClass", "ReviewDate",
]


def load_log():
    if not LOG_PATH.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(LOG_PATH)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    df = df[COLUMNS]
    for col in ["OutcomeClass", "ReviewDate"]:
        df[col] = df[col].astype(object)
    df["Reviewed"] = df["Reviewed"].astype(object)
    for col in ["EntryOpen", "ReturnPct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch(ticker, start, end):
    for attempt in range(4):
        try:
            return yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        except Exception as e:
            if "Rate limit" in str(e) or "Too Many Requests" in str(e):
                wait = 2 ** attempt * 3
                print(f"  {ticker}: rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            print(f"  {ticker}: fetch error ({e})")
            return None
    return None


def review():
    df = load_log()
    if df.empty:
        print("No pick log yet -- nothing to review.")
        return df

    df["WindowEndDate"] = pd.to_datetime(df["WindowEndDate"])
    today = pd.Timestamp.now().normalize()
    reviewed_mask = df["Reviewed"].isin([True, "True", "TRUE"])
    due = df[(df["WindowEndDate"] <= today) & (~reviewed_mask)]

    # A window ending today isn't gradeable until today has a closing price.
    if session_is_incomplete():
        ends_today = due["WindowEndDate"] == today
        if ends_today.any():
            batches = ", ".join(sorted(due.loc[ends_today, "BatchDate"].unique()))
            now_et = datetime.now(MARKET_TZ).strftime("%H:%M ET")
            print(f"Holding batch {batches}: its window ends today and the market "
                  f"is still open ({now_et}).\n  Grading now would read a partial "
                  f"bar as the closing price. Re-run after 4:00 PM ET.")
            due = due[~ends_today]

    if due.empty:
        print("No closed-out batches awaiting review.")
        return df

    print(f"Reviewing {len(due)} logged picks across {due['BatchDate'].nunique()} batch(es)...")
    today_str = today.strftime("%Y-%m-%d")
    for idx, row in due.iterrows():
        ticker = row["Ticker"]
        batch_date = pd.to_datetime(row["BatchDate"])
        window_end = row["WindowEndDate"]

        hist = fetch(ticker,
                     batch_date.strftime("%Y-%m-%d"),
                     (window_end + pd.Timedelta(days=2)).strftime("%Y-%m-%d"))
        if hist is None or hist.empty:
            print(f"  {ticker}: no price data in window, leaving unreviewed")
            continue
        time.sleep(0.4)

        hist.index = hist.index.tz_localize(None)
        window_hist = hist[hist.index <= window_end]
        if window_hist.empty:
            window_hist = hist

        # The whole model: in at the first open, out at the last close.
        # Both come from the bars that actually exist inside the window, so
        # a holiday or an unscheduled closure needs no special handling --
        # there is simply no bar for that date to pick up.
        entry = float(window_hist["Open"].iloc[0])
        exit_px = float(window_hist["Close"].iloc[-1])
        if entry <= 0:
            print(f"  {ticker}: bad open price, skipping")
            continue
        ret = (exit_px / entry - 1) * 100

        df.loc[idx, "EntryOpen"] = round(entry, 2)
        df.loc[idx, "ReturnPct"] = round(ret, 2)
        df.loc[idx, "OutcomeClass"] = "win" if ret > 0 else "loss"
        df.loc[idx, "Reviewed"] = True
        df.loc[idx, "ReviewDate"] = today_str
        print(f"  {ticker}: {'win' if ret > 0 else 'loss'} ({ret:+.1f}%)  "
              f"{entry:.2f} -> {exit_px:.2f}")

    df.to_csv(LOG_PATH, index=False)
    summarize(df[df["ReviewDate"] == today_str])
    return df


def summarize(rows):
    """Print the batch summary and the two system-level diagnostics.

    Split out from review() so a batch can be re-summarized later without
    refetching prices (`--summary`).
    """
    if rows.empty:
        return

    print("\n--- BATCH REVIEW SUMMARY ---")
    print(rows.groupby("OutcomeClass")["Ticker"].count().to_string())
    print(f"\nAvg return (first open -> last close of the week): "
          f"{rows['ReturnPct'].mean():+.2f}%")

    by_setup = rows.groupby("SetupType")["ReturnPct"].agg(["mean", "count"])
    by_setup = by_setup.sort_values("mean", ascending=False)
    if not by_setup.empty:
        print("\nAvg return by setup type (with n):")
        print(by_setup.to_string())

    # --- the two that judge the SYSTEM, not the individual picks ---
    for batch, grp in rows.groupby("BatchDate"):
        w = pd.to_numeric(grp["Weight"], errors="coerce")
        r = pd.to_numeric(grp["ReturnPct"], errors="coerce")
        if w.notna().all() and r.notna().all() and w.sum() > 0:
            cash = pd.to_numeric(grp["CashPct"], errors="coerce").iloc[0]
            cash = 0.0 if pd.isna(cash) else cash
            port = float((w * r).sum())
            equal = float(r.mean() * w.sum())
            print(f"\nBatch {batch} portfolio result:")
            print(f"  Weighted return on total capital: {port:+.2f}%  ({cash:.0%} in cash)")
            print(f"  Same picks equal-weighted:        {equal:+.2f}%")
            verdict = "sizing ADDED value" if port > equal else "sizing COST value"
            print(f"  -> {verdict} ({port - equal:+.2f} pts)")

    # Conviction calibration: the single most important check on this whole
    # system. If high-conviction names don't out-return low ones, the
    # conviction scores are noise and the sizing built on them is theater.
    # Needs several batches before it means anything.
    conv = pd.to_numeric(rows["Conviction"], errors="coerce")
    if conv.notna().sum() >= 4 and conv.nunique() >= 2:
        calib = rows.assign(C=conv).groupby("C")["ReturnPct"].agg(["mean", "count"])
        print("\nConviction calibration (do higher scores return more?):")
        print(calib.to_string())
        hi = calib[calib.index >= 4]["mean"].mean()
        lo = calib[calib.index <= 2]["mean"].mean()
        if pd.notna(hi) and pd.notna(lo):
            if hi > lo:
                print(f"  -> ordered correctly this batch (high {hi:+.1f}% vs low {lo:+.1f}%)")
            else:
                print(f"  -> INVERTED this batch (high {hi:+.1f}% vs low {lo:+.1f}%) "
                      f"-- watch whether this persists across batches")
    print("----------------------------")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Grade closed-out swing-trade batches")
    ap.add_argument("--summary", metavar="BATCH", nargs="?", const="latest",
                    help="re-print the summary for an already-reviewed batch "
                         "(YYYY-MM-DD, or omit for the most recent) instead of grading")
    opts = ap.parse_args()

    if opts.summary:
        log = load_log()
        graded = log[log["Reviewed"].isin([True, "True", "TRUE"])]
        if graded.empty:
            sys.exit("No reviewed batches in the log yet.")
        batch = opts.summary
        if batch == "latest":
            batch = sorted(graded["BatchDate"].unique())[-1]
        sel = graded[graded["BatchDate"] == batch]
        if sel.empty:
            sys.exit(f"No reviewed batch dated {batch}. Reviewed batches: "
                     f"{', '.join(sorted(graded['BatchDate'].unique()))}")
        summarize(sel)
    else:
        review()
