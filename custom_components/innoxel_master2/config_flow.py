"""Config flow of the Innoxel Master 2 integration."""
from __future__ import annotations

import asyncio
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .client import Master2Client, Master2Error, parse_address
from .const import (
    CONF_DIMMER,
    CONF_KEY,
    CONF_KEY_DOWN,
    CONF_KEY_UP,
    CONF_OUTPUT,
    CONF_OUTPUT_DOWN,
    CONF_OUTPUT_UP,
    DEFAULT_PORT,
    DOMAIN,
    REFRESH_DELAY,
    SUBENTRY_BUTTON,
    SUBENTRY_COVER,
    SUBENTRY_DIMMER,
    SUBENTRY_LIGHT,
    SUBENTRY_SWITCH,
)

# Address kind of every address field.
ADDRESS_KINDS = {
    CONF_KEY: "I",
    CONF_KEY_UP: "I",
    CONF_KEY_DOWN: "I",
    CONF_OUTPUT: "O",
    CONF_OUTPUT_UP: "O",
    CONF_OUTPUT_DOWN: "O",
    CONF_DIMMER: "D",
}


class Master2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a Master 2 by the address of its serial device server."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and port and check that a master answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            client = Master2Client(user_input[CONF_HOST], user_input[CONF_PORT])
            try:
                await client.get_revision()
            except Master2Error:
                errors["base"] = "cannot_connect"
            finally:
                await client.close()
            if not errors:
                return self.async_create_entry(title="Innoxel Master 2", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the channel types that can be added to a master."""
        return {
            SUBENTRY_SWITCH: SwitchSubentryFlow,
            SUBENTRY_LIGHT: LightSubentryFlow,
            SUBENTRY_DIMMER: DimmerSubentryFlow,
            SUBENTRY_COVER: CoverSubentryFlow,
            SUBENTRY_BUTTON: ButtonSubentryFlow,
        }


class ChannelSubentryFlow(ConfigSubentryFlow):
    """Add or change one channel. Subclasses only list their address fields."""

    # Field name -> required. Optional fields may stay empty.
    FIELDS: dict[str, bool] = {}
    # Output field that is detected by pressing the key when left empty.
    DETECT: str | None = None

    def _schema(self) -> vol.Schema:
        fields: dict[Any, Any] = {vol.Required(CONF_NAME): cv.string}
        for name, required in self.FIELDS.items():
            marker = vol.Required if required else vol.Optional
            fields[marker(name)] = cv.string
        return vol.Schema(fields)

    async def _detect_output(self, key_text: str) -> str | None:
        """Press the key once, see which single output changed, press it back."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return None
        client: Master2Client = entry.runtime_data.client
        key = parse_address(key_text, "I")
        try:
            before = (await client.get_states()).outputs_on()
            await client.send_key(key)
            await asyncio.sleep(REFRESH_DELAY)
            after = (await client.get_states()).outputs_on()
            changed = before ^ after
            if changed:
                # Put the output back into the state it had.
                await client.send_key(key)
        except Master2Error:
            return None
        if len(changed) != 1:
            return None
        module, channel = next(iter(changed))
        return f"O{module}-{channel}"

    async def _validate(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Return the normalised channel data and the form errors."""
        data: dict[str, Any] = {}
        errors: dict[str, str] = {}
        for name in self.FIELDS:
            text = (user_input.get(name) or "").strip()
            if not text:
                continue
            try:
                data[name] = str(parse_address(text, ADDRESS_KINDS[name]))
            except ValueError:
                errors[name] = "invalid_address"
        if not errors and self.DETECT and self.DETECT not in data:
            detected = await self._detect_output(data[CONF_KEY])
            if detected is None:
                errors[self.DETECT] = "detect_failed"
            else:
                data[self.DETECT] = detected
        return data, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a channel."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._validate(user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(self._schema(), user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Change a channel."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = await self._validate(user_input)
            if not errors:
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=user_input[CONF_NAME],
                    data=data,
                )
        suggested = user_input or {CONF_NAME: subentry.title, **subentry.data}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(self._schema(), suggested),
            errors=errors,
        )


class SwitchSubentryFlow(ChannelSubentryFlow):
    """A switch: a key that toggles an output."""

    FIELDS = {CONF_KEY: True, CONF_OUTPUT: False}
    DETECT = CONF_OUTPUT


class LightSubentryFlow(ChannelSubentryFlow):
    """A light on a switch output."""

    FIELDS = {CONF_KEY: True, CONF_OUTPUT: False}
    DETECT = CONF_OUTPUT


class DimmerSubentryFlow(ChannelSubentryFlow):
    """A light on a dimmer channel."""

    FIELDS = {CONF_KEY: True, CONF_DIMMER: True}


class CoverSubentryFlow(ChannelSubentryFlow):
    """A blind with an up key and a down key."""

    FIELDS = {
        CONF_KEY_UP: True,
        CONF_KEY_DOWN: True,
        CONF_OUTPUT_UP: False,
        CONF_OUTPUT_DOWN: False,
    }


class ButtonSubentryFlow(ChannelSubentryFlow):
    """A single key, e.g. for a scene programmed in the master."""

    FIELDS = {CONF_KEY: True}
