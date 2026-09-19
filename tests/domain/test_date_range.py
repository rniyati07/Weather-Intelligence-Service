"""`domain.rules.date_range` — the single source of truth for date-range
business rules, shared by the HTTP layer and `ChatOrchestrator`."""

from datetime import date

import pytest

from app.domain.rules.date_range import InvalidDateRangeError, validate_date_range

TODAY = date(2026, 8, 27)


class TestValidRanges:
    def test_single_day_within_horizon(self) -> None:
        result = validate_date_range(TODAY, TODAY, max_horizon_days=16, today=TODAY)
        assert result.start == TODAY
        assert result.end == TODAY

    def test_full_horizon_span_is_accepted(self) -> None:
        end = date(2026, 9, 11)  # 16 days ahead
        result = validate_date_range(TODAY, end, max_horizon_days=16, today=TODAY)
        assert result.end == end

    def test_range_starting_in_past_reaching_today_is_accepted(self) -> None:
        """Mixed range — not historical-only — the spec doesn't exclude it."""
        result = validate_date_range(
            date(2026, 8, 20), TODAY, max_horizon_days=16, today=TODAY
        )
        assert result.start == date(2026, 8, 20)


class TestEndBeforeStart:
    def test_reversed_range_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError) as exc_info:
            validate_date_range(
                date(2026, 9, 1), date(2026, 8, 30), max_horizon_days=16, today=TODAY
            )
        assert exc_info.value.reason == "end_before_start"


class TestHistoricalRange:
    def test_range_entirely_in_the_past_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError) as exc_info:
            validate_date_range(
                date(2026, 8, 1), date(2026, 8, 5), max_horizon_days=16, today=TODAY
            )
        assert exc_info.value.reason == "historical_range"

    def test_historical_checked_before_span_when_both_apply(self) -> None:
        """A range that is both historical AND too long — historical wins,
        since "we don't serve history" is the reason the caller can act on."""
        with pytest.raises(InvalidDateRangeError) as exc_info:
            validate_date_range(
                date(2019, 1, 1), date(2019, 12, 31), max_horizon_days=16, today=TODAY
            )
        assert exc_info.value.reason == "historical_range"


class TestSpanExceedsHorizon:
    def test_span_longer_than_horizon_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError) as exc_info:
            validate_date_range(
                TODAY, date(2026, 9, 20), max_horizon_days=16, today=TODAY
            )
        assert exc_info.value.reason in ("span_exceeds_horizon", "beyond_horizon")


class TestBeyondHorizon:
    def test_end_date_beyond_horizon_is_rejected(self) -> None:
        with pytest.raises(InvalidDateRangeError) as exc_info:
            validate_date_range(
                date(2026, 9, 10), date(2026, 9, 15), max_horizon_days=16, today=TODAY
            )
        assert exc_info.value.reason == "beyond_horizon"
        assert exc_info.value.days_ahead == (date(2026, 9, 15) - TODAY).days
