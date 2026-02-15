"""Diagnostics tests for Leasing Mileage Tracker."""

from __future__ import annotations

from custom_components.leasing_mileage_tracker.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_redacts_note(
    hass, mock_config_entry, set_odometer_state
) -> None:
    set_odometer_state(10000)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_rebaseline(
        new_odometer_km=12000,
        note="contains personal text",
        user_id="abc",
    )
    await hass.async_block_till_done()

    payload = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert payload["runtime"]["adjustments"]
    assert payload["runtime"]["adjustments"][-1]["note"] == "**REDACTED**"
    assert payload["runtime"]["adjustments"][-1]["user_id"] == "**REDACTED**"
