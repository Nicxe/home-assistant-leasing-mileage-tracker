"""Data models and pure calculations for Leasing Mileage Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    MAX_ADJUSTMENTS,
    MAX_HISTORY_POINTS,
    ROLLING_WINDOW_DAYS,
)


@dataclass(frozen=True, slots=True)
class ContractVersion:
    """Versioned contract terms."""

    effective_from: date
    start_date: date
    end_date: date
    actual_end_date: date | None
    contract_total_km: float
    overage_rate_sek_per_mil: float
    underage_refund_rate_sek_per_mil: float
    underage_refund_max_mil: float

    @property
    def effective_end_date(self) -> date:
        """Return the date where this version ends for quota math."""
        if self.actual_end_date is None:
            return self.end_date
        return min(self.actual_end_date, self.end_date)

    def as_dict(self) -> dict[str, Any]:
        return {
            "effective_from": self.effective_from.isoformat(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "actual_end_date": (
                self.actual_end_date.isoformat() if self.actual_end_date else None
            ),
            "contract_total_km": float(self.contract_total_km),
            "overage_rate_sek_per_mil": float(self.overage_rate_sek_per_mil),
            "underage_refund_rate_sek_per_mil": float(
                self.underage_refund_rate_sek_per_mil
            ),
            "underage_refund_max_mil": float(self.underage_refund_max_mil),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ContractVersion":
        return ContractVersion(
            effective_from=parse_iso_date(data["effective_from"]),
            start_date=parse_iso_date(data["start_date"]),
            end_date=parse_iso_date(data["end_date"]),
            actual_end_date=parse_iso_date(data["actual_end_date"])
            if data.get("actual_end_date")
            else None,
            contract_total_km=float(data["contract_total_km"]),
            overage_rate_sek_per_mil=float(data["overage_rate_sek_per_mil"]),
            underage_refund_rate_sek_per_mil=float(
                data.get(
                    "underage_refund_rate_sek_per_mil",
                    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                )
            ),
            underage_refund_max_mil=float(
                data.get("underage_refund_max_mil", DEFAULT_UNDERAGE_REFUND_MAX_MIL)
            ),
        )


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    """Daily odometer snapshot."""

    day: date
    odometer_km: float

    def as_dict(self) -> dict[str, Any]:
        return {"day": self.day.isoformat(), "odometer_km": float(self.odometer_km)}

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "HistoryPoint":
        return HistoryPoint(
            day=parse_iso_date(data["day"]),
            odometer_km=float(data["odometer_km"]),
        )


@dataclass(frozen=True, slots=True)
class AdjustmentRecord:
    """Forward-only manual odometer correction."""

    timestamp: datetime
    delta_km: float
    new_odometer_km: float
    note: str | None
    user_id: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "delta_km": float(self.delta_km),
            "new_odometer_km": float(self.new_odometer_km),
            "note": self.note,
            "user_id": self.user_id,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "AdjustmentRecord":
        return AdjustmentRecord(
            timestamp=parse_iso_datetime(data["timestamp"]),
            delta_km=float(data["delta_km"]),
            new_odometer_km=float(data["new_odometer_km"]),
            note=data.get("note"),
            user_id=data.get("user_id"),
        )


@dataclass(frozen=True, slots=True)
class ComputedLeaseState:
    """All calculated values exposed by entities and events."""

    timestamp: datetime
    odometer_km: float | None
    used_km: float
    allowed_km_today: float
    balance_km: float
    remaining_km_to_contract_end: float
    daily_quota_km: float
    weekly_quota_km: float
    monthly_quota_km: float
    current_overage_cost_sek: float
    projected_overage_cost_sek: float
    avoided_overage_value_sek: float
    underage_km_capped: float
    projected_overage_km: float
    projected_used_km: float
    rolling_km_per_day: float
    active_contract_total_km: float
    overage_rate_sek_per_mil: float
    underage_refund_rate_sek_per_mil: float
    underage_refund_max_mil: float
    over_quota_now: bool
    projected_over_quota_end: bool
    source_stale: bool
    last_source_update: datetime | None
    anomaly_count: int
    last_anomaly: dict[str, Any] | None


def parse_iso_date(raw: str) -> date:
    """Parse YYYY-MM-DD from storage/config."""
    parsed = dt_util.parse_date(raw)
    if parsed is None:
        raise ValueError(f"Invalid date value: {raw}")
    return parsed


def parse_iso_datetime(raw: str) -> datetime:
    """Parse ISO datetime and ensure tz-aware UTC fallback."""
    parsed = dt_util.parse_datetime(raw)
    if parsed is None:
        raise ValueError(f"Invalid datetime value: {raw}")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt_util.UTC)
    return parsed


def days_inclusive(start_day: date, end_day: date) -> int:
    """Return inclusive day count with floor at zero."""
    return max((end_day - start_day).days + 1, 0)


def normalize_contract_versions(
    versions: list[ContractVersion],
) -> list[ContractVersion]:
    """Sort and de-duplicate versions by effective_from keeping newest item."""
    by_day: dict[date, ContractVersion] = {v.effective_from: v for v in versions}
    return [by_day[d] for d in sorted(by_day)]


def active_contract_version(
    versions: list[ContractVersion], target_day: date
) -> ContractVersion:
    """Return active version for target_day."""
    normalized = normalize_contract_versions(versions)
    active = normalized[0]
    for version in normalized:
        if version.effective_from <= target_day:
            active = version
        else:
            break
    return active


def _segment_active_end(
    versions: list[ContractVersion],
    index: int,
) -> date:
    """End date of the currently active segment for one version."""
    current = versions[index]
    segment_end = current.effective_end_date
    if index + 1 < len(versions):
        next_start = versions[index + 1].effective_from
        segment_end = min(segment_end, next_start - timedelta(days=1))
    return segment_end


def compute_allowed_km_at(versions: list[ContractVersion], target_day: date) -> float:
    """Compute cumulative allowed km on a given day with versioning support."""
    normalized = normalize_contract_versions(versions)
    if not normalized:
        return 0.0

    allowed_total = 0.0
    cumulative_end_of_segments = 0.0

    for index, version in enumerate(normalized):
        effective_start = version.effective_from
        effective_end = version.effective_end_date
        if effective_end < effective_start:
            continue

        total_days_for_version = days_inclusive(effective_start, effective_end)
        if total_days_for_version <= 0:
            continue

        remaining_target = max(
            version.contract_total_km - cumulative_end_of_segments, 0.0
        )
        daily_rate = remaining_target / total_days_for_version

        active_segment_end = _segment_active_end(normalized, index)
        if active_segment_end < effective_start:
            continue

        full_active_days = days_inclusive(effective_start, active_segment_end)
        cumulative_end_of_segments += daily_rate * full_active_days

        if target_day < effective_start:
            continue

        segment_upto = min(target_day, active_segment_end)
        if segment_upto >= effective_start:
            active_days = days_inclusive(effective_start, segment_upto)
            allowed_total += daily_rate * active_days

    return max(allowed_total, 0.0)


def current_quota_per_day(versions: list[ContractVersion], today: date) -> float:
    """Compute current forward quota in km/day based on active contract version."""
    if not versions:
        return 0.0

    active = active_contract_version(versions, today)
    end_day = active.effective_end_date
    if today > end_day:
        return 0.0

    allowed_until_yesterday = compute_allowed_km_at(versions, today - timedelta(days=1))
    remaining_allowance = max(active.contract_total_km - allowed_until_yesterday, 0.0)
    remaining_days = days_inclusive(today, end_day)
    if remaining_days <= 0:
        return 0.0

    return remaining_allowance / remaining_days


def rolling_km_per_day(
    history_points: list[HistoryPoint],
    today: date,
    current_odometer_km: float | None,
    contract_start: date,
    used_km: float,
) -> float:
    """Compute rolling pace from daily history with fallback to since-start average."""
    by_day: dict[date, float] = {
        point.day: point.odometer_km for point in history_points
    }
    if current_odometer_km is not None:
        by_day[today] = float(current_odometer_km)

    points = [HistoryPoint(day=d, odometer_km=o) for d, o in sorted(by_day.items())]
    window_start = today - timedelta(days=ROLLING_WINDOW_DAYS)
    points_window = [point for point in points if point.day >= window_start]

    if len(points_window) >= 2:
        first = points_window[0]
        last = points_window[-1]
        span_days = (last.day - first.day).days
        delta = last.odometer_km - first.odometer_km
        if span_days > 0 and delta >= 0:
            return delta / span_days

    elapsed_days = max((today - contract_start).days, 1)
    return max(used_km, 0.0) / elapsed_days


def upsert_history_point(
    history_points: list[HistoryPoint],
    day: date,
    odometer_km: float,
) -> list[HistoryPoint]:
    """Insert or replace one daily snapshot and enforce max size."""
    by_day: dict[date, float] = {
        point.day: point.odometer_km for point in history_points
    }
    by_day[day] = float(odometer_km)
    result = [HistoryPoint(day=d, odometer_km=v) for d, v in sorted(by_day.items())]
    return result[-MAX_HISTORY_POINTS:]


def current_offset_km(adjustments: list[AdjustmentRecord], now: datetime) -> float:
    """Sum all correction offsets active at current timestamp."""
    return sum(adj.delta_km for adj in adjustments if adj.timestamp <= now)


def trim_adjustments(adjustments: list[AdjustmentRecord]) -> list[AdjustmentRecord]:
    """Bound adjustment list length in storage."""
    return sorted(adjustments, key=lambda item: item.timestamp)[-MAX_ADJUSTMENTS:]
