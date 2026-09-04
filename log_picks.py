"""
Append a finalized batch of swing-trade picks to pick_log.csv.

Run this once per screening cycle, right after the ranked list is
finalized (see SWING_TRADE_PROCESS.md Step 5). Works out which week the
picks are for -- the next one that hasn't started trading -- and stamps its
first and last NYSE sessions, so review_picks.py knows both when the
position opens and when it's fair to grade.

The run can happen any time between one week's close and the next week's
open, so the batch is dated by the week it targets rather than by the
moment it was generated. A Saturday run and a Monday-morning run for the
same week produce the same BatchDate.

This log is a factual performance record only -- it never feeds back into
candidate selection (clean slate stays clean). See review_picks.py for how
it gets read back.

Usage:
    python log_picks.py picks.json

picks.json: a JSON array of objects, one per ticker, e.g.
    [{"Ticker": "ABCD", "Sector": "Technology", "SetupType": "breakout",
      "Rank": 1, "Thesis": "...", "ReferenceClose": 123.45}, ...]
BatchDate defaults to the upcoming week's first session; pass
{"BatchDate": "YYYY-MM-DD"} in any row to override.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from market_calendar import upcoming_week_window

LOG_PATH = Path(r"M:\Code\income\pick_log.csv")
COLUMNS = [
    "BatchDate", "Ticker", "Sector", "SetupType", "Rank", "Thesis",
    "Conviction", "Weight", "CashPct", "RegimeScore",
    "ReferenceClose", "WindowEndDate", "GeneratedAt",
    "Reviewed", "EntryOpen", "ReturnPct", "OutcomeClass", "ReviewDate",
]


def append_picks(picks, batch_date=None, window_end=None):
    # The batch is dated by the week it targets, not by when it was run.
    # upcoming_week_window() reads the clock and returns the next week that
    # hasn't opened yet, so Friday evening, Saturday, Sunday and Monday
    # pre-open all land on the same batch.
    first_session, last_session = upcoming_week_window()
    if first_session is None:
        sys.exit("ERROR: could not determine the upcoming trading week.")

    override = next((p["BatchDate"] for p in picks if p.get("BatchDate")), None)
    batch_date = pd.Timestamp(batch_date or override or first_session)
    window_end = pd.Timestamp(window_end) if window_end is not None else last_session
    generated_at = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")

    rows = []
    for p in picks:
        rows.append({
            "BatchDate": batch_date.strftime("%Y-%m-%d"),
            "Ticker": p["Ticker"],
            "Sector": p.get("Sector", ""),
            "SetupType": p.get("SetupType", ""),
            "Rank": p.get("Rank", ""),
            "Thesis": p.get("Thesis", ""),
            "Conviction": p.get("Conviction", np.nan),
            "Weight": p.get("Weight", np.nan),
            "CashPct": p.get("CashPct", np.nan),
            "RegimeScore": p.get("RegimeScore", np.nan),
            "ReferenceClose": p.get("ReferenceClose", np.nan),
            "WindowEndDate": window_end.strftime("%Y-%m-%d"),
            "GeneratedAt": generated_at,
            "Reviewed": False,
            "EntryOpen": np.nan,
            "ReturnPct": np.nan,
            "OutcomeClass": "",
            "ReviewDate": "",
        })
    new_df = pd.DataFrame(rows, columns=COLUMNS)

    if LOG_PATH.exists():
        existing = pd.read_csv(LOG_PATH)
        for col in COLUMNS:
            if col not in existing.columns:
                existing[col] = np.nan
        combined = pd.concat([existing[COLUMNS], new_df], ignore_index=True)
    else:
        combined = new_df

    combined.to_csv(LOG_PATH, index=False)
    print(f"Logged {len(rows)} picks for the week of "
          f"{batch_date.strftime('%a %Y-%m-%d')} to "
          f"{window_end.strftime('%a %Y-%m-%d')} -> {LOG_PATH}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    window_end = None
    if "--window-end" in args:
        i = args.index("--window-end")
        window_end = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print("Usage: python log_picks.py picks.json [--window-end YYYY-MM-DD]")
        print("  --window-end: exit date to grade against. Defaults to the last")
        print("                NYSE session of the upcoming week, holidays included.")
        sys.exit(1)
    with open(args[0], encoding="utf-8") as f:
        loaded = json.load(f)
    append_picks(loaded, window_end=window_end)
