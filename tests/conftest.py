"""A stand-in for the Innoxel Master 2 behind a serial device server.

The tests talk to a small TCP server on localhost that speaks the serial
protocol of the master: revision, states, weather and key commands. No real
master and no device server is contacted.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from custom_components.innoxel_master2.client import checksum

HOST = "127.0.0.1"
WEATHER_EXAMPLE = "8100000B7E0A141E28000023"  # valid, rain, 21.1 °C, 3.5 m/s
WEATHER_NONE = "0" * 24  # no weather station connected


def frame(payload: str) -> bytes:
    """One protocol line: payload, checksum, carriage return."""
    return f"{payload}{checksum(payload)}\r".encode("ascii")


class FakeMaster:
    """Answers the commands of the client like a Master 2 would."""

    def __init__(self) -> None:
        self.revision = "09.23"
        self.outputs: set[tuple[int, int]] = set()
        self.dimmers: dict[tuple[int, int], int] = {}
        # (input module, key) -> outputs the key toggles
        self.wiring: dict[tuple[int, int], list[tuple[int, int]]] = {}
        self.weather = WEATHER_NONE
        self.keys: list[tuple[int, int, int]] = []  # (module, key, action)
        self.commands: list[str] = []
        self.connections = 0
        self.drop_next = 0  # close the connection instead of answering
        self.reject_keys: str | None = None  # return code for key commands
        self.lag = 0  # state polls a key needs before its outputs change
        self._pending: list[tuple[int, list[tuple[int, int]]]] = []
        self.server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()

    @property
    def port(self) -> int:
        assert self.server is not None
        return self.server.sockets[0].getsockname()[1]

    def state_string(self) -> str:
        modules = [0] * 64
        for module, channel in self.outputs:
            modules[module] |= 1 << channel
        dimmers = "".join(
            f"{self.dimmers.get((module, channel), 0):02X}"
            for module in range(32)
            for channel in range(4)
        )
        return "".join(f"{value:02X}" for value in modules) + dimmers

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._serve, HOST, 0)

    async def stop(self) -> None:
        assert self.server is not None
        self.server.close()
        for writer in list(self._writers):
            writer.close()
        await self.server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self._writers.add(writer)
        try:
            while True:
                try:
                    line = (await reader.readuntil(b"\r"))[:-1].decode("ascii")
                except (asyncio.IncompleteReadError, ConnectionError):
                    return
                command, received = line[:-2], line[-2:]
                assert checksum(command) == received, line
                self.commands.append(command)
                if self.drop_next:
                    self.drop_next -= 1
                    return
                writer.write(self._answer(command))
                await writer.drain()
        finally:
            self._writers.discard(writer)
            writer.close()

    def _answer(self, command: str) -> bytes:
        if command == "V":
            return frame(f"REV {self.revision}")
        if command == "y":
            waiting = []
            for polls_left, outputs in self._pending:
                if polls_left <= 1:
                    for output in outputs:
                        self.outputs ^= {output}
                else:
                    waiting.append((polls_left - 1, outputs))
            self._pending = waiting
            return frame(self.state_string()) + frame("F00")
        if command == "s":
            return frame(self.weather) + frame("F00")
        if command.startswith("Y"):
            if self.reject_keys:
                return frame(self.reject_keys)
            module = (int(command[1:5], 16) - 1024) // 2
            action, key = int(command[5:7], 16), int(command[7:9], 16)
            self.keys.append((module, key, action))
            if action == 2:  # impulse
                outputs = self.wiring.get((module, key), [])
                if self.lag:
                    self._pending.append((self.lag + 1, outputs))
                else:
                    for output in outputs:
                        self.outputs ^= {output}
            return frame("F00")
        return frame("F06")


@pytest.fixture
async def master(socket_enabled: None) -> AsyncIterator[FakeMaster]:
    """A running stand-in master on a free localhost port.

    The Home Assistant test harness blocks sockets; `socket_enabled` allows
    them for the tests that use this fixture (localhost only).
    """
    fake = FakeMaster()
    await fake.start()
    yield fake
    await fake.stop()


@pytest.fixture
def no_refresh_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the pause between a key and the state read that follows it."""
    monkeypatch.setattr("custom_components.innoxel_master2.coordinator.REFRESH_STEP", 0)
    monkeypatch.setattr("custom_components.innoxel_master2.config_flow.REFRESH_STEP", 0)
