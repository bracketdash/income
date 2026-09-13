"""
Step 3 -- price-structure check for candidates.

The screener's flags say "did this pattern roughly fire". This reads how the
chart is actually behaving over a one-week horizon and raises the conditions
that most often make a written thesis wrong:

  EXTENDED   >10% above the 20d SMA. Not a penalty: across 40 backtested
             weeks the 10-20%-extended bucket was the best-returning
             extension bucket. It is a LABELLING constraint -- a name this
             far above its average cannot honestly be called a pullback --
             and a dispersion warning: expect a wider move than ATR14 says.
  BELOW20    under its 20d SMA. Fatal to any pullback-in-an-uptrend thesis.
             A past cycle called a name below its 20d "pulling back on light
             volume"; it lost 13% that week.
  DISTRIB    down sessions carrying more volume than up sessions over the
             last 10. Supply in control while price still looks fine. A past
             cycle wrote "an orderly pullback, not distribution" over a 0.50
             ratio; it lost 4%.
  GAPFADE    a recent gap that price has given back. Post-earnings drift only
             works while the gap holds.
  VOLEXP     ATR expanding >30% vs 20 sessions ago: it will move more than
             the sizer's ATR14 assumes.

A flag is a question the thesis must answer honestly, not a veto. What is
not acceptable is a flag going unmentioned in a thesis it contradicts.

Reads the price cache swing_screen.py wrote, so it sees the same bars.

Usage:
    python scripts/technicals.py                      # top 30 of this run's shortlist
    python scripts/technicals.py --tickers BX,AXON
    python scripts/technicals.py --short-interest     # one live call per name
"""

import argparse
import glob
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from paths import CACHE_DIR, SHORTLIST, run_dir

EXTENDED_PCT = 10.0
DISTRIB_RATIO = 0.80
VOLEXP_RATIO = 1.30
GAP_PCT = 4.0


def load_frames():
    paths = sorted(glob.glob(str(CACHE_DIR / "prices_*.pkl")), reverse=True)
    if not paths:
        return None, None
    with open(paths[0], "rb") as f:
        return pickle.load(f), Path(paths[0]).name


def atr(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    p = c.shift(1)
    return pd.concat([h - l, (h - p).abs(), (l - p).abs()], axis=1).max(axis=1).rolling(n).mean()


def analyse(df):
    if df is None or len(df) < 60:
        return None
    close = df["Close"]
    last = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    hi52 = float(df["High"].tail(252).max())
    win = df.tail(20)
    lo, hi = float(win["Low"].min()), float(win["High"].max())
    range_pos = 100 * (last - lo) / (hi - lo) if hi > lo else np.nan

    recent = df.tail(10)
    chg = recent["Close"].diff()
    up_v, dn_v = float(recent["Volume"][chg > 0].sum()), float(recent["Volume"][chg < 0].sum())
    uv = up_v / dn_v if dn_v > 0 else np.inf

    a = atr(df)
    atr_trend = float(a.iloc[-1]) / float(a.iloc[-21]) if float(a.iloc[-21]) > 0 else np.nan

    d = np.sign(close.diff().tail(10).values)
    streak = 0
    for v in d[::-1]:
        if v == 0 or (streak and np.sign(streak) != v):
            break
        streak += int(v)

    gap_held = None
    gaps = ((df["Open"] / df["Close"].shift(1) - 1) * 100).tail(10)
    big = gaps[gaps.abs() >= GAP_PCT]
    if len(big):
        gap_held = last >= float(df.loc[big.index[-1], "Close"])

    ext20 = (last / sma20 - 1) * 100
    flags = []
    if ext20 > EXTENDED_PCT:
        flags.append("EXTENDED")
    if last < sma20:
        flags.append("BELOW20")
    if uv < DISTRIB_RATIO:
        flags.append("DISTRIB")
    if gap_held is False:
        flags.append("GAPFADE")
    if atr_trend and atr_trend > VOLEXP_RATIO:
        flags.append("VOLEXP")
    return dict(last=last, ext20=ext20, ext50=(last / sma50 - 1) * 100, from_hi=(last / hi52 - 1) * 100,
                range_pos=range_pos, uv_ratio=uv, atr_trend=atr_trend, streak=streak, flags=flags)


def main():
    ap = argparse.ArgumentParser(description="Step 3: price-structure check")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--tickers")
    ap.add_argument("--short-interest", action="store_true")
    args = ap.parse_args()

    frames, cache_name = load_frames()
    if frames is None:
        sys.exit("ERROR: no price cache -- run scripts/swing_screen.py first.")
    if args.tickers:
        names = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        sl = run_dir(create=False) / SHORTLIST
        if not sl.exists():
            sys.exit(f"ERROR: {sl} not found -- run scripts/swing_screen.py first.")
        names = pd.read_csv(sl).head(args.top)["Symbol"].tolist()

    print(f"Price structure for {len(names)} candidates (from {cache_name})\n")
    print(f"{'':6} {'last':>9} {'vs20d':>7} {'vs50d':>7} {'vs52wH':>7} {'rng%':>6} {'upVol':>6} {'ATRtr':>6} {'strk':>5}  flags")
    rows, missing = [], []
    for t in names:
        r = analyse(frames.get(t))
        if r is None:
            missing.append(t)
            continue
        r["ticker"] = t
        rows.append(r)
        uv = "inf" if np.isinf(r["uv_ratio"]) else f"{r['uv_ratio']:.2f}"
        print(f"{t:6} {r['last']:>9.2f} {r['ext20']:>+6.1f}% {r['ext50']:>+6.1f}% {r['from_hi']:>+6.1f}% "
              f"{r['range_pos']:>5.0f}% {uv:>6} {r['atr_trend']:>6.2f} {r['streak']:>+5d}  {' '.join(r['flags'])}")

    if args.short_interest:
        import time
        import warnings
        import yfinance as yf
        warnings.filterwarnings("ignore")
        print("\nShort interest (% of float):")
        for r in rows:
            try:
                v = yf.Ticker(r["ticker"]).info.get("shortPercentOfFloat")
                note = "  <-- crowded short; cuts both ways" if v is not None and v >= 0.15 else ""
                print(f"  {r['ticker']:6} {v * 100:.1f}%{note}" if v is not None else f"  {r['ticker']:6} n/a")
            except Exception:
                print(f"  {r['ticker']:6} lookup failed")
            time.sleep(0.3)

    print("\n" + "=" * 72)
    by_flag = {}
    for r in rows:
        for f in r["flags"]:
            by_flag.setdefault(f, []).append(r["ticker"])
    meaning = {
        "EXTENDED": f"> {EXTENDED_PCT:.0f}% over the 20d SMA: cannot be labelled a pullback; expect a wider move than ATR14 implies",
        "BELOW20": "under its 20d SMA: kills a pullback-in-an-uptrend thesis",
        "DISTRIB": "down sessions carrying the volume: supply in control",
        "GAPFADE": "recent gap not holding: a drift thesis is broken",
        "VOLEXP": "ATR expanding fast: will move more than the sizer assumes",
    }
    if by_flag:
        print("Flagged -- each needs an honest answer in its thesis (not a veto, not a throwaway sentence):")
        for f, ts in by_flag.items():
            print(f"  {f:<9} {', '.join(ts)}\n  {'':9} {meaning[f]}")
    else:
        print("No structural flags.")
    clean = [r["ticker"] for r in rows if not r["flags"]]
    if clean:
        print(f"\nClean structure: {', '.join(clean)}")
    if missing:
        print(f"\nNot in cache: {', '.join(missing)}")


if __name__ == "__main__":
    main()
