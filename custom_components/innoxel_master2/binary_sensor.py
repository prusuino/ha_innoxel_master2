"""Binary sensors of the Innoxel Master 2 integration: the rain flag of the
weather station and outputs that are only read."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import parse_address
from .const import CONF_OUTPUT, SUBENTRY_SENSOR
from .coordinator import Master2ConfigEntry, Master2Coordinator
from .entity import Master2ChannelEntity, subentries_of_type
from .sensor import add_when_weather_present


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one sensor per sensor channel, and the rain sensor once a
    weather station answers."""
    coordinator = entry.runtime_data
    for subentry in subentries_of_type(entry, SUBENTRY_SENSOR):
        async_add_entities(
            [Master2OutputSensor(coordinator, subentry)],
            config_subentry_id=subentry.subentry_id,
        )

    @callback
    def add() -> None:
        async_add_entities([Master2RainSensor(coordinator)])

    add_when_weather_present(coordinator, entry, add)


class Master2OutputSensor(Master2ChannelEntity, BinarySensorEntity):
    """The state of one output, read only.

    For what the master reports in the output range but Home Assistant should
    not operate: a 230 V input module (NOXin-0800h, addressed like an output),
    or an output the master uses as a flag (night setback, a weather function).
    """

    def __init__(self, coordinator: Master2Coordinator, subentry: ConfigSubentry) -> None:
        super().__init__(coordinator, subentry)
        self._output = parse_address(subentry.data[CONF_OUTPUT], "O")

    @property
    def is_on(self) -> bool:
        """Return the state of the output as the master reports it."""
        return self.coordinator.data.states.output(
            self._output.module, self._output.channel
        )


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
