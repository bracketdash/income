"""
Backtest the screener's signals and score weights on the price cache.

The pick log grades ~12 names a week, so it takes months to learn anything
about a *screening rule*. The price cache holds a year of daily bars for the
whole universe -- ~40 weekly rebalances x ~1,500 liquid names -- which is the
right place to ask "does this flag predict next week?" before changing a
weight. PROCESS.md forbids changing a score weight without running this.

For every week in the cache it recomputes the screener's metrics as of that
week's last session (same definitions as swing_screen.py, vectorised), then
measures the NEXT week's open->close return -- the same definition
review_picks.py grades the real batches on. Reports each signal's excess
return over the liquid non-downtrend universe, with a t-stat and a
first-half / second-half split so a signal that only worked once shows up.

Known limits, so the numbers are read with the right scepticism:
  - Survivorship: the universe is the CURRENT symbol directory. Names that
    delisted during the year are absent. This flatters every bucket a
    little and probably the momentum buckets most.
  - One year. A regime-specific result can look structural.
  - No transaction-cost or slippage model. Open->close is the grading
    convention, not a fill.

Usage:
    python scripts/backtest_screen.py
    python scripts/backtest_screen.py --weights 0.40,0.25,0.15,0.20   # test other weights
"""

import argparse
import glob
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import swing_screen as S
from paths import CACHE_DIR

warnings.filterwarnings("ignore")


def load_panels():
    paths = sorted(glob.glob(str(CACHE_DIR / "prices_*.pkl")), reverse=True)
    if not paths:
        raise SystemExit("No price cache -- run scripts/swing_screen.py first.")
    frames = pickle.load(open(paths[0], "rb"))
    skip = set(S.REGIME_TICKERS)

    def panel(f):
        return pd.DataFrame({t: df[f] for t, df in frames.items() if t not in skip}).sort_index()
    return frames, panel("Close"), panel("Open"), panel("High"), panel("Volume"), Path(paths[0]).name


def tstat(x):
    x = x.dropna()
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 and x.std() > 0 else np.nan


def main():
    ap = argparse.ArgumentParser(description="Backtest screener signals on the price cache")
    ap.add_argument("--top", type=int, default=S.TOP_N_DEFAULT)
    ap.add_argument("--weights", default=None,
                    help="W_BREAKOUT,W_RS,W_GAP,W_PULLBACK to test instead of the live ones")
    args = ap.parse_args()
    wb, wr, wg, wp = (S.W_BREAKOUT, S.W_RS, S.W_GAP_EVENT, S.W_PULLBACK)
    if args.weights:
        wb, wr, wg, wp = (float(x) for x in args.weights.split(","))

    frames, C, O, H, V, cache_name = load_panels()
    spy = frames["SPY"]["Close"].reindex(C.index)
    spy_o = frames["SPY"]["Open"].reindex(C.index)
    print(f"Cache {cache_name}: {C.shape[1]} names, {C.index[0].date()} -> {C.index[-1].date()}")

    sma20, sma50, sma200 = C.rolling(20).mean(), C.rolling(50).mean(), C.rolling(200).mean()
    dv = C * V
    dv20, dvdays = dv.rolling(20).mean(), (dv >= S.MIN_DOLLAR_VOL).rolling(20).sum()
    vr = V / V.rolling(20).mean()
    rs20 = (C / C.shift(20) - 1).sub(spy / spy.shift(20) - 1, axis=0)
    ext20 = (C / sma20 - 1) * 100
    breakout = (C >= S.BREAKOUT_HIGH_FRAC * H.rolling(20).max()) & (vr >= S.BREAKOUT_VOL_RATIO)
    up = ((C > sma50) & (sma50 > sma200)).where(sma200.notna(), (C > sma20) & (sma20 > sma50))
    dn = ((C < sma50) & (sma50 < sma200)).where(sma200.notna(), (C < sma20) & (sma20 < sma50))
    pullback = (up & (sma20 > sma20.shift(5)) & (C >= (1 - S.PULLBACK_BAND) * sma20)
                & (C <= (1 + S.PULLBACK_BAND) * sma20) & (vr <= S.PULLBACK_VOL_RATIO))
    ret1 = C.pct_change().abs()
    gap = ((ret1 >= S.GAP_RET) & (V / V.rolling(20).mean() >= S.GAP_VOL_RATIO)).rolling(10).max().astype(bool)
    liquid = (C >= S.MIN_PRICE) & (dv20 >= S.MIN_DOLLAR_VOL) & (dvdays >= S.MIN_DOLLAR_VOL_DAYS)

    weeks = pd.Series(C.index, index=C.index).groupby(C.index.to_period("W")).agg(["first", "last"])
    rows = []
    for i in range(len(weeks) - 1):
        t = weeks.iloc[i]["last"]
        nf, nl = weeks.iloc[i + 1]["first"], weeks.iloc[i + 1]["last"]
        if t < C.index[55]:
            continue
        fwd = (C.loc[nl] / O.loc[nf] - 1) * 100
        base = liquid.loc[t] & fwd.notna() & rs20.loc[t].notna() & ~dn.loc[t]
        d = pd.DataFrame({"fwd": fwd[base], "rs": rs20.loc[t][base], "ext": ext20.loc[t][base],
                          "bo": breakout.loc[t][base], "pb": pullback.loc[t][base],
                          "gap": gap.loc[t][base], "vr": vr.loc[t][base]})
        if len(d) < 300:
            continue
        d["rsp"] = d.rs.rank(pct=True) * 100
        score = wb * 100 * d.bo + wr * d.rsp + wg * 100 * d.gap + wp * 100 * d.pb
        top = d.loc[score.sort_values(ascending=False).index[:args.top]]
        rows.append(dict(week=nf.date(), n=len(d), univ=d.fwd.mean(),
                         spy=(spy.loc[nl] / spy_o.loc[nf] - 1) * 100,
                         top=top.fwd.mean(), top_bo=int(top.bo.sum()),
                         bo=d[d.bo].fwd.mean() if d.bo.any() else np.nan, n_bo=int(d.bo.sum()),
                         pb=d[d.pb].fwd.mean() if d.pb.any() else np.nan,
                         gap=d[d.gap].fwd.mean() if d.gap.any() else np.nan,
                         rs_hi=d[d.rsp >= 80].fwd.mean(), rs_lo=d[d.rsp <= 20].fwd.mean(),
                         ext_hi=d[d.ext > 10].fwd.mean(), ext_mid=d[(d.ext > 0) & (d.ext <= 10)].fwd.mean(),
                         vr_med=d.vr.median()))
    R = pd.DataFrame(rows)
    n, h = len(R), len(R) // 2
    print(f"\n{n} weekly rebalances, next-week open->close. Weights B/RS/Gap/PB = {wb}/{wr}/{wg}/{wp}, top {args.top}.\n")
    print(f"Absolute avg weekly return:  SPY {R.spy.mean():+.2f}%   universe {R.univ.mean():+.2f}%   "
          f"top-{args.top} {R.top.mean():+.2f}%   (top list averages {R.top_bo.mean():.0f} Breakout names)\n")
    print(f"{'Excess over universe':26s} {'mean':>7s} {'t':>6s} {'1st half':>9s} {'2nd half':>9s} {'win%':>5s}")
    for lab, col in [(f"top-{args.top} by score", "top"), ("Breakout flag", "bo"), ("Pullback flag", "pb"),
                     ("GapEvent flag", "gap"), ("RS20 top quintile", "rs_hi"), ("RS20 bottom quintile", "rs_lo"),
                     ("EXTENDED (>10% over 20d)", "ext_hi"), ("0-10% over 20d", "ext_mid")]:
        x = R[col] - R.univ
        print(f"  {lab:24s} {x.mean():+7.2f} {tstat(x):+6.2f} {x.iloc[:h].mean():+9.2f} {x.iloc[h:].mean():+9.2f} "
              f"{100 * (x > 0).mean():5.0f}")
    print(f"\nBreakout flag fires on ~{R.n_bo.mean():.0f} names/week. "
          f"Universe VolRatio median averages {R.vr_med.mean():.2f}.")
    print("\nA |t| under ~2 on 40 weeks is indistinguishable from noise. A signal whose two")
    print("halves disagree in sign was probably one regime, not a rule.")
    out = CACHE_DIR / "backtest_last.csv"
    R.to_csv(out, index=False)
    print(f"Per-week detail written to {out}")


if __name__ == "__main__":
    main()
