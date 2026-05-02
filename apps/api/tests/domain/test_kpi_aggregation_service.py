"""Unit tests for the KPI aggregation service (Story 5.4).

These are pure unit tests — no database connection required.
The domain conftest.py already overrides the `db` fixture with a no-op.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.domain.reporting.kpi_aggregation_service import (
    _compute_kpi,
    _merge_kpis,
    _zero_kpi,
    get_kpi_summary,
    get_kpi_trend,
)

# ---------------------------------------------------------------------------
# _compute_kpi — derived metric correctness and zero-division safety
# _compute_kpi(contacts, signals, qualified, bookings, errors, sla_met, sla_breached)
# Returns: contacts_processed, signal_yield_rate, conversion_rate,
#          booking_sla_compliance_pct, provider_errors
# ---------------------------------------------------------------------------


def test_compute_kpi_normal() -> None:
    result = _compute_kpi(100, 40, 20, 10, 0, 8, 2)
    assert result["signal_yield_rate"] == pytest.approx(40.0)
    assert result["conversion_rate"] == pytest.approx(50.0)
    assert result["booking_sla_compliance_pct"] == pytest.approx(80.0)
    assert result["contacts_processed"] == 100


def test_compute_kpi_zero_contacts_no_division_error() -> None:
    result = _compute_kpi(0, 0, 0, 0, 0, 0, 0)
    assert result["signal_yield_rate"] == 0.0
    assert result["conversion_rate"] == 0.0


def test_compute_kpi_zero_sla_total_no_division_error() -> None:
    result = _compute_kpi(10, 0, 0, 0, 0, 0, 0)
    assert result["booking_sla_compliance_pct"] is None


def test_compute_kpi_full_compliance() -> None:
    result = _compute_kpi(50, 50, 50, 50, 0, 50, 0)
    assert result["booking_sla_compliance_pct"] == pytest.approx(100.0)
    assert result["signal_yield_rate"] == pytest.approx(100.0)
    assert result["conversion_rate"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# _merge_kpis — combines two computed KPI dicts (weighted-average rates)
# ---------------------------------------------------------------------------


def test_merge_kpis_sums_contacts() -> None:
    a = _compute_kpi(10, 5, 3, 1, 0, 1, 0)
    b = _compute_kpi(20, 10, 6, 2, 0, 2, 1)
    merged = _merge_kpis(a, b)
    assert merged["contacts_processed"] == 30


def test_merge_kpis_weighted_signal_yield() -> None:
    # a: 50% yield on 100 contacts; b: 10% yield on 100 contacts → merged 30%
    a = _compute_kpi(100, 50, 0, 0, 0, 0, 0)
    b = _compute_kpi(100, 10, 0, 0, 0, 0, 0)
    merged = _merge_kpis(a, b)
    assert merged["signal_yield_rate"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# get_kpi_summary — period-over-period delta
# ---------------------------------------------------------------------------


def test_get_kpi_summary_returns_three_keys() -> None:
    mock_session = MagicMock()
    start = date.today() - timedelta(days=30)
    end = date.today()

    with (
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
            return_value=_compute_kpi(100, 40, 20, 10, 0, 8, 2),
        ),
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_today_live",
            return_value=_zero_kpi(),
        ),
    ):
        result = get_kpi_summary(mock_session, "ws-test", start, end, "weekly")

    assert "current_period" in result
    assert "prior_period" in result
    assert "delta_pct" in result


def test_get_kpi_summary_delta_positive_when_current_higher() -> None:
    mock_session = MagicMock()
    start = date.today() - timedelta(days=30)
    end = date.today()

    current = _compute_kpi(200, 0, 0, 0, 0, 0, 0)
    prior = _compute_kpi(100, 0, 0, 0, 0, 0, 0)

    with (
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
            side_effect=[current, prior],
        ),
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_today_live",
            return_value=_zero_kpi(),
        ),
    ):
        result = get_kpi_summary(mock_session, "ws-test", start, end, "weekly")

    # delta should be positive (current > prior)
    assert result["delta_pct"]["contacts_processed"] > 0


def test_get_kpi_summary_delta_none_when_prior_zero() -> None:
    """When prior period is all zeros, delta should be None (no division error)."""
    mock_session = MagicMock()
    start = date.today() - timedelta(days=30)
    end = date.today()

    with (
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
            side_effect=[_compute_kpi(100, 0, 0, 0, 0, 0, 0), _zero_kpi()],
        ),
        patch(
            "app.domain.reporting.kpi_aggregation_service._agg_today_live",
            return_value=_zero_kpi(),
        ),
    ):
        result = get_kpi_summary(mock_session, "ws-test", start, end, "weekly")

    # prior is zero → delta is None (not a division error)
    assert result["delta_pct"]["contacts_processed"] is None


# ---------------------------------------------------------------------------
# get_kpi_trend — bucket count by granularity
# ---------------------------------------------------------------------------


def test_get_kpi_trend_weekly_bucket_count() -> None:
    """A 28-day range with weekly granularity should produce 4 buckets."""
    mock_session = MagicMock()
    start = date(2024, 1, 1)
    end = date(2024, 1, 28)

    with patch(
        "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
        return_value=_zero_kpi(),
    ):
        buckets = get_kpi_trend(mock_session, "ws-test", start, end, "weekly")

    assert len(buckets) == 4


def test_get_kpi_trend_monthly_bucket_count() -> None:
    """A 60-day range with monthly (30-day) granularity should produce 2 buckets."""
    mock_session = MagicMock()
    start = date(2024, 1, 1)
    end = date(2024, 3, 1)  # exactly 61 days → 3 buckets: 30+30+1

    with patch(
        "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
        return_value=_zero_kpi(),
    ):
        buckets = get_kpi_trend(mock_session, "ws-test", start, end, "monthly")

    # 30-day buckets over 60 days (Jan 1–Mar 1) → 3 buckets
    assert len(buckets) == 3


def test_get_kpi_trend_bucket_has_period_fields() -> None:
    mock_session = MagicMock()
    start = date(2024, 1, 1)
    end = date(2024, 1, 14)

    with patch(
        "app.domain.reporting.kpi_aggregation_service._agg_snapshots",
        return_value=_zero_kpi(),
    ):
        buckets = get_kpi_trend(mock_session, "ws-test", start, end, "weekly")

    assert buckets
    assert "period_start" in buckets[0]
    assert "period_end" in buckets[0]
