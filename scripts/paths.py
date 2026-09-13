"""
Where everything lives. Every script imports this, so the layout is defined
exactly once and no script writes a same-named file over another week's.

    ROOT/
      PROCESS.md            the process -- every step, in order
      learnings.md          standing lessons + a dated note after each review
      pick_log.csv          the record: what each table said, and what those names did
      scripts/              one script per step (this folder)
      runs/<batch-date>/    everything one weekly run produces, isolated by week
      .cache/               symbol directory, price cache, enrichment cache

A run is named by the first session of the week it picks for, which
market_calendar.upcoming_week_window() reads from the clock: a Friday-evening
run, a Sunday run and a Monday-pre-open run for the same week all land in the
same folder. Files inside a run folder, in the order the process makes them:

    shortlist.csv     Step 1   the screener's ranked 60
    regime.txt        Step 1   the regime snapshot
    researched.txt    Step 3   every ticker looked at, including rejections
    candidates.json   Step 3   the finalists, with conviction and thesis
    picks.json        Step 4   the sized book (feeds the log)
    table.md          Step 4   the table as printed by the sizer
    output.md         Step 5   exactly what was delivered, paragraph to process line
"""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:          # so `import scripts.paths` from the root also works
    sys.path.insert(0, str(SCRIPTS))

from market_calendar import sessions_in_week, upcoming_week_window  # noqa: E402

ROOT = SCRIPTS.parent
CACHE_DIR = ROOT / ".cache"
RUNS_DIR = ROOT / "runs"
PICK_LOG = ROOT / "pick_log.csv"

SHORTLIST = "shortlist.csv"
REGIME = "regime.txt"
RESEARCHED = "researched.txt"
CANDIDATES = "candidates.json"
PICKS = "picks.json"
TABLE = "table.md"
OUTPUT = "output.md"


def batch_date():
    """YYYY-MM-DD of the first session of the week being picked for."""
    first, _ = upcoming_week_window()
    return first.strftime("%Y-%m-%d")


def run_dir(batch=None, create=True):
    """The run folder for `batch` (default: the upcoming week)."""
    d = RUNS_DIR / (batch or batch_date())
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


if __name__ == "__main__":
    # `python scripts/paths.py` -- the first command of every run: which week,
    # how many sessions, and where this run's files will go.
    first, last = upcoming_week_window()
    print(f"WINDOW {first.date()} {first.strftime('%a')} -> {last.date()} {last.strftime('%a')} | "
          f"{sessions_in_week(first)} sessions | run folder: runs/{batch_date()}/")
