"""Weather station sensors of the Innoxel Master 2 integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import Weather
from .coordinator import Master2ConfigEntry, Master2Coordinator


@dataclass(frozen=True, kw_only=True)
class Master2SensorDescription(SensorEntityDescription):
    """Describes one weather value."""

    value_fn: Callable[[Weather], float | int | None]


SENSORS: tuple[Master2SensorDescription, ...] = (
    Master2SensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.temperature,
    ),
    Master2SensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.wind_speed,
    ),
    Master2SensorDescription(
        key="sun_east",
        translation_key="sun_east",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.sun_east,
    ),
    Master2SensorDescription(
        key="sun_south",
        translation_key="sun_south",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.sun_south,
    ),
    Master2SensorDescription(
        key="sun_west",
        translation_key="sun_west",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.sun_west,
    ),
    Master2SensorDescription(
        key="twilight",
        translation_key="twilight",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda weather: weather.twilight,
    ),
)


@callback
def add_when_weather_present(
    coordinator: Master2Coordinator,
    entry: Master2ConfigEntry,
    add: Callable[[], None],
) -> None:
    """Call add once, as soon as the master reports valid weather data.

    Installations without a weather station never get weather entities.
    """
    unsubscribe: Callable[[], None] | None = None

    @callback
    def check() -> None:
        nonlocal unsubscribe
        weather = coordinator.data.weather
        if weather is None or not weather.valid:
            return
        if unsubscribe is not None:
            unsubscribe()
            unsubscribe = None
        add()

    weather = coordinator.data.weather
    if weather is not None and weather.valid:
        add()
        return
    unsubscribe = coordinator.async_add_listener(check)

    @callback
    def cancel() -> None:
        if unsubscribe is not None:
            unsubscribe()

    entry.async_on_unload(cancel)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Master2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the weather sensors once a weather station answers."""
    coordinator = entry.runtime_data

    @callback
    def add() -> None:
        async_add_entities(
            Master2WeatherSensor(coordinator, description) for description in SENSORS
        )

    add_when_weather_present(coordinator, entry, add)


class Master2WeatherSensor(CoordinatorEntity[Master2Coordinator], SensorEntity):
    """One value of the weather station connected to the master."""

    _attr_has_entity_name = True
    entity_description: Master2SensorDescription

    def __init__(
        self, coordinator: Master2Coordinator, description: Master2SensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Return False while the master reports no valid weather data."""
        weather = self.coordinator.data.weather
        return super().available and weather is not None and weather.valid

    @property
    def native_value(self) -> float | int | None:
        """Return the weather value."""
        weather = self.coordinator.data.weather
        if weather is None:
            return None
        return self.entity_description.value_fn(weather)
