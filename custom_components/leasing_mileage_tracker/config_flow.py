"""Config flow for Leasing Mileage Tracker."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import callback
from homeassistant.helpers.selector import selector
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import (
    CONF_ACTUAL_END_DATE,
    CONF_CONTRACT_END_DATE,
    CONF_CONTRACT_START_DATE,
    CONF_CONTRACT_TOTAL_KM,
    CONF_OVERAGE_RATE_SEK_PER_MIL,
    CONF_PICKUP_ODOMETER_KM,
    CONF_SOURCE_ENTITY_ID,
    CONF_UNDERAGE_REFUND_MAX_MIL,
    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DEFAULT_NAME,
    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
    DOMAIN,
)

_ALLOWED_STATE_CLASSES = {"total", "total_increasing"}
_STATE_CLASS_ATTR = "state_class"
_ALLOWED_DISTANCE_UNITS = {
    "km",
    "kilometer",
    "kilometers",
    "mi",
    "mile",
    "miles",
    "m",
    "meter",
    "meters",
}


def _parse_date_value(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return dt_util.parse_date(value)
    return None


def _normalize_unit(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().lower()


class LeasingMileageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Leasing Mileage Tracker."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        errors: dict[str, str] = {}

        if user_input is not None:
            source_entity_id = str(user_input[CONF_SOURCE_ENTITY_ID])
            source_state = self.hass.states.get(source_entity_id)
            if source_state is None:
                errors["base"] = "source_unavailable"
            else:
                try:
                    float(source_state.state)
                except (TypeError, ValueError):
                    errors["base"] = "invalid_numeric_state"

                state_class = source_state.attributes.get(_STATE_CLASS_ATTR)
                if state_class not in _ALLOWED_STATE_CLASSES:
                    errors["base"] = "invalid_state_class"

                normalized_unit = _normalize_unit(
                    source_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
                )
                if normalized_unit not in _ALLOWED_DISTANCE_UNITS:
                    errors["base"] = "invalid_unit"

            start_date = _parse_date_value(user_input.get(CONF_CONTRACT_START_DATE))
            end_date = _parse_date_value(user_input.get(CONF_CONTRACT_END_DATE))
            if start_date is None or end_date is None or end_date < start_date:
                errors["base"] = "invalid_dates"

            if not errors:
                await self.async_set_unique_id(source_entity_id)
                self._abort_if_unique_id_configured()

                data = {
                    "name": str(user_input.get("name", DEFAULT_NAME)),
                    CONF_SOURCE_ENTITY_ID: source_entity_id,
                    CONF_CONTRACT_START_DATE: start_date.isoformat(),
                    CONF_CONTRACT_END_DATE: end_date.isoformat(),
                    CONF_CONTRACT_TOTAL_KM: float(user_input[CONF_CONTRACT_TOTAL_KM]),
                    CONF_PICKUP_ODOMETER_KM: float(user_input[CONF_PICKUP_ODOMETER_KM]),
                    CONF_OVERAGE_RATE_SEK_PER_MIL: float(
                        user_input[CONF_OVERAGE_RATE_SEK_PER_MIL]
                    ),
                    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL: float(
                        user_input[CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL]
                    ),
                    CONF_UNDERAGE_REFUND_MAX_MIL: float(
                        user_input[CONF_UNDERAGE_REFUND_MAX_MIL]
                    ),
                }
                return self.async_create_entry(title=data["name"], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("name", default=DEFAULT_NAME): str,
                    vol.Required(CONF_SOURCE_ENTITY_ID): selector(
                        {
                            "entity": {
                                "multiple": False,
                                "filter": {"domain": ["sensor"]},
                            }
                        }
                    ),
                    vol.Required(CONF_CONTRACT_START_DATE): selector({"date": {}}),
                    vol.Required(CONF_CONTRACT_END_DATE): selector({"date": {}}),
                    vol.Required(CONF_CONTRACT_TOTAL_KM, default=45000): selector(
                        {
                            "number": {
                                "min": 1,
                                "max": 1000000,
                                "step": 1,
                                "mode": "box",
                                "unit_of_measurement": "km",
                            }
                        }
                    ),
                    vol.Required(CONF_PICKUP_ODOMETER_KM, default=0): selector(
                        {
                            "number": {
                                "min": 0,
                                "max": 10000000,
                                "step": 1,
                                "mode": "box",
                                "unit_of_measurement": "km",
                            }
                        }
                    ),
                    vol.Required(CONF_OVERAGE_RATE_SEK_PER_MIL, default=11): selector(
                        {
                            "number": {
                                "min": 0,
                                "max": 10000,
                                "step": 0.1,
                                "mode": "box",
                                "unit_of_measurement": "SEK/mil",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                        default=DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                    ): selector(
                        {
                            "number": {
                                "min": 0,
                                "max": 10000,
                                "step": 0.1,
                                "mode": "box",
                                "unit_of_measurement": "SEK/mil",
                            }
                        }
                    ),
                    vol.Required(
                        CONF_UNDERAGE_REFUND_MAX_MIL,
                        default=DEFAULT_UNDERAGE_REFUND_MAX_MIL,
                    ): selector(
                        {
                            "number": {
                                "min": 0,
                                "max": 10000,
                                "step": 1,
                                "mode": "box",
                                "unit_of_measurement": "mil",
                            }
                        }
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        if entry is None:
            return self.async_abort(reason="entry_not_found")

        errors: dict[str, str] = {}

        default_name = str(entry.data.get("name", DEFAULT_NAME))
        default_total = float(
            entry.options.get(
                CONF_CONTRACT_TOTAL_KM, entry.data[CONF_CONTRACT_TOTAL_KM]
            )
        )
        default_rate = float(
            entry.options.get(
                CONF_OVERAGE_RATE_SEK_PER_MIL,
                entry.data[CONF_OVERAGE_RATE_SEK_PER_MIL],
            )
        )
        default_underage_rate = float(
            entry.options.get(
                CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                entry.data.get(
                    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                ),
            )
        )
        default_underage_max_mil = float(
            entry.options.get(
                CONF_UNDERAGE_REFUND_MAX_MIL,
                entry.data.get(
                    CONF_UNDERAGE_REFUND_MAX_MIL,
                    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
                ),
            )
        )
        default_actual_end = entry.options.get(CONF_ACTUAL_END_DATE)

        if user_input is not None:
            actual_end_raw = user_input.get(CONF_ACTUAL_END_DATE)
            actual_end = _parse_date_value(actual_end_raw) if actual_end_raw else None

            start_date = _parse_date_value(entry.data[CONF_CONTRACT_START_DATE])
            end_date = _parse_date_value(entry.data[CONF_CONTRACT_END_DATE])
            if actual_end and (
                start_date is None
                or end_date is None
                or actual_end < start_date
                or actual_end > end_date
            ):
                errors["base"] = "invalid_actual_end"

            if not errors:
                new_data = dict(entry.data)
                new_data["name"] = str(user_input.get("name", default_name))

                new_options = dict(entry.options)
                new_options[CONF_CONTRACT_TOTAL_KM] = float(
                    user_input[CONF_CONTRACT_TOTAL_KM]
                )
                new_options[CONF_OVERAGE_RATE_SEK_PER_MIL] = float(
                    user_input[CONF_OVERAGE_RATE_SEK_PER_MIL]
                )
                new_options[CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL] = float(
                    user_input[CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL]
                )
                new_options[CONF_UNDERAGE_REFUND_MAX_MIL] = float(
                    user_input[CONF_UNDERAGE_REFUND_MAX_MIL]
                )
                if actual_end is not None:
                    new_options[CONF_ACTUAL_END_DATE] = actual_end.isoformat()
                else:
                    new_options.pop(CONF_ACTUAL_END_DATE, None)
                new_options["name"] = str(user_input.get("name", default_name))

                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    options=new_options,
                    reason="reconfigured",
                )

        schema_data: dict[Any, Any] = {
            vol.Optional("name", default=default_name): str,
            vol.Required(CONF_CONTRACT_TOTAL_KM, default=default_total): selector(
                {
                    "number": {
                        "min": 1,
                        "max": 1000000,
                        "step": 1,
                        "mode": "box",
                        "unit_of_measurement": "km",
                    }
                }
            ),
            vol.Required(
                CONF_OVERAGE_RATE_SEK_PER_MIL,
                default=default_rate,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 0.1,
                        "mode": "box",
                        "unit_of_measurement": "SEK/mil",
                    }
                }
            ),
            vol.Required(
                CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                default=default_underage_rate,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 0.1,
                        "mode": "box",
                        "unit_of_measurement": "SEK/mil",
                    }
                }
            ),
            vol.Required(
                CONF_UNDERAGE_REFUND_MAX_MIL,
                default=default_underage_max_mil,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 1,
                        "mode": "box",
                        "unit_of_measurement": "mil",
                    }
                }
            ),
        }

        if default_actual_end:
            schema_data[
                vol.Optional(CONF_ACTUAL_END_DATE, default=default_actual_end)
            ] = selector({"date": {}})
        else:
            schema_data[vol.Optional(CONF_ACTUAL_END_DATE)] = selector({"date": {}})

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema_data),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Return options flow handler."""
        return LeasingMileageOptionsFlowHandler(config_entry)


class LeasingMileageOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle options flow for Leasing Mileage Tracker."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        default_name = str(
            self.config_entry.options.get(
                "name",
                self.config_entry.data.get("name", DEFAULT_NAME),
            )
        )
        default_total = float(
            self.config_entry.options.get(
                CONF_CONTRACT_TOTAL_KM,
                self.config_entry.data[CONF_CONTRACT_TOTAL_KM],
            )
        )
        default_rate = float(
            self.config_entry.options.get(
                CONF_OVERAGE_RATE_SEK_PER_MIL,
                self.config_entry.data[CONF_OVERAGE_RATE_SEK_PER_MIL],
            )
        )
        default_underage_rate = float(
            self.config_entry.options.get(
                CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                self.config_entry.data.get(
                    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                    DEFAULT_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                ),
            )
        )
        default_underage_max_mil = float(
            self.config_entry.options.get(
                CONF_UNDERAGE_REFUND_MAX_MIL,
                self.config_entry.data.get(
                    CONF_UNDERAGE_REFUND_MAX_MIL,
                    DEFAULT_UNDERAGE_REFUND_MAX_MIL,
                ),
            )
        )
        default_actual_end = self.config_entry.options.get(CONF_ACTUAL_END_DATE)

        if user_input is not None:
            actual_end_raw = user_input.get(CONF_ACTUAL_END_DATE)
            actual_end = _parse_date_value(actual_end_raw) if actual_end_raw else None

            start_date = _parse_date_value(
                self.config_entry.data[CONF_CONTRACT_START_DATE]
            )
            end_date = _parse_date_value(self.config_entry.data[CONF_CONTRACT_END_DATE])
            if actual_end and (
                start_date is None
                or end_date is None
                or actual_end < start_date
                or actual_end > end_date
            ):
                errors["base"] = "invalid_actual_end"

            if not errors:
                options: dict[str, Any] = {
                    "name": str(user_input.get("name", default_name)),
                    CONF_CONTRACT_TOTAL_KM: float(user_input[CONF_CONTRACT_TOTAL_KM]),
                    CONF_OVERAGE_RATE_SEK_PER_MIL: float(
                        user_input[CONF_OVERAGE_RATE_SEK_PER_MIL]
                    ),
                    CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL: float(
                        user_input[CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL]
                    ),
                    CONF_UNDERAGE_REFUND_MAX_MIL: float(
                        user_input[CONF_UNDERAGE_REFUND_MAX_MIL]
                    ),
                }
                if actual_end is not None:
                    options[CONF_ACTUAL_END_DATE] = actual_end.isoformat()
                return self.async_create_entry(title="", data=options)

        schema_data: dict[Any, Any] = {
            vol.Optional("name", default=default_name): str,
            vol.Required(CONF_CONTRACT_TOTAL_KM, default=default_total): selector(
                {
                    "number": {
                        "min": 1,
                        "max": 1000000,
                        "step": 1,
                        "mode": "box",
                        "unit_of_measurement": "km",
                    }
                }
            ),
            vol.Required(
                CONF_OVERAGE_RATE_SEK_PER_MIL,
                default=default_rate,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 0.1,
                        "mode": "box",
                        "unit_of_measurement": "SEK/mil",
                    }
                }
            ),
            vol.Required(
                CONF_UNDERAGE_REFUND_RATE_SEK_PER_MIL,
                default=default_underage_rate,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 0.1,
                        "mode": "box",
                        "unit_of_measurement": "SEK/mil",
                    }
                }
            ),
            vol.Required(
                CONF_UNDERAGE_REFUND_MAX_MIL,
                default=default_underage_max_mil,
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 10000,
                        "step": 1,
                        "mode": "box",
                        "unit_of_measurement": "mil",
                    }
                }
            ),
        }

        if default_actual_end:
            schema_data[
                vol.Optional(CONF_ACTUAL_END_DATE, default=default_actual_end)
            ] = selector({"date": {}})
        else:
            schema_data[vol.Optional(CONF_ACTUAL_END_DATE)] = selector({"date": {}})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_data),
            errors=errors,
        )
