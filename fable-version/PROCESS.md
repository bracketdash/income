# Weekly Swing Screen — Process

This folder produces **one allocation table**: a cash row plus 10–20
NYSE/NASDAQ common stocks with percentage weights, held for **one trading
week** — bought at the open of the week's first session, sold at the close
of its last. Nothing else. The user reads the table and acts on it; they
make no judgment calls of their own, so nothing in the output may ask them
to decide anything.

**Trigger.** Any request meaning "run the screen" starts this process end to
end. It is run by hand, any time between one week's closing bell and the
next week's opening bell. Nothing has traded in that window, so every
moment inside it is equally valid; the scripts read the clock.

**Budget.** Expect an hour or more. Most of it is Step 3. A run that
finishes in fifteen minutes did not research its candidates.

## The run

```bash
python -c "from market_calendar import upcoming_week_window as w, sessions_in_week as s; f,l=w(); print('WINDOW', f.date(), f.strftime('%a'), '->', l.date(), l.strftime('%a'), '|', s(f), 'sessions')"
python review_picks.py                                   # 0  grade last batch + pooled record
python swing_screen.py                                   # 1  ~10 min; background it
#                                                          2  regime call (regime.txt + web search)
python technicals.py --tickers <30-36 names>             # 3  price structure
python research_brief.py --tickers <same names> --days 21  # 3  headlines + keyword hits
#                                                          3  per-name research -> candidates.json + researched.txt
python rank_and_size.py candidates.json --regime N --out picks.json   # 4
#                                                          5  paste the table through
python log_picks.py picks.json --researched researched.txt            # 5
```

If the printed first session is today or earlier, the week has already
begun: say so at the top and recommend skipping the week. Never produce a
normal-looking table for a week already underway.

## Ground rules

- **Long-only common stock.** No ETFs, ETNs, leveraged/inverse products,
  preferreds, warrants, units, SPACs, OTC, sub-3-month listings. The
  screener enforces the mechanical ones; pending-M&A targets have to be
  caught by reading.
- **Clean slate for selection.** Prior batches, the user's holdings, and
  the pick log never decide which tickers appear. The log is read for
  *process* learning only.
- **No execution data exists in this system, by design.** Never ask the
  user what they traded, sold, or paid. Step 0 needs only the command.
- **No Max Buy, stops, limits, order types, or conditions.** The table is
  the whole instruction. That is also exactly what Step 0 grades.
- **What is forecastable at a one-week horizon.** Expected *move*
  (dispersion) is — volatility clusters, and the ATR estimate is real.
  Expected *return* is not, to any useful precision; noise exceeds any
  plausible edge many times over. Conviction scores are ordinal judgments.
  Never present an expected move as a predicted gain.
- **Never read a still-forming bar as a close.** The scripts refuse; do
  not do it by hand either. The last completed session is the newest
  information that exists, and it is all that is needed.

## Step 0 — Grade the last batch, read the pooled record

`review_picks.py` grades every logged batch whose window has closed
(open of first session → close of last; holidays are part of the window
definition), then prints the batch against SPY over the same window, and
the **pooled** record across every graded batch. Read the pooled section;
a single batch is ~12 names and proves nothing.

The system-level checks, in order of importance:

1. **Conviction calibration.** Do 4s out-return 3s? If not over 40+ picks,
   the rubric is noise and the sizing built on it is theatre.
2. **Sizing vs equal-weight.** Inverse-vol sizing wins mechanically in
   down weeks; only count it validated once it has also held up in up
   weeks.
3. **Setup type and flagged-vs-clean.** Which labels are earning money.
4. **Research funnel.** Did the picks beat the never-researched remainder
   of the shortlist? If not, the funnel started in the wrong place.
5. **Dispersion calibration.** Median |realised| / expected move. Above
   1.0 means ATR is understating the weeks being traded.

Write a short dated note in `learnings.md`: what the data showed, the
sample size, and what (if anything) changes in *judgment* this cycle.
Then disclose it in one line in the final output.

**Changing a constant** — a score weight, `CONVICTION_POWER`, `MAX_WEIGHT`,
the regime tables — requires (a) a pattern that has held across **5+
batches / 40+ picks**, and (b) for anything in the screener, a run of
`backtest_screen.py` showing the change helps across both halves of the
year. Then say so in that cycle's output and in `learnings.md` with the
before/after values. One noisy week changes judgment, not code.

## Step 1 — Screen

`swing_screen.py` filters ~5,000 names to price ≥ $5, 20-day dollar
volume ≥ $25M on at least 15 of the last 20 sessions, drops downtrends,
scores the rest, and writes `shortlist.csv` (top 60) and `regime.txt`.
Always rerun it fresh.

Three things to check before reading a single row:

- **`Generated:` in `regime.txt` is from this run.** If not, the screener
  failed and the files are stale.
- **VolRatio median across the shortlist.** Healthy is ~0.8–1.0; a holiday
  lull sits at 0.6–0.8; **0.2–0.3 is a broken session**, and every
  volume-based flag is an artefact until it is rerun.
- **The universe diff**, if the symbol cache refreshed this week. Removed
  symbols are delistings and completed mergers. In Step 3 check them
  against the finalists' *acquirers* — the buyer never leaves the universe.

What the score is: the **Breakout flag** carries most of it. Over 40
backtested weeks it was the only signal in the system with a real edge
(+1.03 pts/week over the universe, t = 2.7, positive in both halves).
20-day relative strength is a tiebreaker only — flat across quintiles.
The **Pullback flag has zero score weight**: it was negative in both halves
(−0.53 pts/week) and the old score's 20% on it packed the shortlist with
names whose only merit was drifting quietly near an average. The flag is
still printed because it is a useful label — see Step 3.

## Step 2 — Regime

Read `regime.txt`, then web-search the next ~10 trading days for: FOMC
decision, CPI / PCE, the jobs report, and mega-cap earnings clusters.
Also confirm the *direction* of rate expectations — the tape reads
differently when a hike is priced than when a cut is.

Write a 2–3 line regime call: trending / choppy / risk-off, and what that
favours — a choppy or hawkish tape favours relative-strength leaders and
volume-confirmed setups over speculative extension; a clean uptrend can
carry more breakouts and post-earnings drift.

Score it 1–5 with the rubric in `rank_and_size.py --show-rubric`. **A
binary macro event inside the window is by itself a 2**, and a 2 caps
deployment at 65% regardless of what the book's measured volatility says.

## Step 3 — Research

**Research ~30–36 names to hold 10–20.** Pick them from across the whole
shortlist and across sectors, not the top 30 by score. If the researched
set and the final list are nearly identical, research only wrote
justifications for the screener's ranking.

Run `technicals.py` and `research_brief.py` on the research set first.
Then, **for every name that might make the table**, all of the following:

1. **Verify price, volume, and structure** against the last completed
   session. Every `technicals.py` flag is a question the thesis has to
   answer honestly; a flag going unmentioned in a thesis it contradicts is
   the single most expensive failure this process has had (AXON, "pulling
   back on light volume" while below its 20d SMA: −13%).
2. **Setup type**, from the closed list: `breakout`, `pullback`,
   `post-earnings-drift`, `rs-continuation`, `other`. The label has to be
   earned: a `pullback` needs price above a rising 20d SMA *and* up/down
   volume above 1.0 — "drifting down quietly" is not a pullback, and the
   pooled record says that mislabel is where the losses have come from.
   `post-earnings-drift` needs a positive print, a holding gap, and no
   one-time flatterer (a tariff refund is not a beat).
3. **Catalyst.** Why is it moving, is the story still live or already
   played out, is there a dated event ahead. A GapEvent-flagged name
   needs this answered explicitly.
4. **Red flags**: dilution, litigation, leadership exit, insider selling,
   pending-merger pinning. The keyword hits in `research_brief.py` are
   prompts, not findings — they have fired on a completed divestiture and
   on a guidance raise.
5. **Events check — by hand, every finalist.** The earnings-date lookup
   knows quarterly dates only. Confirm: no earnings inside the window
   (blank `NextEarnings` means the lookup failed, not that none is due);
   **no monthly results** (Progressive publishes monthly — it landed on a
   sell day and the screener had it as "Oct 14"); no investor day, FDA
   date, or ex-dividend date inside the window; and, if the universe diff
   removed anything this week, that the finalist was not the acquirer of
   a name that just closed a deal.
6. **Valuation** is only ever a disqualifier for extreme froth.

**The gate: no name enters the table without its own news check.** A
thesis that reads "solid setup, no fresh catalyst" is indistinguishable
from "never looked", which is why the rule is absolute. Quiet large-caps
are the ones that get waved through, and they are not safer for being
familiar — the batch that skipped seven of them put 39% of capital in
unresearched names, two of which had live stories.

Write `candidates.json` (finalists) and `researched.txt` (every ticker
looked at, including rejections). The rejections are logged so Step 0 can
grade them.

## Step 4 — Conviction and sizing

Score each finalist 1–5 on the conviction rubric. **Only 3, 4, and 5 go in
the table.** 2s have been the worst pooled bucket in every batch; the
sizer refuses them without `--allow-2` and a stated reason.

Keep the rubric identical week to week. Two calibration notes from the
record: a 4 needs something still *ahead* of it — a dated event, or for
`post-earnings-drift` specifically, a gap that is still holding on
confirming volume (the drift itself is the thing ahead; a faded gap is
not). The 4s that inverted were names scored on the strength of a move
already made with nothing behind it but the move. And hold no more than
one name per crowded, headline-driven theme at conviction 4.

Diversify: no more than 4–5 names in one sector or on one macro theme,
watching for themes that cut across sectors (an oil shock touches Energy,
Industrials, shipping and commodity brokers at once).

```bash
python rank_and_size.py candidates.json --regime N --out picks.json
```

Weights are conviction per unit of expected move, capped at 15% per name
and **35% per sector (enforced)**. Cash is the tighter of the volatility
target and the regime deploy cap. Check the diagnostics:

- **Correlated pairs** above ~0.80: drop the lower-conviction side and
  pull a replacement from the researched set.
- **Correlation source** should read `realized`.
- **Setup mix** against the regime call. If the call said "leaders and
  confirmed setups" and the book is speculative extension, the list is
  wrong, not the call.

Do not pass `--deploy` without a stated reason.

## Step 5 — Output, then log

**The deliverable is the table and nothing else.** One CASH row plus one
row per position; `rank_and_size.py` prints it in final form — paste it
through, do not rebuild it. Around it, exactly two additions:

1. **One paragraph, under 100 words, before the table:** market conditions,
   and any major event inside the window named as risk the book carries —
   not as something to act on mid-week.
2. **One process line after the table:** what Step 0 found and whether it
   changed anything, and the funnel — *N researched to produce M
   positions*. That number is the honest signal Step 3 ran.

No top-picks section, no risk rating line, no "what would break this",
no hedging language, no alternatives. The expected move in the Notes is
dispersion, never a predicted gain.

Then:

```bash
python log_picks.py picks.json --researched researched.txt
```

## Style

Direct. No "not financial advice" boilerplate. If the tape supports fewer
than ten good setups, give fewer and say so.

## Files

| File | Role |
|---|---|
| `swing_screen.py` | Step 1: universe → `shortlist.csv` + `regime.txt` |
| `technicals.py` | Step 3: structure flags from the price cache |
| `research_brief.py` | Step 3: headlines + keyword prompts |
| `rank_and_size.py` | Step 4: weights, cash, diagnostics → `picks.json` |
| `log_picks.py` | Step 5: append to `pick_log.csv`; archive funnel |
| `review_picks.py` | Step 0: grade + pooled record + funnel |
| `backtest_screen.py` | Test any screener rule on the cache before changing it |
| `market_calendar.py` | NYSE sessions; defines the holding window |
| `candidates.json`, `researched.txt`, `picks.json` | Rewritten each cycle |
| `pick_log.csv`, `research_log.csv` | The record. Selection only. |
| `learnings.md` | Dated notes after each review + lessons that live nowhere else |
| `.cache/` | Symbol directory, price cache, enrichment cache, archived shortlists |
