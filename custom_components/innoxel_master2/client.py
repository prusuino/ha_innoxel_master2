"""Serial protocol client for the Innoxel Master 2 behind a serial device server.

The Master 2 has no network port. It is reached through a serial device server
(e.g. Moxa NPort in TCP server mode, 115200 8N1) and speaks a line based ASCII
protocol:

    request:  <command><checksum>\r
    response: <data><checksum>\r            (commands that return data)
              F<nn><checksum>\r             (return code, F00 = ok)

The checksum is the sum of all bytes of the payload, modulo 256, written as two
upper case hex digits.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging

_LOGGER = logging.getLogger(__name__)

RC_OK = "F00"

CMD_REVISION = "V"
CMD_STATES = "y"
CMD_WEATHER = "s"
CMD_KEY = "Y"

KEY_RELEASE = 0
KEY_PRESS = 1
KEY_IMPULSE = 2

STATE_LENGTH = 384
WEATHER_LENGTH = 24
DIMMER_OFFSET = 128

SWITCH_MODULES = 64
SWITCH_CHANNELS = 8
INPUT_MODULES = 256
INPUT_KEYS = 4
DIMMER_MODULES = 32
DIMMER_CHANNELS = 4

WEATHER_FLAG_VALID = 0x8000
WEATHER_FLAG_RAIN = 0x0100
WEATHER_FLAG_SENSOR_DEFECT = 0x0080


class Master2Error(Exception):
    """Base error of the Master 2 client."""


class Master2ConnectionError(Master2Error):
    """The serial device server cannot be reached or dropped the connection."""


class Master2ProtocolError(Master2Error):
    """The master answered with something unexpected."""


class Master2CommandError(Master2Error):
    """The master rejected a command."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Master returned {code}")
        self.code = code


def checksum(payload: str) -> str:
    """Return the two digit hex checksum of a payload."""
    return f"{sum(payload.encode('ascii')) & 0xFF:02X}"


@dataclass(frozen=True)
class Address:
    """An Innoxel address such as O0-3 (output), I10-1 (input) or D2-0 (dimmer)."""

    kind: str  # "O", "I" or "D"
    module: int
    channel: int

    def __str__(self) -> str:
        return f"{self.kind}{self.module}-{self.channel}"


def parse_address(text: str, kind: str) -> Address:
    """Parse an address of the given kind.

    Accepts the notation of the Innoxel software (O0-3, I10-1, D2-0) and, for
    inputs, the event notation of INNOXEL Setup (GR28 = module 10, key 1).
    Raises ValueError when the text is not a valid address of that kind.
    """
    raw = text.strip().upper().replace(" ", "")
    if kind == "I" and raw.startswith("GR"):
        event = int(raw[2:], 16)
        module, channel = event // INPUT_KEYS, event % INPUT_KEYS + 1
    else:
        if not raw.startswith(kind):
            raise ValueError(text)
        module_text, sep, channel_text = raw[1:].partition("-")
        if not sep:
            raise ValueError(text)
        module, channel = int(module_text), int(channel_text)
    if kind == "O":
        valid = 0 <= module < SWITCH_MODULES and 0 <= channel < SWITCH_CHANNELS
    elif kind == "I":
        valid = 0 <= module < INPUT_MODULES and 1 <= channel <= INPUT_KEYS
    elif kind == "D":
        valid = 0 <= module < DIMMER_MODULES and 0 <= channel < DIMMER_CHANNELS
    else:
        valid = False
    if not valid:
        raise ValueError(text)
    return Address(kind, module, channel)


@dataclass(frozen=True)
class States:
    """Decoded answer of the state command."""

    raw: str

    def output(self, module: int, channel: int) -> bool:
        """Return whether a switch/motor output is on."""
        # Two hex digits per module: first digit channels 4-7, second 0-3.
        value = int(self.raw[2 * module : 2 * module + 2], 16)
        return bool(value >> channel & 1)

    def dimmer(self, module: int, channel: int) -> int:
        """Return the raw value (0-255) of a dimmer channel."""
        index = DIMMER_OFFSET + 8 * module + 2 * channel
        return int(self.raw[index : index + 2], 16)

    def outputs_on(self) -> set[tuple[int, int]]:
        """Return all (module, channel) pairs of outputs that are on."""
        return {
            (module, channel)
            for module in range(SWITCH_MODULES)
            for channel in range(SWITCH_CHANNELS)
            if self.output(module, channel)
        }


@dataclass(frozen=True)
class Weather:
    """Decoded answer of the weather command."""

    valid: bool
    sensor_defect: bool
    rain: bool
    temperature: float | None  # degrees Celsius
    sun_south: int | None  # lux
    sun_west: int | None  # lux
    sun_east: int | None  # lux
    twilight: float | None  # lux
    wind_speed: float | None  # m/s


def decode_weather(raw: str) -> Weather:
    """Decode the 24 character weather string of the master."""
    if len(raw) != WEATHER_LENGTH:
        raise Master2ProtocolError(f"Weather string has length {len(raw)}")
    flags = int(raw[0:4], 16)
    valid = bool(flags & WEATHER_FLAG_VALID)
    defect = bool(flags & WEATHER_FLAG_SENSOR_DEFECT)
    if not valid or defect:
        return Weather(valid, defect, False, None, None, None, None, None, None)
    return Weather(
        valid=True,
        sensor_defect=False,
        rain=bool(flags & WEATHER_FLAG_RAIN),
        temperature=round(int(raw[6:10], 16) * 0.1 - 273.15, 1),
        sun_south=int(raw[10:12], 16) * 1000,
        sun_west=int(raw[12:14], 16) * 1000,
        sun_east=int(raw[14:16], 16) * 1000,
        twilight=int(raw[16:18], 16) * 0.25,
        wind_speed=round(int(raw[20:24], 16) * 0.1, 1),
    )


class Master2Client:
    """Talks to one Master 2 over a persistent TCP connection.

    Serial device servers usually accept a single connection, so all requests
    are serialised through one lock and share one connection.
    """

    def __init__(self, host: str, port: int, timeout: float = 3.0) -> None:
        self.host = host
        self.port = port
        self._timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        # While paused the client refuses to connect, so that another program
        # (INNOXEL Setup) can use the single connection of the device server.
        self.paused = False
        # The weather answer as the master sent it, kept for the diagnostics.
        self.last_weather_raw: str | None = None

    async def pause(self) -> None:
        """Release the connection and refuse requests until resume()."""
        self.paused = True
        await self.close()

    def resume(self) -> None:
        """Allow requests again; the next one reconnects."""
        self.paused = False

    async def _connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self._timeout
            )
        except (OSError, TimeoutError) as err:
            raise Master2ConnectionError(
                f"Cannot connect to {self.host}:{self.port}: {err}"
            ) from err

    async def close(self) -> None:
        """Close the connection."""
        async with self._lock:
            await self._close()

    async def _close(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is None:
            return
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 1)
        except (OSError, TimeoutError):
            pass

    async def _read_line(self) -> str:
        assert self._reader is not None
        try:
            data = await asyncio.wait_for(
                self._reader.readuntil(b"\r"), self._timeout
            )
        except asyncio.IncompleteReadError as err:
            raise Master2ConnectionError("Connection closed by peer") from err
        except asyncio.LimitOverrunError as err:
            raise Master2ProtocolError("Answer too long") from err
        except TimeoutError as err:
            raise Master2ConnectionError("No answer from the master") from err
        except OSError as err:
            raise Master2ConnectionError(str(err)) from err
        line = data[:-1].decode("ascii", "replace")
        if len(line) < 2 or checksum(line[:-2]) != line[-2:]:
            raise Master2ProtocolError(f"Bad checksum in {line!r}")
        return line[:-2]

    async def _request(self, command: str, *, data: bool, return_code: bool) -> str:
        """Send a command and return its data line ("" when it has none)."""
        async with self._lock:
            if self.paused:
                raise Master2ConnectionError("The connection is switched off")
            last_error: Master2Error | None = None
            # One retry on a fresh connection: a device server silently drops
            # idle connections, which only shows on the next request.
            for _ in range(2):
                try:
                    if self._writer is None:
                        await self._connect()
                    assert self._writer is not None
                    frame = f"{command}{checksum(command)}\r".encode("ascii")
                    try:
                        self._writer.write(frame)
                        await asyncio.wait_for(self._writer.drain(), self._timeout)
                    except (OSError, TimeoutError) as err:
                        raise Master2ConnectionError(str(err)) from err
                    result = await self._read_line() if data else ""
                    if data and result.startswith("F") and len(result) == 3:
                        # The master answered with a return code only.
                        raise Master2CommandError(result)
                    if return_code:
                        code = await self._read_line()
                        if code != RC_OK:
                            raise Master2CommandError(code)
                    return result
                except Master2CommandError:
                    raise
                except Master2Error as err:
                    last_error = err
                    await self._close()
            assert last_error is not None
            raise last_error

    async def get_revision(self) -> str:
        """Return the firmware revision, e.g. "09.23"."""
        answer = await self._request(CMD_REVISION, data=True, return_code=False)
        if not answer.startswith("REV "):
            raise Master2ProtocolError(f"Unexpected revision answer {answer!r}")
        return answer[4:].strip()

    async def get_states(self) -> States:
        """Return the state of all outputs and dimmers."""
        answer = await self._request(CMD_STATES, data=True, return_code=True)
        if len(answer) != STATE_LENGTH:
            raise Master2ProtocolError(f"State string has length {len(answer)}")
        return States(answer)

    async def get_weather(self) -> Weather:
        """Return the weather station data."""
        answer = await self._request(CMD_WEATHER, data=True, return_code=True)
        self.last_weather_raw = answer
        return decode_weather(answer)

    async def send_key(self, address: Address, action: int = KEY_IMPULSE) -> None:
        """Simulate a key of an input module (press, release or short impulse)."""
        if address.kind != "I":
            raise ValueError(f"{address} is not an input address")
        can_address = 1024 + 2 * address.module
        command = f"{CMD_KEY}{can_address:04X}{action:02X}{address.channel:02X}"
        await self._request(command, data=False, return_code=True)
