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
