"""Diagnostics support for Leasing Mileage Tracker."""

from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {"note", "user_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    """Return diagnostics for one config entry."""
    data: dict = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        }
    }

    runtime_data = getattr(entry, "runtime_data", None)
    if runtime_data is not None:
        coordinator = runtime_data.coordinator
        data["runtime"] = coordinator.diagnostics_snapshot()

    return async_redact_data(data, TO_REDACT)
