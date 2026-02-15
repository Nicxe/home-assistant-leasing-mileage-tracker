"""Fixtures for Leasing Mileage Tracker tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.leasing_mileage_tracker.const import (
    CONF_CONTRACT_END_DATE,
    CONF_CONTRACT_START_DATE,
    CONF_CONTRACT_TOTAL_KM,
    CONF_OVERAGE_RATE_SEK_PER_MIL,
    CONF_PICKUP_ODOMETER_KM,
    CONF_SOURCE_ENTITY_ID,
    CONF_UNDERAGE_REFUND_MAX_MIL,
    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests in this package."""
    yield


@pytest.fixture
def default_entry_data() -> dict:
    return {
        "name": "My Lease Car",
        CONF_SOURCE_ENTITY_ID: "sensor.test_odometer",
        CONF_CONTRACT_START_DATE: "2026-01-01",
        CONF_CONTRACT_END_DATE: "2028-12-31",
        CONF_CONTRACT_TOTAL_KM: 45000.0,
        CONF_PICKUP_ODOMETER_KM: 10000.0,
        CONF_OVERAGE_RATE_SEK_PER_MIL: 11.0,
        CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL: 5.5,
        CONF_UNDERAGE_REFUND_MAX_MIL: 500.0,
    }


@pytest.fixture
def mock_config_entry(default_entry_data: dict) -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, data=default_entry_data, options={})


@pytest.fixture
def set_odometer_state(hass):
    def _set(
        value: float, unit: str = "km", state_class: str = "total_increasing"
    ) -> None:
        hass.states.async_set(
            "sensor.test_odometer",
            str(value),
            {
                "unit_of_measurement": unit,
                "state_class": state_class,
            },
        )

    return _set
