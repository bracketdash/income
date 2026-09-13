# Weekly Swing Screen (fable-version)

A rebuilt version of the weekly allocation process in the parent folder.
Same job — one table of 10–20 stocks plus cash, held open-to-close for one
trading week — with the screener re-weighted on backtested evidence, a
regime deploy cap that actually holds cash, a research-funnel diagnostic,
and every path relative to this folder so it can be copied anywhere.

`REVIEW.md` explains what was wrong with the predecessor and what changed.

## Use

1. Open Claude Code **inside this folder** (`cd fable-version`).
2. On a weekend, say "run the weekend process".
3. Read the table. That is the whole instruction: buy every name at the
   open of the week's first session, sell at the close of its last.

## Notes

- First run downloads a year of daily bars for ~5,000 names (~10 minutes)
  and then caches them for the day. Enrichment (sector, earnings dates) is
  cached for a week.
- The pick log starts empty. The pooled diagnostics in `review_picks.py`
  become meaningful after about five batches; the process refuses to
  change any tuning constant before then.
- `backtest_screen.py` tests any screener rule on the cache. Run it before
  changing a score weight; it takes about a minute.
- Nothing here is financial advice. Paper trade until the pooled record
  says something.
