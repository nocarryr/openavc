"""Tests for driver-default + connection-table merge in resolved_device_config.

Verifies the discovery -> add-device gap fix: a driver's
``DRIVER_INFO['default_config']`` is now layered under saved device config
before connection-table overrides, so a discovered device added with only
``host`` still picks up the driver's control port at runtime.

Layering (later wins): driver defaults -> device.config -> connections[id].
"""

from __future__ import annotations

import pytest

from server.core.device_manager import (
    get_driver_default_config,
    register_driver,
    unregister_driver,
)
from server.core.engine import Engine
from server.core.project_loader import DeviceConfig, ProjectConfig, ProjectMeta
from server.drivers.base import BaseDriver
from server.drivers.configurable import create_configurable_driver_class


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_tcp_driver():
    """Register a temporary YAML-style TCP driver with a custom port."""
    definition = {
        "id": "fake_kramer_test",
        "name": "Fake Kramer (test)",
        "manufacturer": "TestCo",
        "category": "switcher",
        "version": "1.0.0",
        "transport": "tcp",
        "default_config": {
            "host": "",
            "port": 5000,
            "machine_number": "01",
            "poll_interval": 10,
        },
        "config_schema": {"host": {"type": "string", "required": True}},
        "state_variables": {},
        "commands": {},
        "responses": [],
    }
    cls = create_configurable_driver_class(definition)
    register_driver(cls)
    yield cls
    unregister_driver("fake_kramer_test")


@pytest.fixture
def engine_with_project(tmp_path, fake_tcp_driver):
    """An Engine wired to a minimal in-memory ProjectConfig."""
    engine = Engine(str(tmp_path / "test.avc"))
    engine.project = ProjectConfig(
        project=ProjectMeta(id="t", name="Test"),
        devices=[],
        connections={},
    )
    return engine


# ---------------------------------------------------------------------------
# get_driver_default_config
# ---------------------------------------------------------------------------


def test_get_driver_default_config_returns_copy(fake_tcp_driver):
    a = get_driver_default_config("fake_kramer_test")
    a["mutated"] = True
    b = get_driver_default_config("fake_kramer_test")
    assert "mutated" not in b, (
        "get_driver_default_config must return a copy so callers can't "
        "mutate the driver's class-level DRIVER_INFO['default_config']"
    )


def test_get_driver_default_config_unknown_driver_returns_empty_dict():
    assert get_driver_default_config("does_not_exist_xyz") == {}


# ---------------------------------------------------------------------------
# resolved_device_config layering
# ---------------------------------------------------------------------------


def test_discovery_added_device_inherits_driver_port(engine_with_project):
    """The discovery -> add bug: device saved with only host, but the
    driver declares port 5000. resolved_device_config must surface it."""
    engine = engine_with_project
    device = DeviceConfig(
        id="kramer1",
        driver="fake_kramer_test",
        name="Conference Room Kramer",
        config={},  # discovery add_device leaves protocol config empty
    )
    engine.project.devices.append(device)
    engine.project.connections["kramer1"] = {"host": "192.0.2.50"}

    resolved = engine.resolved_device_config(device)

    assert resolved["config"]["host"] == "192.0.2.50"
    assert resolved["config"]["port"] == 5000, (
        "driver default_config.port must be applied when not overridden"
    )
    assert resolved["config"]["machine_number"] == "01"
    assert resolved["config"]["poll_interval"] == 10


def test_saved_device_config_overrides_driver_default(engine_with_project):
    """A field saved in device.config must win over default_config."""
    engine = engine_with_project
    device = DeviceConfig(
        id="kramer2",
        driver="fake_kramer_test",
        name="Custom",
        config={"machine_number": "07"},
    )
    engine.project.devices.append(device)
    engine.project.connections["kramer2"] = {"host": "192.0.2.51"}

    resolved = engine.resolved_device_config(device)
    assert resolved["config"]["machine_number"] == "07"
    # Other defaults still apply
    assert resolved["config"]["port"] == 5000


def test_connection_table_overrides_both(engine_with_project):
    """Connection-table values must win over saved config and defaults."""
    engine = engine_with_project
    device = DeviceConfig(
        id="kramer3",
        driver="fake_kramer_test",
        name="Custom port",
        config={"machine_number": "07"},
    )
    engine.project.devices.append(device)
    engine.project.connections["kramer3"] = {
        "host": "192.0.2.52",
        "port": 6001,  # custom port saved via PUT /devices/{id}
    }

    resolved = engine.resolved_device_config(device)
    assert resolved["config"]["host"] == "192.0.2.52"
    assert resolved["config"]["port"] == 6001
    assert resolved["config"]["machine_number"] == "07"


def test_orphan_driver_resolves_with_empty_defaults(engine_with_project):
    """An unregistered driver (orphan) must not crash resolution.

    Returns ``{}`` defaults so the device falls through to whatever
    config was saved (which still won't work, but resolution is
    well-defined and the orphan path keeps reporting cleanly).
    """
    engine = engine_with_project
    device = DeviceConfig(
        id="orphan1",
        driver="not_installed",
        name="Orphan",
        config={"host": "192.0.2.99"},
    )
    engine.project.devices.append(device)

    resolved = engine.resolved_device_config(device)
    assert resolved["config"] == {"host": "192.0.2.99"}


# ---------------------------------------------------------------------------
# BaseDriver._required_port hardening
# ---------------------------------------------------------------------------


class _PortOnlyDriver(BaseDriver):
    """Minimal driver used to exercise _required_port in isolation."""

    DRIVER_INFO = {"id": "_port_only_test", "transport": "tcp"}

    async def send_command(self, command, params=None):
        return None


def _make_driver(config):
    from server.core.event_bus import EventBus
    from server.core.state_store import StateStore

    return _PortOnlyDriver("test_dev", config, StateStore(), EventBus())


def test_required_port_returns_int():
    d = _make_driver({"port": 5000})
    assert d._required_port() == 5000


def test_required_port_coerces_string_int():
    d = _make_driver({"port": "5000"})
    assert d._required_port() == 5000


def test_required_port_missing_raises_clear_error():
    d = _make_driver({"host": "10.0.0.1"})
    with pytest.raises(ConnectionError, match="missing 'port'"):
        d._required_port()


def test_required_port_empty_string_raises():
    d = _make_driver({"port": ""})
    with pytest.raises(ConnectionError, match="missing 'port'"):
        d._required_port()


def test_required_port_invalid_value_raises():
    d = _make_driver({"port": "not-a-number"})
    with pytest.raises(ConnectionError, match="invalid port"):
        d._required_port()


# ---------------------------------------------------------------------------
# Discovery /add-device REST endpoint — first-add behavior
# ---------------------------------------------------------------------------


async def test_discovery_add_device_pulls_in_driver_defaults_on_first_add(
    tmp_path, fake_tcp_driver, monkeypatch
):
    """Regression: clicking Add/Install in Discovery must save the driver's
    declared port (and other defaults) into the project file AND apply
    them to the runtime device on first add — without requiring a server
    restart.
    """
    from unittest.mock import AsyncMock, MagicMock

    from server.api import discovery as discovery_api
    from server.api.discovery import AddDeviceRequest, add_device

    # Stub the discovery engine — add_device only reads .results for
    # display-name enrichment.
    fake_discovery = MagicMock()
    fake_discovery.results = {}
    discovery_api.set_discovery_engine(fake_discovery)

    # Real engine with empty project, plus mocked devices manager so we
    # can assert what runtime_config the route handed off.
    engine = Engine(str(tmp_path / "test.avc"))
    engine.project = ProjectConfig(
        project=ProjectMeta(id="t", name="Test"),
        devices=[],
        connections={},
    )
    engine.devices = MagicMock()
    engine.devices.add_device = AsyncMock()
    engine._project_revision = 0

    discovery_api.set_app_engine(engine)

    # Don't actually write to disk
    monkeypatch.setattr(
        "server.core.project_loader.save_project", lambda *a, **k: None
    )

    req = AddDeviceRequest(ip="192.0.2.50", driver_id="fake_kramer_test")
    result = await add_device(req)

    assert result["status"] == "ok"

    # 1. Runtime hand-off includes driver defaults (port etc.)
    runtime_arg = engine.devices.add_device.await_args.args[0]
    assert runtime_arg["config"]["host"] == "192.0.2.50"
    assert runtime_arg["config"]["port"] == 5000, (
        "first-add must include driver default_config.port at runtime"
    )
    assert runtime_arg["config"]["machine_number"] == "01"
    assert runtime_arg["config"]["poll_interval"] == 10

    # 2. Saved project also has the defaults — user opening the device
    #    sees port populated, not a blank field.
    saved_device = engine.project.devices[-1]
    saved_conn = engine.project.connections[saved_device.id]
    assert saved_conn["host"] == "192.0.2.50"
    assert saved_conn["port"] == 5000
    assert saved_device.config["machine_number"] == "01"
    assert saved_device.config["poll_interval"] == 10


# ---------------------------------------------------------------------------
# Bridge binding resolution (v0.6.0 — device-through-device connection model)
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_bridge_driver():
    """Register a temporary YAML-style serial bridge driver.

    Synthetic invented device (core-test rule): advertises one serial port
    that other devices connect through, transparently piped on TCP 4999.
    """
    definition = {
        "id": "fake_bridge_test",
        "name": "Fake Serial Bridge (test)",
        "manufacturer": "TestCo",
        "category": "utility",
        "version": "1.0.0",
        "transport": "tcp",
        "bridge": {
            "ports": [
                {
                    "id": "serial:1",
                    "kind": "serial",
                    "passthrough_port": 4999,
                    "label": "Serial Port 1",
                },
            ],
        },
        "default_config": {"host": "", "port": 4998},
        "config_schema": {},
        "state_variables": {},
        "commands": {},
        "responses": [],
    }
    cls = create_configurable_driver_class(definition)
    register_driver(cls)
    yield cls
    unregister_driver("fake_bridge_test")


@pytest.fixture
def fake_serial_device_driver():
    """Register a temporary dual-transport (tcp|serial) downstream driver."""
    definition = {
        "id": "fake_serial_display_test",
        "name": "Fake Serial Display (test)",
        "manufacturer": "TestCo",
        "category": "display",
        "version": "1.0.0",
        "transport": "serial",
        "transports": ["tcp", "serial"],
        "default_config": {"baudrate": 9600, "port": ""},
        "config_schema": {},
        "state_variables": {},
        "commands": {},
        "responses": [],
    }
    cls = create_configurable_driver_class(definition)
    register_driver(cls)
    yield cls
    unregister_driver("fake_serial_display_test")


def test_get_driver_bridge_ports_reads_declaration(fake_bridge_driver):
    from server.core.device_manager import get_driver_bridge_ports

    ports = get_driver_bridge_ports("fake_bridge_test")
    assert "serial:1" in ports
    assert ports["serial:1"]["kind"] == "serial"
    assert ports["serial:1"]["passthrough_port"] == 4999


def test_get_driver_bridge_ports_non_bridge_returns_empty(fake_tcp_driver):
    from server.core.device_manager import get_driver_bridge_ports

    assert get_driver_bridge_ports("fake_kramer_test") == {}


def test_yaml_bridge_and_transports_survive_into_driver_info(
    fake_bridge_driver, fake_serial_device_driver
):
    """configurable.py must copy `bridge` + `transports` into DRIVER_INFO,
    or the runtime can't see the declaration (the YAML->runtime parity trap)."""
    assert fake_bridge_driver.DRIVER_INFO.get("bridge", {}).get("ports")
    assert fake_serial_device_driver.DRIVER_INFO.get("transports") == ["tcp", "serial"]


def _add_bridge_project(engine, bridge_host="192.0.2.40"):
    """Append a bridge + a downstream serial device bound through it."""
    bridge = DeviceConfig(
        id="bridge1", driver="fake_bridge_test", name="Bridge", config={}
    )
    downstream = DeviceConfig(
        id="disp1", driver="fake_serial_display_test", name="Display", config={}
    )
    engine.project.devices.extend([bridge, downstream])
    engine.project.connections["bridge1"] = {"host": bridge_host}
    engine.project.connections["disp1"] = {
        "bridge": "bridge1",
        "bridge_port": "serial:1",
        "baudrate": 9600,
    }
    return bridge, downstream


def test_serial_bridge_binding_rewrites_to_passthrough(
    engine_with_project, fake_bridge_driver, fake_serial_device_driver
):
    """A bridge-bound serial device resolves to the bridge's transparent TCP
    pass-through endpoint, reusing the existing TCP transport."""
    engine = engine_with_project
    _, downstream = _add_bridge_project(engine)

    cfg = engine.resolved_device_config(downstream)["config"]
    assert cfg["transport"] == "tcp"
    assert cfg["host"] == "192.0.2.40"   # the bridge's host, not the device's
    assert cfg["port"] == 4999           # serial:1 pass-through port
    # serial params survive for the bridge's set_SERIAL push
    assert cfg["baudrate"] == 9600
    # binding markers survive so the connect path can find the bridge to prep it
    assert cfg["bridge"] == "bridge1"
    assert cfg["bridge_port"] == "serial:1"


def test_bridge_unknown_device_leaves_binding_unresolved(
    engine_with_project, fake_serial_device_driver
):
    engine = engine_with_project
    downstream = DeviceConfig(
        id="disp1", driver="fake_serial_display_test", name="Display", config={}
    )
    engine.project.devices.append(downstream)
    engine.project.connections["disp1"] = {
        "bridge": "ghost", "bridge_port": "serial:1",
    }
    cfg = engine.resolved_device_config(downstream)["config"]
    assert cfg.get("host") is None
    assert cfg.get("transport") != "tcp"


def test_bridge_unknown_port_leaves_binding_unresolved(
    engine_with_project, fake_bridge_driver, fake_serial_device_driver
):
    engine = engine_with_project
    _, downstream = _add_bridge_project(engine)
    engine.project.connections["disp1"]["bridge_port"] = "serial:99"
    cfg = engine.resolved_device_config(downstream)["config"]
    assert cfg.get("port") != 4999


def test_bridge_missing_host_leaves_binding_unresolved(
    engine_with_project, fake_bridge_driver, fake_serial_device_driver
):
    engine = engine_with_project
    _, downstream = _add_bridge_project(engine, bridge_host="")
    cfg = engine.resolved_device_config(downstream)["config"]
    assert cfg.get("port") != 4999


def test_direct_serial_device_unaffected_by_bridge_resolver(
    engine_with_project, fake_serial_device_driver
):
    """A normal direct serial connection (no bridge) is left untouched."""
    engine = engine_with_project
    dev = DeviceConfig(
        id="d2", driver="fake_serial_display_test", name="Direct", config={}
    )
    engine.project.devices.append(dev)
    engine.project.connections["d2"] = {"port": "COM3", "baudrate": 19200}
    cfg = engine.resolved_device_config(dev)["config"]
    assert cfg["port"] == "COM3"
    assert cfg.get("transport") != "tcp"
