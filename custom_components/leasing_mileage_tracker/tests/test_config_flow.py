"""Config flow tests for Leasing Mileage Tracker."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.leasing_mileage_tracker.const import (
    CONF_CONTRACT_END_DATE,
    CONF_CONTRACT_START_DATE,
    CONF_CONTRACT_TOTAL_KM,
    CONF_OVERAGE_RATE_SEK_PER_MIL,
    CONF_PICKUP_ODOMETER_KM,
    CONF_SOURCE_ENTITY_ID,
    CONF_UNDERAGE_REFUND_MAX_MIL,
    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DEFAULT_NAME,
    DOMAIN,
)


def _valid_user_input() -> dict:
    return {
        "name": DEFAULT_NAME,
        CONF_SOURCE_ENTITY_ID: "sensor.test_odometer",
        CONF_CONTRACT_START_DATE: "2026-01-01",
        CONF_CONTRACT_END_DATE: "2028-12-31",
        CONF_CONTRACT_TOTAL_KM: 45000,
        CONF_PICKUP_ODOMETER_KM: 10000,
        CONF_OVERAGE_RATE_SEK_PER_MIL: 11,
        CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL: 5.5,
        CONF_UNDERAGE_REFUND_MAX_MIL: 500,
    }


async def test_user_step_creates_entry(hass, set_odometer_state) -> None:
    set_odometer_state(10000, unit="km", state_class="total_increasing")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM

    with patch(
        "custom_components.leasing_mileage_tracker.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            _valid_user_input(),
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SOURCE_ENTITY_ID] == "sensor.test_odometer"


async def test_user_step_rejects_invalid_state_class(hass, set_odometer_state) -> None:
    set_odometer_state(10000, unit="km", state_class="measurement")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _valid_user_input(),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_state_class"


async def test_user_step_rejects_invalid_unit(hass, set_odometer_state) -> None:
    set_odometer_state(10000, unit="kWh", state_class="total_increasing")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _valid_user_input(),
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_unit"


async def test_options_flow_saves_values(
    hass, mock_config_entry, set_odometer_state
) -> None:
    set_odometer_state(10000, unit="km", state_class="total_increasing")
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Updated car",
            CONF_CONTRACT_TOTAL_KM: 50000,
            CONF_OVERAGE_RATE_SEK_PER_MIL: 12,
            CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL: 4.4,
            CONF_UNDERAGE_REFUND_MAX_MIL: 600,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_CONTRACT_TOTAL_KM] == 50000
    assert mock_config_entry.options[CONF_OVERAGE_RATE_SEK_PER_MIL] == 12
    assert mock_config_entry.options[CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL] == 4.4
    assert mock_config_entry.options[CONF_UNDERAGE_REFUND_MAX_MIL] == 600
