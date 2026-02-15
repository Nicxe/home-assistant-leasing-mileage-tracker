"""Leasing Mileage Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
import voluptuous as vol

from .const import (
    ATTR_ENTRY_ID,
    ATTR_NEW_ODOMETER_KM,
    ATTR_NOTE,
    DOMAIN,
    PLATFORMS,
    SERVICE_REBASELINE,
)
from .coordinator import LeasingMileageCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class LeasingMileageRuntimeData:
    """Runtime objects for one config entry."""

    coordinator: LeasingMileageCoordinator


if TYPE_CHECKING:
    type LeasingMileageConfigEntry = ConfigEntry[LeasingMileageRuntimeData]
else:
    LeasingMileageConfigEntry = ConfigEntry


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_REBASELINE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_NEW_ODOMETER_KM): vol.Coerce(float),
        vol.Optional(ATTR_NOTE): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration-level services."""
    if not hass.services.has_service(DOMAIN, SERVICE_REBASELINE):

        async def _async_rebaseline(call: ServiceCall) -> None:
            entry_id = str(call.data[ATTR_ENTRY_ID])
            new_odometer_km = float(call.data[ATTR_NEW_ODOMETER_KM])
            note = call.data.get(ATTR_NOTE)

            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_entry_id",
                    translation_placeholders={"entry_id": entry_id},
                )

            if not entry.runtime_data:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entry_not_loaded",
                )

            coordinator = entry.runtime_data.coordinator
            await coordinator.async_rebaseline(
                new_odometer_km=new_odometer_km,
                note=str(note) if isinstance(note, str) and note else None,
                user_id=call.context.user_id,
            )

        hass.services.async_register(
            DOMAIN,
            SERVICE_REBASELINE,
            _async_rebaseline,
            schema=SERVICE_REBASELINE_SCHEMA,
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeasingMileageConfigEntry,
) -> bool:
    """Set up Leasing Mileage Tracker from a config entry."""
    coordinator = LeasingMileageCoordinator(hass, entry)

    try:
        await coordinator.async_initialize()
    except Exception as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = LeasingMileageRuntimeData(coordinator=coordinator)

    async def _options_update_listener(
        hass: HomeAssistant,
        updated_entry: ConfigEntry,
    ) -> None:
        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: LeasingMileageConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and entry.runtime_data:
        await entry.runtime_data.coordinator.async_shutdown()
    return unload_ok
