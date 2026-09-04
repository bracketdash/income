"""
Price-structure check for shortlist candidates.

The screener ranks on a composite score and sets Breakout/Pullback/GapEvent
flags at full-universe scale. Those flags are cheap and noisy: they answer
"did this pattern roughly fire" rather than "is this chart in good shape."
Research (Step 3) then reads news. Nothing in between actually looks at how
the price is behaving, which is the part a human swing trader would spend
their time on.

This fills that gap. For each name it reports the structure that matters
over a one-week hold, and flags the conditions that most often turn a
good-looking screen row into a losing week:

  EXTENDED     far above the 20d SMA -- the move already happened, and mean
               reversion inside five sessions is the base case
  BELOW20      trading under its 20d SMA -- fatal to a "pullback in an
               intact uptrend" thesis, which is the most common setup here
  DISTRIB      down sessions carrying more volume than up sessions, i.e.
               supply in control while price looks fine
  GAPFADE      a recent earnings/news gap that price has since given back;
               post-earnings drift works when the gap HOLDS
  VOLEXP       ATR expanding sharply, so the position will move more than
               the sizer's ATR14 estimate implies

Reads the price cache swing_screen.py already wrote, so it costs nothing
and sees exactly the same bars the screen did. Short interest needs live
calls and is opt-in.

Usage:
    python technicals.py                     # top 30 of shortlist.csv
    python technicals.py --top 40
    python technicals.py --tickers BX,AXON,DNOW
    python technicals.py --short-interest    # adds a live call per name
"""

import argparse
import glob
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SHORTLIST = Path(r"M:\Code\income\shortlist.csv")
CACHE_DIR = Path(r"M:\Code\income\.cache")

EXTENDED_PCT = 10.0    # above the 20d SMA
DISTRIB_RATIO = 0.80   # up-volume / down-volume
VOLEXP_RATIO = 1.30    # ATR now vs ATR 20 sessions ago
GAP_PCT = 4.0          # what counts as a gap worth tracking


def load_frames():
    paths = sorted(glob.glob(str(CACHE_DIR / "prices_*.pkl")), reverse=True)
    if not paths:
        return None, None
    with open(paths[0], "rb") as f:
        return pickle.load(f), Path(paths[0]).name


def atr(df, n=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def analyse(df):
    """Structure metrics for one ticker's OHLCV history."""
    if df is None or len(df) < 60:
        return None
    close = df["Close"]
    last = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    hi52 = float(df["High"].tail(252).max())

    win = df.tail(20)
    rng_lo, rng_hi = float(win["Low"].min()), float(win["High"].max())
    range_pos = 100 * (last - rng_lo) / (rng_hi - rng_lo) if rng_hi > rng_lo else np.nan

    # Accumulation vs distribution: which direction is carrying the volume.
    recent = df.tail(10)
    chg = recent["Close"].diff()
    up_vol = float(recent["Volume"][chg > 0].sum())
    dn_vol = float(recent["Volume"][chg < 0].sum())
    uv_ratio = up_vol / dn_vol if dn_vol > 0 else np.inf

    a = atr(df)
    atr_now, atr_then = float(a.iloc[-1]), float(a.iloc[-21])
    atr_trend = atr_now / atr_then if atr_then > 0 else np.nan

    # Streak of consecutive same-direction closes.
    d = np.sign(close.diff().tail(10).values)
    streak = 0
    for v in d[::-1]:
        if v == 0 or (streak and np.sign(streak) != v):
            break
        streak += int(v)

    # Most recent meaningful gap and whether price has held it.
    gap_pct = gap_held = None
    o, pc = df["Open"], df["Close"].shift(1)
    gaps = ((o / pc - 1) * 100).tail(10)
    big = gaps[gaps.abs() >= GAP_PCT]
    if len(big):
        idx = big.index[-1]
        gap_pct = float(big.iloc[-1])
        gap_close = float(df.loc[idx, "Close"])
        gap_held = last >= gap_close

    flags = []
    ext20 = (last / sma20 - 1) * 100
    if ext20 > EXTENDED_PCT:
        flags.append("EXTENDED")
    if last < sma20:
        flags.append("BELOW20")
    if uv_ratio < DISTRIB_RATIO:
        flags.append("DISTRIB")
    if gap_held is False:
        flags.append("GAPFADE")
    if atr_trend and atr_trend > VOLEXP_RATIO:
        flags.append("VOLEXP")

    return dict(last=last, ext20=ext20, ext50=(last / sma50 - 1) * 100,
                from_hi=(last / hi52 - 1) * 100, range_pos=range_pos,
                uv_ratio=uv_ratio, atr_trend=atr_trend, streak=streak,
                gap_pct=gap_pct, gap_held=gap_held, flags=flags)


def main():
    ap = argparse.ArgumentParser(description="Price-structure check for candidates")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--tickers", help="comma-separated tickers instead of the shortlist")
    ap.add_argument("--short-interest", action="store_true",
                    help="also fetch short %% of float (one live call per name)")
    args = ap.parse_args()

    frames, cache_name = load_frames()
    if frames is None:
        sys.exit("ERROR: no price cache -- run swing_screen.py first.")

    if args.tickers:
        names = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        if not SHORTLIST.exists():
            sys.exit("ERROR: no shortlist.csv -- run swing_screen.py first.")
        names = pd.read_csv(SHORTLIST).head(args.top)["Symbol"].tolist()

    print(f"Price structure for {len(names)} candidates (from {cache_name})\n")
    print(f"{'':6} {'last':>9} {'vs20d':>7} {'vs50d':>7} {'vs52wH':>7} "
          f"{'rng%':>6} {'upVol':>6} {'ATRtr':>6} {'strk':>5}  flags")

    rows, missing = [], []
    for t in names:
        r = analyse(frames.get(t))
        if r is None:
            missing.append(t)
            continue
        r["ticker"] = t
        rows.append(r)
        uv = "inf" if np.isinf(r["uv_ratio"]) else f"{r['uv_ratio']:.2f}"
        print(f"{t:6} {r['last']:>9.2f} {r['ext20']:>+6.1f}% {r['ext50']:>+6.1f}% "
              f"{r['from_hi']:>+6.1f}% {r['range_pos']:>5.0f}% {uv:>6} "
              f"{r['atr_trend']:>6.2f} {r['streak']:>+5d}  {' '.join(r['flags'])}")

    if args.short_interest:
        import yfinance as yf
        import warnings, time as _t
        warnings.filterwarnings("ignore")
        print("\nShort interest (% of float):")
        for r in rows:
            try:
                v = yf.Ticker(r["ticker"]).info.get("shortPercentOfFloat")
                note = ""
                if v is not None and v >= 0.15:
                    note = "  <-- crowded short; cuts both ways on a 1-week hold"
                print(f"  {r['ticker']:6} {v * 100:.1f}%{note}" if v is not None
                      else f"  {r['ticker']:6} n/a")
            except Exception:
                print(f"  {r['ticker']:6} lookup failed")
            _t.sleep(0.3)

    print("\n" + "=" * 72)
    by_flag = {}
    for r in rows:
        for f in r["flags"]:
            by_flag.setdefault(f, []).append(r["ticker"])
    if by_flag:
        print("Flagged -- each of these needs a reason before it goes in the table:")
        meaning = {
            "EXTENDED": f"more than {EXTENDED_PCT:.0f}% above the 20d SMA; the move already happened",
            "BELOW20": "under its 20d SMA; kills a pullback-in-an-uptrend thesis",
            "DISTRIB": "down sessions carrying the volume; supply in control",
            "GAPFADE": "recent gap not holding; drift thesis is broken",
            "VOLEXP": "ATR expanding fast; will move more than the sizer assumes",
        }
        for f, ts in by_flag.items():
            print(f"  {f:<9} {', '.join(ts)}")
            print(f"  {'':9} {meaning[f]}")
    else:
        print("No structural flags.")
    clean = [r["ticker"] for r in rows if not r["flags"]]
    if clean:
        print(f"\nClean structure: {', '.join(clean)}")
    if missing:
        print(f"\nNot in cache (rerun the screener or check the symbol): {', '.join(missing)}")


if __name__ == "__main__":
    main()
