# Weekly Swing Screen — Process

This folder produces **one allocation table**: a cash row plus 10–20
NYSE/NASDAQ common stocks with percentage weights, held for **one trading
week** — bought at the open of the week's first session, sold at the close
of its last. Nothing else. The user reads the table and acts on it; they
make no judgment calls of their own, so the output never asks them to
decide anything.

**Trigger.** "go", or anything meaning "run the screen", starts this process
end to end. It runs by hand, any time between one week's closing bell and
the next week's opening bell — nothing has traded in that window, so every
moment inside it is equally valid. The scripts read the clock.

**Budget.** An hour or more. Most of it is Step 3. A run that finishes in
fifteen minutes did not research its candidates.

## The run at a glance

```bash
python scripts/paths.py               #    which week, how many sessions, which run folder
python scripts/review_picks.py        # 0  grade the last batch, read the pooled record
#                                       0b fold what was learned into PROCESS.md / learnings.md
python scripts/swing_screen.py        # 1  ~5-10 min; run it in the background
#                                       2  regime call: runs/<batch>/regime.txt + web search
python scripts/technicals.py --tickers <research set>              # 3
python scripts/research_brief.py --tickers <research set> --days 21  # 3
#                                       3  per-name research -> researched.txt, candidates.json
python scripts/rank_and_size.py --regime N   # 4  -> picks.json, table.md
#                                       5  deliver; save output.md
python scripts/log_picks.py           # 5  append to pick_log.csv
```

Every file a run produces lands in **`runs/<batch-date>/`**, where the
batch date is the first session of the week being picked for. The scripts
work that out themselves; nothing is ever written over another week's file.
`scripts/paths.py` is the single definition of the layout.

The upcoming week is always the next one that has not begun trading, so a
mid-week run targets the *following* week. That is permitted but wasteful —
the last completed session will be several days stale by the open — so run
between Friday's close and Monday's open.

## Ground rules

- **Long-only common stock.** No ETFs, ETNs, leveraged/inverse products,
  preferreds, warrants, units, SPACs, OTC, or listings under three months.
  The screener enforces the mechanical ones; pending-M&A names have to be
  caught by reading (Step 3).
- **Clean slate for selection.** Prior batches, the user's holdings, and
  the pick log never decide which tickers appear. The log is read for
  *process* learning only.
- **No execution data exists here, by design.** Never ask the user what
  they traded, sold, or paid. Step 0 needs only its command.
- **No Max Buy, stops, limits, order types, or conditions.** The table is
  the whole instruction — and exactly what Step 0 grades.
- **What is forecastable at one week.** Expected *move* (dispersion) is —
  volatility clusters, and the ATR estimate is real. Expected *return* is
  not, to any useful precision. Conviction scores are ordinal judgments.
  Never present an expected move as a predicted gain.
- **Never read a still-forming bar as a close.** The scripts refuse; do
  not do it by hand either. The last completed session is the newest
  information that exists, and all that is needed.

## Step 0 — Grade the last batch, read the record

```bash
python scripts/review_picks.py
```

Grades every logged batch whose window has closed (open of first session →
close of last; holidays are part of the window definition), then prints
the batch against SPY over the same window, the **research funnel** (did
the picks beat the never-researched remainder of that week's shortlist?),
and the **pooled** record across every graded batch. Read the pooled
section; a single batch is ~12 names and proves nothing.

The system-level checks, in order of importance:

1. **Conviction calibration.** Do 4s out-return 3s? If not over 40+ picks,
   the rubric is noise and the sizing built on it is theatre.
2. **Sizing vs equal-weight.** Inverse-vol sizing wins mechanically in
   down weeks; count it validated only once it has held in up weeks too.
3. **Setup type and flagged-vs-clean.** Which labels are earning money.
4. **Research funnel.** If picks trail the never-researched remainder, the
   research set started in the wrong place; if they trail the rejected
   set, selection itself hurt.
5. **Dispersion calibration.** Median |realised| / expected move. Above
   1.0 means ATR is understating the weeks being traded.

### Step 0b — Fold what was learned into the process

The knowledge in this folder lives in four places, in strict order of
preference. Every finding from the review goes to the **highest** place it
qualifies for, and only there:

1. **A rule or check in `PROCESS.md`** — if it changes what is *done* at a
   step (a new check, a changed threshold, a different order). Edit the
   step itself. Never annotate a rule the finding contradicts; rewrite it.
2. **A standing lesson in `learnings.md`** — if it is a pattern that
   informs judgment but is not a step. One bullet, with the number or the
   example that paid for it.
3. **An open question in `learnings.md`** — if it is suggestive but below
   the evidence bar. State what would settle it.
4. **The dated note** — only what fits none of the above: the batch's
   numbers, and what was folded into 1–3 this cycle. Six lines or fewer.

Then, in this order, every cycle:

- **Answer open questions.** For each one, ask whether the pooled record
  now settles it — 5+ batches / 40+ picks for anything that changes a
  constant, three consistent batches for a judgment question. If settled,
  retire it: move the answer to place 1 or 2 and delete the question. If
  the evidence went the other way, say so and delete it.
- **Promote.** Anything in an older dated note that has since held up
  moves to place 1 or 2. Anything that did not hold up is deleted.
- **Prune.** Keep at most the four most recent dated notes. `pick_log.csv`
  and `runs/` are the archive; the dated section is a staging area.
- **Re-read `PROCESS.md` once** for any sentence the review has made
  untrue, and fix it.

Constants and score weights still need the bar in *Changing the process*
below; a rule about *how to read, check, or label* does not — that is
judgment, and judgment updates on evidence as it arrives.

Disclose in one line of the final output what was folded in, or that
nothing was.

**Done when:** the command has run, the pooled section has been read, open
questions have been revisited, the dated note is written (≤ 6 lines), and
`PROCESS.md` has been re-read. If nothing was due to grade, Step 0b still
runs against the pooled record.

## Step 1 — Screen

```bash
python scripts/swing_screen.py
```

Filters ~5,000 names to price ≥ $5 and 20-day dollar volume ≥ $25M on at
least 15 of the last 20 sessions, drops downtrends, scores the rest, and
writes `shortlist.csv` (top 60) and `regime.txt` into the run folder.
Always rerun it fresh.

Check three things before reading a single row:

- **`Generated:` in `regime.txt` is from this run.** If not, the screener
  failed and the files are stale.
- **VolRatio median across the shortlist** (printed in the last log line).
  Healthy is ~0.8–1.0; a holiday lull sits at 0.6–0.8; **0.2–0.3 is a
  broken session** and every volume-based flag is an artefact until rerun.
  The high side is a trap too. **A median well above ~1.5 means the last
  session was an expiry** — quad-witching is the third Friday of March,
  June, September and December, and the S&P rebalance lands with it. On
  2026-09-18 the median *liquid stock in the whole universe* traded 2.07×
  its 20-day average and the shortlist median was 2.06, i.e. identical to
  the market, so the Breakout flag's volume confirmation carried no
  information and fired on 65 names against 12 the week before. When this
  happens, do not trust the flag: recompute each candidate's volume over
  the **four sessions before** the expiry day against its 20-day average,
  and let that number, not the flag, decide what is really being
  accumulated. Say so in the output.
- **The universe diff**, if the symbol cache refreshed this week (printed
  as `REMOVED: ...`). Removed symbols are delistings and completed mergers.
  Step 3 checks them against the finalists' *acquirers*.

What the score is: the **Breakout flag** carries most of it. Over 40
backtested weeks it was the only signal in the system with a real edge
(+1.03 pts/week over the universe, t = 2.7, positive in both halves).
Twenty-day relative strength is a tiebreaker only — it is flat across
quintiles. The **Pullback flag has no score weight**: it was negative in
both halves (−0.53 pts/week), and a score that rewards it packs the
shortlist with names whose only merit is drifting quietly near an average.
The flag is still printed because it is a useful *label* — see Step 3.

Two consequences to expect. In a week with few breakouts, the tail of the
shortlist is filled by relative strength and is correspondingly
low-information; research accordingly. And a Breakout-flagged name with an
`ExpMovePct` near zero has jumped to a fixed price and stopped moving —
that is a pinned cash deal, not a setup.

**Done when:** the three checks are made and the shortlist is read in full.

## Step 2 — Regime

Read `regime.txt`, then web-search the next ~10 trading days for: FOMC
decision, CPI / PCE, the jobs report, mega-cap earnings clusters, and the
current *direction* of rate expectations — the tape reads differently when
a hike is priced than when a cut is.

Write a 2–3 line regime call: trending / choppy / risk-off, and what that
favours. A choppy or hawkish tape favours relative-strength leaders on
confirming volume over speculative extension; a clean uptrend can carry
more breakouts and post-earnings drift.

Score it 1–5 with `python scripts/rank_and_size.py --show-rubric`. **A
binary macro event inside the window is by itself a 2**, and a 2 caps
deployment at 65% no matter what the book's measured volatility says.

**Done when:** the call is written and the score chosen, with the events
inside the window named.

## Step 3 — Research

**Read `learnings.md` first**, every cycle — the standing lessons are the
mistakes this step exists to avoid.

**Research ~30–36 names to hold 10–20.** Build the research set like this:

1. **Every Breakout-flagged name on the shortlist.** They are the signal.
2. Then widen across the rest of the list **by sector**, not by rank —
   healthcare, financials, industrials and consumer will be under-
   represented in a breakout-led list, and the book needs them. Prefer
   names with up/down volume above 1.0 and price in the top third of its
   20-day range.

If the researched set and the final list are nearly identical, research
only wrote justifications for the screener's ranking.

Run both tools on the set first:

```bash
python scripts/technicals.py --tickers A,B,C,...
python scripts/research_brief.py --tickers A,B,C,... --days 21
```

Then, **for every name that might make the table**, all six:

1. **Verify price, volume and structure** against the last completed
   session. Every `technicals.py` flag is a question the thesis must
   answer honestly. A flag going unmentioned in a thesis it contradicts is
   the single most expensive failure this process has had (a name called
   "pulling back on light volume" while below its 20d SMA lost 13% in a
   week; "not distribution" written over a 0.50 up/down ratio lost 4%).
2. **Setup type**, from the closed list: `breakout`, `pullback`,
   `post-earnings-drift`, `rs-continuation`, `other`. The label has to be
   earned. A `pullback` needs price *above* a rising 20d SMA **and**
   up/down volume above 1.0 — "drifting down quietly" is not a pullback,
   and that mislabel is where the record's losses have come from.
   `post-earnings-drift` needs a positive print, a gap still holding, and
   no one-time flatterer (a tariff refund is not a beat; check what the
   beat was made of).
3. **Catalyst.** Why is it moving; is the story live or played out; is
   there a dated event ahead. A GapEvent-flagged name needs this answered
   explicitly. A move driven by a pending merger — as target *or* as
   acquirer repricing on deal odds — is not a catalyst; exclude it.
4. **Red flags**: dilution, litigation, leadership exit, insider selling,
   pending-merger pinning. `research_brief.py` keyword hits are prompts,
   not findings — they have fired on a completed divestiture and on a
   guidance raise. Read the item.
5. **Events check — by hand, every finalist.** The earnings-date lookup
   knows quarterly dates only. Note also that `EarningsInWindow` and
   `ExDivInWindow` are computed over a **10-calendar-day lookahead from
   the run date**, not over the five-session holding window, so they
   over-flag: check the actual date against the actual window before
   dropping a name. On 2026-09-20 they flagged three ex-dividends that all
   fell on Sept 30, five days after the sell. Confirm: no earnings inside
   the window (a blank `NextEarnings` means the lookup *failed*, not that
   nothing is due); **no monthly results** (Progressive publishes monthly; it landed
   on a sell day while the lookup showed a date a month away); no investor
   day, conference data presentation, FDA date or ex-dividend date inside
   the window (`ExDivInWindow` is computed — it is not the whole check);
   and, if the universe diff removed anything this week, that the finalist
   was not the *acquirer* of a name that just closed a deal (an acquirer
   never leaves the universe; one went into a table at 9.6% with a thesis
   that never mentioned its $10B purchase). An event inside the window
   either excludes the name or drops its conviction by one, and is named
   in the thesis.
6. **Valuation** is only ever a disqualifier for extreme froth.

**The gate: no name enters the table without its own news check.** A
thesis that reads "solid setup, no fresh catalyst" is indistinguishable
from "never looked", which is why the rule is absolute. Quiet large-caps
are the ones that get waved through, and they are not safer for being
familiar.

Write two files into the run folder:

- **`researched.txt`** — every ticker looked at, one per line, including
  the rejections. Step 0 grades them. (The tools above take the same
  names comma-separated; either way, the file is the record.)
- **`candidates.json`** — the finalists. One object each:
  `{"Ticker", "Sector", "SetupType", "Conviction", "ReferenceClose",
  "ATR14", "Flags", "Thesis"}`. `ReferenceClose` and `ATR14` are copied
  from `shortlist.csv`, never typed from memory. `Flags` is the
  space-separated technicals flags, or empty. The thesis carries the
  catalyst, the setup, every flag's answer, the events check, and why the
  conviction is what it is — it is printed verbatim in the table.

**Done when:** every finalist has all six items covered in its thesis, both
files are written, and the researched set is at least twice the final list.

## Step 4 — Conviction and sizing

Score each finalist 1–5 on the conviction rubric. **Only 3, 4 and 5 go in
the table.** 2s have been the worst bucket in every graded batch; the sizer
refuses them without `--allow-2` and a stated reason.

Keep the rubric identical week to week. A 4 needs something still *ahead*
of it — a dated event, or for `post-earnings-drift`, a gap that is holding
on confirming volume (the drift is the thing ahead; a faded gap is not). A
name scored 4 on the strength of a move already made, with nothing behind
it but the move, is a 3. Hold no more than one name per crowded,
headline-driven theme at conviction 4.

Diversify: no more than 4–5 names in one sector or on one macro theme,
watching for themes that cut across sectors (an oil shock touches energy,
shipping, refiners, fertiliser and commodity brokers at once).

```bash
python scripts/rank_and_size.py --regime N
```

Weights are conviction per unit of expected move, capped at 15% per name
and **35% per sector (enforced)**. Cash is the tighter of the volatility
target and the regime deploy cap. Read the diagnostics:

- **Correlated pairs** above ~0.80: drop the lower-conviction side and pull
  a replacement from the researched set. Re-run.
- **Correlation source** should read `realized`.
- **Setup mix** against the regime call. If the call said "leaders on
  confirming volume" and the book is speculative extension, the list is
  wrong, not the call.
- **Any "expected range only X%" warning** is a pinned deal until proven
  otherwise.

Do not pass `--deploy` without a stated reason.

**Done when:** the diagnostics are clean and `picks.json` and `table.md`
exist in the run folder.

## Step 5 — Deliver, then log

**The deliverable is the table and nothing else.** One CASH row plus one
row per position, pasted through from `table.md` — never rebuilt or
edited. Around it, exactly two additions:

1. **One paragraph, under 100 words, before the table:** market conditions,
   and any major event inside the window named as risk the book carries —
   not as something to act on mid-week.
2. **One process line after the table:** what Step 0 found and whether it
   changed anything, and the funnel — *N researched to produce M
   positions*. That number is the honest signal Step 3 ran.

No top-picks section, no risk rating line, no "what would break this", no
hedging language, no alternatives. The expected move in the Notes is
dispersion, never a predicted gain.

Save exactly what was delivered — paragraph, table, process line — as
**`output.md`** in the run folder. Then:

```bash
python scripts/log_picks.py
```

**Done when:** the table is delivered, `output.md` is saved, the log
confirms the batch and window dates.

## Changing the process

Judgment can change on one week's evidence. Code and constants cannot.
Rules about how to read, check, or label a name are judgment: Step 0b edits
them in `PROCESS.md` whenever the record warrants, and the dated note says
what changed. The rest of this section is about constants.

A score weight, `CONVICTION_POWER`, `MAX_WEIGHT`, `SECTOR_MAX`, or either
regime table changes only when (a) a pattern has held across **5+ batches
/ 40+ picks** in the pooled record, and (b) for anything in the screener,
`python scripts/backtest_screen.py` shows the change helps across both
halves of the year. Then say so in that cycle's output and in
`learnings.md`, with before/after values and the reasoning.

The strongest single-week signal this process has seen — four flagged names
losing together — was contradicted the same day by 40 weeks of data. That
is the bar.

## Style

Direct. No "not financial advice" boilerplate. If the tape supports fewer
than ten good setups, give fewer and say why.

## Files

| Path | Role |
|---|---|
| `PROCESS.md` | This document — the authority on every step |
| `learnings.md` | Standing lessons, the evidence base, dated review notes |
| `pick_log.csv` | The record: each table's rows, graded open→close |
| `scripts/paths.py` | The layout, defined once |
| `scripts/market_calendar.py` | NYSE sessions; defines the holding window |
| `scripts/review_picks.py` | Step 0 |
| `scripts/swing_screen.py` | Step 1 |
| `scripts/technicals.py`, `scripts/research_brief.py` | Step 3 tools |
| `scripts/rank_and_size.py` | Step 4 |
| `scripts/log_picks.py` | Step 5 |
| `scripts/backtest_screen.py` | Test a screener rule before changing it |
| `runs/<batch>/` | `shortlist.csv`, `regime.txt`, `researched.txt`, `candidates.json`, `picks.json`, `table.md`, `output.md` |
| `.cache/` | Symbol directory, enrichment cache, price cache (pickles not committed) |
