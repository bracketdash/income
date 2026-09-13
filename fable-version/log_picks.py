"""
Append a finalized batch to pick_log.csv (end of Step 5).

The batch is dated by the week it targets, not by when it was run -- a
Saturday run and a Monday-pre-open run for the same week produce the same
BatchDate -- and the window end is stamped from the NYSE calendar so a
holiday week grades on the right day.

The log records selection only: what the table said, and what those names
then did. No fills, no exits, nothing the user reports. It never feeds
back into which names get picked.

Usage:
    python log_picks.py picks.json
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from market_calendar import upcoming_week_window

HERE = Path(__file__).resolve().parent
LOG_PATH = HERE / "pick_log.csv"
COLUMNS = [
    "BatchDate", "Ticker", "Sector", "SetupType", "Rank", "Thesis",
    "Conviction", "Weight", "CashPct", "RegimeScore",
    "ReferenceClose", "ATR14", "ExpMovePct", "Flags",
    "WindowEndDate", "GeneratedAt",
    "Reviewed", "EntryOpen", "ReturnPct", "OutcomeClass", "ReviewDate",
]


def archive_funnel(batch, researched):
    """Keep the shortlist and the researched set alongside the batch, so
    Step 0 can later measure whether research *selection* beat the raw
    screen (see research_funnel in review_picks.py). Without this archive
    the one honest test of the research hour cannot be run afterwards."""
    sl = HERE / "shortlist.csv"
    if sl.exists():
        arch = HERE / ".cache" / "shortlists"
        arch.mkdir(parents=True, exist_ok=True)
        shutil.copy(sl, arch / f"shortlist_{batch.strftime('%Y-%m-%d')}.csv")
    if researched:
        rl = HERE / "research_log.csv"
        rows = pd.DataFrame({"BatchDate": batch.strftime("%Y-%m-%d"), "Ticker": researched})
        if rl.exists():
            rows = pd.concat([pd.read_csv(rl), rows], ignore_index=True)
        rows.to_csv(rl, index=False)
        print(f"Archived shortlist + {len(researched)} researched tickers for the funnel diagnostic.")


def append_picks(picks, researched=None):
    first, last = upcoming_week_window()
    if first is None:
        sys.exit("ERROR: could not determine the upcoming trading week.")
    batch = pd.Timestamp(first)
    archive_funnel(batch, researched)
    gen = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    rows = [{
        "BatchDate": batch.strftime("%Y-%m-%d"), "Ticker": p["Ticker"],
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
    if LOG_PATH.exists():
        old = pd.read_csv(LOG_PATH)
        for c in COLUMNS:
            if c not in old.columns:
                old[c] = np.nan
        if ((old["BatchDate"] == rows[0]["BatchDate"]) & (~old["Reviewed"].isin([True, "True"]))).any():
            sys.exit(f"ERROR: an ungraded batch dated {rows[0]['BatchDate']} is already logged. "
                     f"Remove it by hand if this is a deliberate re-run.")
        new = pd.concat([old[COLUMNS], new], ignore_index=True)
    new.to_csv(LOG_PATH, index=False)
    print(f"Logged {len(rows)} picks for {batch.strftime('%a %Y-%m-%d')} -> "
          f"{pd.Timestamp(last).strftime('%a %Y-%m-%d')} in {LOG_PATH.name}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Append a finalized batch to pick_log.csv")
    ap.add_argument("picks", help="picks.json from rank_and_size.py --out")
    ap.add_argument("--researched", help="file listing every ticker researched this cycle "
                                         "(comma- or newline-separated), for the funnel diagnostic")
    a = ap.parse_args()
    researched = None
    if a.researched:
        txt = Path(a.researched).read_text(encoding="utf-8")
        researched = sorted({t.strip().upper() for t in txt.replace("\n", ",").split(",") if t.strip()})
    append_picks(json.load(open(a.picks, encoding="utf-8")), researched=researched)
