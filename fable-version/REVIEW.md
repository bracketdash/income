# Review of the original process, and what this version changes

Written 2026-09-13 after running the predecessor three times, reading every
script, grading 43 picks, and backtesting the screener's signals on a year
of price history. The verdict first, then the evidence, then the changes.

## Verdict

The process is well-built where it is mechanical — the calendar, the
grading model, the deliverable format, the sizing arithmetic, the
correlation diagnostic — and its documentation is unusually honest about
what a one-week horizon does and does not allow. Its problem is upstream
of all that: **the screener ranked on a signal that has no measurable
edge and rewarded a pattern that is mildly anti-predictive**, so an hour
of careful research each week was being spent choosing among names that
were, on average, no better than the liquid universe. Everything
downstream was working correctly on the wrong input.

Three batches, three losses (−0.30%, −1.89%, −2.23% on capital; cumulative
−4.4% against SPY +0.3% and QQQ +0.6% over the same weeks). Three weeks
prove nothing on their own. The backtest is what makes the diagnosis
specific rather than a complaint about the tape.

## What the record says

**43 graded picks.** Conviction was correctly ordered (4s −0.86%, 3s
−2.46%, 2s −3.34%) — the rubric ranks names, which is the one part of the
judgment layer with evidence behind it. Sizing beat equal-weight in all
three batches, but all three were down weeks, where inverse-volatility
sizing wins by construction; it is not yet validated. The `pullback`
setup label was the largest bucket (n=23) and the main drag (−2.60%),
and the only positive buckets were post-earnings setups (n=7 combined).

**Cash never fired.** Regime was scored 2 in two of three weeks — a CPI
print on the exit day, then an FOMC with a hike priced — and the book
deployed 100% both times, because the volatility target (3.0%) sat above
what a diversified book of low-ATR names measures (2.1–2.3%). "Cash is
computed, not chosen" was the design, and the computation always said
zero. The regime score was decoration.

**The research funnel, on the one week it can be measured:** the 13 picks
returned −2.45% equal-weight; the full 60-name shortlist −1.96%; the 24
names never researched −1.48%. Rejections were good at the tail (the five
worst rejected names lost 5–16%), but the 36 chosen for research were
already a worse subset than the remainder. One week; it had never been
measured before because nothing archived the shortlist.

## What the backtest says

Forty weekly rebalances (2025-10 → 2026-09), each signal computed as of the
week's last session exactly as the screener computes it, measured on the
next week's open→close return against the liquid non-downtrend universe.
Survivorship-biased (current listings only) and one year long; read the
t-stats, not the means.

| Signal | Excess/wk | t-stat | 1st half | 2nd half |
|---|---:|---:|---:|---:|
| **Breakout flag** | **+1.03** | **+2.68** | +1.67 | +0.39 |
| Old score, top 60 | +0.12 | +0.54 | +0.22 | +0.01 |
| New score, top 60 | +0.35 | +1.17 | +0.75 | −0.05 |
| Pullback flag | −0.53 | −1.54 | −1.02 | −0.05 |
| RS20 top quintile | −0.00 | −0.01 | +0.24 | −0.24 |
| Extension >10% over 20d | +0.34 | +0.94 | +0.78 | −0.10 |
| 6–1 month momentum, top decile | −0.52 | −0.95 | +1.19 | −1.12 |

The old score put 40% on 20-day relative strength (flat across all five
quintiles: +0.37, +0.22, +0.20, +0.18, +0.24), 25% on Breakout (the only
signal with |t| > 2, positive in both halves), 20% on Pullback (negative
in both halves), 15% on GapEvent (noise). Because Pullback fires on ~9% of
the universe but earned 20 score points, the shortlist was 75–83%
pullback-labelled by construction — the screen was manufacturing the
bucket that lost the most.

Honest limits of this: the reweighted top-60 is better (+0.35 vs +0.12)
but still not significant, and its second half is flat. The defensible
claims are only that Breakout is real, Pullback is not, and RS20 is
nothing. In a week with few breakouts (this one has 12), the tail of the
shortlist is filled by RS20 and is correspondingly low-information.

## Specific problems, ranked by what they cost

1. **Wrong ranking signal.** Above. Fixed: weights 0.60 / 0.25 / 0.15 /
   0.00 (Breakout / RS / Gap / Pullback), with `backtest_screen.py`
   shipped so the next change is tested, not argued.
2. **Cash mechanism vestigial.** Fixed: a hard deploy cap per regime score
   (100 / 90 / 80 / 65 / 40%), binding whenever it is tighter than the
   volatility target. Regime 2 now holds at least 35% cash. This has a
   cost in weeks that go up; that is the trade.
3. **The learning loop overreacts to single weeks and under-reacts to
   pooled patterns.** The predecessor's own last entry (mine, written the
   morning of this review) added a rule that EXTENDED costs a conviction
   point, on four names in one week. The backtest shows the extended
   bucket *outperformed*. Withdrawn, and recorded in `learnings.md` as the
   example not to repeat. Meanwhile the pullback pattern was visible in
   the pooled data for two cycles before anyone acted on it. Fixed in
   part: `review_picks.py` now prints the pooled record every run, so
   the aggregate view is unavoidable, and `PROCESS.md` requires a
   backtest before any screener constant moves.
4. **Setup labels were free text**, so the log held `pullback`,
   `post-earnings pullback`, `post-catalyst momentum`, and the
   calibration diluted across variants. Fixed: closed list, validated by
   the sizer.
5. **The events check had holes the tools could not see.** A monthly
   reporter (PGR) landed on a sell day while the screener showed its
   next date as Oct 14; an ex-dividend date (NOV) sat on an exit day; an
   acquirer (VRTX, $10B for CRNX four sessions before entry) went in at
   9.6% with no mention. Fixed: ex-dividend date now captured during
   enrichment and flagged in-window; the universe diff is printed at
   refresh with an instruction to check removals against finalists'
   acquirers; the by-hand events check is a numbered step with the
   monthly-reporter case named.
6. **Research keyword hits were treated as findings.** "merger" fired on
   a completed divestiture (FLR/NuScale) and "guidance" on a guidance
   raise (DELL). Fixed in wording only — the regexes are unchanged, the
   docs now call them prompts.
7. **Engineering.** Every script hard-coded `M:\Code\income\...`, so the
   folder could not be copied or run from elsewhere. Enrichment was
   serial with exponential backoff and took 10+ minutes per run.
   Five-letter warrant symbols (`ALOVW`) passed the name filter. There was
   no way to test a screening rule except by waiting months. Fixed:
   relative paths throughout; enrichment parallel and cached for a week
   (this run: 15 seconds); warrant/rights suffixes excluded (106 removed,
   all verified as warrants); `backtest_screen.py`.
8. **Nothing archived the shortlist or the researched set**, so the
   research hour could not be graded. Fixed: `log_picks.py` archives
   both; `review_picks.py` reports picked vs rejected vs never-researched
   every batch.

## What was right and is kept unchanged

The NYSE calendar module. Open-to-close grading with no execution data
and no way to ask for it. The one-table deliverable with a sub-100-word
paragraph and a one-line process note. Clean slate per cycle. No stops,
no limits, no conditions. The conviction rubric (now with 2s excluded by
rule, which the doc already leaned toward). Inverse-volatility sizing with
a 15% cap. Realised-correlation pairs as the concentration check. The
technicals flags — with their meaning corrected from "penalty" to
"labelling constraint". The absolute news gate. The insistence that
expected move is dispersion, not a forecast.

## What I am not confident about

- One year of backtest is one regime. The Breakout edge was +1.67 in the
  first half and +0.39 in the second. It may be decaying, or the second
  half may simply have been a harder tape for momentum. The pooled pick
  log will settle it slowly; `backtest_screen.py` can be rerun as the
  cache extends.
- The regime deploy cap will bind most weeks in a tape like this one.
  If the next several weeks are up weeks, the cap will look like a
  mistake. It is a risk-management choice, not a return forecast.
- Whether the research hour adds value at all is an open question now
  measured every week. If the picked set keeps trailing the
  never-researched remainder, the honest response is to change what the
  research does, not to do more of it.

## What the first run of this version did differently, same weekend, same data

Run against the same Friday close as the predecessor's batch: 12 names at
**35% cash** (the regime cap binding; the volatility target alone would have
deployed 100% again). The new `ExpMovePct` column exposed two pinned
cash deals (DBRG, CBZ) sitting at #11–12 on the shortlist; the pending-M&A
rule caught the SWKS/QRVO arb repricing and SPSC's buyout chatter; the
by-hand events check dropped SMMT for a data presentation on Tuesday; the
ex-dividend column flagged HPE and VG inside the window. Enrichment took
15 seconds. The funnel was 43 researched → 12 held, and both sets are
archived so next Step 0 can grade the research itself for the first time.

## Notes on my own conduct across these runs

For the record, since the learning loop depends on it: I put VRTX in a
table without mentioning its $10B acquisition; I called regime 2 three
times and shipped 0% cash each time without questioning why the
mechanism never fired; and I wrote a rule into `learnings.md` on four
names' worth of evidence hours before disproving it on 40 weeks'. The
process rules that would have caught all three existed. They are now
harder to skip.
