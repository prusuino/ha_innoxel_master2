"""Covers (blinds) of the Innoxel Master 2 integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import Address, parse_address
from .const import (
    CONF_KEY_DOWN,
    CONF_KEY_UP,
    CONF_OUTPUT_DOWN,
    CONF_OUTPUT_UP,
    SUBENTRY_COVER,
)
from .coordinator import Master2ConfigEntry, Master2Coordinator
from .entity import Master2ChannelEntity, optional_address, subentries_of_type


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one cover per cover channel."""
    for subentry in subentries_of_type(entry, SUBENTRY_COVER):
        async_add_entities(
            [Master2Cover(entry.runtime_data, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class Master2Cover(Master2ChannelEntity, CoverEntity):
    """A blind driven by an up key and a down key.

    A short key impulse starts a full run; an impulse while the blind is
    moving stops it. The master does not know the position, so the cover only
    reports whether its motor outputs are running (when they are configured).
    """

    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_is_closed = None
    _attr_assumed_state = True

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator, subentry)
        self._key_up = parse_address(subentry.data[CONF_KEY_UP], "I")
        self._key_down = parse_address(subentry.data[CONF_KEY_DOWN], "I")
        self._output_up = optional_address(subentry, CONF_OUTPUT_UP, "O")
        self._output_down = optional_address(subentry, CONF_OUTPUT_DOWN, "O")
        # Direction of the last command, used to stop when no outputs are known.
        self._last_key: Address | None = None

    def _running(self, output: Address | None) -> bool | None:
        if output is None:
            return None
        return self.coordinator.data.states.output(output.module, output.channel)

    @property
    def is_opening(self) -> bool | None:
        """Return whether the up output is on."""
        return self._running(self._output_up)

    @property
    def is_closing(self) -> bool | None:
        """Return whether the down output is on."""
        return self._running(self._output_down)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Start a full run up."""
        self._last_key = self._key_up
        await self._send_key(self._key_up)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Start a full run down."""
        self._last_key = self._key_down
        await self._send_key(self._key_down)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop a running blind with an impulse on the key of its direction."""
        if self._output_up is not None or self._output_down is not None:
            await self.coordinator.async_refresh()
            if self.is_opening:
                await self._send_key(self._key_up)
            elif self.is_closing:
                await self._send_key(self._key_down)
            return
        if self._last_key is not None:
            await self._send_key(self._last_key)
            self._last_key = None
