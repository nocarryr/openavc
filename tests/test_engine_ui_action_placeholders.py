"""Tests for engine._execute_action placeholder substitution.

The UI action executor substitutes a small set of placeholders into
device.command params before calling devices.send_command:
  $value  — slider/change/submit value (scaled to output range)
  $input  — matrix route input number
  $output — matrix route output number
  $mute   — mute_route / audio_mute_route mute value (bool)

Since the $-resolver was unified, a binding param can also reference any
$var/$device/$system state key (resolved from the state store), not just the
four UI-event tokens — exercised by the handle_ui_event integration tests below.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from server.core.engine import Engine


@pytest.fixture
def engine(tmp_path):
    eng = Engine(str(tmp_path / "no_project.avc"))
    eng.devices = AsyncMock()
    return eng


def _project_with_element(element):
    """Wrap a single element in the minimal project shape _find_element walks."""
    page = SimpleNamespace(elements=[element])
    ui = SimpleNamespace(pages=[page])
    return SimpleNamespace(ui=ui)


@pytest.mark.asyncio
async def test_input_output_placeholders_resolve(engine):
    """$input and $output substitute from the data dict."""
    action = {
        "action": "device.command",
        "device": "sw",
        "command": "route",
        "params": {"in": "$input", "out": "$output", "static": "x"},
    }
    await engine._execute_action(action, {"input": 3, "output": 1}, element=None)
    engine.devices.send_command.assert_awaited_once_with(
        "sw", "route", {"in": 3, "out": 1, "static": "x"}
    )


@pytest.mark.asyncio
async def test_mute_placeholder_resolves_true(engine):
    """$mute substitutes from the data dict (bool)."""
    action = {
        "action": "device.command",
        "device": "sw",
        "command": "mute",
        "params": {"output": "$output", "mute": "$mute"},
    }
    await engine._execute_action(action, {"output": 2, "mute": True}, element=None)
    engine.devices.send_command.assert_awaited_once_with(
        "sw", "mute", {"output": 2, "mute": True}
    )


@pytest.mark.asyncio
async def test_mute_placeholder_resolves_false(engine):
    """$mute carries the false (unmute) value through."""
    action = {
        "action": "device.command",
        "device": "sw",
        "command": "mute",
        "params": {"output": "$output", "mute": "$mute"},
    }
    await engine._execute_action(action, {"output": 2, "mute": False}, element=None)
    engine.devices.send_command.assert_awaited_once_with(
        "sw", "mute", {"output": 2, "mute": False}
    )


# --- handle_ui_event integration: resolution through the public entry point ---


@pytest.mark.asyncio
async def test_handle_ui_event_slider_value_scales(engine):
    """A slider change binding's $value is scaled to the element output range."""
    element = SimpleNamespace(
        id="vol",
        bindings={
            "change": [
                {
                    "action": "device.command",
                    "device": "dsp",
                    "command": "set_level",
                    "params": {"level": "$value"},
                }
            ]
        },
        output_min=0,
        output_max=1,
        min=0,
        max=100,
        scale_to_full=True,
    )
    engine.project = _project_with_element(element)
    await engine.handle_ui_event("change", "vol", {"value": 50})
    engine.devices.send_command.assert_awaited_once_with(
        "dsp", "set_level", {"level": 0.5}
    )


@pytest.mark.asyncio
async def test_handle_ui_event_button_resolves_var(engine):
    """A button press binding's $var.<name> resolves from the state store."""
    engine.state.set("var.target", 7)
    element = SimpleNamespace(
        id="btn",
        bindings={
            "press": [
                {
                    "action": "device.command",
                    "device": "dsp",
                    "command": "set_level",
                    "params": {"level": "$var.target"},
                }
            ]
        },
    )
    engine.project = _project_with_element(element)
    await engine.handle_ui_event("press", "btn", {})
    engine.devices.send_command.assert_awaited_once_with(
        "dsp", "set_level", {"level": 7}
    )


@pytest.mark.asyncio
async def test_handle_ui_event_route_resolves_input_output(engine):
    """A matrix route binding's $input / $output resolve from the event data."""
    element = SimpleNamespace(
        id="mtx",
        bindings={
            "route": [
                {
                    "action": "device.command",
                    "device": "sw",
                    "command": "route",
                    "params": {"in": "$input", "out": "$output"},
                }
            ]
        },
    )
    engine.project = _project_with_element(element)
    await engine.handle_ui_event("route", "mtx", {"input": 3, "output": 2})
    engine.devices.send_command.assert_awaited_once_with(
        "sw", "route", {"in": 3, "out": 2}
    )
