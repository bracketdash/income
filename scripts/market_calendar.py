"""
NYSE trading calendar: which days the market is actually open.

The holding window is defined by the *week*: in at the open of its first
trading day, out at the close of its last. A Labor Day or Good Friday week
is four sessions; Thanksgiving week ends on a Friday that is a half day but
still a trading day. Counting a fixed number of business days forward would
roll a short week into the next Monday and grade a position on a day it was
never held, so the boundaries are read off a real calendar instead.

No dependency provides one here (neither pandas_market_calendars nor
exchange_calendars is installed), so the rules are spelled out below. They
are stable and known years ahead, which is what lets a window end date be
computed on Monday for the Friday that hasn't happened yet.

NYSE differs from the federal calendar in three ways, all handled below:
  - the market trades on Columbus Day and Veterans Day
  - the market closes on Good Friday, which is not a federal holiday
  - New Year's Day is not observed on a Friday when Jan 1 is a Saturday

Not modelled: early closes (1:00 PM the day after Thanksgiving, Christmas
Eve). They are still trading days with a real closing price, which is all
the grading needs. Also not modelled: unscheduled closures such as a
national day of mourning or a hurricane. Those are rare and unknowable in
advance; when one happens, the grader simply finds no bar for that date and
uses the sessions that exist.

Usage:
    from market_calendar import trading_days, week_bounds
    first, last = week_bounds("2026-09-08")   # -> Tue 09-08, Fri 09-11
"""

from datetime import time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
    USMartinLutherKingJr, USMemorialDay, USPresidentsDay, USThanksgivingDay,
    nearest_workday, sunday_to_monday,
)


class NYSEHolidayCalendar(AbstractHolidayCalendar):
    """Full-day NYSE closures."""

    rules = [
        # Jan 1 on a Saturday is NOT observed on the preceding Friday -- the
        # market trades Dec 31. Only a Sunday rolls forward to the Monday.
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        # Federal holiday only from June 2021; first observed by NYSE in 2022.
        Holiday("Juneteenth", month=6, day=19, start_date="2022-06-19",
                observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


_CALENDAR = NYSEHolidayCalendar()

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN = dtime(9, 30)


def holidays(start, end):
    """NYSE full-day closures falling in [start, end]."""
    return _CALENDAR.holidays(pd.Timestamp(start), pd.Timestamp(end))


def trading_days(start, end):
    """Every NYSE session in [start, end], inclusive, as a DatetimeIndex."""
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end < start:
        return pd.DatetimeIndex([])
    days = pd.bdate_range(start, end)  # weekdays only
    return days.difference(holidays(start, end))


def is_trading_day(day):
    day = pd.Timestamp(day).normalize()
    return len(trading_days(day, day)) > 0


def week_bounds(any_day):
    """First and last NYSE session of the calendar week containing `any_day`.

    The week is Monday-through-Sunday, so any day inside it returns the same
    pair. Returns (None, None) for the pathological case of a week with no
    sessions at all.
    """
    day = pd.Timestamp(any_day).normalize()
    monday = day - pd.Timedelta(days=day.weekday())
    days = trading_days(monday, monday + pd.Timedelta(days=6))
    if len(days) == 0:
        return None, None
    return days[0], days[-1]


def upcoming_week_window(now=None):
    """(first, last) sessions of the next week that has not begun trading.

    This is the question the screen actually asks -- "which week am I
    picking for?" -- and it has to be answered from a clock, not from a
    calendar date, because the run can happen any time between one week's
    closing bell and the next week's opening bell. Friday evening, Saturday,
    Sunday, and Monday before 9:30 all name the same upcoming week.

    The test is whether this week's first session has already opened. Once
    it has, the week is underway and the answer rolls forward:

        Fri Sep 4, 5pm   -> Tue Sep 8 - Fri Sep 11   (Labor Day week)
        Sun Sep 6        -> Tue Sep 8 - Fri Sep 11
        Mon Sep 7 (hol.) -> Tue Sep 8 - Fri Sep 11
        Mon Sep 14, 5am  -> Mon Sep 14 - Fri Sep 18  (not yet open)
        Mon Sep 14, 11am -> Mon Sep 21 - Fri Sep 25  (this week is underway)

    That last case is a run at the wrong time, not a normal one; callers
    should compare the returned first session against `now` and say so.
    """
    now = pd.Timestamp.now(tz=MARKET_TZ) if now is None else pd.Timestamp(now)
    if now.tzinfo is None:
        now = now.tz_localize(MARKET_TZ)

    first, last = week_bounds(now.date())
    started = first is not None and (
        now.date() > first.date()
        or (now.date() == first.date() and now.time() >= MARKET_OPEN))
    if started:
        next_monday = pd.Timestamp(now.date()) + pd.Timedelta(
            days=7 - pd.Timestamp(now.date()).weekday())
        first, last = week_bounds(next_monday)
    return first, last


def sessions_in_week(any_day):
    """How many sessions the week containing `any_day` holds (usually 5)."""
    day = pd.Timestamp(any_day).normalize()
    monday = day - pd.Timedelta(days=day.weekday())
    return len(trading_days(monday, monday + pd.Timedelta(days=6)))


if __name__ == "__main__":
    print("-- upcoming_week_window, from various run times --")
    for label, t in [
        ("Fri 09-04 5:00pm (after close)", "2026-09-04 17:00"),
        ("Sat 09-05 10:00am", "2026-09-05 10:00"),
        ("Sun 09-06 9:00am", "2026-09-06 09:00"),
        ("Mon 09-07 8:00am (Labor Day)", "2026-09-07 08:00"),
        ("Mon 09-14 5:00am (pre-open)", "2026-09-14 05:00"),
        ("Mon 09-14 11:00am (open!)", "2026-09-14 11:00"),
    ]:
        a, b = upcoming_week_window(t)
        print(f"  {label:32} -> {a.date()} ({a.strftime('%a')}) - "
              f"{b.date()} ({b.strftime('%a')}), {sessions_in_week(a)} sessions")

    print("\n-- week_bounds on the weeks that differ from a naive Mon-Fri --")
    for label, d in [
        ("Labor Day week 2026", "2026-09-08"),
        ("normal week 2026", "2026-08-31"),
        ("Thanksgiving 2026", "2026-11-25"),
        ("Good Friday 2026", "2026-04-01"),
        ("July 4 2026 (Sat)", "2026-06-29"),
        ("New Year 2027 (Fri)", "2027-01-01"),
        ("Christmas 2026 (Fri)", "2026-12-21"),
    ]:
        a, b = week_bounds(d)
        print(f"{label:24} {a.date()} ({a.strftime('%a')}) -> "
              f"{b.date()} ({b.strftime('%a')})  {sessions_in_week(d)} sessions")
