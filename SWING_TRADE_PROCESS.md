# Swing Trade Screening Process

This folder is dedicated to one job: producing **a single allocation
table** — one cash position plus 10-20 NYSE/NASDAQ stocks with percentage
weights — to be held for **one trading week**, for a hypothetical
greenfield portfolio the user reallocates weekly.

The week is the unit throughout: every name is bought at the open of its
first trading day and sold at the close of its last. Usually Monday→Friday,
four sessions when a holiday lands inside it.

**Run it any time between one week's closing bell and the next week's
opening bell** — Friday evening, either weekend day, or the morning before
the open all work equally well, because nothing has traded in between and
the last completed session is the newest information that exists. The
scripts read the clock and work out which week the picks are for;
`upcoming_week_window()` in `market_calendar.py` is the single source of
that answer. Never hard-code Monday, and never assume the run is happening
pre-market on the first trading day.

**Trigger:** any request meaning "run the screen" — *"run the weekly trade
picks"*, *"run the weekend process"*, *"let's do this week's picks"* —
starts this process, and it runs end to end without needing re-explaining.
It is run by hand; there is no scheduled task. `CLAUDE.md` in this folder
points here and is the only thing a fresh session loads on its own.

**Expect this to take an hour or more of real work.** Most of that is Step
3, and it is the step where quality is actually won or lost. A cycle that
finishes in fifteen minutes did not research its candidates; see the gate
at the end of Step 3.

The whole run, in order:

```bash
python -c "from market_calendar import upcoming_week_window, sessions_in_week; f,l=upcoming_week_window(); print('WINDOW', f.date(), f.strftime('%a'), '->', l.date(), l.strftime('%a'), '|', sessions_in_week(f), 'sessions')"   # 0a  which week
python review_picks.py                                    # 0   grade last batch
python swing_screen.py                                    # 1   ~10 min, backgroundable
#                                                           2   regime call (read regime.txt + web search)
python research_brief.py --top 30                         # 3   headlines + red flags
python technicals.py --top 30                             # 3   price structure
#                                                           3   per-name research, then write candidates.json
python rank_and_size.py candidates.json --regime <1-5> --out picks.json   # 4
#                                                           5   paste the table through
python log_picks.py picks.json                            # 5   log it
```

Read `learnings.md` before Step 3 — it carries the standing lessons that
past cycles paid for.

**The user is deliberately not a human in the loop.** They want to read
one table and act on it, without making judgment calls of their own —
that's how they maintain discipline. So every number in the output must
be computed or reasoned here, and the output must not ask them to decide
anything. Two consequences: don't hedge allocations with "consider" or
"you might want to," and don't offer alternatives for them to choose
between. Give the table. If something genuinely can't be resolved here,
say so plainly in the Notes rather than pushing the decision to them.

## Ground rules

- **Individual equities only.** No shorts, no options, no ETFs/ETNs, no
  leveraged or inverse products. The universe builder already excludes
  ETFs/ETNs, leveraged/inverse products, preferreds, warrants, rights,
  units, and SPAC shells by construction — this is a long-only common-stock
  screen and should stay that way unless the user explicitly asks to widen
  scope.
- **Clean slate every time, for selection.** Ignore any of the user's
  actual holdings and don't let prior batches bias which *new* names get
  picked. The pick log (Step 0) is read for process learning only — never
  to decide which tickers appear this cycle.
- **Fundamentals don't predict a one-week move.** Weight short-term relative
  strength, breakout-on-volume, orderly pullback-to-support in an intact
  uptrend, post-earnings drift, and dated near-term catalysts. Valuation is
  only ever a *disqualifier* for extreme froth, never a reason to include.
- **Verify, don't trust the CSV blindly.** Confirm price, volume and trend
  against the last completed session for every finalist before it makes the
  list. There is no live quote during the run window and none is needed —
  that session's close is the last thing that happened.
- **No OTC, no sub-3-month listings, nothing pinned by pending M&A
  arbitrage.** The first two are enforced by the screener; merger-arb
  pinning has to be caught by reading the news during research.
- **Know which half of "magnitude" is forecastable.** Expected *move*
  (dispersion — how far a name typically travels) genuinely is: volatility
  clusters and is strongly autocorrelated, and the ATR-derived estimate is
  real. Expected *return* (direction x magnitude) is not, at this horizon:
  noise exceeds any plausible edge by roughly 4-8x, so a point forecast
  like "+3.2%" would be almost entirely noise. Conviction scores are
  ordinal judgments, not calibrated edges — running them through the
  sizing arithmetic in Step 4 does not make them more accurate than the
  judgment that produced them. Never present an expected move as a
  predicted gain.

## Step 0a — Confirm which week these picks are for

```bash
python -c "from market_calendar import upcoming_week_window, sessions_in_week; f,l=upcoming_week_window(); print('WINDOW', f.date(), f.strftime('%a'), '->', l.date(), l.strftime('%a'), '|', sessions_in_week(f), 'sessions')"
```

This is the week the table is for, holidays already accounted for — a Labor
Day week correctly starts Tuesday. Use these dates in the output and don't
work them out by hand.

**If the printed first session is today or earlier, the week has already
begun trading and the run is late.** Say so plainly at the top of the
response and recommend skipping the week rather than entering mid-week. Do
not quietly produce a normal-looking table for a week already underway: the
reference prices are stale, the first session's open is gone, and grading
will mark the batch from a day the user never bought on.

## Step 0 — Review the last batch before doing anything new

```bash
python review_picks.py
```

Grades any logged batch whose window has closed against `pick_log.csv` and
prints a summary. **Every pick is graded exactly one way:**

- **EntryOpen** — the *open* of the week's **first trading day**. Not the
  reference close the pick was written against; grading against the prior
  close would credit gains that were never purchasable.
- **ReturnPct** — from that open to the **close of the week's last trading
  day**. That's it.

The window is the trading week, holidays part of the definition rather
than exceptions to it: Labor Day week runs Tuesday→Friday, Good Friday week
Monday→Thursday, Thanksgiving week Monday→Friday with Thursday missing and
a half-day Friday that still counts. `market_calendar.py` computes it and
`log_picks.py` stamps the window end when the batch is written — never work
it out by hand and never assume Friday.

**The log measures selection, not trading.** It records what the table
called for and what those names then did. It holds no fills, no exit
prices, and no record of which positions were taken — and **never ask the
user for any of it.** Step 0 needs nothing from them but the command above.

That split is deliberate. The log answers one question — *does the screen
pick names that rise across the week?* — plus the weighting question that
follows from it. Folding the brokerage account into the same number answers
something else, and mixing the two degrades both: a good week of trading
hides a bad week of picking, and the reverse. So the graded record will not
match the user's own tally to the penny — fills and commissions live
outside this file. But the *method* it grades is now exactly the routine
the user follows: buy every name at the week's first open, sell at its last
close. There is no gap in the model to explain away.

This is a factual record only — **it never determines which tickers get
picked this cycle.** What it's for:

- Read the summary. If a pattern is visible (e.g. pullback setups have
  outperformed breakouts for the last several cycles, or names with
  earnings inside the window have underperformed), let that inform this
  cycle's *qualitative* judgment calls in Steps 3-4 — which setups to lean
  into, how much to discount event risk, etc.
- **Check the two system-level diagnostics**, which judge the method
  rather than the individual picks:
  - **Portfolio vs. equal-weight.** Did conviction/volatility sizing beat
    simply splitting capital evenly across the same names? If sizing keeps
    costing value across several batches, the weighting scheme is wrong,
    not just unlucky.
  - **Conviction calibration.** Do 4s and 5s actually out-return 2s and
    3s? This is the most important check in the system: if conviction
    doesn't predict returns, then the scores are noise and every
    allocation built on them is theater. One inverted batch is normal
    variance; a persistent inversion means the rubric needs rethinking.
- Append a short freeform note to `learnings.md` in your own words:
  what the data showed, what if anything you're adjusting because of it,
  and the sample size (small samples should be noted as such, not
  overreacted to).
- If nothing was due for review, that's fine — say so in one line and
  move on.
- **Disclose this in the final output** (see Step 5) — one line saying
  what was reviewed and whether anything changed as a result.

Only change tuning constants — `swing_screen.py`'s scoring weights, or
`rank_and_size.py`'s `CONVICTION_POWER`, `MAX_WEIGHT` and
`REGIME_TARGET_VOL` — when a pattern has held over **several consecutive
cycles** (rule of thumb: 5+ batches / ~40+ logged picks), not off one
noisy week. If you do change one, say so explicitly in that cycle's output
and in `learnings.md`, with the before/after value and the reasoning.

## Step 1 — Run the screener

Any time inside the run window works: the market is closed throughout it,
so the screener always sees complete bars. It still guards against a
mid-session run — detecting an open market and dropping the still-forming
daily bar, saying so in the log and in `regime.txt` — but that guard should
never fire during a normal cycle. If it does, the run is happening at the
wrong time; check before trusting the output.

```bash
python swing_screen.py
```

This downloads a year of price history for the ~5,000-name NYSE/NASDAQ
common-stock universe, filters to price >= $5, requires 20-day avg dollar
volume >= $25M *and* that at least 15 of the last 20 sessions individually
clear $25M (so one spike day can't carry an otherwise illiquid name),
drops outright downtrends, and scores the rest on relative strength +
breakout + pullback + gap-event signals. It writes:

- `shortlist.csv` — top-ranked candidates (default top 60) with sector,
  trend, RS, breakout/pullback/gap-event flags, ATR, expected move, and
  next earnings date (flagged if inside a ~10-day window)
- `regime.txt` — SPY/QQQ trend, VIX level & direction, 10Y yield
  direction, and breadth (% of the *liquid* universe above its 50-day SMA
  — breadth is deliberately measured only across names that clear the
  price/liquidity filters, so illiquid microcaps can't skew a number meant
  to describe the tape you can actually trade)

Always rerun this fresh unless the user says otherwise — don't reuse a
shortlist from an earlier session. `regime.txt` opens with a `Generated:`
timestamp; **check it before reading anything else.** If it isn't from the
run just made, the screener failed and the files on disk are stale — say
so rather than quietly building a list on old data.

## Step 2 — Regime check (let it shape everything else)

- Read `regime.txt`.
- Web search for anything landing inside the next ~10 trading days: FOMC
  meeting/decision, CPI/PCE prints, the jobs report, and any major
  sector-moving earnings cluster (mega-cap tech, etc.).
- Write a 2-3 line regime call: trending/risk-on, choppy/mixed, or
  risk-off — and state how that should tilt setup selection (e.g. a
  risk-off or choppy tape favors relative-strength leaders and orderly
  pullbacks over aggressive breakouts; a clean uptrend favors breakouts
  and continuation).

## Step 3 — Research and verify each candidate

**Research more names than you intend to hold.** Aim to work through
roughly **30 candidates to end up with 10-20**, so the rejecting happens
here, in research, rather than upstream in the screener's ranking. If the
researched set and the final list are nearly identical, research did no
selection work — it only wrote justifications for whatever the score
already ranked highest, which is not the same thing and is worth
considerably less.

Don't work purely top-down either. The composite score is noisy on
individual names (the doc says so below), so read all 60 rows and pick the
~30 to research from across the range and across sectors, not just the top
30 by score.

Start by pulling headlines for the whole set in one pass:

```bash
python research_brief.py --top 30
python technicals.py --top 30
```

`research_brief.py` prints recent headlines per name plus keyword hits for
dilution, litigation, merger, leadership change, insider selling,
downgrades and guidance cuts. It is raw material, not a verdict — a keyword
hit needs confirming and silence is not a clean bill of health. What it
buys is that the *cost* of checking a name is no longer a reason to skip
one.

`technicals.py` reads the price structure the screener's flags gloss over:
extension above the 20d SMA, whether price still holds it, where the volume
is going on up versus down days, whether a recent gap is holding, and
whether ATR is expanding. **Its real job is catching a thesis that the tape
contradicts.** In the 2026-08-31 batch it flagged AXON as trading *below*
its 20d SMA while the written thesis called it "pulling back on light
volume" — that is a breakdown, not an orderly pullback, and it went on to
lose 13%. It flagged U as DISTRIB, up/down volume 0.50, against a thesis
that said in as many words "an orderly pullback, not distribution."

Treat every flag as a question to answer in the Notes, not a veto. A name
can be EXTENDED and still worth holding through a drift; it just cannot be
described as a pullback. What is not acceptable is a flag going unmentioned
in a thesis it contradicts.

Then, for each name worth considering:

- Confirm price, recent volume, and trend structure against the last
  completed session — don't just take the CSV's numbers. There is no live
  quote during the run window and none is needed; that session's close is
  the price every name will be bought near.
- Confirm the next earnings date. If it falls inside the holding week it
  is event risk the position is held straight through, with no way out
  before the last session's close: either exclude the name, or flag the
  risk explicitly and size conviction down. A blank `NextEarnings` means
  the lookup failed, **not** that no earnings are scheduled — the screener
  log flags these, and `research_brief.py` prints "earnings UNKNOWN" for
  them. Look those up by hand before trusting the name.
- Pull recent news for the actual catalyst: why is this name moving, is
  there a dated catalyst ahead (product launch, guidance, analyst day, FDA
  date, contract win), and are there red flags (dilution, investigation,
  litigation, leadership exit, pending merger arb)? For any GapEvent-
  flagged name specifically, determine whether the catalyst is still live
  (developing story) or already fully priced in (one-off news that's
  played out) — don't credit a stale pop as ongoing momentum.
- Classify the setup: breakout on volume, pullback to support in an
  intact uptrend, relative-strength continuation, post-earnings drift, or
  another momentum-driven setup. Use the screener's Breakout/Pullback/
  GapEvent flags as a starting point, not as gospel — they're computed at
  full-universe scale and can be noisy on individual names.
- **Sanity-check the VolRatio column before trusting any volume-based
  flag.** Its median across the shortlist should sit near 1.0. If it's
  far below (say a median under 0.5), the run picked up a partial or
  otherwise broken session and every Breakout/Pullback flag is suspect —
  investigate before building a list on it. Seasonal lulls (late August,
  holiday weeks) legitimately push it into the 0.6-0.8 range; 0.2-0.3 is
  a data problem, not a market.
- Apply the valuation-froth disqualifier here if warranted (never use
  valuation as a reason *to* include).

**The gate: no name enters the table without its own news check.** Not one.
A thesis reading "solid setup, no fresh catalyst" is indistinguishable in
the output from "I never looked," which is exactly why the rule has to be
absolute rather than a matter of judgment about which names seem safe
enough to wave through. Quiet, familiar, large-cap names are the ones that
get skipped, and they are not safer for being familiar — the 2026-08-31
batch put 38.9% of capital into seven names that had no news check at all,
and two of them had live stories (a private-credit redemption run, an
acquisition integration) that the theses simply failed to mention.

Before moving to Step 4, confirm for every finalist that you have:
catalyst or reason for the move, a red-flag scan, a confirmed earnings
date, and the setup classified. If any of those is missing for any name,
Step 3 is not finished.

## Step 4 — Score conviction, then let the sizer rank and weight

- Build a list of **10-20 names** — fewer if the tape genuinely doesn't
  support that many good setups, and say so plainly.
- Diversify: no more than ~4-5 names from one sector, and no more than
  ~4-5 riding the same macro theme or catalyst (watch for a theme spread
  *across* sectors too — e.g. an AI-power-demand theme touching Tech,
  Industrials, and Utilities is still one concentrated bet).
- Assign each finalist a **Conviction score of 1-5** using the rubric
  below. This is the only judgment input to sizing; everything after it is
  arithmetic.

```
5  Multiple confirming factors: fresh dated catalyst, clean technical
   setup, strong relative strength, regime-aligned, no red flags, no
   earnings inside the window.
4  Strong setup plus a confirmed catalyst; only minor concerns.
3  Good setup OR good catalyst, not both — or both with a real
   offsetting risk.
2  Speculative: genuine thesis but a material overhang (dilution,
   stretched extension, event risk inside the window).
1  Lottery ticket. Rarely worth including.
```

Keep this rubric consistent across cycles. If a "4" means different things
week to week, the pick log records noise and the learning loop is worthless.
`python rank_and_size.py --show-rubric` prints it.

Then write a JSON array of the finalists — `{"Ticker", "Sector",
"SetupType", "Conviction", "ReferenceClose", "ATR14", "Thesis"}`, using the
last completed session's close and the screener's ATR14. `ReferenceClose`
only scales ATR into a percentage; it is not an entry price, since entry is
whatever the first session opens at. Also score the **regime 1-5**
(rubric below); it sets the portfolio volatility target, which sets cash.

```
5  Clean uptrend, broad participation (breadth >60%), VIX low/falling,
   no market-moving events inside the window.
4  Constructive but not pristine: minor divergence, mild event risk.
3  Mixed, choppy, or rotational. Indices split, breadth near 50%.
2  Deteriorating breadth, VIX rising, or a major binary event lands
   inside the window (FOMC, CPI/PCE, mega-cap earnings).
1  Risk-off. Breadth collapsing, indices below key averages, VIX spiking.
```

```bash
python rank_and_size.py candidates.json --regime <1-5> --out picks.json
```

This computes each name's expected move from ATR, scaled to the number of
sessions in the week, weights the book
by conviction-per-unit-volatility, caps any single name at 15%, drops
positions too small to be worth a slot, and ranks by resulting weight.
**Rank #1 is the largest allocation, not necessarily the highest
conviction** — a lower-conviction, low-volatility name can outrank a
higher-conviction, wild one, because it earns more of the capital budget
per unit of risk it brings.

**Cash is computed, not chosen.** The script measures the book's expected
move over the week using ATR volatilities and *realized* correlations between the
finalists, then deploys whatever fraction lands portfolio risk on the
regime's target. So cash responds automatically to what is actually in the
list — a batch of wild post-catalyst names holds more cash than a batch of
quiet pullbacks, without anyone deciding that. A tame book in a strong
regime can legitimately reach 0% cash; that is by design, not a bug.
Do not pass `--deploy` (it overrides the targeting) unless there is a
specific stated reason.

Check the diagnostics printed under the table:

- **Risk contribution spread** — tight means no single name dominates.
- **Sector exposure** — flags any sector over 35%.
- **Most correlated pairs** — realized 60-day correlation between
  finalists. Sector labels miss themes that cut across them, and this does
  not care what sector anyone was assigned to. Any pair above ~0.80 is
  close to one position held twice; drop the lower-conviction side and pull
  a replacement from the researched set rather than accepting it.
- **Correlation source** — should read `realized`. If it says FALLBACK the
  estimate is a guess and the cash figure is softer than it looks.

If something looks wrong, revisit the candidate list; don't override the
arithmetic.

**Then check the list against your own regime call.** Step 2 wrote down
which setups the tape favors. Read the final mix and confirm it actually
reflects that — if the call was "choppy, favor relative-strength leaders
and orderly pullbacks" and the book is two-thirds breakouts, one of the two
is wrong and it is usually the list. Say in the Notes which way it went.
A regime call that never changes the selection is decoration.

## Step 5 — Output the table, then log the batch

**The deliverable is a single table and nothing else.** One CASH row plus
one row per position, 11-21 rows total. `rank_and_size.py` prints it in
final form — paste it through, don't rebuild it or adjust the numbers.

```
**Week of Tue Sep 8 - Fri Sep 11 (4 sessions)**

| Position | Allocation | Notes |
|---|---:|---|
| **CASH** | **X.X%** | why this much cash |
| TICKER | X.X% | thesis, conviction, expected move, why this size |
```

`rank_and_size.py` prints the week line above the table from
`upcoming_week_window()`, so it names the right days in a holiday week
without anyone working it out. Keep it — it is the only place the user sees
which days they are buying and selling.

**There are no entry limits and no stop losses.** Every name is bought at
the open of the week's first session and sold at the close of its last,
unconditionally. Don't publish a Max Buy or Stop Loss column, don't suggest
a limit price, don't tell the user to place any order type, and don't add
conditions like "skip it if it gaps." The table is the whole instruction:
these names, these weights, that week. That is also precisely what Step 0
grades, which is why the log and the account now describe the same thing.

The Notes column carries the whole rationale: the catalyst and setup, the
conviction score, the expected move, and how those produced the allocation. The CASH row's note explains the
regime read and the volatility target behind it.

Around the table, keep it to two short additions:

1. **One paragraph, under 100 words**, before the table: market conditions
   and macro environment, and a flag if a major event lands inside the
   window (FOMC, CPI/PCE, jobs report, mega-cap earnings) — named as risk
   the book carries, not as something to act on mid-week. The position is
   held through it either way.
2. **Process note**, one line after the table: what Step 0 found (or
   "nothing due for review yet"), whether it changed anything, and the
   research funnel — how many candidates were researched to produce this
   many positions. That last number is the one honest signal that Step 3
   actually ran, so never omit or estimate it.

Nothing else. No separate risk rating line (the cash row carries it), no
"top picks" section, no "what would break the list" section — the table
and the paragraph cover that ground. The point of this format is that it
requires no interpretation: the allocations are the instructions.

The expected move quoted in Notes is an ATR-derived *dispersion* estimate,
**not** a return forecast; never present it as a predicted gain.

Then log the batch so Step 0 has something to grade next time. If
`rank_and_size.py` was run with `--out picks.json`, that file already
carries conviction, weight, cash, and regime score:

```bash
python log_picks.py picks.json
```

## Style

- Be direct. Skip "not financial advice" boilerplate. Don't hedge every
  claim.
- If the tape doesn't support 10-20 good setups, give fewer and say why.

## Files in this folder

| File | Purpose |
|---|---|
| `swing_screen.py` | The quantitative screener (Step 1) |
| `research_brief.py` | Batch headlines + red-flag scan for shortlist candidates (Step 3) |
| `technicals.py` | Price-structure check: extension, MA hold, volume, gap-hold (Step 3) |
| `market_calendar.py` | NYSE sessions and week boundaries; defines the holding window |
| `review_picks.py` | Grades closed-out logged batches (Step 0) |
| `rank_and_size.py` | Ranks and risk-weights researched finalists (Step 4) |
| `log_picks.py` | Appends a finalized batch to the pick log (end of Step 5) |
| `candidates.json` | The researched finalists Claude hands to the sizer (rewritten each cycle) |
| `picks.json` | The sizer's ranked output, fed straight to `log_picks.py` (rewritten each cycle) |
| `shortlist.csv` | Most recent screener output (regenerated each run) |
| `regime.txt` | Most recent regime snapshot (regenerated each run) |
| `pick_log.csv` | Every logged pick ever made, plus graded outcomes once due. Selection record only — no execution data, by design |
| `learnings.md` | Standing lessons + notes written after each review — read this each cycle, before Step 3 |
| `CLAUDE.md` | Auto-loaded by a fresh session; points here and carries the trigger phrases |
| `.cache/` | Cached NASDAQ/NYSE symbol directory (refreshes weekly) + same-day price cache |
| `SWING_TRADE_PROCESS.md` | This file |

## Maintenance

- Scoring weights and filter thresholds are constants at the top of
  `swing_screen.py` — tune there if the shortlist consistently feels off,
  but see Step 0's rule about only doing so on a persistent, multi-cycle
  pattern.
- If yfinance's data format changes or the NASDAQ Trader symbol directory
  URL breaks, that's the first place to look.
