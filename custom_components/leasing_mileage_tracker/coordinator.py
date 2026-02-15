"""Coordinator for Leasing Mileage Tracker."""

from __future__ import annotations

from datetime import date, datetime
from dataclasses import asdict
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    ATTR_ALLOWED_KM,
    ATTR_BALANCE_KM,
    ATTR_ENTITY_ID,
    ATTR_ENTRY_ID,
    ATTR_ODOMETER_KM,
    ATTR_PROJECTED_OVERAGE_COST_SEK,
    ATTR_PROJECTED_OVERAGE_KM,
    ATTR_SOURCE_STALE,
    ATTR_TIMESTAMP,
    ATTR_USED_KM,
    BALANCE_TOLERANCE_KM,
    CONF_ACTUAL_END_DATE,
    CONF_ADJUSTMENTS,
    CONF_ANOMALY_COUNT,
    CONF_CONTRACT_END_DATE,
    CONF_CONTRACT_START_DATE,
    CONF_CONTRACT_TOTAL_KM,
    CONF_CONTRACT_VERSIONS,
    CONF_EVENT_FLAGS,
    CONF_HISTORY_POINTS,
    CONF_LAST_ANOMALY,
    CONF_LAST_SOURCE_UPDATE,
    CONF_LAST_VALID_ODOMETER_KM,
    CONF_OVERAGE_RATE_SEK_PER_MIL,
    CONF_PICKUP_ODOMETER_KM,
    CONF_SOURCE_ENTITY_ID,
    CONF_UNDERAGE_REFUND_MAX_MIL,
    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DOMAIN,
    EVENT_OVER_QUOTA_CLEARED,
    EVENT_OVER_QUOTA_ENTERED,
    EVENT_PROJECTED_OVERAGE_CLEARED,
    EVENT_PROJECTED_OVERAGE_ENTERED,
    EVENT_SOURCE_RECOVERED,
    EVENT_SOURCE_STALE,
    MAX_HISTORY_POINTS,
    METER_IN_KM,
    MILE_IN_KM,
    MIL_IN_KM,
    SOURCE_STALE_THRESHOLD,
    STALE_CHECK_INTERVAL,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .models import (
    AdjustmentRecord,
    ComputedLeaseState,
    ContractVersion,
    HistoryPoint,
    active_contract_version,
    compute_allowed_km_at,
    current_offset_km,
    current_quota_per_day,
    normalize_contract_versions,
    parse_iso_date,
    parse_iso_datetime,
    rolling_km_per_day,
    trim_adjustments,
    upsert_history_point,
)

_LOGGER = logging.getLogger(__name__)


class LeasingMileageCoordinator(DataUpdateCoordinator[ComputedLeaseState]):
    """Main runtime coordinator for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            config_entry=entry,
        )
        self.entry = entry
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY_PREFIX}{entry.entry_id}",
        )

        self._contract_versions: list[ContractVersion] = []
        self._history_points: list[HistoryPoint] = []
        self._adjustments: list[AdjustmentRecord] = []
        self._last_valid_odometer_km: float | None = None
        self._last_source_update: datetime | None = None
        self._anomaly_count: int = 0
        self._last_anomaly: dict[str, Any] | None = None
        self._event_flags: dict[str, bool | None] = {
            "over_quota_now": None,
            "projected_over_quota_end": None,
            "source_stale": None,
        }

        self._entity_ids: dict[str, str] = {}
        self._unsubs: list[CALLBACK_TYPE] = []

    @property
    def source_entity_id(self) -> str:
        return str(self.entry.data[CONF_SOURCE_ENTITY_ID])

    @property
    def contract_start_date(self) -> date:
        return parse_iso_date(str(self.entry.data[CONF_CONTRACT_START_DATE]))

    @property
    def contract_end_date(self) -> date:
        return parse_iso_date(str(self.entry.data[CONF_CONTRACT_END_DATE]))

    @property
    def pickup_odometer_km(self) -> float:
        return float(self.entry.data[CONF_PICKUP_ODOMETER_KM])

    @property
    def config_name(self) -> str:
        return str(self.entry.options.get("name", self.entry.data.get("name", DOMAIN)))

    def _desired_total_km(self) -> float:
        return float(
            self.entry.options.get(
                CONF_CONTRACT_TOTAL_KM,
                self.entry.data[CONF_CONTRACT_TOTAL_KM],
            )
        )

    def _desired_rate(self) -> float:
        return float(
            self.entry.options.get(
                CONF_OVERAGE_RATE_SEK_PER_MIL,
                self.entry.data[CONF_OVERAGE_RATE_SEK_PER_MIL],
            )
        )

    def _desired_actual_end(self) -> date | None:
        raw = self.entry.options.get(CONF_ACTUAL_END_DATE)
        if raw in (None, ""):
            return None
        return parse_iso_date(str(raw))

    def _desired_underage_refund_rate(self) -> float:
        return float(
            self.entry.options.get(
                CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                self.entry.data.get(
                    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                ),
            )
        )

    def _desired_underage_refund_max_mil(self) -> float:
        return float(
            self.entry.options.get(
                CONF_UNDERAGE_REFUND_MAX_MIL,
                self.entry.data.get(
                    CONF_UNDERAGE_REFUND_MAX_MIL,
                    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
                ),
            )
        )

    async def async_initialize(self) -> None:
        """Initialize storage, sync terms and listeners."""
        await self._async_load_storage()
        self._sync_contract_terms_with_entry()
        await self._async_save_storage()
        self._setup_listeners()
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        """Unregister listeners."""
        while self._unsubs:
            unsub = self._unsubs.pop()
            unsub()

    def register_entity_id(self, key: str, entity_id: str) -> None:
        """Register entity IDs for better event payloads."""
        self._entity_ids[key] = entity_id

    def unregister_entity_id(self, key: str, entity_id: str) -> None:
        """Unregister entity IDs when entities are removed."""
        if self._entity_ids.get(key) == entity_id:
            self._entity_ids.pop(key, None)

    def _setup_listeners(self) -> None:
        @callback
        def _source_changed(_event: Event) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        @callback
        def _midnight_tick(_now: datetime) -> None:
            self.hass.async_create_task(self._async_midnight_snapshot())

        @callback
        def _stale_tick(_now: datetime) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        self._unsubs.append(
            async_track_state_change_event(
                self.hass,
                [self.source_entity_id],
                _source_changed,
            )
        )
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                _midnight_tick,
                hour=0,
                minute=0,
                second=5,
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                _stale_tick,
                STALE_CHECK_INTERVAL,
            )
        )

    async def _async_load_storage(self) -> None:
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return

        self._contract_versions = []
        for raw in stored.get(CONF_CONTRACT_VERSIONS, []):
            if isinstance(raw, dict):
                try:
                    self._contract_versions.append(ContractVersion.from_dict(raw))
                except (TypeError, ValueError):
                    _LOGGER.debug("Skipping invalid contract version payload")

        self._history_points = []
        for raw in stored.get(CONF_HISTORY_POINTS, []):
            if isinstance(raw, dict):
                try:
                    self._history_points.append(HistoryPoint.from_dict(raw))
                except (TypeError, ValueError):
                    _LOGGER.debug("Skipping invalid history payload")

        self._adjustments = []
        for raw in stored.get(CONF_ADJUSTMENTS, []):
            if isinstance(raw, dict):
                try:
                    self._adjustments.append(AdjustmentRecord.from_dict(raw))
                except (TypeError, ValueError):
                    _LOGGER.debug("Skipping invalid adjustment payload")

        last_valid_raw = stored.get(CONF_LAST_VALID_ODOMETER_KM)
        if isinstance(last_valid_raw, (int, float)):
            self._last_valid_odometer_km = float(last_valid_raw)

        last_source_raw = stored.get(CONF_LAST_SOURCE_UPDATE)
        if isinstance(last_source_raw, str):
            try:
                self._last_source_update = parse_iso_datetime(last_source_raw)
            except ValueError:
                self._last_source_update = None

        anomaly_count = stored.get(CONF_ANOMALY_COUNT)
        if isinstance(anomaly_count, int):
            self._anomaly_count = anomaly_count

        last_anomaly = stored.get(CONF_LAST_ANOMALY)
        if isinstance(last_anomaly, dict):
            self._last_anomaly = last_anomaly

        event_flags = stored.get(CONF_EVENT_FLAGS)
        if isinstance(event_flags, dict):
            for key in self._event_flags:
                value = event_flags.get(key)
                if isinstance(value, bool) or value is None:
                    self._event_flags[key] = value

        self._contract_versions = normalize_contract_versions(self._contract_versions)
        self._adjustments = trim_adjustments(self._adjustments)
        self._history_points = sorted(self._history_points, key=lambda item: item.day)[
            -MAX_HISTORY_POINTS:
        ]

    def _sync_contract_terms_with_entry(self) -> None:
        today = dt_util.as_local(dt_util.utcnow()).date()
        desired_total = self._desired_total_km()
        desired_rate = self._desired_rate()
        desired_underage_rate = self._desired_underage_refund_rate()
        desired_underage_max_mil = self._desired_underage_refund_max_mil()
        desired_actual_end = self._desired_actual_end()

        if not self._contract_versions:
            self._contract_versions = [
                ContractVersion(
                    effective_from=self.contract_start_date,
                    start_date=self.contract_start_date,
                    end_date=self.contract_end_date,
                    actual_end_date=desired_actual_end,
                    contract_total_km=desired_total,
                    overage_rate_sek_per_mil=desired_rate,
                    underage_refund_rate_sek_per_mil=desired_underage_rate,
                    underage_refund_max_mil=desired_underage_max_mil,
                )
            ]
            return

        latest = self._contract_versions[-1]
        boundaries_changed = (
            latest.start_date != self.contract_start_date
            or latest.end_date != self.contract_end_date
        )
        terms_changed = (
            abs(latest.contract_total_km - desired_total) > 1e-9
            or abs(latest.overage_rate_sek_per_mil - desired_rate) > 1e-9
            or abs(latest.underage_refund_rate_sek_per_mil - desired_underage_rate)
            > 1e-9
            or abs(latest.underage_refund_max_mil - desired_underage_max_mil) > 1e-9
            or latest.actual_end_date != desired_actual_end
        )

        if boundaries_changed or terms_changed:
            self._contract_versions.append(
                ContractVersion(
                    effective_from=today,
                    start_date=self.contract_start_date,
                    end_date=self.contract_end_date,
                    actual_end_date=desired_actual_end,
                    contract_total_km=desired_total,
                    overage_rate_sek_per_mil=desired_rate,
                    underage_refund_rate_sek_per_mil=desired_underage_rate,
                    underage_refund_max_mil=desired_underage_max_mil,
                )
            )
            self._contract_versions = normalize_contract_versions(
                self._contract_versions
            )

    async def _async_save_storage(self) -> None:
        payload: dict[str, Any] = {
            CONF_CONTRACT_VERSIONS: [
                item.as_dict() for item in self._contract_versions
            ],
            CONF_HISTORY_POINTS: [item.as_dict() for item in self._history_points],
            CONF_ADJUSTMENTS: [item.as_dict() for item in self._adjustments],
            CONF_LAST_VALID_ODOMETER_KM: self._last_valid_odometer_km,
            CONF_LAST_SOURCE_UPDATE: (
                self._last_source_update.isoformat()
                if isinstance(self._last_source_update, datetime)
                else None
            ),
            CONF_ANOMALY_COUNT: self._anomaly_count,
            CONF_LAST_ANOMALY: self._last_anomaly,
            CONF_EVENT_FLAGS: self._event_flags,
        }
        await self._store.async_save(payload)

    async def _async_midnight_snapshot(self) -> None:
        if self._last_valid_odometer_km is not None:
            local_today = dt_util.as_local(dt_util.utcnow()).date()
            self._history_points = upsert_history_point(
                self._history_points,
                local_today,
                self._last_valid_odometer_km,
            )
            await self._async_save_storage()
        await self.async_request_refresh()

    def _expected_balance_entity_id(self) -> str:
        if entity_id := self._entity_ids.get("balance_km"):
            return entity_id
        slug = slugify(self.entry.title or self.config_name)
        return f"sensor.{slug}_balance_km"

    def _base_event_payload(self, computed: ComputedLeaseState) -> dict[str, Any]:
        return {
            ATTR_ENTRY_ID: self.entry.entry_id,
            ATTR_ENTITY_ID: self._expected_balance_entity_id(),
            ATTR_TIMESTAMP: computed.timestamp.isoformat(),
            ATTR_ODOMETER_KM: computed.odometer_km,
            ATTR_USED_KM: computed.used_km,
            ATTR_ALLOWED_KM: computed.allowed_km_today,
            ATTR_BALANCE_KM: computed.balance_km,
            ATTR_PROJECTED_OVERAGE_KM: computed.projected_overage_km,
            ATTR_PROJECTED_OVERAGE_COST_SEK: computed.projected_overage_cost_sek,
            ATTR_SOURCE_STALE: computed.source_stale,
        }

    def _fire_event(self, event_type: str, computed: ComputedLeaseState) -> None:
        self.hass.bus.async_fire(event_type, self._base_event_payload(computed))

    def _emit_transition_events(self, computed: ComputedLeaseState) -> None:
        previous_over = self._event_flags.get("over_quota_now")
        if previous_over is not None and previous_over != computed.over_quota_now:
            self._fire_event(
                EVENT_OVER_QUOTA_ENTERED
                if computed.over_quota_now
                else EVENT_OVER_QUOTA_CLEARED,
                computed,
            )
        self._event_flags["over_quota_now"] = computed.over_quota_now

        previous_projected = self._event_flags.get("projected_over_quota_end")
        if (
            previous_projected is not None
            and previous_projected != computed.projected_over_quota_end
        ):
            self._fire_event(
                EVENT_PROJECTED_OVERAGE_ENTERED
                if computed.projected_over_quota_end
                else EVENT_PROJECTED_OVERAGE_CLEARED,
                computed,
            )
        self._event_flags["projected_over_quota_end"] = (
            computed.projected_over_quota_end
        )

        previous_stale = self._event_flags.get("source_stale")
        if previous_stale is not None and previous_stale != computed.source_stale:
            self._fire_event(
                EVENT_SOURCE_STALE if computed.source_stale else EVENT_SOURCE_RECOVERED,
                computed,
            )
        self._event_flags["source_stale"] = computed.source_stale

    def _convert_to_km(self, value: float, unit_raw: str | None) -> float | None:
        if unit_raw is None:
            return None

        unit = unit_raw.strip().lower()
        if unit in {
            str(UnitOfLength.KILOMETERS).lower(),
            "km",
            "kilometer",
            "kilometers",
        }:
            return value
        if unit in {str(UnitOfLength.MILES).lower(), "mi", "mile", "miles"}:
            return value * MILE_IN_KM
        if unit in {str(UnitOfLength.METERS).lower(), "m", "meter", "meters"}:
            return value * METER_IN_KM
        return None

    def _read_source_odometer_km(self) -> float | None:
        state = self.hass.states.get(self.source_entity_id)
        if state is None:
            return None

        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None

        try:
            raw_value = float(state.state)
        except (TypeError, ValueError):
            return None

        unit_raw = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if not isinstance(unit_raw, str):
            return None

        return self._convert_to_km(raw_value, unit_raw)

    def _update_last_valid_odometer(self, now: datetime) -> None:
        source_km = self._read_source_odometer_km()
        if source_km is None:
            return

        offset_km = current_offset_km(self._adjustments, now)
        effective_km = source_km + offset_km

        if self._last_valid_odometer_km is not None and effective_km < (
            self._last_valid_odometer_km - 1e-9
        ):
            self._anomaly_count += 1
            self._last_anomaly = {
                "timestamp": now.isoformat(),
                "incoming_odometer_km": effective_km,
                "previous_odometer_km": self._last_valid_odometer_km,
                "source_entity_id": self.source_entity_id,
            }
            _LOGGER.warning(
                "Ignoring lower odometer value %.3f km (previous %.3f km)",
                effective_km,
                self._last_valid_odometer_km,
            )
            return

        self._last_valid_odometer_km = effective_km
        self._last_source_update = now

    def _is_source_stale(self, now: datetime) -> bool:
        if self._last_source_update is None:
            return True
        return (now - self._last_source_update) > SOURCE_STALE_THRESHOLD

    def _build_computed_state(self, now: datetime) -> ComputedLeaseState:
        local_today = dt_util.as_local(now).date()

        if not self._contract_versions:
            raise HomeAssistantError("No contract versions available")

        active_contract = active_contract_version(self._contract_versions, local_today)

        used_km = 0.0
        if self._last_valid_odometer_km is not None:
            used_km = max(self._last_valid_odometer_km - self.pickup_odometer_km, 0.0)

        allowed_km_today = compute_allowed_km_at(self._contract_versions, local_today)
        balance_km = used_km - allowed_km_today

        contract_total_km = active_contract.contract_total_km
        rate_sek_per_mil = active_contract.overage_rate_sek_per_mil
        underage_rate_sek_per_mil = active_contract.underage_refund_rate_sek_per_mil
        underage_refund_max_mil = max(active_contract.underage_refund_max_mil, 0.0)
        remaining_km = contract_total_km - used_km

        daily_quota_km = current_quota_per_day(self._contract_versions, local_today)
        weekly_quota_km = daily_quota_km * 7
        monthly_quota_km = daily_quota_km * 30

        contract_end = active_contract.effective_end_date
        remaining_days = max((contract_end - local_today).days, 0)

        rolling_per_day = rolling_km_per_day(
            self._history_points,
            local_today,
            self._last_valid_odometer_km,
            self.contract_start_date,
            used_km,
        )
        projected_used_km = used_km + (rolling_per_day * remaining_days)
        projected_overage_km = max(projected_used_km - contract_total_km, 0.0)

        current_overage_cost_sek = (max(balance_km, 0.0) / MIL_IN_KM) * rate_sek_per_mil
        projected_overage_cost_sek = (
            projected_overage_km / MIL_IN_KM
        ) * rate_sek_per_mil
        underage_km_capped = min(
            max(-balance_km, 0.0),
            underage_refund_max_mil * MIL_IN_KM,
        )
        avoided_overage_value_sek = (
            underage_km_capped / MIL_IN_KM
        ) * underage_rate_sek_per_mil

        over_quota_now = balance_km > BALANCE_TOLERANCE_KM
        projected_over_quota_end = projected_overage_km > 0.0
        source_stale = self._is_source_stale(now)

        return ComputedLeaseState(
            timestamp=now,
            odometer_km=self._last_valid_odometer_km,
            used_km=used_km,
            allowed_km_today=allowed_km_today,
            balance_km=balance_km,
            remaining_km_to_contract_end=remaining_km,
            daily_quota_km=daily_quota_km,
            weekly_quota_km=weekly_quota_km,
            monthly_quota_km=monthly_quota_km,
            current_overage_cost_sek=current_overage_cost_sek,
            projected_overage_cost_sek=projected_overage_cost_sek,
            avoided_overage_value_sek=avoided_overage_value_sek,
            underage_km_capped=underage_km_capped,
            projected_overage_km=projected_overage_km,
            projected_used_km=projected_used_km,
            rolling_km_per_day=rolling_per_day,
            active_contract_total_km=contract_total_km,
            overage_rate_sek_per_mil=rate_sek_per_mil,
            underage_refund_rate_sek_per_mil=underage_rate_sek_per_mil,
            underage_refund_max_mil=underage_refund_max_mil,
            over_quota_now=over_quota_now,
            projected_over_quota_end=projected_over_quota_end,
            source_stale=source_stale,
            last_source_update=self._last_source_update,
            anomaly_count=self._anomaly_count,
            last_anomaly=self._last_anomaly,
        )

    async def _async_update_data(self) -> ComputedLeaseState:
        now = dt_util.utcnow()
        self._update_last_valid_odometer(now)

        computed = self._build_computed_state(now)
        self._emit_transition_events(computed)
        await self._async_save_storage()
        return computed

    async def async_rebaseline(
        self,
        *,
        new_odometer_km: float,
        note: str | None,
        user_id: str | None,
    ) -> None:
        """Apply forward-only correction offset."""
        now = dt_util.utcnow()
        source_km = self._read_source_odometer_km()

        if source_km is None:
            if self._last_valid_odometer_km is None:
                raise HomeAssistantError("No valid odometer data available")
            source_km = self._last_valid_odometer_km - current_offset_km(
                self._adjustments,
                now,
            )

        delta_km = float(new_odometer_km) - float(source_km)
        self._adjustments = trim_adjustments(
            self._adjustments
            + [
                AdjustmentRecord(
                    timestamp=now,
                    delta_km=delta_km,
                    new_odometer_km=float(new_odometer_km),
                    note=note,
                    user_id=user_id,
                )
            ]
        )

        await self._async_save_storage()
        await self.async_request_refresh()

    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Return bounded diagnostics payload."""
        history = [item.as_dict() for item in self._history_points[-90:]]
        adjustments = [item.as_dict() for item in self._adjustments[-30:]]
        versions = [item.as_dict() for item in self._contract_versions]

        return {
            "entry_id": self.entry.entry_id,
            "source_entity_id": self.source_entity_id,
            "contract_versions": versions,
            "history_points": history,
            "adjustments": adjustments,
            "last_valid_odometer_km": self._last_valid_odometer_km,
            "last_source_update": (
                self._last_source_update.isoformat()
                if self._last_source_update
                else None
            ),
            "anomaly_count": self._anomaly_count,
            "last_anomaly": self._last_anomaly,
            "event_flags": self._event_flags,
            "latest_computed": (
                {
                    **asdict(self.data),
                    "timestamp": self.data.timestamp.isoformat(),
                    "last_source_update": (
                        self.data.last_source_update.isoformat()
                        if self.data.last_source_update
                        else None
                    ),
                }
                if self.data
                else None
            ),
        }
