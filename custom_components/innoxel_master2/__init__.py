"""Innoxel Master 2 integration (serial protocol through a serial device server)."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .client import (
    KEY_IMPULSE,
    KEY_PRESS,
    KEY_RELEASE,
    Master2Client,
    Master2Error,
    parse_address,
)
from .const import (
    ATTR_ACTION,
    ATTR_ADDRESS,
    ATTR_CONFIG_ENTRY_ID,
    DOMAIN,
    SERVICE_SEND_KEY,
)
from .coordinator import Master2ConfigEntry, Master2Coordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

KEY_ACTIONS = {"impulse": KEY_IMPULSE, "press": KEY_PRESS, "release": KEY_RELEASE}

SEND_KEY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_ADDRESS): cv.string,
        vol.Optional(ATTR_ACTION, default="impulse"): vol.In(KEY_ACTIONS),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration services."""

    async def send_key(call: ServiceCall) -> None:
        entries: list[Master2ConfigEntry] = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.state is ConfigEntryState.LOADED
        ]
        entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
        if entry_id:
            entries = [entry for entry in entries if entry.entry_id == entry_id]
        if len(entries) != 1:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="entry_not_unique"
            )
        try:
            address = parse_address(call.data[ATTR_ADDRESS], "I")
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_input_address",
                translation_placeholders={"address": call.data[ATTR_ADDRESS]},
            ) from err
        try:
            await entries[0].runtime_data.async_send_key(
                address, KEY_ACTIONS[call.data[ATTR_ACTION]]
            )
        except Master2Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    hass.services.async_register(DOMAIN, SERVICE_SEND_KEY, send_key, SEND_KEY_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Master2ConfigEntry) -> bool:
    """Set up one Master 2."""
    client = Master2Client(entry.data[CONF_HOST], entry.data[CONF_PORT])
    try:
        revision = await client.get_revision()
    except Master2Error as err:
        await client.close()
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = Master2Coordinator(hass, entry, client, revision)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.close()
        raise
    entry.runtime_data = coordinator

    # The master itself: parent of the channel devices, carries the weather.
    master = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **coordinator.device_info
    )
    coordinator.master_device_id = master.id

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: Master2ConfigEntry) -> None:
    """Reload after a channel was added, changed or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Master2ConfigEntry) -> bool:
    """Unload a config entry and release the connection to the device server."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.close()
    return unloaded
