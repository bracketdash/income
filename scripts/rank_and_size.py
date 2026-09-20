"""
Step 4 -- turn researched finalists into a ranked, risk-weighted allocation table.

Research supplies a conviction score per name (runs/<batch>/candidates.json);
this does every piece of arithmetic after that, so sizing involves no
judgment. Writes runs/<batch>/picks.json (for the log) and table.md.

Sizing: weight ~ conviction^1.5 / expected-move, capped per name (15%) and
per sector (35%, enforced). Inverse-volatility because an equal-dollar book
across names with very different volatility is a concentrated bet on the
wild ones wearing a diversified costume.

Cash: the tighter of two bounds wins.
  (a) Volatility target: the book's expected move over the week (ATR
      volatilities x realised correlations) is measured, and capital is
      deployed to land it on the regime's target.
  (b) Regime deploy cap: a hard ceiling on deployment by regime score.
  A volatility target on its own lets a book of clean, low-ATR names deploy
  fully into an event week, because trailing ATR understates the week that
  contains the event. The cap is what makes the regime score actually brake.

What is and is not forecastable: expected MOVE (dispersion) is -- volatility
clusters. Expected RETURN at a one-week horizon is not, to any useful
precision. Conviction is ordinal. Arithmetic adds no accuracy the judgment
did not have.

Usage:
    python scripts/rank_and_size.py --regime 3
    python scripts/rank_and_size.py --regime 3 --input other.json --out other_picks.json
    python scripts/rank_and_size.py --show-rubric

Input JSON: array of {"Ticker","Sector","SetupType","Conviction",
"ReferenceClose","ATR14","Thesis", optional "Flags"}.
"""

import argparse
import json
import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from market_calendar import sessions_in_week, upcoming_week_window
from paths import CACHE_DIR, CANDIDATES, PICKS, TABLE, run_dir

CONVICTION_POWER = 1.5
MAX_WEIGHT = 0.15
SECTOR_MAX = 0.35        # of deployed capital; enforced, not just flagged
MIN_WEIGHT = 0.02
MIN_EXP_MOVE_PCT = 3.0   # sizing floor: stillness alone should not attract capital
MIN_CONVICTION = 3       # 2s have been the worst bucket in every graded batch; excluded unless --allow-2
DEFAULT_WINDOW_DAYS = 5

REGIME_TARGET_VOL = {5: 6.5, 4: 5.5, 3: 4.5, 2: 3.0, 1: 2.0}
REGIME_MAX_DEPLOY = {5: 1.00, 4: 0.90, 3: 0.80, 2: 0.65, 1: 0.40}
MIN_DEPLOY = 0.20
CORR_LOOKBACK_DAYS = 60
FALLBACK_CORR = 0.45

SETUP_TYPES = {"breakout", "pullback", "post-earnings-drift", "rs-continuation", "other"}

REGIME_RUBRIC = """
Regime score (sets the vol target AND the deploy cap -> cash):
  5  Clean uptrend, breadth >60%, VIX low/falling, no market-moving event in window.  cap 100%
  4  Constructive, minor divergence or mild event risk.                                cap  90%
  3  Mixed / choppy / rotational; breadth near 50%.                                    cap  80%
  2  Deteriorating breadth, VIX rising, OR a binary macro event inside the window
     (FOMC, CPI/PCE, jobs) -- the event alone is enough for a 2.                       cap  65%
  1  Risk-off: breadth collapsing, indices below key averages, VIX spiking.            cap  40%
""".strip()

CONVICTION_RUBRIC = """
Conviction (ordinal; a "4" must mean the same thing every week):
  5  Fresh DATED catalyst still ahead, clean structure, strong RS, regime-aligned,
     no flags, no event in window. Rare.
  4  Strong setup plus a confirmed catalyst; only minor concerns.
  3  Good setup OR good catalyst, not both -- or both with a real offsetting risk.
  2  Speculative: genuine thesis but a material overhang. EXCLUDED by default.
  1  Lottery ticket. Never.
Setup types (closed list, so the log stays comparable):
  breakout | pullback | post-earnings-drift | rs-continuation | other
""".strip()


def expected_move_pct(atr14, price, sessions):
    if not atr14 or not price or price <= 0:
        return np.nan
    return (atr14 / price) * math.sqrt(sessions) * 100


def fetch_returns(tickers, as_of=None):
    for path in sorted(CACHE_DIR.glob("prices_*.pkl"), reverse=True):
        try:
            with open(path, "rb") as f:
                frames = pickle.load(f)
            closes = {t: frames[t]["Close"] for t in tickers if t in frames}
            if len(closes) == len(tickers):
                px = pd.DataFrame(closes)
                if as_of is not None:
                    px = px[px.index <= pd.Timestamp(as_of)]
                px = px.tail(CORR_LOOKBACK_DAYS + 1)
                if len(px) >= 20:
                    return px.pct_change().dropna(how="all")
        except Exception:
            continue
    try:
        data = yf.download(list(tickers), period="4mo", interval="1d", group_by="ticker",
                           auto_adjust=True, progress=False, threads=True)
        closes = {}
        for t in tickers:
            try:
                closes[t] = data[t]["Close"] if len(tickers) > 1 else data["Close"]
            except Exception:
                continue
        if len(closes) < 2:
            return None
        px = pd.DataFrame(closes)
        if getattr(px.index, "tz", None) is not None:
            px.index = px.index.tz_localize(None)
        if as_of is not None:
            px = px[px.index <= pd.Timestamp(as_of)]
        return px.tail(CORR_LOOKBACK_DAYS + 1).pct_change().dropna(how="all")
    except Exception:
        return None


def portfolio_vol_pct(weights, exp_moves, tickers, as_of=None):
    w, sig = np.asarray(weights, float), np.asarray(exp_moves, float)
    rets = fetch_returns(list(tickers), as_of=as_of)
    corr = None
    if rets is not None and rets.shape[1] == len(tickers):
        c = rets[list(tickers)].corr().values
        if np.isfinite(c).all():
            corr = c
    used_real = corr is not None
    if corr is None:
        corr = np.full((len(w), len(w)), FALLBACK_CORR)
        np.fill_diagonal(corr, 1.0)
    var = float(w @ (np.outer(sig, sig) * corr) @ w)
    return math.sqrt(max(var, 0.0)), used_real, corr


def solve_weights(raw, sectors=None):
    """Normalise raw scores to weights under a per-name cap and a per-sector
    cap. Capping pushes weight elsewhere, which can breach another cap, so
    iterate to a fixed point."""
    raw = np.asarray(raw, float)
    if raw.sum() <= 0 or not np.isfinite(raw).any():
        return np.full(len(raw), 1.0 / len(raw))
    w = raw / raw.sum()
    sectors = np.asarray(sectors) if sectors is not None else None
    for _ in range(200):
        changed = False
        over = w > MAX_WEIGHT + 1e-12
        if over.any():
            free = ~over
            room = 1.0 - MAX_WEIGHT * over.sum()
            w[over] = MAX_WEIGHT
            if w[free].sum() > 0 and room > 0:
                w[free] = w[free] / w[free].sum() * room
            changed = True
        if sectors is not None:
            for s in set(sectors):
                m = sectors == s
                if w[m].sum() > SECTOR_MAX + 1e-12 and (~m).sum() > 0:
                    excess = w[m].sum() - SECTOR_MAX
                    w[m] *= SECTOR_MAX / w[m].sum()
                    w[~m] += excess * (w[~m] / w[~m].sum())
                    changed = True
        if not changed:
            break
    return w / w.sum()


def build(rows, regime, deploy=None, as_of=None, sessions=DEFAULT_WINDOW_DAYS, allow_2=False):
    df = pd.DataFrame(rows)
    required = {"Ticker", "Conviction", "ReferenceClose", "ATR14", "SetupType", "Sector"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: input rows missing {sorted(missing)}")
    bad = df[~df["SetupType"].isin(SETUP_TYPES)]
    if not bad.empty:
        sys.exit(f"ERROR: SetupType must be one of {sorted(SETUP_TYPES)}; got "
                 f"{bad['SetupType'].tolist()} for {bad['Ticker'].tolist()}")
    bad = df[~df["Conviction"].between(1, 5)]
    if not bad.empty:
        sys.exit(f"ERROR: Conviction must be 1-5; got {bad['Conviction'].tolist()}")
    low = df[df["Conviction"] < MIN_CONVICTION]
    if not low.empty and not allow_2:
        sys.exit(f"ERROR: {low['Ticker'].tolist()} have conviction < {MIN_CONVICTION}. "
                 f"Drop them, or pass --allow-2 with a stated reason.")

    df["ExpMovePct"] = df.apply(lambda r: expected_move_pct(r["ATR14"], r["ReferenceClose"], sessions), axis=1)
    if df["ExpMovePct"].isna().any():
        sys.exit(f"ERROR: bad ATR14/ReferenceClose for {df[df['ExpMovePct'].isna()]['Ticker'].tolist()}")
    for _, r in df[df["ExpMovePct"] < MIN_EXP_MOVE_PCT].iterrows():
        print(f"Warning: {r['Ticker']} expected range only {r['ExpMovePct']:.1f}% -- sized as "
              f"{MIN_EXP_MOVE_PCT:.1f}%. A range this narrow on a name that just jumped usually "
              f"means a pinned cash deal; check.")
    sizing_sigma = df["ExpMovePct"].clip(lower=MIN_EXP_MOVE_PCT)
    df["RawScore"] = (df["Conviction"] ** CONVICTION_POWER) / sizing_sigma
    df["Weight"] = solve_weights(df["RawScore"].values, df["Sector"].values)

    tiny = df["Weight"] < MIN_WEIGHT
    if tiny.any() and (~tiny).sum() >= 5:
        print(f"Note: dropped {df[tiny]['Ticker'].tolist()} -- under {MIN_WEIGHT:.0%}, too small to matter.")
        df = df[~tiny].copy()
        df["Weight"] = solve_weights(df["RawScore"].values, df["Sector"].values)

    book_vol, used_real, corr = portfolio_vol_pct(df["Weight"].values, df["ExpMovePct"].values,
                                                  df["Ticker"].values, as_of=as_of)
    target_vol = REGIME_TARGET_VOL[regime]
    cap = REGIME_MAX_DEPLOY[regime]
    vol_deploy = float(np.clip(target_vol / book_vol if book_vol > 0 else 1.0, MIN_DEPLOY, 1.0))
    if deploy is None:
        deploy = min(vol_deploy, cap)
        binding = "vol target" if vol_deploy < cap else "regime cap"
    else:
        binding = "override"

    df.attrs.update(regime=regime, book_vol=book_vol, target_vol=target_vol, deploy=deploy,
                    cap=cap, vol_deploy=vol_deploy, binding=binding, used_real_corr=used_real,
                    sessions=sessions, realized_vol=book_vol * deploy)
    tickers = list(df["Ticker"])
    df.attrs["top_pairs"] = sorted(
        [(corr[i][j], tickers[i], tickers[j]) for i in range(len(tickers)) for j in range(i + 1, len(tickers))],
        reverse=True)[:5]

    df["Weight"] *= deploy
    df = df.sort_values("Weight", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    df["RiskContribPct"] = df["Weight"] * df["ExpMovePct"]
    df["RiskContribPct"] = df["RiskContribPct"] / df["RiskContribPct"].sum() * 100
    return df


def emit_table(df, window):
    cash_pct = max(0.0, 1.0 - df["Weight"].sum())
    a = df.attrs
    lines = [f"**Week of {window}**", "", "| Position | Allocation | Notes |", "|---|---:|---|"]
    corr_note = "" if a["used_real_corr"] else " (correlation estimated)"
    if a["binding"] == "regime cap":
        why = (f"Regime {a['regime']}/5 caps deployment at {a['cap']:.0%}. The book's measured "
               f"weekly move ({a['book_vol']:.1f}%) would have allowed more, but a trailing-ATR "
               f"estimate only knows what these names have already done, not what the week ahead "
               f"holds, which is what the cap is for")
    elif a["binding"] == "vol target":
        why = (f"Regime {a['regime']}/5 sets a {a['target_vol']:.1f}% target move over the "
               f"{a['sessions']}-session week; fully invested the book would swing ~{a['book_vol']:.1f}%, "
               f"so {df['Weight'].sum():.0%} deployed lands on target")
    else:
        why = f"Deployment overridden to {df['Weight'].sum():.0%}"
    lines.append(f"| **CASH** | **{cash_pct:.1%}** | {why}{corr_note}. |")
    for _, r in df.iterrows():
        note = str(r.get("Thesis", "")).strip().rstrip(".")
        lines.append(f"| {r['Ticker']} | {r['Weight']:.1%} | {note}. Conviction {int(r['Conviction'])}/5, "
                     f"expected move +/-{r['ExpMovePct']:.1f}% -> {r['Weight']:.1%}. |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Step 4: rank and risk-weight researched candidates")
    ap.add_argument("--regime", type=int, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--input", default=None, help=f"default: runs/<batch>/{CANDIDATES}")
    ap.add_argument("--out", default=None, help=f"default: runs/<batch>/{PICKS}")
    ap.add_argument("--deploy", type=float, default=None, help="override; normally omit")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--sessions", type=int, choices=range(1, 6), metavar="N")
    ap.add_argument("--allow-2", action="store_true", help="permit conviction-2 names (state why in Notes)")
    ap.add_argument("--show-rubric", action="store_true")
    args = ap.parse_args()
    if args.show_rubric:
        print(CONVICTION_RUBRIC + "\n\n" + REGIME_RUBRIC)
        return
    if args.regime is None:
        sys.exit("usage: rank_and_size.py --regime N   (see --show-rubric)")

    rd = run_dir()
    src = Path(args.input) if args.input else rd / CANDIDATES
    out = Path(args.out) if args.out else rd / PICKS
    if not src.exists():
        sys.exit(f"ERROR: {src} not found -- write the finalists there first (Step 3).")
    rows = json.load(open(src, encoding="utf-8"))
    if not rows:
        sys.exit("ERROR: input is empty")
    first, last = upcoming_week_window()
    sessions = args.sessions or sessions_in_week(first)
    window = f"{first.strftime('%a %b %#d')} - {last.strftime('%a %b %#d')} ({sessions} sessions)"
    df = build(rows, regime=args.regime, deploy=args.deploy, as_of=args.as_of,
               sessions=sessions, allow_2=args.allow_2)
    table = emit_table(df, window)
    print(table)

    a = df.attrs
    print("\n--- diagnostics ---")
    print(f"Book vol fully invested: {a['book_vol']:.1f}%  |  target: {a['target_vol']:.1f}%  |  "
          f"vol-target deploy: {a['vol_deploy']:.0%}  |  regime cap: {a['cap']:.0%}  |  "
          f"deployed: {a['deploy']:.0%} ({a['binding']})  |  portfolio move: ~{a['realized_vol']:.1f}%")
    print(f"Correlation source: {'realized' if a['used_real_corr'] else 'FALLBACK ' + str(FALLBACK_CORR)}")
    spread = df["RiskContribPct"].max() - df["RiskContribPct"].min()
    print(f"Risk contribution spread: {spread:.0f} points (tight is good)")
    print("Most correlated pairs (60d realized) -- above ~0.80 is one position held twice:")
    for c, x, y in a["top_pairs"]:
        print(f"  {x:<6} {y:<6} {c:+.2f}{'  <-- drop the lower-conviction side' if c >= 0.80 else ''}")
    total = df["Weight"].sum()
    print("Sector exposure (of deployed; hard cap 35%):")
    for s, w in df.groupby("Sector")["Weight"].sum().sort_values(ascending=False).items():
        print(f"  {s:<24} {w / total:.0%}")
    print("Setup mix:", ", ".join(f"{k} {v}" for k, v in df["SetupType"].value_counts().items()))

    keep = [c for c in ["Ticker", "Sector", "SetupType", "Rank", "Thesis", "Conviction",
                        "ReferenceClose", "ATR14", "ExpMovePct", "Flags"] if c in df.columns]
    payload = df[keep].copy()
    payload["ExpMovePct"] = payload["ExpMovePct"].round(2)
    payload["Weight"] = df["Weight"].round(4)
    payload["CashPct"] = round(max(0.0, 1.0 - df["Weight"].sum()), 4)
    payload["RegimeScore"] = a["regime"]
    out.write_text(json.dumps(payload.to_dict(orient="records"), indent=2), encoding="utf-8")
    (out.parent / TABLE).write_text(table + "\n", encoding="utf-8")
    print(f"\nWrote {out} and {out.parent / TABLE}")


if __name__ == "__main__":
    main()
