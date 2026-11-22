"""Switches of the Innoxel Master 2 integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import parse_address
from .const import CONF_KEY, CONF_OUTPUT, SUBENTRY_SWITCH
from .coordinator import Master2ConfigEntry, Master2Coordinator
from .entity import Master2ChannelEntity, subentries_of_type


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one switch per switch channel."""
    for subentry in subentries_of_type(entry, SUBENTRY_SWITCH):
        async_add_entities(
            [Master2Switch(entry.runtime_data, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class Master2ToggleEntity(Master2ChannelEntity):
    """An output that a virtual key toggles; shared by switch and light."""

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator, subentry)
        self._key = parse_address(subentry.data[CONF_KEY], "I")
        self._output = parse_address(subentry.data[CONF_OUTPUT], "O")

    @property
    def is_on(self) -> bool:
        """Return the state of the output as the master reports it."""
        return self.coordinator.data.states.output(
            self._output.module, self._output.channel
        )

    async def _set(self, on: bool) -> None:
        # The key toggles, so only press it when the output is in the other
        # state. Read the state fresh: the last poll may be two seconds old.
        await self.coordinator.async_refresh()
        if self.is_on != on:
            await self._send_key(self._key)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        await self._set(False)


class Master2Switch(Master2ToggleEntity, SwitchEntity):
    """A switch output of the master."""
