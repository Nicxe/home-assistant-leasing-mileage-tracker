"""Unit tests for Leasing Mileage Tracker calculation helpers."""

from __future__ import annotations

from datetime import date

from custom_components.leasing_mileage_tracker.const import (
    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
)
from custom_components.leasing_mileage_tracker.models import (
    ContractVersion,
    HistoryPoint,
    compute_allowed_km_at,
    current_quota_per_day,
    rolling_km_per_day,
    upsert_history_point,
)


def test_compute_allowed_single_version_linear() -> None:
    version = ContractVersion(
        effective_from=date(2026, 1, 1),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        actual_end_date=None,
        contract_total_km=1000,
        overage_rate_sek_per_mil=11,
        underage_refund_rate_sek_per_mil=5.5,
        underage_refund_max_mil=500,
    )

    allowed_day1 = compute_allowed_km_at([version], date(2026, 1, 1))
    allowed_day10 = compute_allowed_km_at([version], date(2026, 1, 10))

    assert allowed_day1 == 100.0
    assert allowed_day10 == 1000.0


def test_compute_allowed_versioned_terms() -> None:
    v1 = ContractVersion(
        effective_from=date(2026, 1, 1),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        actual_end_date=None,
        contract_total_km=1000,
        overage_rate_sek_per_mil=11,
        underage_refund_rate_sek_per_mil=5.5,
        underage_refund_max_mil=500,
    )
    v2 = ContractVersion(
        effective_from=date(2026, 1, 6),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        actual_end_date=None,
        contract_total_km=1200,
        overage_rate_sek_per_mil=11,
        underage_refund_rate_sek_per_mil=5.5,
        underage_refund_max_mil=500,
    )

    before_change = compute_allowed_km_at([v1, v2], date(2026, 1, 5))
    at_end = compute_allowed_km_at([v1, v2], date(2026, 1, 10))

    assert round(before_change, 3) == 500.0
    assert round(at_end, 3) == 1200.0


def test_current_quota_per_day_uses_remaining_allowance() -> None:
    version = ContractVersion(
        effective_from=date(2026, 1, 1),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        actual_end_date=None,
        contract_total_km=1000,
        overage_rate_sek_per_mil=11,
        underage_refund_rate_sek_per_mil=5.5,
        underage_refund_max_mil=500,
    )

    quota = current_quota_per_day([version], date(2026, 1, 6))
    assert round(quota, 4) == 100.0


def test_rolling_km_per_day_fallback_since_start() -> None:
    pace = rolling_km_per_day(
        history_points=[HistoryPoint(day=date(2026, 1, 1), odometer_km=10000)],
        today=date(2026, 1, 11),
        current_odometer_km=10100,
        contract_start=date(2026, 1, 1),
        used_km=100,
    )

    assert pace > 0


def test_upsert_history_point_replaces_same_day() -> None:
    points = [HistoryPoint(day=date(2026, 1, 1), odometer_km=10000)]
    updated = upsert_history_point(points, date(2026, 1, 1), 10050)

    assert len(updated) == 1
    assert updated[0].odometer_km == 10050


def test_contract_version_from_dict_defaults_underage_terms() -> None:
    version = ContractVersion.from_dict(
        {
            "effective_from": "2026-01-01",
            "start_date": "2026-01-01",
            "end_date": "2026-01-10",
            "actual_end_date": None,
            "contract_total_km": 1000,
            "overage_rate_sek_per_mil": 11,
        }
    )

    assert version.underage_refund_rate_sek_per_mil == (
        DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL
    )
    assert version.underage_refund_max_mil == DEFAULT_UNDERAGE_REFUND_MAX_MIL
