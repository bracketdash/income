# Learnings

Dated notes written after each Step 0 review, newest first, plus the few
standing lessons that do not fit in `PROCESS.md` as a rule. Read before
Step 3, every cycle. Nothing here changes selection automatically.

The rule for this file: name the sample size every time, and say whether a
finding changes *judgment* (allowed on one week) or *code* (five batches
and a backtest). The first three batches of the predecessor process were
lost partly to overreacting to single weeks and partly to under-reacting to
a pattern that was already visible in the pooled data.

---

## Standing lessons

- **Answering a flag in prose is not the same as heeding it.** Every
  `technicals.py` flag in the 2026-09-08 batch had a careful paragraph
  written about it; three of the four flagged names were still three of
  the four worst. The paragraph is required, but what matters is whether
  the *label* survives the flag — a BELOW20 or DISTRIB name cannot be a
  pullback no matter how the sentence is phrased.
- **A one-time flatterer is not a beat.** ANF's $4.17 "beat" was $1.75 of
  tariff refund on flat comps; NOV's EBITDA carried a $40M refund. Read
  the composition of a beat before calling anything post-earnings drift.
- **The screener's earnings field is not an events calendar.** It missed
  a monthly reporter (PGR) landing on a sell day, an ex-dividend date
  (NOV), and it says nothing about investor days or FDA dates. The
  by-hand events check in Step 3 exists because of these.
- **The universe diff is a corporate-actions feed.** Removed symbols are
  mergers closing. VRTX went into a table at 9.6% with a thesis that never
  mentioned it had just spent $10B buying CRNX — the acquirer never leaves
  the universe, so check finalists against the *buyers*.
- **Crowded, headline-driven themes get one conviction-4 slot, not
  three.** The hawkish-repricing book of 2026-09-08 had the regime call
  right (energy was the only green sector) and still lost, because the
  names chosen to *express* it (MRX −7.4%, JXN flat) did not behave like
  the call, while the mid-cap growth names the call said to avoid were held
  anyway and did the damage (RELY −15%, TARS −12%).

---

## 2026-09-13 — First run of this version (batch 2026-09-14, regime 2, 12 names, 35% cash)

Nothing to grade yet. Recording what the rebuilt tools caught on their first
pass, so the next review can judge whether the catches were worth anything:

- **Two pinned deals surfaced by the ExpMovePct column alone.** DBRG (0.4%
  expected move; $16 cash from SoftBank) and CBZ (1.0%; $55 cash from Grant
  Thornton) were the #11 and #12 rows by score — both Breakout-flagged on
  heavy volume, both dead money. The old score would have ranked them too.
- **Merger-arb repricing masquerading as strength.** SWKS +22% in five
  days and QRVO +17% were the pending $22B SWKS/QRVO combination clearing
  regulators; QRVO is the target and trades on the ratio. SPSC +11% was
  GTCR buyout chatter. All three excluded under the pending-M&A rule.
- **The events check removed SMMT** — a WCLC data presentation Sept 15,
  inside the window, on a biotech already +20% over its 20d. Neither the
  earnings field nor the headline scan would have shown it.
- **The ex-dividend column flagged HPE (Sept 17) and VG (Sept 15)** inside
  the window. Both cent-scale; both named in the theses. The predecessor
  held HPE the same week without knowing.
- **The regime deploy cap bound**: the volatility target alone would have
  deployed 100% into an FOMC hike week for the third time running; the cap
  held it to 65%.
- **Funnel:** 43 researched → 12 held. The breakout-weighted shortlist had
  only 12 Breakout names this week, so its tail was RS-ranked and thin on
  healthcare and financials; the research set was widened into that tail
  to find AVAH, INSP and ATRC. Whether that helped is now measurable.
- **Setup mix** 7 rs-continuation / 3 breakout / 2 post-earnings-drift, no
  `pullback` labels — every name is near its highs on confirming volume,
  which is what the regime call asked for.

---

## 2026-09-13 — Inherited evidence, and what this version changed because of it

This folder started with an empty pick log but not with no evidence. The
predecessor process graded 43 picks across three batches, and its price
cache allowed a 40-week backtest of every screener signal. Both are
summarised here so the reasoning behind the design is on the record.

### The 43 graded picks (three batches, all losses: −0.30%, −1.89%, −2.23% on capital; SPY +0.60%, +0.37%, −0.62% the same weeks)

- **Conviction was monotonic:** 4s −0.86% (n=11), 3s −2.46% (n=28),
  2s −3.34% (n=4). The rubric orders names correctly. It does not make
  them profitable — ordering losers is not an edge — but it is the one
  part of the judgment layer with evidence behind it, and it justified
  keeping the 1–5 rubric unchanged and excluding 2s by rule.
- **Sizing beat equal-weight three times** (+1.43, +0.29, +0.22 pts).
  All three were down weeks, where underweighting volatile names wins by
  construction. Not yet validated in an up week. Constants unchanged.
- **Setup type:** post-earnings-drift +1.38% (n=4) and post-earnings
  pullback +0.61% (n=3) were the only positive buckets; `pullback` was
  −2.60% on n=23 and was the largest bucket by far. That mattered because
  the old screener *scored* the Pullback flag (+20 points), so the
  shortlist was 75–83% pullback-labelled by construction.
- **Cash never fired.** Regime 2 produced 0% cash twice: the volatility
  target (3.0%) sat above what a diversified book of clean, low-ATR names
  measures (2.1–2.3%), so the regime score had no effect on deployment.
  This version adds a hard deploy cap per regime; regime 2 caps at 65%.
- **Research funnel (one week, n=1):** the 13 picks returned −2.45%
  equal-weight against −1.96% for the full 60-name shortlist and −1.48%
  for the 24 names never researched. Rejections were good at the tail
  (RUM −16%, HCC −7%, GPI −6% were all rejected), but the research set
  itself started in the wrong place. One week proves nothing; it is now
  measured every week (`research_funnel` in `review_picks.py`).
- **Dispersion:** in the 2026-09-08 batch, three names moved 1.3–1.8×
  their ATR-expected move; the rest stayed inside it. Event weeks widen
  realised moves beyond trailing ATR. Now tracked pooled.

### The 40-week backtest (next-week open→close vs the liquid non-downtrend universe; survivorship-biased, one year)

| Signal | Excess/wk | t | 1st half | 2nd half |
|---|---:|---:|---:|---:|
| Breakout flag | +1.03 | +2.68 | +1.67 | +0.39 |
| Old score top-60 (RS 40% / BO 25% / PB 20% / gap 15%) | +0.12 | +0.54 | +0.22 | +0.01 |
| Pullback flag | −0.53 | −1.54 | −1.02 | −0.05 |
| RS20 top quintile | −0.00 | −0.01 | +0.24 | −0.24 |
| RS20 bottom quintile | +0.12 | +0.60 | | |
| Extension >10% over 20d | +0.35 | +0.82 | | |
| 6-1 month momentum top decile | −0.52 | −0.95 | +1.19 | −1.12 |

So: the Breakout flag is the only signal with a t-stat above 2, and it
held in both halves (weaker in the second). Twenty-day relative strength —
40% of the old score — is flat across quintiles. Pullback is negative in
both halves. Extension is *not* predictive of underperformance; the
10–20%-extended bucket was in fact the best-returning one.

**Because of this, the score is now Breakout 0.60 / RS 0.25 / Gap 0.15 /
Pullback 0.00.** Re-test with `backtest_screen.py` before touching it.

### A retraction

The predecessor's last learnings entry (written 2026-09-13, on the strength
of four EXTENDED names losing in one week) added a rule that EXTENDED costs
a conviction point. The 40-week data does not support it — the extended
bucket outperformed. That rule is **withdrawn**. EXTENDED remains a
labelling constraint (it cannot be a pullback) and a dispersion warning
(expect a wider move than ATR14), not a penalty. This is exactly the
one-week overreaction the process warns about, and it is recorded here so
it is not repeated.

### Open questions to watch

- Does the Breakout edge survive in the pooled pick log, where it has so
  far been −2.31% on n=6? The backtest says yes on ~44 names/week; the
  log's six are too few to say anything.
- Does sizing still beat equal-weight in an up week?
- Does the research funnel add anything once it starts from a
  breakout-weighted shortlist rather than a pullback-weighted one?
- Is the regime deploy cap costing return in the weeks it binds? It will
  bind often; that is the point, but it has a price.
