"""
Step 3 -- batch headline pull + red-flag keyword scan for candidates.

Front-loads the raw material for every candidate in one pass so the cost of
checking a name is never a reason to skip one. It is a starting point, not a
verdict, and it has two known weaknesses the process works around:

  1. The feed is yfinance news: thin for small names, sometimes about a
     different company, and it never says whether a catalyst is still live.
  2. The red-flag regexes match keywords, not meaning. "merger" has fired
     on a completed divestiture and "guidance" on a guidance RAISE. Treat a
     hit as "go read it", never as a finding.

What it cannot see at all: company event calendars. Monthly reporters
(Progressive publishes monthly results), investor days, FDA dates and
ex-dividend dates do not appear here. The per-finalist events check in
PROCESS.md Step 3 exists because this tool cannot do it.

Usage:
    python scripts/research_brief.py                    # top 30 of this run's shortlist
    python scripts/research_brief.py --tickers BX,DNOW --days 21
"""

import argparse
import re
import sys
import time

import pandas as pd
import yfinance as yf

from paths import SHORTLIST, run_dir

RED_FLAGS = {
    "dilution": r"\b(offering|secondary|dilut\w*|at-the-market|ATM program|convertible note|shelf registration)\b",
    "legal": r"\b(lawsuit|litigation|sued|investigation|probe|subpoena|SEC charges|class action|DOJ)\b",
    "merger": r"\b(to be acquired|acquisition of|merger|takeover|buyout|going private|tender offer)\b",
    "leadership": r"\b(CEO|CFO|chief executive|chief financial)\b.{0,40}\b(steps? down|resign\w*|depart\w*|ousted|to retire|transition)\b",
    "insider": r"(\binsider (sell\w*|sale|alert|trading)\b|\b(sells?|sold|unload\w*|dumps?)\b[^|]{0,30}\$[\d.]+ ?(million|billion|M\b|B\b))",
    "downgrade": r"\b(downgrade[sd]?|cut to (sell|underweight|neutral)|lowers? (price )?target|slashes)\b",
    "guidance": r"\b(cuts? guidance|lowers? outlook|warns?|profit warning|withdraws? guidance|misses)\b",
}


def ascii_safe(text):
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'),
                 ("—", "-"), ("–", "-"), ("…", "..."), (" ", " ")):
        text = text.replace(a, b)
    return text.encode("ascii", "replace").decode("ascii")


def headlines(ticker, days):
    cutoff = pd.Timestamp.now("UTC").tz_localize(None) - pd.Timedelta(days=days)
    out = []
    try:
        for item in yf.Ticker(ticker).news or []:
            c = item.get("content", item)
            title = ascii_safe((c.get("title") or "").strip())
            if not title:
                continue
            raw = c.get("pubDate") or c.get("providerPublishTime") or ""
            try:
                when = (pd.to_datetime(raw, unit="s") if isinstance(raw, (int, float))
                        else pd.to_datetime(raw).tz_localize(None))
            except Exception:
                when = None
            if when is not None and when < cutoff:
                continue
            out.append((when, title))
    except Exception as e:
        return None, str(e)
    out.sort(key=lambda x: (x[0] is not None, x[0]), reverse=True)
    return out, None


def scan(titles):
    blob = " || ".join(t for _, t in titles)
    return [n for n, p in RED_FLAGS.items() if re.search(p, blob, re.IGNORECASE)]


def main():
    ap = argparse.ArgumentParser(description="Step 3: headlines + keyword prompts")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--tickers")
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--max-headlines", type=int, default=6)
    args = ap.parse_args()

    sl = run_dir(create=False) / SHORTLIST
    meta = pd.read_csv(sl).set_index("Symbol").to_dict("index") if sl.exists() else {}
    if args.tickers:
        names = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        if not sl.exists():
            sys.exit(f"ERROR: {sl} not found -- run scripts/swing_screen.py first.")
        names = pd.read_csv(sl).head(args.top)["Symbol"].tolist()

    print(f"Briefing {len(names)} candidates, headlines from the last {args.days} days.")
    print("Raw material, not a verdict. Keyword hits are prompts to read, not findings.\n")
    flagged, quiet, failed = [], [], []
    for i, t in enumerate(names, 1):
        m = meta.get(t, {})
        bits = []
        if m.get("Sector") == m.get("Sector") and m.get("Sector"):
            bits.append(str(m["Sector"]))
        ne = m.get("NextEarnings")
        if m:
            bits.append(f"earnings {ne}" if ne == ne and ne else "earnings UNKNOWN -- look up by hand")
        xd = m.get("ExDivDate")
        if xd == xd and xd and m.get("ExDivInWindow"):
            bits.append(f"EX-DIV {xd} INSIDE WINDOW")
        print(f"[{i}/{len(names)}] {t}" + (f"   ({' | '.join(bits)})" if bits else ""))
        items, err = headlines(t, args.days)
        if err:
            print(f"    fetch failed: {err}")
            failed.append(t)
        elif not items:
            print(f"    no headlines in {args.days}d -- silence is not clean; search by hand")
            quiet.append(t)
        else:
            hits = scan(items)
            if hits:
                print(f"    keyword hits: {', '.join(hits)}")
                flagged.append((t, hits))
            for when, title in items[:args.max_headlines]:
                print(f"    {when.strftime('%m-%d') if when is not None else '  ?  '}  {title[:105]}")
        print()
        time.sleep(0.3)

    print("=" * 64)
    if flagged:
        print("Keyword hits (read each before deciding anything):")
        for t, hits in flagged:
            print(f"  {t:<6} {', '.join(hits)}")
    if quiet:
        print(f"\nNo recent headlines: {', '.join(quiet)}")
    if failed:
        print(f"\nFetch failed, research by hand: {', '.join(failed)}")
    print("\nNot covered here for ANY name: monthly results, investor days, FDA/PDUFA")
    print("dates, index changes. Step 3 requires one by-hand events check per finalist.")


if __name__ == "__main__":
    main()
