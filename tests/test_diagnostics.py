"""The diagnostics download: raw answers of the master, channels, entities,
and the address of the device server redacted."""
from __future__ import annotations

import json

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.innoxel_master2.const import DOMAIN
from custom_components.innoxel_master2.diagnostics import (
    REDACTED,
    async_get_config_entry_diagnostics,
)

from .conftest import HOST, WEATHER_EXAMPLE, FakeMaster

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "no_refresh_delay")


def entry_for(master: FakeMaster) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Innoxel Master 2",
        data={CONF_HOST: HOST, CONF_PORT: master.port},
        subentries_data=[
            ConfigSubentryData(
                data={"key": "I10-1", "output": "O0-3"}, subentry_type="switch", title="Test lamp", unique_id=None
            ),
            ConfigSubentryData(
                data={"key": "I10-3", "dimmer": "D0-2"}, subentry_type="dimmer", title="Table", unique_id=None
            ),
        ],
    )


async def test_diagnostics_carry_the_raw_answers_and_hide_the_address(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.outputs = {(0, 3), (5, 1)}
    master.dimmers[(0, 2)] = 120
    master.weather = WEATHER_EXAMPLE
    entry = entry_for(master)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(diagnostics)  # must be plain JSON
    assert HOST not in text

    assert diagnostics["entry"]["data"] == {CONF_HOST: REDACTED, CONF_PORT: master.port}
    assert diagnostics["entry"]["state"] == "loaded"
    assert diagnostics["channels"] == [
        {"type": "switch", "name": "Test lamp", "key": "I10-1", "output": "O0-3"},
        {"type": "dimmer", "name": "Table", "key": "I10-3", "dimmer": "D0-2"},
    ]
    assert diagnostics["master"] == {
        "revision": "09.23",
        "connection_in_use": True,
        "poll_interval_seconds": 1,
        "weather_every_n_polls": 30,
        "last_update_success": True,
        "last_error": None,
    }
    # Exactly what the master sent, so a decoding problem can be checked.
    assert diagnostics["raw"] == {"states": master.state_string(), "weather": WEATHER_EXAMPLE}
    assert diagnostics["decoded"]["outputs_on"] == ["O0-3", "O5-1"]
    assert diagnostics["decoded"]["weather"]["temperature"] == 21.1

    states = {entity["entity_id"].split(".")[0] + ":" + str(entity["state"]) for entity in diagnostics["entities"]}
    assert "switch:on" in states and "light:on" in states
    dimmer = next(e for e in diagnostics["entities"] if e["entity_id"].startswith("light."))
    assert dimmer["attributes"]["dim_value"] == 120
    assert any(entity["unique_id"].endswith("_connection") for entity in diagnostics["entities"])


async def test_diagnostics_of_a_master_that_does_not_answer(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = entry_for(master)
    await master.stop()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    json.dumps(diagnostics)
    assert diagnostics["entry"]["state"] == "setup_retry"
    assert diagnostics["entry"]["data"][CONF_HOST] == REDACTED
    assert len(diagnostics["channels"]) == 2
    assert "master" not in diagnostics and "raw" not in diagnostics
    assert diagnostics["entities"] == []
    await master.start()


async def test_the_last_error_is_named_without_its_text(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = entry_for(master)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await master.stop()
    await entry.runtime_data.async_refresh()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["master"]["last_update_success"] is False
    assert diagnostics["master"]["last_error"] == "UpdateFailed"
    assert HOST not in json.dumps(diagnostics)
    await master.start()
