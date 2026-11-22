"""Data update coordinator of the Innoxel Master 2 integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    KEY_IMPULSE,
    Address,
    Master2Client,
    Master2Error,
    States,
    Weather,
)
from .const import DOMAIN, REFRESH_DELAY, SCAN_INTERVAL, WEATHER_EVERY

_LOGGER = logging.getLogger(__name__)

type Master2ConfigEntry = ConfigEntry[Master2Coordinator]


@dataclass(frozen=True)
class Master2Data:
    """One poll result."""

    states: States
    weather: Weather | None


class Master2Coordinator(DataUpdateCoordinator[Master2Data]):
    """Polls output/dimmer states and, less often, the weather station."""

    config_entry: Master2ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: Master2ConfigEntry,
        client: Master2Client,
        revision: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.client = client
        self.revision = revision
        self._poll_count = 0
        self._weather: Weather | None = None
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Innoxel",
            model="Master 2",
            sw_version=revision,
        )

    async def _async_update_data(self) -> Master2Data:
        try:
            states = await self.client.get_states()
            if self._poll_count % WEATHER_EVERY == 0:
                self._weather = await self.client.get_weather()
        except Master2Error as err:
            raise UpdateFailed(str(err)) from err
        self._poll_count += 1
        return Master2Data(states, self._weather)

    async def async_send_key(self, address: Address, action: int = KEY_IMPULSE) -> None:
        """Simulate a key and read the states back shortly afterwards."""
        await self.client.send_key(address, action)
        await asyncio.sleep(REFRESH_DELAY)
        await self.async_refresh()
