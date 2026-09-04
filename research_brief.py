"""
Pull a compact research brief for every shortlist candidate at once.

Step 3 of the swing-trade process requires a news and red-flag check on
every name before it can enter the table. Done one web search at a time
that is slow enough to tempt shortcuts, and the shortcuts are invisible in
the output -- a thesis reading "no fresh catalyst" looks identical whether
it was checked or assumed. This front-loads the raw material for all of
them in one pass, so the expensive part is judgment rather than fetching.

What it does NOT do is replace the research. Headlines are a starting
point: they are noisy, sometimes about a different company entirely, and
they never explain whether a catalyst is still live or already priced in.
Anything flagged here still needs a real look before it is acted on.

Usage:
    python research_brief.py                  # top 30 of shortlist.csv
    python research_brief.py --top 40
    python research_brief.py --tickers BX,DNOW,JXN
    python research_brief.py --days 21        # widen the headline window
"""

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

SHORTLIST = Path(r"M:\Code\income\shortlist.csv")

# Phrases worth having surfaced automatically. These are the categories the
# process names as disqualifying or size-reducing, and they are exactly the
# ones easiest to miss when a name looks clean on the chart.
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
    """Flatten smart quotes and dashes; this prints to a cp1252 console."""
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("—", "-"), ("–", "-"),
                 ("…", "..."), (" ", " ")):
        text = text.replace(a, b)
    return text.encode("ascii", "replace").decode("ascii")


def headlines(ticker, days):
    """Recent headlines for one ticker, newest first."""
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
    """Which red-flag categories appear in these headlines."""
    blob = " || ".join(t for _, t in titles)
    return [name for name, pattern in RED_FLAGS.items()
            if re.search(pattern, blob, re.IGNORECASE)]


def main():
    ap = argparse.ArgumentParser(description="Batch research brief for shortlist candidates")
    ap.add_argument("--top", type=int, default=30,
                    help="how many shortlist rows to brief (default 30)")
    ap.add_argument("--tickers", help="comma-separated tickers instead of the shortlist")
    ap.add_argument("--days", type=int, default=14,
                    help="headline lookback window in days (default 14)")
    ap.add_argument("--max-headlines", type=int, default=6,
                    help="headlines to print per name (default 6)")
    args = ap.parse_args()

    if args.tickers:
        names = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        meta = {}
    else:
        if not SHORTLIST.exists():
            sys.exit("ERROR: no shortlist.csv -- run swing_screen.py first.")
        df = pd.read_csv(SHORTLIST).head(args.top)
        names = df["Symbol"].tolist()
        meta = df.set_index("Symbol").to_dict("index")

    print(f"Briefing {len(names)} candidates, headlines from the last {args.days} days.\n"
          f"Headlines are raw material, NOT a verdict -- every flag still needs a look.\n")

    flagged, quiet, failed = [], [], []
    for i, t in enumerate(names, 1):
        m = meta.get(t, {})
        bits = []
        sector = m.get("Sector")
        if sector is not None and sector == sector:  # present and not NaN
            bits.append(str(sector))
        for k, label in (("RS_20d", "RS20"), ("ExpMovePct", "move"), ("VolRatio", "vol")):
            if k in m and m[k] == m[k]:
                bits.append(f"{label} {m[k]:+.1f}" if k == "RS_20d" else f"{label} {m[k]:.2f}")
        if m.get("NextEarnings") == m.get("NextEarnings") and m.get("NextEarnings"):
            bits.append(f"earnings {m['NextEarnings']}")
        elif meta:
            bits.append("earnings UNKNOWN -- look up by hand")

        print(f"[{i}/{len(names)}] {t}" + (f"   ({' | '.join(bits)})" if bits else ""))

        items, err = headlines(t, args.days)
        if err:
            print(f"    fetch failed: {err}")
            failed.append(t)
        elif not items:
            print(f"    no headlines in {args.days}d -- verify by hand before trusting silence")
            quiet.append(t)
        else:
            hits = scan(items)
            if hits:
                print(f"    RED FLAGS: {', '.join(hits)}")
                flagged.append((t, hits))
            for when, title in items[:args.max_headlines]:
                stamp = when.strftime("%m-%d") if when is not None else "  ?  "
                print(f"    {stamp}  {title[:105]}")
        print()
        time.sleep(0.3)

    print("=" * 64)
    if flagged:
        print("Names with red-flag keywords (confirm each before including):")
        for t, hits in flagged:
            print(f"  {t:<6} {', '.join(hits)}")
    else:
        print("No red-flag keywords matched.")
    if quiet:
        print(f"\nNo recent headlines: {', '.join(quiet)}")
        print("  Silence is not a clean bill of health -- it often means the feed")
        print("  is thin for that name, so search these ones directly.")
    if failed:
        print(f"\nFetch failed, must be researched by hand: {', '.join(failed)}")


if __name__ == "__main__":
    main()
