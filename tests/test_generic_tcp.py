"""Regression tests for GenericTCPDriver.

Covers the bug-fix campaign findings for this driver:

- H-060: connect() closes the prior transport before reconnecting (no socket /
  reader-task leak on auto-reconnect) — now inherited from BaseDriver.
- M-106: a transport disconnect runs the BaseDriver cleanup (stop polling +
  close the dead transport), not a custom override that dropped both.
- M-107: connect() binds to the configured control_interface (local_addr) and
  passes name=device_id, like every other driver.
- L-071: the disconnect cleanup task is tracked (no orphaned fire-and-forget).
- L-072: the delimiter default agrees between default_config and config_schema.
- L-073: a string port yields a clear ConnectionError, not a raw socket error.
- H-061: the `commands` map is robust to a JSON-string / non-dict config value
  (an Add-dialog or hand-edit slip) instead of crashing with AttributeError.
"""

import asyncio
from unittest.mock import patch, AsyncMock

import pytest

from server.core.event_bus import EventBus
from server.core.state_store import StateStore
from server.drivers.generic_tcp import GenericTCPDriver
from server.transport.binary_helpers import encode_escape_sequences


def _mk(config=None):
    return GenericTCPDriver(
        device_id="gtcp",
        config={"host": "10.0.0.5", "port": 23} if config is None else config,
        state=StateStore(),
        events=EventBus(),
    )


class _FakeTransport:
    def __init__(self):
        self.closed = False
        self.connected = True
        self.sent: bytes | None = None

    async def close(self):
        self.closed = True
        self.connected = False

    async def send(self, data: bytes):
        self.sent = data


# --- Inherits BaseDriver connect/disconnect (no diverging override) ---------


class TestInheritsBaseConnect:
    def test_overrides_removed(self):
        # The hand-rolled connect/disconnect/_handle_disconnect forks are gone;
        # the driver uses the hardened BaseDriver versions.
        assert "connect" not in GenericTCPDriver.__dict__
        assert "disconnect" not in GenericTCPDriver.__dict__
        assert "_handle_disconnect" not in GenericTCPDriver.__dict__

    async def test_connect_closes_prior_transport(self):
        """H-060: a reconnect closes the old transport before reassigning."""
        drv = _mk()
        old = _FakeTransport()
        drv.transport = old
        created = _FakeTransport()
        with patch("server.transport.tcp.TCPTransport.create",
                   new_callable=AsyncMock, return_value=created), \
             patch("server.system_config.get_system_config") as cfg:
            cfg.return_value.get.return_value = ""  # no control interface
            await drv.connect()
        assert old.closed is True
        assert drv.transport is created

    async def test_connect_binds_control_interface_and_name(self):
        """M-107: connect honors control_interface and passes name."""
        drv = _mk()
        created = _FakeTransport()
        with patch("server.transport.tcp.TCPTransport.create",
                   new_callable=AsyncMock, return_value=created) as mock_create, \
             patch("server.system_config.get_system_config") as cfg:
            cfg.return_value.get.return_value = "10.20.30.40"
            await drv.connect()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["local_addr"] == ("10.20.30.40", 0)
        assert kwargs["name"] == "gtcp"

    async def test_string_port_gives_clear_error(self):
        """L-073: a non-numeric port raises an actionable ConnectionError."""
        drv = _mk(config={"host": "10.0.0.5", "port": "garbage"})
        with patch("server.system_config.get_system_config") as cfg:
            cfg.return_value.get.return_value = ""
            with pytest.raises(ConnectionError, match="invalid port"):
                await drv.connect()


class TestDisconnectCleanup:
    async def test_on_disconnect_cleanup_closes_transport(self):
        """M-106: the inherited cleanup closes + drops the dead transport."""
        drv = _mk()
        fake = _FakeTransport()
        drv.transport = fake
        await drv._on_disconnect_cleanup()
        assert fake.closed is True
        assert drv.transport is None

    async def test_disconnect_task_is_tracked(self):
        """L-071: the fire-and-forget cleanup task is held in _bg_tasks."""
        drv = _mk()
        fake = _FakeTransport()
        drv.transport = fake
        drv._handle_transport_disconnect()
        tasks = list(drv._bg_tasks)
        assert len(tasks) == 1
        await asyncio.gather(*tasks)
        assert fake.closed is True


# --- L-072: delimiter default consistency -----------------------------------


def test_delimiter_defaults_agree():
    info = GenericTCPDriver.DRIVER_INFO
    dc = info["default_config"]["delimiter"]
    cs = info["config_schema"]["delimiter"]["default"]
    assert dc == cs == "\\r\\n"
    assert encode_escape_sequences(dc) == b"\r\n"


# --- H-061: command map is robust to a string / non-dict config -------------


class TestCommandMap:
    def test_dict_passthrough(self):
        drv = _mk(config={"commands": {"on": "PWR ON"}})
        assert drv._command_map() == {"on": "PWR ON"}

    def test_json_string_parsed(self):
        drv = _mk(config={"commands": '{"on": "PWR ON"}'})
        assert drv._command_map() == {"on": "PWR ON"}

    def test_empty_string(self):
        drv = _mk(config={"commands": "   "})
        assert drv._command_map() == {}

    def test_invalid_json_string(self):
        drv = _mk(config={"commands": "not json {"})
        assert drv._command_map() == {}

    def test_non_dict(self):
        drv = _mk(config={"commands": ["a", "b"]})
        assert drv._command_map() == {}

    def test_missing(self):
        drv = _mk(config={"host": "x"})
        assert drv._command_map() == {}

    async def test_send_command_with_string_commands_no_crash(self):
        """A string commands map (Add-dialog slip / hand-edit) must not raise
        AttributeError — it's parsed and the command still sends."""
        drv = _mk(config={"commands": '{"on": "PWR ON"}'})
        fake = _FakeTransport()
        drv.transport = fake
        await drv.send_command("on")
        assert fake.sent == b"PWR ON"

    async def test_send_command_param_substitution(self):
        drv = _mk(config={"commands": {"vol": "VOL {level}"}})
        fake = _FakeTransport()
        drv.transport = fake
        await drv.send_command("vol", {"level": 30})
        assert fake.sent == b"VOL 30"
