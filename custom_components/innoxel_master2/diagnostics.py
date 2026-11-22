"""Diagnostics download (Settings → Devices & services → entry menu →
Download diagnostics).

The file carries what an issue report needs: the firmware revision, the raw
state and weather answers of the master exactly as they came over the serial
line, the channels with their addresses, and the entities with their current
state. With the raw answers a decoding problem (a dimmer value, a weather
value) can be checked without access to the installation.

The address of the serial device server is redacted. Channel and entity
names stay readable; they are the names you gave your channels.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import SCAN_INTERVAL, WEATHER_EVERY
from .coordinator import Master2ConfigEntry

REDACTED = "**REDACTED**"
TO_REDACT = {CONF_HOST}


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: REDACTED if key in TO_REDACT and value not in (None, "") else value
        for key, value in data.items()
    }


def _json_safe(value: Any) -> Any:
    """State attributes can hold objects (enums, sets); keep the file valid JSON."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: Master2ConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of one master."""
    diagnostics: dict[str, Any] = {
        "entry": {
            "version": entry.version,
            "state": entry.state.value,
            "data": _redact(dict(entry.data)),
        },
        "channels": [
            {
                "type": subentry.subentry_type,
                "name": subentry.title,
                **dict(subentry.data),
            }
            for subentry in entry.subentries.values()
        ],
    }

    if entry.state is ConfigEntryState.LOADED:
        coordinator = entry.runtime_data
        data = coordinator.data
        error = coordinator.last_exception
        diagnostics["master"] = {
            "revision": coordinator.revision,
            "connection_in_use": coordinator.connected,
            "poll_interval_seconds": SCAN_INTERVAL,
            "weather_every_n_polls": WEATHER_EVERY,
            "last_update_success": coordinator.last_update_success,
            # Only the type: the text of a connection error repeats the address.
            "last_error": type(error).__name__ if error else None,
        }
        diagnostics["raw"] = {
            # 384 hex characters: 64 switch modules (two characters each),
            # then 32 dimmer modules with four channels of two characters.
            "states": data.states.raw if data else None,
            # 24 hex characters, None until the weather was read once.
            "weather": coordinator.client.last_weather_raw,
        }
        diagnostics["decoded"] = {
            "outputs_on": (
                sorted(f"O{module}-{channel}" for module, channel in data.states.outputs_on())
                if data
                else None
            ),
            "weather": asdict(data.weather) if data and data.weather else None,
        }

    registry = er.async_get(hass)
    entities = []
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        state = hass.states.get(item.entity_id)
        entities.append(
            {
                "entity_id": item.entity_id,
                "unique_id": item.unique_id,
                "original_name": item.original_name,
                "translation_key": item.translation_key,
                "disabled_by": item.disabled_by,
                "state": state.state if state else None,
                "attributes": _json_safe(dict(state.attributes)) if state else None,
            }
        )
    diagnostics["entities"] = sorted(entities, key=lambda entity: entity["entity_id"])
    return diagnostics
