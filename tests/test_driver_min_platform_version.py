"""A65 — install_community_driver enforces min_platform_version parsed from
the YAML body itself, so /api/discovery/install-and-match and other callers
that don't carry the field on the request still get the check.
"""

import pytest

from fastapi import HTTPException

from server.api.routes.drivers import (
    _enforce_min_platform_version,
    _peek_min_platform_version,
)


def test_peek_yaml_min_platform_version():
    yaml_text = """
id: foo
name: Foo
transport: tcp
min_platform_version: "0.6.0"
"""
    assert _peek_min_platform_version(yaml_text) == "0.6.0"


def test_peek_returns_none_when_absent():
    yaml_text = """
id: foo
name: Foo
transport: tcp
"""
    assert _peek_min_platform_version(yaml_text) is None


def test_peek_handles_malformed_yaml():
    assert _peek_min_platform_version("::: not yaml :::") is None


def test_peek_handles_non_string():
    yaml_text = """
id: foo
min_platform_version: 5
"""
    assert _peek_min_platform_version(yaml_text) is None


def test_enforce_blocks_when_running_is_older(monkeypatch):
    # Pretend we're running 0.5.0 and the driver demands 0.6.0.
    import server.version
    monkeypatch.setattr(server.version, "__version__", "0.5.0")
    with pytest.raises(HTTPException) as excinfo:
        _enforce_min_platform_version("0.6.0")
    assert excinfo.value.status_code == 422
    assert "0.6.0" in str(excinfo.value.detail)


def test_enforce_passes_when_running_is_equal(monkeypatch):
    import server.version
    monkeypatch.setattr(server.version, "__version__", "0.6.0")
    # Should not raise.
    _enforce_min_platform_version("0.6.0")


def test_enforce_passes_when_running_is_newer(monkeypatch):
    import server.version
    monkeypatch.setattr(server.version, "__version__", "0.7.1")
    _enforce_min_platform_version("0.6.0")


def test_enforce_swallows_unparseable(monkeypatch):
    import server.version
    monkeypatch.setattr(server.version, "__version__", "0.7.1")
    # An unparseable required version logs and allows.
    _enforce_min_platform_version("not-a-version")
