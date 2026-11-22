"""Rain sensor of the Innoxel Master 2 integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Master2ConfigEntry, Master2Coordinator
from .sensor import add_when_weather_present


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the rain sensor once a weather station answers."""
    coordinator = entry.runtime_data

    @callback
    def add() -> None:
        async_add_entities([Master2RainSensor(coordinator)])

    add_when_weather_present(coordinator, entry, add)


class Master2RainSensor(CoordinatorEntity[Master2Coordinator], BinarySensorEntity):
    """Rain flag of the weather station connected to the master."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_translation_key = "rain"

    def __init__(self, coordinator: Master2Coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_rain"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return False while the master reports no valid weather data."""
        weather = self.coordinator.data.weather
        return super().available and weather is not None and weather.valid

    @property
    def is_on(self) -> bool | None:
        """Return whether it rains."""
        weather = self.coordinator.data.weather
        return weather.rain if weather is not None else None
