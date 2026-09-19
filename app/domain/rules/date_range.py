"""The one place `end >= start`, the no-history rule, and the forecast
horizon are decided (API Spec §11). Both `interface/http/dependencies.py`
(HTTP layer, all weather/narrative endpoints) and `ChatOrchestrator`
(application layer, chat) call this — neither re-implements the rules.

Pure: no clock read, `today` is always supplied by the caller.
"""

from dataclasses import dataclass
from datetime import date


class InvalidDateRangeError(Exception):
    """A date range fails a business rule.

    `reason` is a stable code (`end_before_start` | `historical_range` |
    `span_exceeds_horizon` | `beyond_horizon`) a caller can switch on without
    parsing message text; `span_days`/`days_ahead` carry the numbers behind
    the two horizon reasons so each caller can phrase its own user-facing
    copy (an HTTP `ErrorDetailSchema` and a conversational clarification
    sentence are not the same shape of text, even though they enforce the
    same rule).
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        span_days: int | None = None,
        days_ahead: int | None = None,
    ) -> None:
        self.reason = reason
        self.span_days = span_days
        self.days_ahead = days_ahead
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ValidatedDateRange:
    start: date
    end: date


def validate_date_range(
    start: date, end: date, *, max_horizon_days: int, today: date
) -> ValidatedDateRange:
    """Apply the shared cross-field date rules.

    Checked in this order deliberately: for a range like 2019-01-01 to
    2019-12-31, both "this is historical" and "this span is too long" apply
    — "we don't serve history" is the reason the caller can actually act on,
    so it is reported first rather than sending them to just shorten a range
    that would still be rejected afterward.
    """
    if end < start:
        raise InvalidDateRangeError(
            "endDate must be on or after startDate.", reason="end_before_start"
        )

    if end < today:
        raise InvalidDateRangeError(
            "Historical date ranges are not served by the forecast endpoints.",
            reason="historical_range",
        )

    span_days = (end - start).days + 1
    if span_days > max_horizon_days:
        raise InvalidDateRangeError(
            f"The requested range exceeds the maximum of {max_horizon_days} days.",
            reason="span_exceeds_horizon",
            span_days=span_days,
        )

    days_ahead = (end - today).days
    if days_ahead > max_horizon_days:
        raise InvalidDateRangeError(
            f"endDate is beyond the supported {max_horizon_days}-day forecast window.",
            reason="beyond_horizon",
            days_ahead=days_ahead,
        )

    return ValidatedDateRange(start=start, end=end)


__all__ = ["InvalidDateRangeError", "ValidatedDateRange", "validate_date_range"]
