"""Lights of the Innoxel Master 2 integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import parse_address
from .const import CONF_DIMMER, CONF_KEY, SUBENTRY_DIMMER, SUBENTRY_LIGHT
from .coordinator import Master2ConfigEntry, Master2Coordinator
from .entity import Master2ChannelEntity, subentries_of_type
from .switch import Master2ToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one light per light and dimmer channel."""
    for subentry in subentries_of_type(entry, SUBENTRY_LIGHT):
        async_add_entities(
            [Master2Light(entry.runtime_data, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
    for subentry in subentries_of_type(entry, SUBENTRY_DIMMER):
        async_add_entities(
            [Master2DimmerLight(entry.runtime_data, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class Master2Light(Master2ToggleEntity, LightEntity):
    """A light on a switch output of the master."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}


class Master2DimmerLight(Master2ChannelEntity, LightEntity):
    """A light on a dimmer channel.

    The serial protocol reports the dim value but has no command to set one;
    a dimmer is operated through its key like on the wall. The light is
    therefore on/off, the reported value is exposed as an attribute.
    """

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator, subentry)
        self._key = parse_address(subentry.data[CONF_KEY], "I")
        self._dimmer = parse_address(subentry.data[CONF_DIMMER], "D")

    @property
    def _value(self) -> int:
        return self.coordinator.data.states.dimmer(
            self._dimmer.module, self._dimmer.channel
        )

    @property
    def is_on(self) -> bool:
        """Return whether the dimmer reports a value above zero."""
        return self._value > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw dim value of the master."""
        return {"dim_value": self._value}

    async def _set(self, on: bool) -> None:
        await self.coordinator.async_refresh()
        if self.is_on != on:
            await self._send_key(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on with its key."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmer off with its key."""
        await self._set(False)
