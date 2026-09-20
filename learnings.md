# Learnings

Read before Step 3, every cycle. Four parts: **standing lessons** (rules
that have each been paid for), the **evidence base** the process is built
on (so the reasoning behind every constant stays checkable), the **open
questions** the record has not yet answered, and **dated notes** written
after each Step 0 review, newest first.

How this file stays current (Step 0b in `PROCESS.md`): a finding goes to
the highest place it qualifies for — a rule in `PROCESS.md` first, a
standing lesson second, an open question third, the dated note last. Open
questions are revisited every cycle and retired once the pooled record
settles them. Dated notes are a staging area, not an archive: at most four
are kept, and anything in them that holds up is promoted. `pick_log.csv`
and `runs/` hold the history.

The rule for every entry: name the sample size, and say whether a finding
changes *judgment* (allowed on one week) or *code* (five batches and a
backtest). Losses have come from both overreacting to single weeks and
under-reacting to patterns already visible in the pooled data.

---

## Standing lessons

- **A flag is answered by the label, not the sentence.** Every
  `technicals.py` flag must be addressed in the thesis, but writing a
  careful paragraph about an EXTENDED or DISTRIB name is not the same as
  heeding it. What matters is whether the setup label survives: a BELOW20
  or DISTRIB name cannot be a `pullback` however the sentence is phrased.
  Names called pullbacks while below their 20d SMA or on 0.50 up/down
  volume lost 13% and 4% in the same week.
- **A `pullback` label has to be earned.** Price above a rising 20d SMA
  *and* up/down volume above 1.0. Pooled, `pullback` was the largest
  bucket (n=23) and the worst (−2.60%), mostly because "drifting down
  quietly" was being labelled a pullback.
- **Extension is a label, not a penalty.** Over 40 backtested weeks the
  10–20%-over-SMA bucket was the *best*-returning extension bucket.
  EXTENDED means: not a pullback, and expect a wider move than ATR14 says.
  It does not mean cut conviction.
- **A one-time flatterer is not a beat.** A $4.17 "beat" that was $1.75 of
  tariff refund on flat comps; an EBITDA line carrying a $40M refund. Read
  what the beat was made of before calling anything post-earnings drift.
- **An expected move near zero on a name that just jumped is a pinned cash
  deal.** Two Breakout-flagged names at #11–12 on a shortlist had
  `ExpMovePct` of 0.4% and 1.0%; both were sitting at an agreed
  take-private price. Merger-arb repricing (an acquirer up 22% in five
  days on regulatory odds; the target moving on the ratio) and buyout
  chatter are the same category: exclude.
- **The earnings field is not an events calendar.** It missed a monthly
  reporter landing on a sell day, an ex-dividend on an exit day, and a
  conference data presentation on a biotech mid-window. The by-hand events
  check in Step 3 exists because of these.
- **The universe diff is a corporate-actions feed.** Removed symbols are
  mergers closing. Check finalists against the *buyers*: an acquirer never
  leaves the universe, and one went into a table at 9.6% with a thesis
  that never mentioned its $10B purchase four sessions earlier.
- **Crowded, headline-driven themes get one conviction-4 slot.** A
  hawkish-repricing book had the regime call right — energy was the only
  green sector — and still lost, because the names chosen to *express*
  it did not behave like the call, while the mid-cap growth names the call
  said to avoid were held anyway and did the damage (−15%, −12%).
- **The conviction rubric orders names in both directions of tape.** It
  was monotonic across three down weeks (4s −0.86%, 3s −2.46%, 2s −3.34%,
  n=43) and again in the first up week (4s +2.04% n=4, 3s +0.67% n=8). Four
  cycles, 55 picks, no inversion. It is the only part of the judgment layer
  with evidence behind it — which is why the rubric is kept identical week
  to week and 2s are excluded by rule rather than sized down.
- **The ATR expected move is a dispersion estimate, not a range the week
  will fill.** Over a full quiet batch the median |realised| / expected was
  0.57, with only 17% of names exceeding 1.0; in an FOMC week three names
  ran 1.3–1.8×. The error is not a constant scale — ATR reads wide when
  nothing is scheduled and tight when something is. Use it for what the
  sizer uses it for, ranking how far names travel relative to each other,
  and never as a forecast of the week's move.
- **VolRatio median is the canary.** Check it before trusting any
  volume-based flag. ~0.8–1.0 is healthy; 0.6–0.8 is a holiday lull;
  0.2–0.3 means a partial session was read as a close.
- **Cash has to be able to fire.** A volatility target alone let a
  diversified book of low-ATR names deploy 100% into CPI and FOMC weeks
  three times running, because trailing ATR does not know an event is
  coming. The regime deploy cap is what makes a 2 mean something.

---

## Evidence base (as of 2026-09-13)

### The screener's signals, backtested

Forty weekly rebalances (October 2025 → September 2026), each signal
computed as of the week's last session exactly as `swing_screen.py`
computes it, measured on the next week's open→close return against the
liquid non-downtrend universe. Survivorship-biased (current listings only)
and one year long: read the t-stats, not the means.

| Signal | Excess/wk | t | 1st half | 2nd half |
|---|---:|---:|---:|---:|
| **Breakout flag** | **+1.03** | **+2.68** | +1.67 | +0.39 |
| Score top-60 (B 0.60 / RS 0.25 / Gap 0.15 / PB 0) | +0.35 | +1.17 | +0.75 | −0.05 |
| Score top-60 with RS 0.40 / PB 0.20 instead | +0.12 | +0.54 | +0.22 | +0.01 |
| GapEvent flag | +0.16 | +0.40 | +0.70 | −0.37 |
| Pullback flag | −0.53 | −1.54 | −1.02 | −0.05 |
| RS20 top quintile | −0.00 | −0.01 | +0.24 | −0.24 |
| RS20 bottom quintile | +0.12 | +0.60 | +0.09 | +0.16 |
| Extension >10% over 20d | +0.34 | +0.94 | +0.78 | −0.10 |
| 6–1 month momentum, top decile | −0.52 | −0.95 | +1.19 | −1.12 |

RS20 is flat across all five quintiles (+0.37, +0.22, +0.20, +0.18,
+0.24). Breakout is the only signal with |t| > 2 and it held in both
halves, weaker in the second. Pullback is negative in both halves. That is
why the score weights are what they are, and why they are not changed
without `backtest_screen.py`.

### Forty-three graded picks from three earlier cycles

The pick log begins with the 2026-09-14 batch. Three earlier cycles
(batches 2026-08-24, 2026-08-31, 2026-09-08) were graded under the same
open-to-close convention; their lessons are in the standing lessons and in
`PROCESS.md`, and the numbers are kept here so the reasoning stays
checkable.

- All three lost on capital: −0.30%, −1.89%, −2.23% (SPY those weeks:
  +0.60%, +0.37%, −0.62%). Cumulative −4.4% vs SPY +0.3%.
- **Conviction was monotonic:** 4s −0.86% (n=11), 3s −2.46% (n=28),
  2s −3.34% (n=4). The rubric orders names correctly — the one part of the
  judgment layer with evidence — which is why it is unchanged and 2s are
  excluded by rule.
- **Sizing beat equal-weight three times** (+1.43, +0.29, +0.22 pts), all
  in down weeks, where underweighting volatile names wins by construction.
  Not yet validated in an up week.
- **Setup type:** post-earnings setups were the only positive buckets
  (+1.38% n=4, +0.61% n=3); `pullback` −2.60% on n=23.
- **Cash:** regime scored 2 in two of three weeks; 0% cash both times.
- **Research funnel (one week):** the 13 picks returned −2.45%
  equal-weight against −1.96% for the 60-name shortlist and −1.48% for the
  24 names never researched. Rejections were good at the tail (the five
  worst rejected names lost 5–16%); the research set itself started in the
  wrong place. Now measured every week.
- **Dispersion:** three names moved 1.3–1.8× their ATR-expected move in an
  FOMC week; the rest stayed inside it. Now tracked pooled.

---

## Open questions

What the record has not yet answered. Each one names what would settle it.
Revisited every Step 0b; retired to a rule or a standing lesson once the
pooled data settles it, or deleted if the evidence goes the other way.

- Does the Breakout edge survive in the pooled pick log? The backtest says
  yes on ~44 names/week. First batch went the other way — `breakout` picks
  −3.17% (n=3) against +1.15% for rs-continuation (n=7) — on a sample far
  too small to weigh against 40 weeks. Settled by: `breakout`-labelled picks
  vs the rest over 5+ batches.
- Does sizing still beat equal-weight in an up week? First up week in:
  it did not. Book +0.51% on capital against +0.73% equal-weight, a cost of
  0.22 pts, which is exactly what the mechanism predicts when volatile names
  lead. One of the two up weeks needed. Settled by: the second.
- Does the research funnel add anything once it starts from a
  breakout-weighted shortlist? Two cycles, both negative: picks +1.13% vs
  +4.12% never-researched and +2.35% rejected this week, and −2.45% vs
  −1.48% never-researched a cycle earlier. Picks have now trailed the
  *rejected* set too, which points at selection rather than where the set
  started. Settled by: a third batch. If it holds, change what the research
  *does* — not how much of it there is.
- Is a conviction 3 written around a hole in its own thesis worse than a
  conviction 3 that is simply a good setup with no fresh catalyst? The two
  worst names in the first batch were the two whose theses named their own
  defect — VG −12.6% ("the QatarEnergy report is chatter, not a signed
  deal") and CRGY −7.3% ("one house already calls it fully priced after a
  64% run") — while the no-catalyst 3 (ATRC) returned +5.9%. n=2, so
  suggestive only. Settled by: tagging which 3s are hole-in-thesis vs
  no-catalyst over 3+ batches. If it holds, the hole becomes a 2, and 2s
  are already excluded.
- Is the regime deploy cap costing return in the weeks it binds? First
  capped batch that has been graded cost about 0.27 pts — +0.51% at 65%
  deployed against roughly +0.78% the same book fully deployed, in a week
  that finished up. It will bind often and it has a price; the question is
  whether the event weeks it protects pay for the quiet ones it taxes.
  Settled by: book return vs the same book at 100% deployed, over 5+ capped
  batches.

## Dated notes

Newest first, one entry per Step 0 review, six lines or fewer, at most four
kept. Each says what the batch did and what was folded into the sections
above.

### 2026-09-20 — Batch 2026-09-14 graded (8W/4L, +1.13%/name)

Book +0.51% on capital vs SPY +0.60%, equal-weight +0.73%: sizing cost 0.22
pts and the 65% cap about 0.27 pts, both in an up week, both as the mechanism
predicts, so no constant moved. Conviction monotonic again (4s +2.04%, 3s
+0.67%). Funnel 43→12 trailed everything (never-researched +4.12%, rejected
+2.35%); dispersion median 0.57. Folded in: two standing lessons
(conviction-holds-in-up-tape, ATR-as-dispersion), five open questions
re-scored including a new one on hole-in-thesis 3s, and two `PROCESS.md`
rules from the 2026-09-21 run — the VolRatio canary now covers the *high*
side (an expiry week inflates every volume flag; check pre-expiry volume
instead) and the events check now warns that the in-window flags use a
10-day lookahead, not the holding window. Also fixed the sizer's cash-row
note, which asserted "an event week" whenever the regime cap bound, even
when the 2 came from breadth and no event was scheduled.

### 2026-09-13 — Batch 2026-09-14 written (regime 2, 12 names, 35% cash)

Nothing to grade yet. Funnel 43 → 12; only 12 Breakout names on the
shortlist, so the set was widened by sector into the RS tail (AVAH, INSP,
ATRC). Mix 7 rs-continuation / 3 breakout / 2 post-earnings-drift, no
`pullback`. Excluded by rule: DBRG, CBZ (pinned deals); SWKS, QRVO, SPSC
(merger repricing); SMMT (in-window data presentation). Deploy cap bound
at 65%. Folded in: pinned-deal tell, merger-repricing rule, events cases.
