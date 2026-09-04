# This folder does one thing

It produces **a single allocation table** — one cash row plus 10-20
NYSE/NASDAQ stocks with percentage weights — to be held for one trading
week: bought at the open of the week's first trading day, sold at the close
of its last.

## Trigger

When the user says anything meaning "run the screen" — *"run the weekly
trade picks"*, *"run the weekend process"*, *"let's do this week's picks"* —
**read `SWING_TRADE_PROCESS.md` and follow it end to end.** That file is the
authority on every step; don't improvise around it and don't ask the user to
re-explain a step it already covers.

Start by confirming which week the picks are for:

```bash
python -c "from market_calendar import upcoming_week_window, sessions_in_week; f,l=upcoming_week_window(); print('WINDOW', f.date(), f.strftime('%a'), '->', l.date(), l.strftime('%a'), '|', sessions_in_week(f), 'sessions')"
```

## Five things that are easy to get wrong

1. **Expect an hour or more of real work.** Most of it is research (Step 3),
   and that is where the quality comes from. A fifteen-minute run has
   skipped the research gate — see the end of Step 3 for why that keeps
   happening and what it cost.
2. **Never ask the user what they traded, sold, or paid.** There is no
   execution data in this system by design. Step 0 is `python
   review_picks.py` and needs nothing from them.
3. **No Max Buy, no stop losses, no order types, no "skip it if it gaps."**
   The table is the entire instruction: these names, these weights, that
   week.
4. **The output is the table and nothing else** — a sub-100-word paragraph
   before it, a one-line process note after it. No top-picks section, no
   risk rating, no asking the user to decide anything.
5. **The run window is the non-trading hours** between one week's close and
   the next week's open. Any time in there is equally valid; the scripts
   read the clock themselves.

## Scripts, in the order the process uses them

| | |
|---|---|
| `review_picks.py` | Grade the last closed-out batch (Step 0) |
| `swing_screen.py` | Screen the universe to a 60-name shortlist (Step 1) |
| `research_brief.py` | Batch headlines + red-flag scan (Step 3) |
| `technicals.py` | Price-structure check (Step 3) |
| `rank_and_size.py` | Conviction + volatility into weights and cash (Step 4) |
| `log_picks.py` | Append the finalized batch to the log (Step 5) |
| `market_calendar.py` | NYSE sessions; defines the holding window |

`learnings.md` carries standing lessons earned from past cycles — read it
each time, before Step 3.
