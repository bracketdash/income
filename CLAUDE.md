# This folder does one thing

It produces **a single allocation table** — one cash row plus 10–20
NYSE/NASDAQ stocks with percentage weights — held for one trading week:
bought at the open of the week's first session, sold at the close of its
last.

## Trigger

When the user says **"go"**, or anything meaning "run the screen" — *"run
the weekly picks"*, *"run the weekend process"*, *"let's do this week's
picks"* — **read `PROCESS.md` and follow it end to end.** It is the
authority on every step; do not improvise around it or ask the user to
re-explain a step it covers.

Start by confirming which week the picks are for:

```bash
python scripts/paths.py
```

It prints the week, its session count, and the run folder `runs/<date>/`
where every file this run produces will go. Run all commands from this
folder.

## Six things that are easy to get wrong

1. **It takes an hour or more.** Step 3 is where the quality is. A short
   run skipped the research gate.
2. **Never ask the user what they traded.** There is no execution data in
   this system. Step 0 is `python scripts/review_picks.py`, nothing more.
3. **No Max Buy, no stops, no order types, no conditions.** The table is
   the entire instruction.
4. **The output is the table**, a sub-100-word paragraph before it, and a
   one-line process note after it. Nothing else. Save it as `output.md`.
5. **Every finalist gets a by-hand events check.** The earnings lookup only
   knows quarterly dates; monthly reporters, conference presentations,
   FDA dates and ex-dividends are invisible to it.
6. **Do not change a constant on one week's evidence.** Five batches, and
   for screener rules a `backtest_screen.py` run, first.

## Layout

| | |
|---|---|
| `PROCESS.md` | Every step, in order |
| `learnings.md` | What the record has taught. Read before Step 3, every cycle |
| `pick_log.csv` | The record, graded open→close |
| `scripts/` | One script per step; `paths.py` defines the layout |
| `runs/<batch>/` | Everything one week's run produces |
| `.cache/` | Symbol directory, price and enrichment caches |
