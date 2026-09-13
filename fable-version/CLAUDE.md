# This folder does one thing

It produces **a single allocation table** — one cash row plus 10–20
NYSE/NASDAQ stocks with percentage weights — held for one trading week:
bought at the open of the week's first session, sold at the close of its
last.

Run everything from inside this folder (`fable-version/`). Every script
resolves its paths relative to itself, so the cache, log and outputs live
here and nowhere else.

## Trigger

When the user says anything meaning "run the screen" — *"run the weekly
picks"*, *"run the weekend process"*, *"let's do this week's picks"* —
**read `PROCESS.md` and follow it end to end.** It is the authority on
every step; do not improvise around it or ask the user to re-explain a
step it covers.

Start by confirming the week:

```bash
python -c "from market_calendar import upcoming_week_window as w, sessions_in_week as s; f,l=w(); print('WINDOW', f.date(), f.strftime('%a'), '->', l.date(), l.strftime('%a'), '|', s(f), 'sessions')"
```

## Six things that are easy to get wrong

1. **It takes an hour or more.** Step 3 is where the quality is. A short
   run skipped the research gate.
2. **Never ask the user what they traded.** There is no execution data in
   this system. Step 0 is `python review_picks.py`, nothing more.
3. **No Max Buy, no stops, no order types, no conditions.** The table is
   the entire instruction.
4. **The output is the table**, a sub-100-word paragraph before it, and a
   one-line process note after it. Nothing else.
5. **Every finalist gets a by-hand events check.** The earnings lookup
   only knows quarterly dates; monthly reporters, ex-dividend dates and
   investor days are invisible to it.
6. **Do not change a constant on one week's evidence.** Five batches, and
   for screener rules a `backtest_screen.py` run, first.

## Scripts, in the order the process uses them

| | |
|---|---|
| `review_picks.py` | Grade the last batch; pooled record (Step 0) |
| `swing_screen.py` | Universe → 60-name shortlist + regime (Step 1) |
| `technicals.py` | Price-structure flags (Step 3) |
| `research_brief.py` | Headlines + keyword prompts (Step 3) |
| `rank_and_size.py` | Conviction + volatility → weights and cash (Step 4) |
| `log_picks.py` | Append the batch; archive the funnel (Step 5) |
| `backtest_screen.py` | Test a screener rule before changing it |
| `market_calendar.py` | NYSE sessions; defines the holding window |

`learnings.md` carries what the record has taught so far. Read it before
Step 3, every cycle.
