# Swing Screen Learnings

Notes written after reviewing each closed-out batch (see
SWING_TRADE_PROCESS.md Step 0). Purpose: notice patterns across cycles and
let them inform the *qualitative* curation judgment each time — which
setups to favor, how hard to lean on relative strength vs. breakout vs.
pullback.

**Read this before Step 3, every cycle.** Nothing here changes candidate
selection automatically, and `swing_screen.py`'s scoring constants are only
edited when a pattern has held across several consecutive cycles — and only
with a note here and in that cycle's output saying what changed and why.

Standing lessons first, then dated entries newest-first.

---

## Standing lessons

Durable rules, each one paid for. These carry forward regardless of what
the sample size says.

- **Check the thesis against the tape before writing it down.** The failure
  mode is not picking a bad name; it is writing a confident description the
  data contradicts. In the 2026-08-31 batch, AXON was called "pulling back
  on light volume" while trading below its 20d SMA (a breakdown, not a
  pullback — it lost 13%), and U was called "an orderly pullback, not
  distribution" while its up/down volume ratio was 0.50. `technicals.py`
  exists to surface exactly these contradictions; a flag it raises must be
  answered in the Notes, not ignored.
- **A name with no news check cannot go in the table.** The ones that get
  waved through are quiet, familiar large-caps, and familiarity is not
  diligence — 38.9% of the 2026-08-31 book went in unresearched, including
  a BX position carrying a live private-credit redemption story and a DNOW
  position described as having no catalyst while mid-acquisition.
- **Research more names than you hold, or research is not selecting.** That
  batch researched 16 and held 18. When the researched set and the final
  list are near-identical, research only wrote justifications for whatever
  the screener already ranked highest.
- **VolRatio median is the canary.** Check it across the shortlist before
  trusting any volume-based flag. Healthy is ~1.0; late-August and holiday
  lulls legitimately sit at 0.6-0.8; 0.2-0.3 means the run caught a partial
  session and every Breakout/Pullback flag is an artifact of the clock.
- **Never read a still-forming bar as a closing price.** Both scripts now
  refuse — `swing_screen.py` drops today's partial bar, `review_picks.py`
  holds a batch whose window ends today until after the 4:00 PM ET close —
  but the underlying mistake is easy to make by hand too.
- **Positions are held to the end of the week; there are no stops.** If a
  drawdown ever prompts the question, the levers are position size and how
  much ATR the book carries — both of which `rank_and_size.py` already
  weights on — not a stop rule bolted back on.

---

## 2026-09-07b - The universe.csv diff is a free corporate-actions feed

Noticed while answering a question about the weekly universe refresh, not from
any deliberate check - which is the point.

`.cache/universe.csv` is a cache of the NASDAQ Trader symbol directory that
`swing_screen.py` re-downloads once its age passes the weekly threshold. Its
git diff between two runs is therefore a **list of what stopped and started
trading that week**, and the removals are dominated by completed mergers.
The 2026-09-07 refresh dropped 22 symbols, including CRNX (acquired by
Vertex, $85/share cash, ~$10B, delisted Sept 1), LEG (merged into Somnigroup
Aug 26) and TWO (taken private by CrossCountry Mortgage Aug 25).

**The miss it exposed.** CRNX was bought by **VRTX**, which this cycle put in
the table at 9.6% of the book - and the written thesis never mentioned the
acquisition. Step 3 surfaced the guidance raise, JOURNAVX ramp and the
zimislecel manufacturing postponement, but not a $10B cash deal that closed
four sessions before entry. Direction of the call is unchanged (the tape
absorbed it constructively - up/down volume 2.41, clean structure, 2.5% off
the high, and the deal diversifies Vertex away from CF dependence), so this
is not the AXON-style case of a thesis the tape contradicts. It is the
BX-style case: a live story on a large position that the note failed to name.

**Standing rule to add: check completed corporate actions for every
finalist, and use the universe diff to do it.** After Step 1 regenerates the
cache, `git diff .cache/universe.csv` costs one command and names every
delisting of the week. Cross-reference the removals against the finalists'
*acquirers*, not just against the finalist tickers themselves - the pick that
needed this was the buyer, and buyers never leave the universe. That also
covers the process doc's merger-arb-pinning rule from the other direction:
the doc warns about holding a target, and this catches the acquirer.

**Nothing changed in code or constants for this.**

---

## 2026-09-07 — The 2026-08-31 batch graded: -1.89% into a rising tape

**The result.** 18 picks, 5 wins / 13 losses, avg -2.18% per name, portfolio
**-1.89%** on capital with 0% cash. The week it was held (Mon 2026-08-31 ->
Fri 2026-09-04) SPY opened-to-closed **+0.37%**, QQQ +0.53%, IWM +0.31%. So
this was not a batch dragged down by a bad tape — it *underperformed a
rising market by roughly 2.3 points*. That matters for how to read it: there
is no market excuse available.

**Read it as evidence about the research gap, exactly as predicted.** The
2026-09-04 entry below said to read a poor result from this batch as
evidence about the seven unresearched names rather than about the method,
and the outcome cooperates: AXON -12.7% (called a "pullback" while trading
below its 20d SMA), EXPE -8.4%, ESTC -6.3%, U -4.1% (called "not
distribution" at 0.50 up/down volume), BX -3.8% (live private-credit
redemption story, unmentioned). The two names `technicals.py` explicitly
contradicted were the single worst and the fourth worst in the book. The
standing lessons about the news gate and checking the thesis against the
tape are now paid for twice over — **treat them as hard rules, not
aspirations.**

**Sizing passed again — second data point.** Conviction/volatility weighting
returned -1.89% against -2.18% equal-weighted, **+0.29 pts**. Prior batch
was +0.82 pts. Two for two. No reason to touch `MAX_WEIGHT` or
`CONVICTION_POWER`.

**Conviction inverted, and this is now the pattern to watch.** This batch:
4s -3.01% (n=4), 3s -2.23% (n=13), 2s +1.86% (n=1). Prior batch: 4s -1.0%,
3s -0.4%, 2s -5.1%. Across both, **the 4-bucket has been the worst or
near-worst bucket twice running** (n=7 total). One inversion is variance;
two consecutive is worth naming, but seven picks is far below the 5-batch /
40-pick threshold the process sets for touching a constant, so **nothing is
being changed this cycle.** The honest read is that a "4" has been going to
names with the loudest recent move rather than the cleanest setup — the
2026-08-31 4s were AXON, EXPE, BX, CRM. Adjusting *judgment* rather than
arithmetic: this cycle, reserve 4 for names where the catalyst is dated and
still ahead, and refuse to award it on the strength of a move that has
already happened.

**Setup types, first cycle where the labels mean anything.** pullback -2.52%
(n=12), post-earnings drift -1.10% (n=3), breakout -0.80% (n=2),
relative-strength continuation -4.14% (n=1). The pullback bucket dominated
the book and dragged it. Caveat that at least two of those "pullbacks" were
misclassified breakdowns, so the label's poor showing is partly a research
failure wearing a setup's name. Sample is one batch — carry it as a
question into the next few cycles, not a rule.

**Nothing changed in code or constants this cycle.**

---

## 2026-09-04 — Everything learned so far, and why the record restarts here

**Read this before drawing any conclusion from the two logged batches.**
The process changed materially on 2026-09-04. Both batches in `pick_log.csv`
were *selected* under earlier versions of it, so neither is a clean test of
the process that runs from now on. The first clean test is the batch
created 2026-09-08.

### What the record actually holds

| Batch | Picks | Status | Result |
|---|---|---|---|
| 2026-08-24 | 12 | graded | avg -1.73%; portfolio **-0.30%** on capital (35% cash) vs **-1.12%** equal-weighted |
| 2026-08-31 | 18 | grades on the next run | window closed 2026-09-04 |

### What the graded batch showed

**Sizing earned its keep.** Conviction/volatility weighting returned -0.30%
against -1.12% equal-weighted across the same names — **+0.82 pts**. That
is the diagnostic that most directly justifies the whole weighting scheme,
and on its one data point it passed.

**Conviction was directionally right at the extremes, muddled in the
middle.** 2s returned -5.1%, 3s -0.4%, 4s -1.0%. The speculative bucket was
where the damage landed — AMLX, VOYG and RDW all scored 2 and all lost
5-9% — but 3s edged out 4s. At three picks per bucket that is noise. The
thing to watch across cycles is whether the 2-bucket keeps being the drag;
if it does, the honest response is to stop including 2s rather than to
re-weight them.

**Two caveats that make this the weakest calibration point the log will
ever have.** Its conviction scores were reconstructed after the fact rather
than assigned live, so they carry hindsight the process is designed to
exclude. And its setup labels are meaningless for comparison: that batch
was screened mid-session, VolRatio median came in at **0.28** against a
healthy ~1.0, so `breakout` (needs ≥1.5) fired once in sixty rows while
`pullback` (needs ≤0.9) fired fifty times. Seven of twelve picks are
labelled some flavour of "pullback" by accident of the clock. Draw nothing
about setup-type performance from it.

### What changed on 2026-09-04

- **Grading is open-to-close and nothing else** — bought at the open of the
  week's first trading day, sold at the close of its last. No stops, no
  fills, no record of what was actually traded, nothing the user reports.
  The log measures *selection*.
- **The window is the trading week**, holidays included in the definition:
  Labor Day week runs Tue-Fri, Good Friday week Mon-Thu.
- **Max Buy and stop losses were removed entirely.** The table is the whole
  instruction. A useful side effect: the graded model is now exactly the
  user's routine, so the log and the account describe the same thing.
- **The run window is the non-trading hours** between one week's close and
  the next week's open, resolved from the clock by `upcoming_week_window()`.
- **`research_brief.py` and `technicals.py` were added**, plus a hard gate
  requiring a news check on every finalist — both in response to the
  research failure recorded in the standing lessons above.

**Comparability:** the two batches remain directly comparable on returns
despite the change, because the 2026-08-24 batch had no stop fires and no
skipped entries, so its graded returns were already open-to-close. The
migration was a rename, not a recomputation. Conviction calibration can be
read across both — carefully, given the reconstruction caveat.

**What to expect from the 2026-08-31 batch when it grades.** Its conviction
scores *were* assigned live, so it is a genuine calibration point. But it
is also the batch with the research gap: seven of eighteen names, 38.9% of
capital, went in with no news check. Read a poor result as evidence about
that gap rather than about the method, and a good one with the same
suspicion.
