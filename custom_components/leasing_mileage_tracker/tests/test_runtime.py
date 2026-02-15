"""Runtime tests for Leasing Mileage Tracker."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.leasing_mileage_tracker.const import (
    ATTR_ENTRY_ID,
    ATTR_NEW_ODOMETER_KM,
    ATTR_NOTE,
    CONF_CONTRACT_TOTAL_KM,
    DOMAIN,
    EVENT_OVER_QUOTA_ENTERED,
    SERVICE_REBASELINE,
)


async def _setup_entry(hass, mock_config_entry, set_odometer_state) -> None:
    set_odometer_state(10000)
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_creates_expected_entities(
    hass,
    mock_config_entry,
    set_odometer_state,
) -> None:
    await _setup_entry(hass, mock_config_entry, set_odometer_state)

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # 11 sensors + 3 binary sensors
    assert len(entries) == 14


async def test_over_quota_event_emitted_on_transition(
    hass,
    mock_config_entry,
    set_odometer_state,
) -> None:
    events: list[Event] = []

    @callback
    def _listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_OVER_QUOTA_ENTERED, _listener)

    await _setup_entry(hass, mock_config_entry, set_odometer_state)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator._event_flags["over_quota_now"] = False

    assert coordinator.data is not None
    computed = replace(coordinator.data, over_quota_now=True)
    coordinator._emit_transition_events(computed)
    await hass.async_block_till_done()

    assert events
    assert events[-1].data[ATTR_ENTRY_ID] == mock_config_entry.entry_id


async def test_rebaseline_service_adds_adjustment(
    hass,
    mock_config_entry,
    set_odometer_state,
) -> None:
    await _setup_entry(hass, mock_config_entry, set_odometer_state)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REBASELINE,
        {
            ATTR_ENTRY_ID: mock_config_entry.entry_id,
            ATTR_NEW_ODOMETER_KM: 15000,
            ATTR_NOTE: "Manual correction",
        },
        blocking=True,
    )

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator is not None
    snapshot = coordinator.diagnostics_snapshot()
    assert snapshot["adjustments"]
    assert snapshot["adjustments"][-1]["new_odometer_km"] == 15000


async def test_source_stale_binary_sensor_turns_on(
    hass,
    mock_config_entry,
    set_odometer_state,
) -> None:
    await _setup_entry(hass, mock_config_entry, set_odometer_state)

    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator._last_source_update = dt_util.utcnow() - timedelta(hours=49)
    assert coordinator._is_source_stale(dt_util.utcnow()) is True


async def test_underage_refund_is_capped_to_max_mil(
    hass,
    default_entry_data,
    set_odometer_state,
) -> None:
    entry_data = dict(default_entry_data)
    entry_data[CONF_CONTRACT_TOTAL_KM] = 200000.0
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, options={})

    await _setup_entry(hass, entry, set_odometer_state)

    coordinator = entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert coordinator.data.underage_km_capped == 5000.0
    assert coordinator.data.avoided_overage_value_sek == 2750.0
