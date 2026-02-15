"""Sensor platform for Leasing Mileage Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LeasingMileageConfigEntry
from .const import DOMAIN, MIL_IN_KM
from .coordinator import LeasingMileageCoordinator
from .models import ComputedLeaseState


@dataclass(frozen=True, kw_only=True)
class LeasingMileageSensorDescription(SensorEntityDescription):
    """Leasing mileage sensor description."""

    value_fn: Callable[[ComputedLeaseState], float | None]


SENSOR_DESCRIPTIONS: tuple[LeasingMileageSensorDescription, ...] = (
    LeasingMileageSensorDescription(
        key="balance_km",
        translation_key="balance_km",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.balance_km,
        suggested_display_precision=1,
    ),
    LeasingMileageSensorDescription(
        key="balance_mil",
        translation_key="balance_mil",
        native_unit_of_measurement="mil",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.balance_km / MIL_IN_KM,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="allowed_km_today",
        translation_key="allowed_km_today",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.allowed_km_today,
        suggested_display_precision=1,
    ),
    LeasingMileageSensorDescription(
        key="used_km",
        translation_key="used_km",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.used_km,
        suggested_display_precision=1,
    ),
    LeasingMileageSensorDescription(
        key="remaining_km_to_contract_end",
        translation_key="remaining_km_to_contract_end",
        native_unit_of_measurement="km",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.remaining_km_to_contract_end,
        suggested_display_precision=1,
    ),
    LeasingMileageSensorDescription(
        key="daily_quota_km",
        translation_key="daily_quota_km",
        native_unit_of_measurement="km/day",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.daily_quota_km,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="weekly_quota_km",
        translation_key="weekly_quota_km",
        native_unit_of_measurement="km/week",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.weekly_quota_km,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="monthly_quota_km",
        translation_key="monthly_quota_km",
        native_unit_of_measurement="km/month",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.monthly_quota_km,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="current_overage_cost_sek",
        translation_key="current_overage_cost_sek",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        value_fn=lambda data: data.current_overage_cost_sek,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="projected_overage_cost_sek",
        translation_key="projected_overage_cost_sek",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        value_fn=lambda data: data.projected_overage_cost_sek,
        suggested_display_precision=2,
    ),
    LeasingMileageSensorDescription(
        key="avoided_overage_value_sek",
        translation_key="avoided_overage_value_sek",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="SEK",
        value_fn=lambda data: data.avoided_overage_value_sek,
        suggested_display_precision=2,
    ),
)


async def async_setup_entry(
    hass,
    entry: LeasingMileageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Leasing Mileage Tracker sensors from config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            LeasingMileageSensor(entry, coordinator, description)
            for description in SENSOR_DESCRIPTIONS
        ]
    )


class LeasingMileageSensor(
    CoordinatorEntity[LeasingMileageCoordinator],
    SensorEntity,
):
    """Sensor backed by computed lease state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: LeasingMileageConfigEntry,
        coordinator: LeasingMileageCoordinator,
        description: LeasingMileageSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_translation_key = description.translation_key

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared device for all entities in one entry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self.coordinator.config_name,
        )

    @property
    def native_value(self):
        """Return the state value."""
        if self.coordinator.data is None:
            return None
        value = self.entity_description.value_fn(self.coordinator.data)
        if value is None:
            return None

        precision = self.entity_description.suggested_display_precision
        if isinstance(precision, int):
            return round(float(value), precision)
        return float(value)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return stable extra attributes."""
        data = self.coordinator.data
        if data is None:
            return {
                "odometer_km": None,
                "used_km": None,
                "allowed_km_today": None,
                "balance_km": None,
                "projected_overage_km": None,
                "projected_used_km": None,
                "underage_km_capped": None,
                "underage_refund_rate_sek_per_mil": None,
                "underage_refund_max_mil": None,
                "rolling_km_per_day": None,
                "source_stale": None,
                "last_source_update": None,
                "anomaly_count": None,
                "last_anomaly": None,
            }

        return {
            "odometer_km": data.odometer_km,
            "used_km": data.used_km,
            "allowed_km_today": data.allowed_km_today,
            "balance_km": data.balance_km,
            "projected_overage_km": data.projected_overage_km,
            "projected_used_km": data.projected_used_km,
            "underage_km_capped": data.underage_km_capped,
            "underage_refund_rate_sek_per_mil": data.underage_refund_rate_sek_per_mil,
            "underage_refund_max_mil": data.underage_refund_max_mil,
            "rolling_km_per_day": data.rolling_km_per_day,
            "source_stale": data.source_stale,
            "last_source_update": (
                data.last_source_update.isoformat() if data.last_source_update else None
            ),
            "anomaly_count": data.anomaly_count,
            "last_anomaly": data.last_anomaly,
        }

    async def async_added_to_hass(self) -> None:
        """Register entity ID in coordinator."""
        await super().async_added_to_hass()
        if self.entity_id:
            self.coordinator.register_entity_id(
                self.entity_description.key, self.entity_id
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister entity ID in coordinator."""
        if self.entity_id:
            self.coordinator.unregister_entity_id(
                self.entity_description.key,
                self.entity_id,
            )
        await super().async_will_remove_from_hass()
