"""Buttons of the Innoxel Master 2 integration: one virtual key each."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import parse_address
from .const import CONF_KEY, SUBENTRY_BUTTON
from .coordinator import Master2ConfigEntry, Master2Coordinator
from .entity import Master2ChannelEntity, subentries_of_type


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one button per key channel."""
    for subentry in subentries_of_type(entry, SUBENTRY_BUTTON):
        async_add_entities(
            [Master2Button(entry.runtime_data, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class Master2Button(Master2ChannelEntity, ButtonEntity):
    """Sends a short impulse on a key, e.g. for a scene programmed in the master."""

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator, subentry)
        self._key = parse_address(subentry.data[CONF_KEY], "I")

    async def async_press(self) -> None:
        """Send a key impulse."""
        async with self.coordinator.command_lock:
            await self._send_key(self._key)
