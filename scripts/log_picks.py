"""
Step 5 -- append the finalized batch to pick_log.csv.

Reads runs/<batch>/picks.json (written by rank_and_size.py) and appends one
row per position. The batch is dated by the week it targets, not by when it
was run, and the window end is stamped from the NYSE calendar so a holiday
week grades on the right day.

The log records selection only: what the table said, and what those names
then did. No fills, no exits, nothing the user reports. It never feeds back
into which names get picked. The run folder itself (shortlist.csv,
researched.txt) is the archive review_picks.py reads to grade the research.

Usage:
    python scripts/log_picks.py
"""
import json
import sys

import numpy as np
import pandas as pd

from market_calendar import upcoming_week_window
from paths import PICK_LOG, PICKS, RESEARCHED, run_dir

COLUMNS = [
    "BatchDate", "Ticker", "Sector", "SetupType", "Rank", "Thesis",
    "Conviction", "Weight", "CashPct", "RegimeScore",
    "ReferenceClose", "ATR14", "ExpMovePct", "Flags",
    "WindowEndDate", "GeneratedAt",
    "Reviewed", "EntryOpen", "ReturnPct", "OutcomeClass", "ReviewDate",
]


def append_picks():
    first, last = upcoming_week_window()
    if first is None:
        sys.exit("ERROR: could not determine the upcoming trading week.")
    rd = run_dir()
    src = rd / PICKS
    if not src.exists():
        sys.exit(f"ERROR: {src} not found -- run scripts/rank_and_size.py first (Step 4).")
    if not (rd / RESEARCHED).exists():
        print(f"Warning: {rd / RESEARCHED} is missing, so this batch's research funnel "
              f"cannot be graded. Step 3 should have written it.")
    picks = json.load(open(src, encoding="utf-8"))

    batch = pd.Timestamp(first).strftime("%Y-%m-%d")
    gen = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    rows = [{
        "BatchDate": batch, "Ticker": p["Ticker"],
        "Sector": p.get("Sector", ""), "SetupType": p.get("SetupType", ""),
        "Rank": p.get("Rank", ""), "Thesis": p.get("Thesis", ""),
        "Conviction": p.get("Conviction", np.nan), "Weight": p.get("Weight", np.nan),
        "CashPct": p.get("CashPct", np.nan), "RegimeScore": p.get("RegimeScore", np.nan),
        "ReferenceClose": p.get("ReferenceClose", np.nan), "ATR14": p.get("ATR14", np.nan),
        "ExpMovePct": p.get("ExpMovePct", np.nan), "Flags": p.get("Flags", ""),
        "WindowEndDate": pd.Timestamp(last).strftime("%Y-%m-%d"), "GeneratedAt": gen,
        "Reviewed": False, "EntryOpen": np.nan, "ReturnPct": np.nan,
        "OutcomeClass": "", "ReviewDate": "",
    } for p in picks]
    new = pd.DataFrame(rows, columns=COLUMNS)
    if PICK_LOG.exists():
        old = pd.read_csv(PICK_LOG)
        for c in COLUMNS:
            if c not in old.columns:
                old[c] = np.nan
        if (old["BatchDate"] == batch).any():
            sys.exit(f"ERROR: batch {batch} is already logged. A deliberate re-run must remove "
                     f"those rows from {PICK_LOG.name} by hand first.")
        new = pd.concat([old[COLUMNS], new], ignore_index=True)
    new.to_csv(PICK_LOG, index=False)
    print(f"Logged {len(rows)} picks for {pd.Timestamp(first).strftime('%a %Y-%m-%d')} -> "
          f"{pd.Timestamp(last).strftime('%a %Y-%m-%d')} in {PICK_LOG.name}")


if __name__ == "__main__":
    import argparse
    argparse.ArgumentParser(
        description="Step 5: append runs/<batch>/picks.json to pick_log.csv. Takes no arguments."
    ).parse_args()
    append_picks()
