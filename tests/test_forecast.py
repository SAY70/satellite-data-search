"""Tests for the empirical revisit-pattern detection and forecasting.

These cover the logic that is easiest to get subtly wrong and hardest to
notice: the gap-pattern detector. No network or credentials needed.
"""

from datetime import date, datetime

import pandas as pd
import pytest

import sat_forecast


class TestDetectPeriod:
    def test_flat_pattern(self):
        """A satellite imaging every 8 days has period 1."""
        assert sat_forecast._detect_period([8, 8, 8, 8]) == 1

    def test_alternating_pattern(self):
        """Swath overlap produces alternating gaps, e.g. Sentinel-2's [6, 13]."""
        assert sat_forecast._detect_period([6, 13, 6, 13]) == 2

    def test_tolerates_one_day_drift(self):
        """Acquisition times drift slightly; +/-1 day still counts as a match."""
        assert sat_forecast._detect_period([8, 9]) == 1

    def test_rejects_larger_drift(self):
        """A 14-day swing is not the same pattern repeating."""
        assert sat_forecast._detect_period([3, 17]) is None

    def test_no_pattern_returns_none(self):
        assert sat_forecast._detect_period([2, 9, 30, 4]) is None

    def test_too_few_gaps_returns_none(self):
        """One gap can't establish a repeat."""
        assert sat_forecast._detect_period([5]) is None
        assert sat_forecast._detect_period([]) is None

    def test_prefers_shortest_period(self):
        """[8,8,8,8] is also consistent with period 2, but 1 is the real answer."""
        assert sat_forecast._detect_period([8, 8, 8, 8]) == 1


class TestBuildForecast:
    @staticmethod
    def _history(platform, days):
        return pd.DataFrame(
            [{"platform": platform, "id": f"scene_{d}", "time": datetime(2026, 1, d)} for d in days]
        )

    def test_projects_detected_pattern_forward(self):
        """A clean 8-day cadence should continue as 8-day predictions."""
        history = self._history("LANDSAT_8", [1, 9, 17, 25])
        out = sat_forecast.build_forecast(history, date(2026, 1, 25), horizon_days=30)

        assert list(out["predicted_datetime_utc"].dt.day) == [2, 10, 18]
        assert list(out["predicted_datetime_utc"].dt.month) == [2, 2, 2]
        assert "empirical pattern [8]" in out.iloc[0]["basis"]

    def test_respects_horizon(self):
        """Nothing should be predicted past today + horizon_days."""
        history = self._history("LANDSAT_8", [1, 9, 17, 25])
        out = sat_forecast.build_forecast(history, date(2026, 1, 25), horizon_days=10)

        assert len(out) == 1  # only 2026-02-02 falls inside 10 days
        assert out.iloc[0]["days_until"] <= 10

    def test_falls_back_to_nominal_cycle(self):
        """Too little history -> use the textbook cycle and say so."""
        history = self._history("LANDSAT_8", [1, 20])  # one irregular gap
        out = sat_forecast.build_forecast(history, date(2026, 1, 20), horizon_days=40)

        assert not out.empty
        assert "nominal 16-day cycle" in out.iloc[0]["basis"]
        assert "pattern not confirmed" in out.iloc[0]["basis"]

    def test_skips_unknown_platform(self):
        """A platform with no known nominal cycle is skipped, not crashed on."""
        history = self._history("MYSTERY-SAT-9", [1, 9, 17])
        out = sat_forecast.build_forecast(history, date(2026, 1, 17), horizon_days=30)
        assert out.empty

    def test_empty_history_returns_empty_frame_with_columns(self):
        """Callers index into these columns, so they must exist even when empty."""
        out = sat_forecast.build_forecast(pd.DataFrame(), date(2026, 1, 1), horizon_days=30)
        assert out.empty
        for col in ["platform", "predicted_datetime_utc", "days_until", "basis", "last_observed"]:
            assert col in out.columns

    def test_multiple_platforms_are_independent(self):
        history = pd.concat([
            self._history("LANDSAT_8", [1, 9, 17]),
            self._history("LANDSAT_9", [4, 12, 20]),
        ], ignore_index=True)
        out = sat_forecast.build_forecast(history, date(2026, 1, 20), horizon_days=30)

        assert set(out["platform"]) == {"LANDSAT_8", "LANDSAT_9"}


def test_every_platform_color_has_a_nominal_cycle():
    """The map legend and the forecast must agree on the platform list."""
    missing = set(sat_forecast.PLATFORM_COLORS) - set(sat_forecast.NOMINAL_REPEAT_CYCLE_DAYS)
    assert not missing, f"platforms with a colour but no nominal cycle: {missing}"
