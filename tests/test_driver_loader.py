"""Tests for driver loader (.avcdriver YAML files)."""

from pathlib import Path

import yaml

from server.drivers.driver_loader import (
    DRIVER_EXTENSION,
    delete_driver_definition,
    list_driver_definitions,
    load_driver_file,
    load_driver_files,
    save_driver_definition,
    validate_driver_definition,
)


VALID_DEFINITION = {
    "id": "test_loader_driver",
    "name": "Loader Test Driver",
    "transport": "tcp",
    "discovery": {"oui": ["aa:bb:cc"]},
    "commands": {
        "power_on": {"label": "Power On", "string": "PON\r", "params": {}},
    },
    "responses": [
        {"pattern": r"PWR=(\d)", "mappings": [{"group": 1, "state": "power"}]},
    ],
    "state_variables": {
        "power": {"type": "string", "label": "Power"},
    },
}


def _write_avcdriver(path: Path, data: dict) -> Path:
    """Helper to write a .avcdriver YAML file."""
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_validate_valid_definition():
    errors = validate_driver_definition(VALID_DEFINITION)
    assert errors == []


def test_validate_missing_required():
    errors = validate_driver_definition({"name": "X"})
    assert any("id" in e for e in errors)
    assert any("transport" in e for e in errors)


def test_validate_accepts_missing_discovery_block_with_warning():
    """A driver with no signals at all loads (the matcher silently
    ignores it) but the loader logs a warning. We don't reject the
    driver — community contributors can ship a placeholder and add
    discovery hints in a follow-up.
    """
    errors = validate_driver_definition({
        "id": "no_discovery",
        "name": "No Discovery",
        "transport": "tcp",
        "commands": {"power_on": {"string": "X\r"}},
    })
    assert errors == []


def test_validate_accepts_hint_only_discovery():
    errors = validate_driver_definition({
        "id": "hint_only_widget",
        "name": "Hint Only Widget",
        "transport": "tcp",
        "discovery": {"oui": ["aa:bb:cc"]},
        "commands": {"power_on": {"string": "X\r"}},
    })
    assert errors == []


def test_validate_accepts_fingerprint_discovery():
    errors = validate_driver_definition({
        "id": "fingerprint_driver",
        "name": "Fingerprint",
        "transport": "tcp",
        "discovery": {
            "tcp_probe": {
                "port": 4321, "send_ascii": "Q\r", "expect": "RESP",
            },
        },
        "commands": {"power_on": {"string": "X\r"}},
    })
    assert errors == []


def test_validate_skips_generic_templates():
    """generic_* templates are exempt from the discovery requirement."""
    errors = validate_driver_definition({
        "id": "generic_anything",
        "name": "Generic",
        "transport": "tcp",
    })
    # No discovery-block error.
    assert not any("discovery:" in e for e in errors)


def test_validate_bad_transport():
    errors = validate_driver_definition({
        "id": "x", "name": "x", "transport": "foobar",
    })
    assert any("transport" in e for e in errors)


def test_validate_bad_regex():
    defn = {**VALID_DEFINITION, "responses": [{"pattern": "[bad"}]}
    errors = validate_driver_definition(defn)
    assert any("regex" in e.lower() or "invalid" in e.lower() for e in errors)


def test_load_driver_file_valid(tmp_path):
    filepath = tmp_path / "test.avcdriver"
    _write_avcdriver(filepath, VALID_DEFINITION)
    result = load_driver_file(filepath)
    assert result is not None
    assert result["id"] == "test_loader_driver"


def test_load_driver_file_invalid_yaml(tmp_path):
    filepath = tmp_path / "bad.avcdriver"
    filepath.write_text("{{{{not yaml!!", encoding="utf-8")
    result = load_driver_file(filepath)
    assert result is None


def test_load_driver_file_missing_fields(tmp_path):
    filepath = tmp_path / "incomplete.avcdriver"
    _write_avcdriver(filepath, {"name": "Missing ID"})
    result = load_driver_file(filepath)
    assert result is None


def test_save_and_load_roundtrip(tmp_path):
    saved_path = save_driver_definition(VALID_DEFINITION, tmp_path)
    assert saved_path.exists()
    assert saved_path.suffix == DRIVER_EXTENSION
    loaded = load_driver_file(saved_path)
    assert loaded is not None
    assert loaded["id"] == VALID_DEFINITION["id"]


def test_save_uses_avcdriver_extension(tmp_path):
    saved_path = save_driver_definition(VALID_DEFINITION, tmp_path)
    assert saved_path.name == "test_loader_driver.avcdriver"


def test_save_writes_yaml(tmp_path):
    saved_path = save_driver_definition(VALID_DEFINITION, tmp_path)
    text = saved_path.read_text(encoding="utf-8")
    # YAML doesn't have braces/brackets at the start like JSON
    assert not text.startswith("{")
    data = yaml.safe_load(text)
    assert data["id"] == "test_loader_driver"


def test_list_driver_definitions(tmp_path):
    save_driver_definition(VALID_DEFINITION, tmp_path)

    defn2 = {**VALID_DEFINITION, "id": "second_driver", "name": "Second"}
    save_driver_definition(defn2, tmp_path)

    result = list_driver_definitions([tmp_path])
    ids = [d["id"] for d in result]
    assert "test_loader_driver" in ids
    assert "second_driver" in ids


def test_list_ignores_nonexistent_dir():
    result = list_driver_definitions([Path("/nonexistent/dir")])
    assert result == []


def test_delete_driver_definition(tmp_path):
    save_driver_definition(VALID_DEFINITION, tmp_path)
    assert delete_driver_definition("test_loader_driver", [tmp_path]) is True
    assert list_driver_definitions([tmp_path]) == []


def test_delete_nonexistent():
    assert delete_driver_definition("no_such_id", []) is False


def test_load_driver_files_registers(tmp_path):
    """load_driver_files creates and registers driver classes."""
    save_driver_definition(VALID_DEFINITION, tmp_path)
    count = load_driver_files([tmp_path])
    assert count >= 1

    # Verify it's in the registry
    from server.core.device_manager import get_driver_registry
    registry = get_driver_registry()
    ids = [d["id"] for d in registry]
    assert "test_loader_driver" in ids


def test_list_python_drivers_skips_companions(tmp_path):
    """``list_python_drivers`` must not list ``_discovery.py`` /
    ``_sim.py`` companions or underscore-prefixed helpers as drivers.

    Regression test for the bug where YAML drivers' sibling discovery
    companions appeared in the Code tab tree and the Installed Drivers
    panel as if they were standalone Python drivers — clicking them
    triggered a fetch on a stem that has no driver class behind it.
    """
    from server.drivers.driver_loader import list_python_drivers

    # Real driver — has a class with DRIVER_INFO.
    (tmp_path / "real_driver.py").write_text(
        '"""A real driver."""\n'
        "from server.drivers.base import BaseDriver\n"
        "class RealDriver(BaseDriver):\n"
        '    DRIVER_INFO = {"id": "real_driver", "name": "Real Driver"}\n',
        encoding="utf-8",
    )

    # Discovery companion — has only an async probe(), no driver class.
    (tmp_path / "real_driver_discovery.py").write_text(
        "async def probe(ctx):\n"
        "    pass\n",
        encoding="utf-8",
    )

    # Python simulator companion — has a Simulator class, no driver.
    (tmp_path / "real_driver_sim.py").write_text(
        "class Simulator:\n"
        "    pass\n",
        encoding="utf-8",
    )

    # Underscore-prefixed helper — already filtered, kept for parity.
    (tmp_path / "_helpers.py").write_text(
        "X = 1\n",
        encoding="utf-8",
    )

    listed = list_python_drivers([tmp_path])
    listed_ids = [d["id"] for d in listed]

    assert "real_driver" in listed_ids
    assert "real_driver_discovery" not in listed_ids
    assert "real_driver_sim" not in listed_ids
    assert "_helpers" not in listed_ids
    assert "helpers" not in listed_ids
