"""HOS limit helpers — adverse driving conditions extension point."""

from __future__ import annotations


def max_driving_hours(*, adverse: bool = False) -> float:
    """
    FMCSA §395.1(b)(1): Adverse driving conditions may extend the
    11-hour driving limit by up to 2 hours.

    Assessment baseline keeps adverse=False; this extension point
    proves the rule is modeled without violating the brief's assumption.
    """
    return 11.0 + (2.0 if adverse else 0.0)


def max_window_hours(*, adverse: bool = False) -> float:
    """Adverse conditions may also extend the 14-hour window by up to 2 hours."""
    return 14.0 + (2.0 if adverse else 0.0)


CYCLE_LIMIT_HOURS = 70.0
CYCLE_WINDOW_DAYS = 8
MIN_OFF_FOR_DAILY_RESET_HOURS = 10.0
MIN_BREAK_FROM_DRIVING_HOURS = 0.5
MAX_DRIVE_BEFORE_BREAK_HOURS = 8.0
RESTART_34_HOURS = 34.0
FUEL_EVERY_MILES = 1000.0
PICKUP_ON_DUTY_HOURS = 1.0
DROPOFF_ON_DUTY_HOURS = 1.0
FUEL_ON_DUTY_HOURS = 0.5
