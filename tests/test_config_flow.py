"""The setup dialog and the dialogs that add or change a channel."""
from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.innoxel_master2.const import DOMAIN

from .conftest import HOST, FakeMaster

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "no_refresh_delay")


async def loaded_entry(hass: HomeAssistant, master: FakeMaster, *channels: ConfigSubentryData) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Innoxel Master 2",
        data={CONF_HOST: HOST, CONF_PORT: master.port},
        subentries_data=list(channels),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def add_channel(hass: HomeAssistant, entry: MockConfigEntry, kind: str, user_input: dict) -> dict:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, kind), context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


async def test_setup_succeeds_when_a_master_answers(hass: HomeAssistant, master: FakeMaster) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: master.port}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Innoxel Master 2"
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: master.port}
    assert "V" in master.commands


async def test_setup_reports_when_nothing_answers_and_can_be_repeated(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    port = master.port
    await master.stop()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: port}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    await master.start()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: master.port}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_the_same_device_server_is_not_set_up_twice(hass: HomeAssistant, master: FakeMaster) -> None:
    await loaded_entry(hass, master)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST, CONF_PORT: master.port}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_switch_with_its_output_given_is_stored_normalised(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    entry = await loaded_entry(hass, master)
    result = await add_channel(
        hass, entry, "switch", {CONF_NAME: "Test lamp", "key": "gr28", "output": " o0-3 "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Test lamp"
    assert subentry.data == {"key": "I10-1", "output": "O0-3"}
    assert master.keys == []  # nothing was pressed


async def test_an_empty_output_is_detected_and_the_output_put_back(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.wiring[(10, 1)] = [(0, 3)]
    entry = await loaded_entry(hass, master)
    result = await add_channel(hass, entry, "light", {CONF_NAME: "Hall", "key": "I10-1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data == {"key": "I10-1", "output": "O0-3"}
    # Pressed twice: once to see what changes, once to put it back.
    assert master.keys == [(10, 1, 2), (10, 1, 2)]
    assert master.outputs == set()


@pytest.mark.parametrize("outputs", [[], [(0, 3), (0, 4)]])
async def test_detection_fails_when_the_key_switches_nothing_or_several_outputs(
    hass: HomeAssistant, master: FakeMaster, outputs: list[tuple[int, int]]
) -> None:
    master.wiring[(10, 1)] = outputs
    entry = await loaded_entry(hass, master)
    result = await add_channel(hass, entry, "switch", {CONF_NAME: "Test lamp", "key": "I10-1"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"output": "detect_failed"}
    assert master.outputs == set()  # put back in both cases
    assert not entry.subentries


async def test_detection_fails_while_the_master_is_not_loaded(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await loaded_entry(hass, master)
    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await add_channel(hass, entry, "switch", {CONF_NAME: "Test lamp", "key": "I10-1"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"output": "detect_failed"}


async def test_wrong_addresses_are_marked_at_their_field(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await loaded_entry(hass, master)
    result = await add_channel(
        hass,
        entry,
        "cover",
        {CONF_NAME: "Blind", "key_up": "O1-1", "key_down": "I12-2", "output_up": "O2-9"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"key_up": "invalid_address", "output_up": "invalid_address"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Blind", "key_up": "I12-1", "key_down": "I12-2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.data == {"key_up": "I12-1", "key_down": "I12-2"}


async def test_dimmer_and_key_channels(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await loaded_entry(hass, master)
    result = await add_channel(hass, entry, "dimmer", {CONF_NAME: "Table", "key": "I10-3", "dimmer": "d0-2"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await add_channel(hass, entry, "button", {CONF_NAME: "Scene", "key": "GR2E"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = {s.title: dict(s.data) for s in entry.subentries.values()}
    assert data == {"Table": {"key": "I10-3", "dimmer": "D0-2"}, "Scene": {"key": "I11-3"}}


async def test_a_channel_can_be_changed(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await loaded_entry(
        hass,
        master,
        ConfigSubentryData(
            data={"key": "I10-1", "output": "O0-3"}, subentry_type="switch", title="Test lamp", unique_id=None
        ),
    )
    subentry_id = next(iter(entry.subentries))
    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Lamp", "key": "I10-2", "output": "O0-9"}
    )
    assert result["errors"] == {"output": "invalid_address"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Lamp", "key": "I10-2", "output": "O0-4"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    subentry = entry.subentries[subentry_id]
    assert subentry.title == "Lamp"
    assert subentry.data == {"key": "I10-2", "output": "O0-4"}


async def test_a_sensor_channel_takes_only_an_output(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await loaded_entry(hass, master)
    result = await add_channel(hass, entry, "sensor", {CONF_NAME: "Door contact", "output": "I8-2"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"output": "invalid_address"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_NAME: "Door contact", "output": "o8-2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(iter(entry.subentries.values()))
    assert subentry.subentry_type == "sensor"
    assert subentry.data == {"output": "O8-2"}
    assert master.keys == []  # nothing is pressed for a sensor


async def test_detection_waits_for_an_output_that_lags(hass: HomeAssistant, master: FakeMaster) -> None:
    master.wiring[(10, 1)] = [(0, 3)]
    master.lag = 2
    entry = await loaded_entry(hass, master)
    result = await add_channel(hass, entry, "switch", {CONF_NAME: "Test lamp", "key": "I10-1"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert next(iter(entry.subentries.values())).data == {"key": "I10-1", "output": "O0-3"}

