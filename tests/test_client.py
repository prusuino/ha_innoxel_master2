"""The serial protocol client: framing, addresses, decoding, reconnecting."""
from __future__ import annotations

import pytest

from custom_components.innoxel_master2.client import (
    KEY_IMPULSE,
    KEY_PRESS,
    KEY_RELEASE,
    Address,
    Master2Client,
    Master2CommandError,
    Master2ConnectionError,
    Master2ProtocolError,
    States,
    checksum,
    decode_weather,
    parse_address,
)

from .conftest import HOST, WEATHER_EXAMPLE, FakeMaster


def test_checksum_is_the_byte_sum_modulo_256_in_upper_case_hex() -> None:
    assert checksum("V") == "56"
    assert checksum("F00") == "A6"
    assert checksum("Y041402" + "01") == f"{sum(b'Y04140201') & 0xFF:02X}"


@pytest.mark.parametrize(
    ("text", "kind", "expected"),
    [
        ("O0-3", "O", Address("O", 0, 3)),
        (" o63-7 ", "O", Address("O", 63, 7)),
        ("I10-1", "I", Address("I", 10, 1)),
        ("i 255-4", "I", Address("I", 255, 4)),
        ("GR28", "I", Address("I", 10, 1)),  # 0x28 = 40 -> module 10, key 1
        ("gr2e", "I", Address("I", 11, 3)),
        ("D0-2", "D", Address("D", 0, 2)),
        ("D31-3", "D", Address("D", 31, 3)),
    ],
)
def test_addresses_are_parsed(text: str, kind: str, expected: Address) -> None:
    assert parse_address(text, kind) == expected
    assert parse_address(str(expected), kind) == expected


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("O64-0", "O"),  # module out of range
        ("O0-8", "O"),  # outputs are 0-7
        ("I10-0", "I"),  # keys are 1-4
        ("I10-5", "I"),
        ("I256-1", "I"),
        ("D32-0", "D"),
        ("D0-4", "D"),
        ("I10-1", "O"),  # wrong kind
        ("O03", "O"),  # no separator
        ("GR28", "O"),  # the event notation is for inputs only
        ("GRZZ", "I"),
        ("", "O"),
        ("O-1", "O"),
    ],
)
def test_invalid_addresses_are_refused(text: str, kind: str) -> None:
    with pytest.raises(ValueError):
        parse_address(text, kind)


def test_states_decode_outputs_and_dimmers() -> None:
    fake = FakeMaster()
    fake.outputs = {(0, 0), (0, 7), (5, 3), (63, 4)}
    fake.dimmers = {(0, 0): 255, (2, 1): 128, (31, 3): 7}
    raw = fake.state_string()
    assert len(raw) == 384
    states = States(raw)
    assert states.outputs_on() == fake.outputs
    assert states.output(0, 0) and not states.output(0, 1)
    assert states.dimmer(0, 0) == 255
    assert states.dimmer(2, 1) == 128
    assert states.dimmer(31, 3) == 7
    assert states.dimmer(1, 0) == 0


def test_weather_is_decoded() -> None:
    weather = decode_weather(WEATHER_EXAMPLE)
    assert weather.valid and not weather.sensor_defect
    assert weather.rain is True
    assert weather.temperature == 21.1
    assert (weather.sun_south, weather.sun_west, weather.sun_east) == (10000, 20000, 30000)
    assert weather.twilight == 10.0
    assert weather.wind_speed == 3.5


def test_weather_without_a_station_or_with_a_defect_has_no_values() -> None:
    none = decode_weather("0" * 24)
    assert not none.valid and none.temperature is None and none.rain is False
    defect = decode_weather("8080" + "0" * 20)
    assert defect.valid and defect.sensor_defect and defect.wind_speed is None
    with pytest.raises(Master2ProtocolError):
        decode_weather("8100")


async def test_revision_states_and_weather_are_read(master: FakeMaster) -> None:
    master.outputs = {(1, 2)}
    master.weather = WEATHER_EXAMPLE
    client = Master2Client(HOST, master.port)
    try:
        assert await client.get_revision() == "09.23"
        assert (await client.get_states()).outputs_on() == {(1, 2)}
        assert (await client.get_weather()).temperature == 21.1
    finally:
        await client.close()
    # One connection for all requests: the device server accepts only one.
    assert master.connections == 1
    assert master.commands == ["V", "y", "s"]


async def test_keys_are_sent_as_impulse_press_and_release(master: FakeMaster) -> None:
    client = Master2Client(HOST, master.port)
    try:
        await client.send_key(Address("I", 10, 1))
        await client.send_key(Address("I", 10, 2), KEY_PRESS)
        await client.send_key(Address("I", 10, 2), KEY_RELEASE)
    finally:
        await client.close()
    assert master.keys == [(10, 1, KEY_IMPULSE), (10, 2, KEY_PRESS), (10, 2, KEY_RELEASE)]
    # CAN address 1024 + 2 * module, then action and key as two hex digits each.
    assert master.commands[0] == "Y04140201"


async def test_only_input_addresses_can_be_pressed(master: FakeMaster) -> None:
    client = Master2Client(HOST, master.port)
    with pytest.raises(ValueError):
        await client.send_key(Address("O", 0, 3))
    await client.close()
    assert master.commands == []


async def test_a_rejected_command_raises_with_the_return_code(master: FakeMaster) -> None:
    master.reject_keys = "F06"
    client = Master2Client(HOST, master.port)
    try:
        with pytest.raises(Master2CommandError) as caught:
            await client.send_key(Address("I", 10, 1))
        assert caught.value.code == "F06"
        # A rejection is an answer, not a broken connection: no second attempt.
        assert len(master.commands) == 1
    finally:
        await client.close()


async def test_a_dropped_connection_is_reopened_once(master: FakeMaster) -> None:
    client = Master2Client(HOST, master.port)
    try:
        assert await client.get_revision() == "09.23"
        master.drop_next = 1
        assert await client.get_revision() == "09.23"
        assert master.connections == 2
        master.drop_next = 2
        with pytest.raises(Master2ConnectionError):
            await client.get_revision()
    finally:
        await client.close()


async def test_nothing_listening_is_a_connection_error(master: FakeMaster) -> None:
    port = master.port
    await master.stop()
    client = Master2Client(HOST, port, timeout=1)
    with pytest.raises(Master2ConnectionError):
        await client.get_revision()
    await client.close()
    await master.start()  # the fixture stops it again


async def test_a_paused_client_releases_the_connection(master: FakeMaster) -> None:
    client = Master2Client(HOST, master.port)
    try:
        await client.get_revision()
        await client.pause()
        with pytest.raises(Master2ConnectionError):
            await client.get_revision()
        assert master.commands == ["V"]
        client.resume()
        assert await client.get_revision() == "09.23"
        assert master.connections == 2
    finally:
        await client.close()


async def test_an_unexpected_answer_is_a_protocol_error(master: FakeMaster) -> None:
    master.revision = ""
    client = Master2Client(HOST, master.port)

    def odd_answer(command: str) -> bytes:
        return b"HELLO00\r"  # wrong checksum

    master._answer = odd_answer  # type: ignore[method-assign]
    try:
        with pytest.raises(Master2ProtocolError):
            await client.get_revision()
    finally:
        await client.close()
