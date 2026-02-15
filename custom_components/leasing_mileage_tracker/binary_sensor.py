"""Binary sensor platform for Leasing Mileage Tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LeasingMileageConfigEntry
from .const import DOMAIN
from .coordinator import LeasingMileageCoordinator
from .models import ComputedLeaseState


@dataclass(frozen=True, kw_only=True)
class LeasingMileageBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description for leasing state."""

    value_fn: Callable[[ComputedLeaseState], bool]


BINARY_DESCRIPTIONS: tuple[LeasingMileageBinaryDescription, ...] = (
    LeasingMileageBinaryDescription(
        key="over_quota_now",
        translation_key="over_quota_now",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.over_quota_now,
    ),
    LeasingMileageBinaryDescription(
        key="projected_over_quota_end",
        translation_key="projected_over_quota_end",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.projected_over_quota_end,
    ),
    LeasingMileageBinaryDescription(
        key="source_stale",
        translation_key="source_stale",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda data: data.source_stale,
    ),
)


async def async_setup_entry(
    hass,
    entry: LeasingMileageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            LeasingMileageBinarySensor(entry, coordinator, description)
            for description in BINARY_DESCRIPTIONS
        ]
    )


class LeasingMileageBinarySensor(
    CoordinatorEntity[LeasingMileageCoordinator],
    BinarySensorEntity,
):
    """Binary sensor for computed lease status."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: LeasingMileageConfigEntry,
        coordinator: LeasingMileageCoordinator,
        description: LeasingMileageBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self.coordinator.config_name,
        )

    @property
    def is_on(self) -> bool | None:
        """Return boolean state."""
        if self.coordinator.data is None:
            return None
        return bool(self.entity_description.value_fn(self.coordinator.data))

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return stable extra attributes."""
        data = self.coordinator.data
        if data is None:
            return {
                "balance_km": None,
                "projected_overage_km": None,
                "source_stale": None,
                "last_source_update": None,
            }

        return {
            "balance_km": data.balance_km,
            "projected_overage_km": data.projected_overage_km,
            "source_stale": data.source_stale,
            "last_source_update": (
                data.last_source_update.isoformat() if data.last_source_update else None
            ),
        }
