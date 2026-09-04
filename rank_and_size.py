"""
Turn a researched candidate list into a ranked, risk-weighted portfolio.

Step 4 of the swing-trade process (see SWING_TRADE_PROCESS.md). Claude
supplies a conviction score per name from the research pass; this script
does every piece of arithmetic that follows, so position sizing involves
no judgment calls from anyone at this stage.

Why inverse-volatility weighting rather than equal dollars:
    An equal-dollar book across names with very different volatility is
    not diversified -- it is a concentrated bet on the most volatile
    names wearing a diversified costume. A 12-name list holding both a
    ~10% expected-range name and a ~27% one will see its P&L dominated
    almost entirely by the latter. Weighting by conviction/volatility
    equalizes each name's *risk* contribution, then tilts toward the
    names research liked most.

What is and isn't forecastable here (this matters -- don't let the
arithmetic imply more precision than exists):
    - Expected MOVE (dispersion) is genuinely forecastable. Volatility
      clusters and is strongly autocorrelated; the ATR-derived figure
      below is a real estimate.
    - Expected RETURN (direction x magnitude) is NOT forecastable to a
      point estimate at a one-week horizon -- noise exceeds any plausible
      edge by roughly 4-8x. Conviction is an ORDINAL judgment ("I like
      this more than that"), not a return forecast. Running it through
      arithmetic does not make it more accurate than the judgment that
      produced it.

Usage:
    python rank_and_size.py candidates.json
    python rank_and_size.py candidates.json --deploy 0.60
    python rank_and_size.py candidates.json --out picks.json

Input JSON: array of objects, one per researched finalist --
    {"Ticker", "Sector", "SetupType", "Conviction" (1-5),
     "ReferenceClose", "ATR14", "Thesis"}

Output: the ranked table (printed), plus optionally a JSON ready to hand
straight to log_picks.py.
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

# Sizing parameters -- tune here.
CONVICTION_POWER = 1.5   # >1 tilts harder toward high-conviction names
MAX_WEIGHT = 0.15        # no single name may exceed this share of deployed capital
MIN_WEIGHT = 0.02        # below this a position is too small to matter; drop or floor it
DEFAULT_WINDOW_DAYS = 5  # sessions in a full week; short weeks pass their own


# Inverse-vol sizing hands its largest allocations to the quietest names,
# which breaks down at the low end: a name with a 0.8% expected range over
# the week would soak up a full-sized position while contributing no risk --
# and, more to the point, cannot produce a swing-trade gain worth the slot
# in the first place. Clamping sigma here caps how much capital stillness
# alone can attract. The clamp only affects sizing; the true expected move
# is still what gets reported.
MIN_EXP_MOVE_PCT = 3.0

# Cash is set by volatility targeting rather than by a lookup table: the
# book's own expected move over the week is measured, then capital is
# deployed to whatever fraction lands portfolio risk on target. Cash responds
# automatically to what is actually in the list -- a batch of wild
# post-catalyst names holds more cash than a batch of quiet pullbacks,
# without anyone choosing that.
#
# The regime score sets the target. It is the one genuinely subjective
# dial in the system, and it is deliberately the only one.
REGIME_TARGET_VOL = {
    5: 6.5,   # clean uptrend, broad participation, no major events in window
    4: 5.5,   # constructive, minor concerns
    3: 4.5,   # mixed / choppy / rotational
    2: 3.0,   # deteriorating breadth, or a major binary event inside the window
    1: 2.0,   # risk-off, breadth collapsing
}
MIN_DEPLOY, MAX_DEPLOY = 0.20, 1.00
CORR_LOOKBACK_DAYS = 60
FALLBACK_CORR = 0.45  # used only if return history can't be fetched

REGIME_RUBRIC = """
Regime score (sets the portfolio volatility target, which sets cash):
  5  Clean uptrend, broad participation (breadth >60%), VIX low/falling,
     no market-moving events inside the window.
  4  Constructive but not pristine: minor divergence, mild event risk.
  3  Mixed, choppy, or rotational. Indices split, breadth near 50%.
  2  Deteriorating breadth, VIX rising, or a major binary event lands
     inside the window (FOMC, CPI/PCE, mega-cap earnings).
  1  Risk-off. Breadth collapsing, indices below key averages, VIX spiking.
""".strip()

CONVICTION_RUBRIC = """
Conviction rubric (keep this consistent across cycles -- a "4" must mean
the same thing every week or the pick log records noise):
  5  Multiple confirming factors: fresh dated catalyst, clean technical
     setup, strong relative strength, regime-aligned, no red flags, no
     earnings inside the window.
  4  Strong setup plus a confirmed catalyst; only minor concerns.
  3  Good setup OR good catalyst, not both -- or both with a real
     offsetting risk.
  2  Speculative: genuine thesis but a material overhang (dilution,
     stretched extension, event risk inside the window).
  1  Lottery ticket. Rarely worth including.
""".strip()


def expected_move_pct(atr14, price, sessions=DEFAULT_WINDOW_DAYS):
    """Typical move over the holding window, in percent.

    ATR is a daily true-range measure (it includes gaps, which close-to-
    close stdev misses -- worth having for catalyst-driven names). Scaled
    by sqrt(sessions) under the usual random-walk assumption.

    `sessions` is the number of trading days in the week actually being
    held, so a holiday week scales to sqrt(4) rather than sqrt(5). Relative
    weights are unaffected (the factor is common to every name), but the
    cash figure is not: the volatility target is an absolute portfolio
    move, so using 5 in a four-session week overstates the book's risk and
    parks capital that should have been deployed.
    """
    if not atr14 or not price or price <= 0:
        return np.nan
    return (atr14 / price) * math.sqrt(sessions) * 100


def fetch_returns(tickers, as_of=None):
    """Daily returns for the finalists, for the correlation matrix.

    Prefers the price cache swing_screen.py already wrote today; falls back
    to a small direct download. Returns None if neither works, in which
    case the caller assumes a flat correlation.
    """
    cache_dir = Path(r"M:\Code\income\.cache")
    for path in sorted(cache_dir.glob("prices_*.pkl"), reverse=True):
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
        data = yf.download(list(tickers), period="4mo", interval="1d",
                           group_by="ticker", auto_adjust=True, progress=False,
                           threads=True)
        closes = {}
        for t in tickers:
            try:
                closes[t] = data[t]["Close"] if len(tickers) > 1 else data["Close"]
            except Exception:
                continue
        if len(closes) < 2:
            return None
        px = pd.DataFrame(closes)
        if as_of is not None:
            idx = px.index
            if getattr(idx, "tz", None) is not None:
                px.index = idx.tz_localize(None)
            px = px[px.index <= pd.Timestamp(as_of)]
        px = px.tail(CORR_LOOKBACK_DAYS + 1)
        return px.pct_change().dropna(how="all")
    except Exception:
        return None


def portfolio_vol_pct(weights, exp_moves, tickers, as_of=None):
    """Expected move of the book over the horizon, in percent, at given weights.

    Diagonal uses the ATR-derived per-name volatility (robust, gap-aware);
    off-diagonal uses realized correlation over the lookback. Assuming
    independence here would badly understate risk -- a long-only momentum
    book is full of names riding the same themes, and they fall together.
    """
    w = np.asarray(weights, dtype=float)
    sig = np.asarray(exp_moves, dtype=float)  # already horizon-scaled, in percent

    rets = fetch_returns(list(tickers), as_of=as_of)
    corr = None
    if rets is not None and rets.shape[1] == len(tickers):
        try:
            c = rets[list(tickers)].corr().values
            if np.isfinite(c).all():
                corr = c
        except Exception:
            corr = None
    if corr is None:
        corr = np.full((len(w), len(w)), FALLBACK_CORR)
        np.fill_diagonal(corr, 1.0)

    cov = np.outer(sig, sig) * corr
    var = float(w @ cov @ w)
    return math.sqrt(max(var, 0.0)), corr is not None, corr


def solve_weights(raw):
    """Normalize raw scores to weights, respecting MAX_WEIGHT.

    Capping one name pushes weight onto the others, which can push a
    second name over the cap, so this iterates to a fixed point rather
    than clipping once.
    """
    raw = np.asarray(raw, dtype=float)
    if raw.sum() <= 0 or not np.isfinite(raw).any():
        return np.full(len(raw), 1.0 / len(raw))

    weights = raw / raw.sum()
    for _ in range(100):
        over = weights > MAX_WEIGHT + 1e-12
        if not over.any():
            break
        excess_room = 1.0 - MAX_WEIGHT * over.sum()
        free = ~over
        free_sum = weights[free].sum()
        weights[over] = MAX_WEIGHT
        if free_sum > 0 and excess_room > 0:
            weights[free] = weights[free] / free_sum * excess_room
        else:
            break
    return weights / weights.sum()


def build(rows, regime, deploy=None, as_of=None, sessions=DEFAULT_WINDOW_DAYS):
    df = pd.DataFrame(rows)

    required = {"Ticker", "Conviction", "ReferenceClose", "ATR14"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"ERROR: input rows missing required field(s): {sorted(missing)}")

    bad = df[~df["Conviction"].between(1, 5)]
    if not bad.empty:
        sys.exit(f"ERROR: Conviction must be 1-5; got {bad['Conviction'].tolist()} "
                 f"for {bad['Ticker'].tolist()}")

    df["ExpMovePct"] = df.apply(
        lambda r: expected_move_pct(r["ATR14"], r["ReferenceClose"], sessions), axis=1)
    df.attrs["sessions"] = sessions

    if df["ExpMovePct"].isna().any():
        sys.exit(f"ERROR: could not compute expected move for "
                 f"{df[df['ExpMovePct'].isna()]['Ticker'].tolist()} -- check ATR14/ReferenceClose")

    # Conviction per unit of volatility. This is the ranking axis: it asks
    # "how much do I like this per unit of risk it brings," which is the
    # question a fixed capital budget actually poses.
    #
    # Note this divides by sigma, not sigma^2. Textbook mean-variance says
    # weight ~ edge/variance, but that assumes the edge estimate is
    # trustworthy enough to justify how violently sigma^2 punishes volatile
    # names (a 27% expected-move name would get ~1/27th the weight of a 5%
    # one, i.e. effectively zero). Conviction here is an ordinal judgment,
    # not a calibrated edge, so the gentler sigma keeps the book from
    # collapsing into whichever names happen to be quietest. Sits between
    # equal-weight and full mean-variance, and is far more robust to the
    # estimation error we certainly have.
    sizing_sigma = df["ExpMovePct"].clip(lower=MIN_EXP_MOVE_PCT)
    too_quiet = df[df["ExpMovePct"] < MIN_EXP_MOVE_PCT]
    if not too_quiet.empty:
        for _, r in too_quiet.iterrows():
            print(f"Warning: {r['Ticker']} has an expected range of only "
                  f"{r['ExpMovePct']:.1f}% -- it likely cannot move enough to be "
                  f"worth a slot. Sizing treats it as {MIN_EXP_MOVE_PCT:.1f}%; "
                  f"consider cutting it.")
    df["RawScore"] = (df["Conviction"] ** CONVICTION_POWER) / sizing_sigma
    df["Weight"] = solve_weights(df["RawScore"].values)

    # Drop dust positions, then re-solve so the book still sums to 1.
    tiny = df["Weight"] < MIN_WEIGHT
    if tiny.any() and (~tiny).sum() >= 5:
        dropped = df[tiny]["Ticker"].tolist()
        print(f"Note: dropped {dropped} -- weight fell below "
              f"{MIN_WEIGHT:.0%}, too small to be worth a slot.")
        df = df[~tiny].copy()
        df["Weight"] = solve_weights(df["RawScore"].values)

    # Volatility targeting: measure the book's expected move over the week at full
    # investment, then deploy the fraction that puts portfolio risk on the
    # regime's target. Cash falls out of this rather than being chosen.
    book_vol, used_real_corr, corr = portfolio_vol_pct(
        df["Weight"].values, df["ExpMovePct"].values, df["Ticker"].values,
        as_of=as_of)
    target_vol = REGIME_TARGET_VOL[regime]
    if deploy is None:
        deploy = target_vol / book_vol if book_vol > 0 else MAX_DEPLOY
        deploy = float(np.clip(deploy, MIN_DEPLOY, MAX_DEPLOY))

    df.attrs["regime"] = regime
    df.attrs["book_vol"] = book_vol
    df.attrs["target_vol"] = target_vol
    df.attrs["deploy"] = deploy
    df.attrs["used_real_corr"] = used_real_corr
    # Sector labels miss themes that cut across them -- an AI trade touching
    # Technology, Industrials and Utilities reads as diversified and is not.
    # Realized correlation does not care what sector anyone was assigned to,
    # so the most-correlated pairs are where hidden doubling-up shows up.
    tickers = list(df["Ticker"])
    pairs = [(corr[i][j], tickers[i], tickers[j])
             for i in range(len(tickers)) for j in range(i + 1, len(tickers))]
    df.attrs["top_pairs"] = sorted(pairs, reverse=True)[:5]
    df.attrs["realized_vol"] = book_vol * deploy

    df["Weight"] *= deploy
    df = df.sort_values("Weight", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))

    # Risk contribution = weight x expected move. In a well-formed book
    # these should cluster; a big outlier means one name is quietly
    # driving the portfolio.
    df["RiskContribPct"] = df["Weight"] * df["ExpMovePct"]
    df["RiskContribPct"] = df["RiskContribPct"] / df["RiskContribPct"].sum() * 100
    return df


def emit_table(df, window):
    """The deliverable: one row of cash, then one row per position."""
    # Clamp: a fully-deployed book can land a hair over 1.0 through float
    # error, which would render as "-0.0%" in the table.
    cash_pct = max(0.0, 1.0 - df["Weight"].sum())
    lines = [f"**Week of {window}**", "",
             "| Position | Allocation | Notes |",
             "|---|---:|---|"]

    corr_note = "" if df.attrs["used_real_corr"] else " (correlation estimated -- return history unavailable)"
    cash_note = (
        f"Regime {df.attrs['regime']}/5 sets a {df.attrs['target_vol']:.1f}% "
        f"target move over the {df.attrs['sessions']}-session week. Fully "
        f"invested this book would swing "
        f"~{df.attrs['book_vol']:.1f}%, so {df['Weight'].sum():.0%} deployed "
        f"lands it near target{corr_note}."
    )
    lines.append(f"| **CASH** | **{cash_pct:.1%}** | {cash_note} |")

    for _, r in df.iterrows():
        note = str(r.get("Thesis", "")).strip().rstrip(".")
        note = (f"{note}. Conviction {int(r['Conviction'])}/5, expected move "
                f"+/-{r['ExpMovePct']:.1f}% -> {r['Weight']:.1%}.")
        lines.append(f"| {r['Ticker']} | {r['Weight']:.1%} | {note} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Rank and risk-weight researched candidates")
    parser.add_argument("input", help="JSON array of researched finalists")
    parser.add_argument("--regime", type=int, required=True, choices=[1, 2, 3, 4, 5],
                        help="regime score 1-5; sets the portfolio vol target, "
                             "which sets cash. See --show-rubric.")
    parser.add_argument("--deploy", type=float, default=None,
                        help="override the computed deploy fraction. Normally omit -- "
                             "cash should follow from volatility targeting.")
    parser.add_argument("--out", help="write a log_picks.py-ready JSON here")
    parser.add_argument("--as-of", default=None,
                        help="only use return history up to this date (YYYY-MM-DD) for "
                             "the correlation matrix. For reconstructing a past batch "
                             "without letting later data leak in. Normally omit.")
    parser.add_argument("--sessions", type=int, choices=range(1, 6), metavar="N",
                        help="trading sessions in the holding week. Defaults to the "
                             "actual count for the current week, so a holiday week "
                             "scales volatility to 4 sessions rather than 5. "
                             "Normally omit.")
    parser.add_argument("--show-rubric", action="store_true")
    args = parser.parse_args()

    if args.show_rubric:
        print(CONVICTION_RUBRIC + "\n\n" + REGIME_RUBRIC)
        return

    if args.deploy is not None and not 0 < args.deploy <= 1.0:
        sys.exit("ERROR: --deploy must be between 0 and 1.0")

    with open(args.input, encoding="utf-8") as f:
        rows = json.load(f)
    if not rows:
        sys.exit("ERROR: input is empty")

    first, last = upcoming_week_window()
    sessions = args.sessions or sessions_in_week(first)
    # ASCII only: this prints to a cp1252 console on Windows.
    window = f"{first.strftime('%a %b %#d')} - {last.strftime('%a %b %#d')}"
    window += f" ({sessions} sessions)"
    df = build(rows, regime=args.regime, deploy=args.deploy, as_of=args.as_of,
               sessions=sessions)

    print(emit_table(df, window))

    # Diagnostics below the table -- for Claude to check, not for the table.
    print(f"\n--- diagnostics ---")
    print(f"Book vol fully invested: {df.attrs['book_vol']:.1f}%  |  "
          f"target: {df.attrs['target_vol']:.1f}%  |  "
          f"deployed: {df.attrs['deploy']:.0%}  |  "
          f"resulting portfolio move: ~{df.attrs['realized_vol']:.1f}%")
    print(f"Correlation source: {'realized' if df.attrs['used_real_corr'] else 'FALLBACK ' + str(FALLBACK_CORR)}")
    spread = df["RiskContribPct"].max() - df["RiskContribPct"].min()
    print(f"Risk contribution spread: {spread:.0f} points "
          f"(tight is good -- large means one name dominates)")
    if df.attrs.get("top_pairs"):
        print("Most correlated pairs (60d realized) -- two names above ~0.80 are "
              "close to one position:")
        for c, a, b in df.attrs["top_pairs"]:
            mark = "  <-- consider dropping one" if c >= 0.80 else ""
            print(f"  {a:<6} {b:<6} {c:+.2f}{mark}")
    if "Sector" in df.columns:
        total = df["Weight"].sum()
        by_sector = df.groupby("Sector")["Weight"].sum().sort_values(ascending=False)
        print("Sector exposure (of deployed):")
        for sector, w in by_sector.items():
            flag = "  <-- over 35%, check concentration" if w / total > 0.35 else ""
            print(f"  {sector:<24} {w / total:.0%}{flag}")

    if args.out:
        keep = ["Ticker", "Sector", "SetupType", "Rank", "Thesis", "Conviction",
                "ReferenceClose"]
        keep = [c for c in keep if c in df.columns]
        payload = df[keep].copy()
        payload["Weight"] = df["Weight"].round(4)
        payload["CashPct"] = round(max(0.0, 1.0 - df["Weight"].sum()), 4)
        payload["RegimeScore"] = df.attrs["regime"]
        Path(args.out).write_text(
            json.dumps(payload.to_dict(orient="records"), indent=2), encoding="utf-8")
        print(f"\nWrote log_picks.py-ready JSON to {args.out}")


if __name__ == "__main__":
    main()
