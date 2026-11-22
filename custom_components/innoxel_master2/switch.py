"""Switches of the Innoxel Master 2 integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    async_add_entities([Master2ConnectionSwitch(entry.runtime_data)])
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
        # state. Read the state fresh: the last poll may be a second old.
        # Under the lock, so that a second command waits for this one and
        # then sees the state it left.
        async with self.coordinator.command_lock:
            await self.coordinator.async_refresh()
            if self.is_on != on:
                await self._send_key(self._key, done=lambda: self.is_on == on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        await self._set(False)


class Master2Switch(Master2ToggleEntity, SwitchEntity):
    """A switch output of the master."""


class Master2ConnectionSwitch(CoordinatorEntity[Master2Coordinator], SwitchEntity):
    """Releases the connection to the serial device server.

    A device server usually accepts one connection. Switch this off before
    working with INNOXEL Setup and on again afterwards.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "connection"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Master2Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_connection"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Stay available while the connection is switched off."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the integration uses the connection."""
        return self.coordinator.connected

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Take the connection and resume polling."""
        await self.coordinator.async_set_connected(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Release the connection and stop polling."""
        await self.coordinator.async_set_connected(False)
        self.async_write_ha_state()
