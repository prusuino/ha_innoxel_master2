"""Setup, channels, the connection switch and the send_key action, against
the stand-in master."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.innoxel_master2.const import DOMAIN

from .conftest import HOST, WEATHER_EXAMPLE, FakeMaster

pytestmark = pytest.mark.usefixtures("enable_custom_integrations", "no_refresh_delay")


def channel(subentry_type: str, title: str, **data: str) -> ConfigSubentryData:
    return ConfigSubentryData(data=data, subentry_type=subentry_type, title=title, unique_id=None)


async def setup(hass: HomeAssistant, master: FakeMaster, *channels: ConfigSubentryData) -> MockConfigEntry:
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


def entity_id(hass: HomeAssistant, entry: MockConfigEntry, domain: str, suffix: str) -> str:
    """Entity id by unique id, independent of how Home Assistant names it."""
    registry = er.async_get(hass)
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        if item.domain == domain and item.unique_id.endswith(suffix):
            return item.entity_id
    raise AssertionError(f"no {domain} entity ending in {suffix}")


def channel_entity(hass: HomeAssistant, entry: MockConfigEntry, domain: str, title: str) -> str:
    subentry = next(s for s in entry.subentries.values() if s.title == title)
    return entity_id(hass, entry, domain, subentry.subentry_id)


async def test_setup_reads_the_revision_and_unload_releases_the_connection(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    entry = await setup(hass, master)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.revision == "09.23"
    assert master.commands[0] == "V"
    client = entry.runtime_data.client
    assert client._writer is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert client._writer is None


async def test_setup_is_retried_when_no_master_answers(hass: HomeAssistant, master: FakeMaster) -> None:
    port = master.port
    await master.stop()
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: port})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    await master.start()


async def test_a_switch_shows_the_real_state_and_only_presses_when_needed(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.wiring[(10, 1)] = [(0, 3)]
    entry = await setup(hass, master, channel("switch", "Test lamp", key="I10-1", output="O0-3"))
    switch = channel_entity(hass, entry, "switch", "Test lamp")
    assert hass.states.get(switch).state == STATE_OFF

    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert master.keys == [(10, 1, 2)]
    assert hass.states.get(switch).state == STATE_ON

    # Already on: the key toggles, so it must not be pressed again.
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch}, blocking=True)
    assert master.keys == [(10, 1, 2)]

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    assert master.keys == [(10, 1, 2), (10, 1, 2)]
    assert hass.states.get(switch).state == STATE_OFF


async def test_a_change_at_the_wall_button_is_seen_before_a_command(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.wiring[(10, 1)] = [(0, 3)]
    entry = await setup(hass, master, channel("light", "Hall", key="I10-1", output="O0-3"))
    light = channel_entity(hass, entry, "light", "Hall")
    # Somebody switches the light on at the wall; the last poll still says off.
    master.outputs = {(0, 3)}

    await hass.services.async_call("light", "turn_on", {"entity_id": light}, blocking=True)
    assert master.keys == []
    assert hass.states.get(light).state == STATE_ON


async def test_a_blind_runs_with_an_impulse_and_stops_in_the_running_direction(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.wiring[(12, 1)] = [(2, 0)]  # up key -> up motor output
    master.wiring[(12, 2)] = [(2, 1)]
    entry = await setup(
        hass,
        master,
        channel("cover", "Blind", key_up="I12-1", key_down="I12-2", output_up="O2-0", output_down="O2-1"),
    )
    cover = channel_entity(hass, entry, "cover", "Blind")

    await hass.services.async_call("cover", "close_cover", {"entity_id": cover}, blocking=True)
    assert master.keys == [(12, 2, 2)]
    assert hass.states.get(cover).state == "closing"

    await hass.services.async_call("cover", "stop_cover", {"entity_id": cover}, blocking=True)
    assert master.keys == [(12, 2, 2), (12, 2, 2)]
    assert master.outputs == set()

    # Nothing is running: stop must not start the blind.
    await hass.services.async_call("cover", "stop_cover", {"entity_id": cover}, blocking=True)
    assert len(master.keys) == 2


async def test_a_key_channel_is_a_button(hass: HomeAssistant, master: FakeMaster) -> None:
    entry = await setup(hass, master, channel("button", "Scene", key="I11-3"))
    button = channel_entity(hass, entry, "button", "Scene")
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert master.keys == [(11, 3, 2)]


async def test_a_dimmer_is_on_above_zero_and_carries_the_value(hass: HomeAssistant, master: FakeMaster) -> None:
    master.dimmers[(0, 2)] = 120
    entry = await setup(hass, master, channel("dimmer", "Table", key="I10-3", dimmer="D0-2"))
    light = channel_entity(hass, entry, "light", "Table")
    state = hass.states.get(light)
    assert state.state == STATE_ON
    assert state.attributes["dim_value"] == 120

    # It is on already, so turning it on presses nothing.
    await hass.services.async_call("light", "turn_on", {"entity_id": light}, blocking=True)
    assert master.keys == []
    await hass.services.async_call("light", "turn_off", {"entity_id": light}, blocking=True)
    assert master.keys == [(10, 3, 2)]


async def test_weather_entities_appear_only_with_a_weather_station(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    entry = await setup(hass, master)
    registry = er.async_get(hass)
    domains = [e.domain for e in er.async_entries_for_config_entry(registry, entry.entry_id)]
    assert "sensor" not in domains and "binary_sensor" not in domains
    assert await hass.config_entries.async_unload(entry.entry_id)

    master.weather = WEATHER_EXAMPLE
    other = MockConfigEntry(domain=DOMAIN, title="Second", data={CONF_HOST: HOST, CONF_PORT: master.port})
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(registry, other.entry_id)
    sensors = [e for e in entities if e.domain == "sensor"]
    # temperature, wind speed, sun east/south/west, twilight
    assert len(sensors) == 6
    values = {hass.states.get(e.entity_id).state for e in sensors}
    assert {"21.1", "10000", "20000", "30000", "10.0"} <= values
    rain = [e for e in entities if e.domain == "binary_sensor"]
    assert len(rain) == 1 and hass.states.get(rain[0].entity_id).state == STATE_ON


async def test_the_connection_switch_releases_and_takes_the_connection(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    master.wiring[(10, 1)] = [(0, 3)]
    entry = await setup(hass, master, channel("switch", "Test lamp", key="I10-1", output="O0-3"))
    connection = entity_id(hass, entry, "switch", "_connection")
    lamp = channel_entity(hass, entry, "switch", "Test lamp")
    assert hass.states.get(connection).state == STATE_ON

    await hass.services.async_call("switch", "turn_off", {"entity_id": connection}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(connection).state == STATE_OFF
    assert hass.states.get(lamp).state == STATE_UNAVAILABLE
    assert entry.runtime_data.client._writer is None  # free for INNOXEL Setup

    await hass.services.async_call("switch", "turn_on", {"entity_id": connection}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(connection).state == STATE_ON
    assert hass.states.get(lamp).state == STATE_OFF


async def test_send_key_sends_impulse_press_and_release(hass: HomeAssistant, master: FakeMaster) -> None:
    await setup(hass, master)
    await hass.services.async_call(DOMAIN, "send_key", {"address": "GR28"}, blocking=True)
    await hass.services.async_call(DOMAIN, "send_key", {"address": "I12-1", "action": "press"}, blocking=True)
    await hass.services.async_call(DOMAIN, "send_key", {"address": "I12-1", "action": "release"}, blocking=True)
    assert master.keys == [(10, 1, 2), (12, 1, 1), (12, 1, 0)]


async def test_send_key_refuses_a_wrong_address_and_reports_a_rejection(
    hass: HomeAssistant, master: FakeMaster
) -> None:
    await setup(hass, master)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "send_key", {"address": "O0-3"}, blocking=True)
    master.reject_keys = "F06"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "send_key", {"address": "I10-1"}, blocking=True)


async def test_send_key_needs_exactly_one_master(hass: HomeAssistant, master: FakeMaster) -> None:
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "send_key", {"address": "I10-1"}, blocking=True)
    first = await setup(hass, master)
    second = MockConfigEntry(domain=DOMAIN, title="Second", data={CONF_HOST: HOST, CONF_PORT: master.port})
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "send_key", {"address": "I10-1"}, blocking=True)
    await hass.services.async_call(
        DOMAIN, "send_key", {"address": "I10-1", "config_entry_id": first.entry_id}, blocking=True
    )
    assert master.keys == [(10, 1, 2)]
